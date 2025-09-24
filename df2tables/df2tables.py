#!/usr/bin/python
# coding=utf8

import datetime
import json
import os
import random
import subprocess
import sys
import warnings
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

# --- Constants ---
try:
    from importlib import resources
    TEMPLATE_PATH = resources.files("df2tables") / "datatable_templ.html"
except ImportError:
    TEMPLATE_PATH = Path(__file__).parent / "datatable_templ.html"

try:
    from . import comnt
except ImportError:
    import comnt

DROPDOWN_SELECT_THRESHOLD = 9
DEFAULT_TABLE_ID = "pd_datatab"
DEFAULT_TABLE_CLASS = "display compact hover order-column"
RENDER_NUM_TAG = "#render_num"

__all__ = [
    "TEMPLATE_PATH",
    "render",
    "render_inline",
    "render_sample_df",
    "get_sample_df",
]


def open_file(filename):
    """Opens a file with the default application in a cross-platform way."""
    filepath = str(filename)  # Ensure path is a string for subprocess
    try:
        if sys.platform.startswith("win"):
            os.startfile(filepath)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            # Use subprocess.run for a more modern and flexible API.
            subprocess.run([opener, filepath], check=True)
    except Exception as e:
        print(f"Error opening file: {e}")


class DataJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for pandas data types.
    Refactored to use isinstance for reliable type checking.
    """

    def default(self, obj):
        if pd.isna(obj) or (isinstance(obj, float) and np.isnan(obj)):
            return None
        elif isinstance(obj, (datetime.datetime, datetime.date, pd.Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, (np.ndarray, list, tuple)):
            return [self.default(item) for item in obj]
        elif isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        elif isinstance(obj, str):
            return obj.strip()
        try:
            # Fallback for other types that JSONEncoder can handle
            return super().default(obj)
        except TypeError:
            # Final fallback to a safe string representation
            return escape(repr(obj))


def html_tag(tag, content="", attrs=None, self_closing=False):
    """Generates an HTML tag."""
    attrs = attrs or {}
    attr_str = "".join(f' {k}="{escape(str(v), quote=True)}"' for k, v in attrs.items())
    if self_closing:
        return f"<{tag}{attr_str} />"
    return f"<{tag}{attr_str}>{content}</{tag}>"


# --- Helper Functions for `render` ---


def _prepare_dataframe(df, precision):
    """
    Prepares a DataFrame for rendering. Handles Series, MultiIndex,
    and data type conversions without modifying the original DataFrame.
    """
    if isinstance(df, pd.Series):
        print("Converting Series to DataFrame...")
        df = df.to_frame(name=df.name or "value").reset_index()

    # Work on a copy to avoid side effects on the original DataFrame.
    df_copy = df.copy()

    df_copy.columns = df_copy.columns.astype(str)
    if isinstance(df_copy.columns, pd.MultiIndex):
        df_copy.columns = ["_".join(map(str, col)).strip() for col in df_copy.columns]

    # Round float columns to the specified precision.
    float_cols = df_copy.select_dtypes(include="number").columns
    df_copy[float_cols] = df_copy[float_cols].round(precision)

    # Convert unhashable types within columns to their string representation.
    for col in df_copy.columns:
        try:
            df_copy[col].nunique()
        except TypeError:
            df_copy[col] = df_copy[col].apply(lambda x: repr(x) if not pd.isna(x) else None)

    return df_copy


def _generate_column_definitions(df, num_html, load_column_control):
    """Generates the column definitions list for DataTables."""
    columns = []
    for col in df.columns:
        nunique = df[col].nunique()
        col_cleaned = col.replace("_", " ")

        if nunique < DROPDOWN_SELECT_THRESHOLD:
            col_def = {"title": col_cleaned}
            if load_column_control:
                col_def["columnControl"] = ["order", ["title", "searchList"]]
        else:
            col_def = {"title": col_cleaned, "searchable": True}
            if load_column_control:
                col_def["columnControl"] = ["order", ["title", "search"]]

        col_def["orderable"] = True

        if col in num_html:
            col_def["render"] = RENDER_NUM_TAG  # Use a constant
            col_def["type"] = "num-html"

        columns.append(col_def)
    return columns


def _render_html_template(template_path, template_vars):
    """Loads and renders the HTML template with the given variables."""
    try:
        with open(template_path, encoding="utf-8") as f:
            template_str = f.read()
        return comnt.render(template_str, template_vars)
    except FileNotFoundError:
        print(f"Error: Template file not found at {template_path}")
        return ""


def render(
    df,
    to_file="datatable.html",
    title="DataFrame",
    precision=2,
    num_html=None,
    startfile=True,
    templ_path=TEMPLATE_PATH,
    load_column_control=True,
    display_logo=True,
):
    """
    Renders a pandas DataFrame as an interactive HTML DataTables.
    Refactored to be a high-level coordinator of helper functions.
    """
    df_prepared = _prepare_dataframe(df, precision)

    data_json = json.dumps(df_prepared.to_dict(orient='split')['data'], cls=DataJSONEncoder)

    columns = _generate_column_definitions(df_prepared, num_html or [], load_column_control)
    columns_json = json.dumps(columns)
    # This replacement is a necessary trick to pass a JS function name into the JSON.
    columns_json = columns_json.replace(f'"{RENDER_NUM_TAG}"', RENDER_NUM_TAG.strip("#"))

    str_cols = df_prepared.select_dtypes(include=["object", "string"]).columns
    auto_width = len(df_prepared.index) < 100 or len(df_prepared.columns) > 10

    template_vars = {
        "title": escape(str(title)),
        "auto_width": json.dumps(auto_width),
        "tab_data": data_json,
        "tab_columns": columns_json,
        "search_columns": json.dumps(list(str_cols)),
    }

    if not display_logo:
        template_vars["datatables_logo"] = ""
    if not load_column_control:
        template_vars["column_control"] = ""

    html_content = _render_html_template(templ_path, template_vars)

    if not to_file:
        return html_content

    try:
        with open(to_file, "w", encoding="utf-8") as outfile:
            outfile.write(html_content)
        if startfile:
            open_file(to_file)
        return to_file  # Return the path for confirmation
    except IOError as e:
        print(f"Error writing to file {to_file}: {e}")
        return None


def render_inline(df, table_attrs=None, **kwargs):
    """Renders a DataFrame as an inline HTML table for embedding."""
    # Use .pop() to safely remove and check for disallowed arguments.
    if kwargs.pop("to_file", None):
        warnings.warn("'to_file' argument is not allowed in render_inline.")
    if kwargs.pop("title", None):
        warnings.warn("'title' argument is not applicable in render_inline.")

    # Always render without a file.
    html = render(df, to_file=None, **kwargs)

    attrs = {
        "id": DEFAULT_TABLE_ID,
        "class": DEFAULT_TABLE_CLASS,
        **(table_attrs or {}),
    }

    base_table = html_tag("table", attrs=attrs)
    # Update the table ID in the JavaScript if a custom ID is provided.
    html = comnt.render(html, {"table_id": f'"{attrs["id"]}"'})

    min_content = base_table + comnt.get_tag_content("min_content", html)
    return min_content


def get_sample_df():
    """Generates a sample DataFrame for demonstration."""
    healthcare = ["Low priority", "Medium priority", "High priority", "Emergency"]
    product = ["Premium", "Standard", "Budget"]
    grades = ["A", "B", "C", "D", "F"]
    size = 7
    fmt = "%Y-%m-%d %H:%M:%S"
    return pd.DataFrame({
        "timestamp": [(datetime.datetime.now() - datetime.timedelta(days=i)).strftime(fmt)
                      for i in range(size)],
        "description": [
            "Lorem ipsum dolor sit amet",
            "<b>HTML content</b> is allowed",
            "Consectetur adipiscing elit",
            None,
            "Integer laoreet odio",
            pd.NA,
            "Nested: " + repr(["C", {
                "a": 1
            }]),
        ],
        "value": np.random.randn(size),
        "grade": np.random.choice(grades, size),
        "measurement": [-0.333, 1, -9, 4, 2, 3, 1111.111],
        "revenue": [random.randint(-2000, 70000) for _ in range(size)],
        "product_type": np.random.choice(product, size),
        "is_active": np.random.choice([True, False], size),
        "priority": np.random.choice(healthcare, size),
    })


def render_sample_df(to_file="df_table.html"):
    """Creates and renders the sample DataFrame."""
    df = get_sample_df()
    return render(
        df,
        to_file=to_file,
        title="Example DataFrame",
        num_html=["revenue", "measurement", "value"],
    )


def main():
    """Main function to run when the script is executed directly."""
    output_path = render_sample_df(to_file="test_datatable.html")
    if output_path:
        print(f"Successfully generated sample table at: {output_path}")


if __name__ == "__main__":
    main()
