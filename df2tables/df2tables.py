#!/usr/bin/python
# coding=utf8
"""
df2tables: Convert pandas/polars DataFrames to interactive HTML DataTables.
This module provides functionality to render DataFrames as interactive HTML tables
using the DataTables JavaScript library, with support for filtering, sorting, and searching.
"""

import json
import os
import subprocess
import sys
import uuid
import warnings
from html import escape
from pathlib import Path
from re import sub

try:
    from importlib import resources

    TEMPLATE_PATH = resources.files("df2tables") / "datatable_templ.html"
except (ImportError, AttributeError):
    TEMPLATE_PATH = Path(__file__).parent / "datatable_templ.html"

try:
    from . import comnt
except ImportError:
    import comnt

# Configuration constants
RENDER_NUM_FUNC = "#render_num"  # Placeholder for JS function injection

__all__ = [
    "TEMPLATE_PATH",
    "render",
    "render_inline",
    "render_sample_df",
    "get_sample_df",
    "load_datatables",
    "render_nb",
]
BUTT_VER = "3.2.5"
BUTTONS_URLS = f"""
<link href="https://cdn.datatables.net/buttons/{BUTT_VER}/css/buttons.dataTables.min.css" 
    rel="stylesheet">
<script src="https://cdn.datatables.net/buttons/{BUTT_VER}/js/dataTables.buttons.min.js">
</script>
<script src="https://cdn.datatables.net/buttons/{BUTT_VER}/js/buttons.html5.min.js">
</script>
"""


def html_tag(tag, content="", attrs=None, self_closing=False):
    """
    Generates an HTML tag with optional attributes and content.
    """
    attrs = attrs or {}
    attr_str = "".join(f' {k}="{escape(str(v), quote=True)}"' for k, v in attrs.items())
    if self_closing:
        return f"<{tag}{attr_str} />"
    return f"<{tag}{attr_str}>{content}</{tag}>"


def open_file(filename):
    """
    Opens a file with the default application in a cross-platform way.
    """
    filepath = str(filename)
    try:
        if sys.platform.startswith("win"):
            os.startfile(filepath)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([opener, filepath], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(
            f"Failed to open file '{filepath}': {e.stderr.decode() if e.stderr else 'Unknown error'}"
        )
    except FileNotFoundError:
        print(f"Could not find system opener. Please open '{filepath}' manually.")
    except Exception as e:
        print(f"Unexpected error opening file '{filepath}': {type(e).__name__}: {e}")


class DataJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder with fallback to string representation.
    """

    def default(self, obj):
        try:
            # Handle datetime objects
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            # Handle Decimal types
            if "decimal" in str(type(obj)).lower():
                return float(obj)
            return super().default(obj)
        except (TypeError, ValueError):
            # Fallback: convert to safe string representation
            return escape(repr(obj))


def minify(html):
    html = html.replace("\n", "")
    html = sub("\\s{2,}", " ", html)
    html = html.replace("> <", "><")
    return html


def _prepare_dataframe(df, precision):
    """
    Prepares a DataFrame for rendering without modifying the original.
    """
    import pandas as pd

    # Convert Series to DataFrame with proper naming
    if isinstance(df, pd.Series):
        print("Converting Series to DataFrame...")
        df = df.to_frame(name=df.name or "value").reset_index()

    # Work on a copy to avoid modifying the original
    df_copy = df.copy()

    # Flatten MultiIndex columns by joining levels with underscores
    if isinstance(df_copy.columns, pd.MultiIndex):
        df_copy.columns = ["_".join(map(str, col)).strip() for col in df_copy.columns]

    # Ensure all column names are strings
    df_copy.columns = df_copy.columns.astype(str)

    # Round numeric columns to specified precision
    float_cols = df_copy.select_dtypes(include="number").columns
    if len(float_cols) > 0:
        df_copy[float_cols] = df_copy[float_cols].round(precision)

    # Convert unhashable types (lists, dicts) to string representation
    for col in df_copy.columns:
        try:
            df_copy[col].nunique()
        except TypeError:
            df_copy[col] = df_copy[col].map(repr)

    return df_copy


def _generate_column_defs(df, num_html, load_column_control, dropdown_select_threshold):
    """
    Generates DataTables column definitions with appropriate search controls.

    Args:
        df: Prepared DataFrame
        num_html: List of column names to render as numeric HTML
        load_column_control: Whether to include column control configuration

    Returns:
        list: Column definition dictionaries for DataTables

    Note:
        Columns with fewer unique values than DROPDOWN_SELECT_THRESHOLD
        get dropdown filters, others get text search.
    """
    columns = []
    for col in df.columns:
        # Determine number of unique values for filter type selection
        try:
            nunique = df[col].nunique()
        except TypeError:
            # If unhashable, default to text search
            nunique = dropdown_select_threshold

        col_cleaned = col.replace("_", " ")
        col_def = {"title": col_cleaned, "orderable": True}

        # Configure search type based on cardinality
        if nunique < dropdown_select_threshold:
            # Low cardinality: use dropdown filter
            if load_column_control:
                col_def["columnControl"] = ["order", ["title", "searchList"]]
        else:
            # High cardinality: use text search
            col_def["searchable"] = True
            if load_column_control:
                col_def["columnControl"] = ["order", ["title", "search"]]

        # Mark numeric HTML columns for special rendering
        if col in num_html:
            col_def["render"] = RENDER_NUM_FUNC
            col_def["type"] = "num-html"

        columns.append(col_def)
    return columns


def process_pandas(df, precision, num_html, load_column_control, dropdown_select_threshold):
    """
    Complete processing pipeline for pandas DataFrames.
    """
    df_prepared = _prepare_dataframe(df, precision)
    columns_defs = _generate_column_defs(df_prepared, num_html or [], load_column_control,
                                         dropdown_select_threshold)
    data_arrays = df_prepared.values.tolist()
    search_columns = list(df_prepared.select_dtypes(include=["object", "string"]).columns)

    return data_arrays, columns_defs, search_columns


def _render_html_template(template_path, template_vars):
    """
    Loads and renders the HTML template with provided variables.

    Args:
        template_path: Path to the HTML template file
        template_vars: Dictionary of template variables

    Returns:
        str: Rendered HTML content, or empty string on error
    """
    try:
        with open(template_path, encoding="utf-8") as f:
            template_str = f.read()
        return comnt.render(template_str, template_vars)
    except FileNotFoundError:
        print(f"Template file not found at: {template_path}")
        print("Ensure the template exists or provide a custom path via 'templ_path' parameter.")
        return ""
    except Exception as e:
        print(f"Error rendering template: {type(e).__name__}: {e}")
        return ""


DEPRECATED_ARGS = {
    "load_column_control",
    "display_logo",
}

DEFAULT_RENDER_OPTS = {
    "locale_fmt": False,  
    "dropdown_select_threshold": 9,  # max unique values for dropdown filters
    "table_id": "pd_datatab",
    "unique_id": False,
    "default_table_class": "display compact hover order-column",
    "load_column_control": True,
    "display_logo": False,
}


def render(
    df,
    to_file="datatable.html",
    title="",
    startfile=True,
    precision=2,
    num_html=None,
    copy_button=False,
    render_opts=None,
    js_opts=None,
    templ_path=TEMPLATE_PATH,
    **kwargs,
):
    """
    Renders a pandas or polars DataFrame as an interactive HTML DataTable.

    Returns:
        str or None: File path if to_file is specified, HTML string if to_file is None,
                     or None on error
    """
    final_opts = DEFAULT_RENDER_OPTS.copy()
    passed_deprecated = {}

    for key, value in kwargs.items():
        if key in DEPRECATED_ARGS:
            passed_deprecated[key] = value
        else:
            # Optional: Warn about unexpected arguments
            warnings.warn(f"Unknown argument '{key}' passed to render().", UserWarning)

    # Update defaults with any deprecated args found
    if passed_deprecated:
        final_opts.update(passed_deprecated)
        arg_names = ", ".join(passed_deprecated.keys())
        # warnings.warn(
        print(
            f"\nPassing arguments like [{arg_names}] directly is deprecated and "
            "will be removed in a future version. "
            "Please use the 'render_opts' dictionary instead.",)

    # The new 'render_opts' dictionary (if provided) OVERRIDES everything else
    if render_opts:
        final_opts.update(render_opts)
    load_column_control = final_opts["load_column_control"]
    display_logo = final_opts["display_logo"]
    dropdown_select_threshold = final_opts["dropdown_select_threshold"]

    # Validate input parameters
    if not isinstance(precision, int) or precision < 0:
        raise ValueError(f"precision must be an integer, got: {type(precision).__name__}")

    if num_html and not isinstance(num_html, list):
        raise ValueError(f"num_html must be a list, got: {type(num_html).__name__}")

    # Determine DataFrame type and process accordingly
    mod_name = type(df).__module__
    data_arrays, columns_defs, search_columns = None, None, None
    if "pandas" in mod_name:
        data_arrays, columns_defs, search_columns = process_pandas(df, precision, num_html,
                                                                   load_column_control,
                                                                   dropdown_select_threshold)
    elif "polars" in mod_name:
        try:
            from . import tablepl
        except ImportError:
            import tablepl
        data_arrays, columns_defs, search_columns = tablepl.process_pl(
            df, precision, num_html, load_column_control, dropdown_select_threshold)
    else:
        raise ValueError(f"Unsupported DataFrame type: {type(df).__name__} from module {mod_name}. "
                         "Expected pandas or polars DataFrame.")

    if not data_arrays:
        raise ValueError("DataFrame is empty or could not be processed")

    # Prepare JSON data with special handling for JS function references
    columns_json = json.dumps(columns_defs, separators=(",", ":"),
                              ensure_ascii=False).replace(f'"{RENDER_NUM_FUNC}"',
                                                          RENDER_NUM_FUNC.strip("#"))

    template_vars = {
        "title": str(title),
        "tab_data": json.dumps(data_arrays, cls=DataJSONEncoder, separators=(",", ":")),
        "tab_columns": columns_json,
        "search_columns": json.dumps(search_columns, separators=(",", ":")),
    }
    if precision != 2:
        template_vars["precision"] = json.dumps(int(precision))
        
    if final_opts.pop("locale_fmt", None):
        template_vars["locale_fmt"] = json.dumps(True)

    if final_opts.pop("unique_id", None):
        unique_id = f'"id_{uuid.uuid4().hex}"'  # use uuid for all instances
        template_vars["table_id"] = unique_id
        template_vars["table_markup"] = (
            f'<table id={unique_id} class="display compact hover order-column"></table>')
    else:
        pass

    # Configure optional template features
    if not display_logo:
        template_vars["datatables_logo"] = ""
    if not load_column_control:
        template_vars["column_control"] = ""

    if js_opts:
        assert isinstance(js_opts, dict)
        assert all(isinstance(key, str) for key in js_opts), "Not all keys are strings"
    else:
        js_opts = {}

    if copy_button:
        template_vars["buttons"] = BUTTONS_URLS
        button_loc = {"topEnd": [{"buttons": ["copy"]}, "pageLength"]}

        if "layout" in js_opts:
            js_opts["layout"].update(button_loc)
        else:
            js_opts["layout"] = button_loc

    template_vars["js_opts"] = json.dumps(js_opts)

    html_content = _render_html_template(templ_path, template_vars)
    # html_content = minify(html_content)

    if not to_file:
        return html_content

    try:
        with open(to_file, "w", encoding="utf-8") as outfile:
            outfile.write(html_content)
        print(f"Successfully created DataTable at: {to_file}")
        if startfile:
            open_file(to_file)
        return to_file
    except IOError as e:
        print(f"Failed to write file '{to_file}': {e}")
        return None
    except Exception as e:
        print(f"Unexpected error writing file: {type(e).__name__}: {e}")
        return None


def render_inline(df, table_attrs=None, **kwargs):
    """
    Renders a DataFrame as inline HTML for embedding in existing pages.

    Args:
        df: DataFrame to render (pandas or polars)
        table_attrs: Custom HTML attributes for the table element (default: None)
        **kwargs: Additional arguments passed to render() (except 'to_file' and 'title')

    Returns:
        str: Minimal HTML content for embedding (table + scripts)

    Warning:
        'to_file' and 'title' arguments are ignored with warnings

    Example:
        >>> html = render_inline(df, table_attrs={'id': 'my-table', 'class': 'custom'})
    """
    # Validate arguments and warn about ignored parameters
    if kwargs.pop("to_file", None):
        warnings.warn(
            "'to_file' argument is ignored in render_inline - output is always returned as string")
    if kwargs.pop("title", None):
        warnings.warn("'title' argument is ignored in render_inline - no page title in inline mode")

    # Always render without file output
    html = render(df, to_file=None, **kwargs)
    attrs = {
        "id": DEFAULT_RENDER_OPTS["table_id"],
        "class": DEFAULT_RENDER_OPTS["default_table_class"],
        **(table_attrs or {}),
    }

    base_table = html_tag("table", attrs=attrs)

    # Update JavaScript to reference correct table ID
    html = comnt.render(html, {"table_id": f'"{attrs["id"]}"'})

    # Extract minimal content needed for embedding
    min_content = base_table + comnt.get_tag_content("min_content", html)
    return min_content


def get_sample_df(df_type="pandas", size=20):
    """
    Generates a sample DataFrame with diverse data types for testing.
    """
    import datetime
    import random

    if df_type not in ["pandas", "polars"]:
        raise ValueError(f"Invalid df_type '{df_type}': must be 'pandas' or 'polars'")

    # Common sample data configuration
    healthcare = ["Low priority", "Medium priority", "High priority", "Emergency"]
    product = ["Premium", "Standard", "Budget"]
    grades = ["A", "B", "C", "D", "F"]

    # Helper functions for random data generation
    def random_choice(options, k):
        return [random.choice(options) for _ in range(k)]

    def random_bools(k):
        return [random.choice([True, False]) for _ in range(k)]

    # Base data common to both DataFrame types
    base_data = {
        "timestamp": [(datetime.datetime.now() - datetime.timedelta(days=i)) for i in range(size)],
        "grade": random_choice(grades, size),
        "revenue": [random.randint(-2000, 70000) for _ in range(size)],
        "product_type": random_choice(product, size),
        "is_active": random_bools(size),
        "priority": random_choice(healthcare, size),
    }

    # Generate pandas DataFrame with NumPy support
    if df_type == "pandas":
        import numpy as np
        import pandas as pd

        base_data["value"] = np.random.randn(size)
        base_data["measurement"] = random_choice(
            [-0.333, 1, -9, 4, 2, np.nan, random.randint(-1000, 10000)], size)

        # Include edge cases: NaT, HTML, nested structures, NA values
        base_data["description"] = random_choice(
            [
                np.datetime64("NaT"),
                "<b>HTML content</b> is allowed",
                {
                    "A": [1, 2, 3, [4, 5]]
                },
                np.timedelta64("NaT"),
                pd.NaT,
                pd.NA,
                np.datetime64(datetime.datetime.now()),
            ],
            size,
        )

        return pd.DataFrame(base_data)

    # Generate polars DataFrame (no NumPy dependency)
    if df_type == "polars":
        import polars as pl

        # Generate normally distributed random values without NumPy
        base_data["value"] = [random.gauss(0, 1) for _ in range(size)]
        base_data["measurement"] = random_choice([-0.333, 1, -9, 4, 2, None, 1111.111], size)

        # Polars-compatible edge cases
        base_data["description"] = random_choice(
            [
                "Lorem ipsum dolor sit amet",
                "<b>HTML content</b> is allowed",
                {
                    "A": [1, 2, 3, [4, 5]]
                },
                100.12345,
                None,
                float("nan"),
                False,
            ],
            size,
        )

        return pl.DataFrame(base_data, strict=False)


def load_datatables():
    """Deprecated: No longer needed since version 0.1.8"""
    print("load_datatables() is not needed since version: 0.1.8")


def render_nb(df, iframe=True, **kwargs):
    """
    Render a DataFrame as interactive HTML within a notebook environment.
    """
    html_content = render(
        df,
        to_file=None,
        render_opts={"unique_id": True, 'display_logo': False},
        **kwargs,
    )
    html_content = html_content.replace('"', "&quot;")
    # html_content = escape(html_content, quote=True)
    iframe_content = f'<!--silence iframe --><iframe srcdoc="{html_content}" style="width:100%;height:450px;border:none;"></iframe>'

    try:
        import IPython.display as disp

        if iframe:
            disp.display(disp.HTML(iframe_content))
        else:
            disp.display(disp.HTML(html_content))

    except ImportError:
        try:
            import marimo

            # print("marimo")
            return marimo.Html(iframe_content)
        except ImportError:
            print("Notebook expected.")
            return None
    return None


def render_sample_df(df_type="pandas", to_file="df_table.html"):
    """
    Creates and renders a sample DataFrame for demonstration.
    """
    df = get_sample_df(df_type)

    # Default to home directory if no path separator provided
    if os.sep not in to_file:
        to_file = str(Path.home() / to_file)

    return render(
        df,
        to_file=to_file,
        precision=3,
        num_html=["measurement", "value"], #"revenue", 
        copy_button=1,
        render_opts={
            "locale_fmt": False,
            "unique_id": 1,
            "title": f"Example <b>{df_type.capitalize()}</b> DataFrame",
            "load_column_control": 1,
            "dropdown_select_threshold": 12,
        },
        js_opts={"_unique_id": True},
    )


def main():
    # df_type = "polars"
    df_type = "pandas"
    output_path = render_sample_df(df_type, to_file="test_datatable.html")
    if output_path:
        print(f"Sample table generation complete: {output_path}")
    else:
        print("Failed to generate sample table")
        sys.exit(1)


if __name__ == "__main__":
    main()
