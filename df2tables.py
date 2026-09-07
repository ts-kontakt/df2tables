#!/usr/bin/python
# coding=utf8
"""
df2tables: Convert pandas/polars DataFrames to interactive HTML DataTables.
This module provides functionality to render DataFrames as interactive HTML tables
using the DataTables JavaScript library, with support for filtering, sorting, and searching.

render()       - rows embedded in the HTML
render_ajax()  - rows fetched from an endpoint (see to_js_array());
                 returns an inline fragment like render_inline() by
                 default, full_page=True for a standalone page. Both are
                 generated from the SINGLE template via comnt regions.
render_inline()/render_nb() - embedding helpers

Errors policy: rendering problems (bad arguments, missing templates, unwritable
output paths) raise instead of being printed and swallowed.
"""

import json
import math
import os
import subprocess
import sys
import uuid
import warnings
from html import escape
from pathlib import Path

try:
    from importlib import resources

    def _template_path(name):
        """Resolve a bundled template. Prefers importlib.resources (correct for
        zip/namespace installs); falls back to __file__ when the package is
        used directly from a source directory."""
        try:
            return resources.files("df2tables") / name
        except (ImportError, AttributeError, NotImplementedError):
            return Path(__file__).parent / name
except ImportError:  # pragma: no cover - very old Python
    def _template_path(name):
        return Path(__file__).parent / name


# Single source of truth: BOTH render() and render_ajax() generate their
# output from this ONE template. The AJAX loader lives inside comnt regions
# (ajax_js / ajax_css + the data_url/button_label/autoload/fetch_opts tags)
# that render_ajax() configures and render() strips - no second template
# file to maintain.
TEMPLATE_PATH = _template_path("datatable_templ.html")

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
    "render_ajax",
    "to_js_array",
    "render_sample_df",
    "get_sample_df",
    "load_datatables",
    "render_nb",
]


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

    Purely cosmetic side effect: failures are reported but never propagate,
    so a missing system opener cannot break an otherwise successful render.
    """
    filepath = str(filename)
    try:
        if sys.platform.startswith("win"):
            os.startfile(filepath)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([opener, filepath], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        detail = e.stderr.decode() if e.stderr else "Unknown error"
        print(f"Failed to open file '{filepath}': {detail}")
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


def _prepare_dataframe(df, precision):
    """
    Prepares a DataFrame for rendering without modifying the original.
    """
    import pandas as pd

    # Convert Series to DataFrame with proper naming
    if isinstance(df, pd.Series):
        df = df.to_frame(name=df.name or "value").reset_index()

    # Work on a copy to avoid modifying the original
    df_copy = df.copy()

    # Flatten MultiIndex columns by joining levels with underscores
    if isinstance(df_copy.columns, pd.MultiIndex):
        df_copy.columns = ["_".join(map(str, col)).strip() for col in df_copy.columns]

    # Ensure all column names are strings
    df_copy.columns = df_copy.columns.astype(str)

    # Make duplicate column names unique ("a", "a" -> "a", "a_1") so that
    # df[col] always returns a Series, not a DataFrame
    if not df_copy.columns.is_unique:
        seen = {}
        new_cols = []
        for col in df_copy.columns:
            seen[col] = seen.get(col, 0) + 1
            new_cols.append(col if seen[col] == 1 else f"{col}_{seen[col] - 1}")
        df_copy.columns = new_cols
        warnings.warn(
            f"Duplicate column names found; renamed to: {new_cols}", UserWarning
        )

    # Round numeric columns to specified precision
    float_cols = df_copy.select_dtypes(include="number").columns
    if len(float_cols) > 0:
        try:
            df_copy[float_cols] = df_copy[float_cols].round(precision)
        except ValueError as e:
            warnings.warn(f"Could not round numeric columns: {e}", UserWarning)

    # Convert unhashable types (lists, dicts) to string representation
    for col in df_copy.columns:
        try:
            df_copy[col].nunique()
        except TypeError:
            df_copy[col] = df_copy[col].map(repr)

    return df_copy


def _generate_column_defs(df, load_column_control, dropdown_select_threshold):
    """
    Generates DataTables column definitions with appropriate search controls.

    - Float columns always get a text search filter.
    - Integer columns use the dropdown_select_threshold (dropdown if few unique values).
    - Other non‑numeric columns also use the dropdown_select_threshold.

    Args:
        df: Prepared DataFrame
        load_column_control: Whether to include column control configuration
        dropdown_select_threshold: Maximum unique values for dropdown filters
                                   (applied to integer & non‑numeric columns only)

    Returns:
        list: Column definition dictionaries for DataTables
    """
    import pandas as pd  # safe because the DataFrame is already pandas

    columns = []
    for col in df.columns:
        col_cleaned = col.replace("_", " ")
        col_def = {"title": col_cleaned, "orderable": True}

        # Determine the column's nature
        is_float = pd.api.types.is_float_dtype(df[col])
        is_integer = pd.api.types.is_integer_dtype(df[col])

        if is_float:
            # Float columns → always text search, never a dropdown
            col_def["searchable"] = True
            if load_column_control:
                col_def["columnControl"] = ["order", ["title", "search"]]
        elif is_integer:
            # Integer columns → use the threshold
            try:
                nunique = df[col].nunique()
            except TypeError:
                nunique = dropdown_select_threshold  # fallback to text search

            if nunique < dropdown_select_threshold:
                if load_column_control:
                    col_def["columnControl"] = ["order", ["title", "searchList"]]
                # no need to set searchable, columnControl defines it
            else:
                col_def["searchable"] = True
                if load_column_control:
                    col_def["columnControl"] = ["order", ["title", "search"]]
        else:
            # Non‑numeric columns (strings, categories, booleans, objects, etc.)
            # Use the threshold just like before
            try:
                nunique = df[col].nunique()
            except TypeError:
                nunique = dropdown_select_threshold

            if nunique < dropdown_select_threshold:
                if load_column_control:
                    col_def["columnControl"] = ["order", ["title", "searchList"]]
            else:
                col_def["searchable"] = True
                if load_column_control:
                    col_def["columnControl"] = ["order", ["title", "search"]]

        columns.append(col_def)
    return columns


def process_pandas(
    df,
    precision,
    load_column_control,
    dropdown_select_threshold,
    include_data=True,
):
    """
    Complete processing pipeline for pandas DataFrames.

    Args:
        include_data: If False, skip the (potentially expensive) conversion of
            all rows to a Python list. Only the prepared DataFrame and column
            definitions are returned. Used by render_ajax(), where the rows
            are fetched later via AJAX.
    """
    df_prepared = _prepare_dataframe(df, precision)
    columns_defs = _generate_column_defs(
        df_prepared, load_column_control, dropdown_select_threshold
    )
    data_arrays = df_prepared.values.tolist() if include_data else []
    # "category" is included for parity with the polars backend.
    search_columns = list(
        df_prepared.select_dtypes(include=["object", "string", "category"]).columns
    )

    return data_arrays, columns_defs, search_columns, df_prepared


def _load_tablepl():
    try:
        from . import tablepl
    except ImportError:
        import tablepl
    return tablepl


def _strict_json_safe(obj):
    """
    Recursively replaces non-finite floats (NaN, inf, -inf) with None.

    Python's json.dumps emits bare NaN/Infinity tokens by default - legal
    inside a <script> block, but invalid strict JSON: JSON.parse /
    fetch().json() reject it. Using null everywhere keeps the payload of
    render() and to_js_array() in one dialect. numpy floats (np.float64)
    are covered - they subclass float.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, (list, tuple)):
        return [_strict_json_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strict_json_safe(v) for k, v in obj.items()}
    return obj


def _columns_to_json(columns_defs):
    """Serializes column definitions, injecting the JS render_num function reference."""
    return json.dumps(
        columns_defs, separators=(",", ":"), ensure_ascii=False
    ).replace(f'"{RENDER_NUM_FUNC}"', RENDER_NUM_FUNC.strip("#"))


def _render_html_template(template_path, template_vars):
    """
    Loads and renders the HTML template with provided variables.

    comnt.render() runs in strict mode: a template_vars key without a
    matching tag in the template raises instead of silently leaving the
    placeholder comment block in the produced HTML.

    Raises:
        FileNotFoundError: If the template file does not exist
        RuntimeError: If the template cannot be read or rendered
    """
    try:
        with open(template_path, encoding="utf-8") as f:
            template_str = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Template file not found at: {template_path}. "
            "Ensure the template exists or provide a custom path via 'templ_path' parameter."
        ) from None
    except Exception as e:
        raise RuntimeError(
            f"Error reading template: {type(e).__name__}: {e}"
        ) from e

    try:
        return comnt.render(template_str, template_vars, strict=True)
    except Exception as e:
        raise RuntimeError(
            f"Error rendering template: {type(e).__name__}: {e}"
        ) from e


def _strip_ajax_blocks(html):
    """
    render() does not use the AJAX loader - remove its regions (ajax_js /
    ajax_css) from the output. render_ajax() generates its variant from the
    SAME template by simply leaving those regions in place, so there is no
    second template file to maintain. Custom templates without the regions
    are fine: a missing tag is not an error here.
    """
    for tag in ("ajax_js", "ajax_css"):
        try:
            html = comnt.render(html, {tag: ""}, strict=True)
        except comnt.NotFoundError:
            pass
    return html


DEPRECATED_ARGS = {
    "load_column_control",
    "display_logo",
    "num_html",
}

DEFAULT_RENDER_OPTS = {
    "locale_fmt": False,
    "reorder": False,
    "dropdown_select_threshold": 9,
    "table_id": "pd_datatab",
    "unique_id": False,
    "default_table_class": "display compact hover order-column",
    "load_column_control": True,
    "add_expand_btn": True,
    "display_logo": False,
    "scroll_x": True,
    "scroll_y": "70vh",
    "scroll_collapse": True,
}

_UNSET = object()


def _resolve_render_opts(render_opts, kwargs, func_name):
    """
    Single place where render()/render_ajax() options are resolved.

    - deprecated kwargs (DEPRECATED_ARGS) are merged into the options dict
      with a DeprecationWarning - and actually take effect downstream
      (this used to be silently broken in render_ajax());
    - 'num_html' (renamed to 'format_negatives') is returned via the sentinel;
    - unknown kwargs produce a UserWarning and are ignored;
    - render_opts (if a dict) override everything.

    Returns:
        (final_opts, num_html): num_html is _UNSET when the kwarg was absent.
    """
    final_opts = DEFAULT_RENDER_OPTS.copy()
    num_html = _UNSET
    deprecated = {}

    for key, value in kwargs.items():
        if key == "num_html":
            num_html = value
        elif key in DEPRECATED_ARGS:
            deprecated[key] = value
        else:
            warnings.warn(
                f"Unknown argument '{key}' passed to {func_name}; ignored.",
                UserWarning,
                stacklevel=3,
            )

    if num_html is not _UNSET:
        warnings.warn(
            "'num_html' was renamed into 'format_negatives'.",
            DeprecationWarning,
            stacklevel=3,
        )
    for key in deprecated:
        warnings.warn(
            f"Passing arguments like [{key}] directly to {func_name} is deprecated "
            "and will be removed in a future version. "
            "Please use the 'render_opts' dictionary instead.",
            DeprecationWarning,
            stacklevel=3,
        )
    final_opts.update(deprecated)

    if render_opts is not None:
        if not isinstance(render_opts, dict):
            raise TypeError(
                f"render_opts must be a dict or None, got {type(render_opts).__name__}"
            )
        final_opts.update(render_opts)

    return final_opts, num_html


def _process_dataframe(df, precision, final_opts, include_data=True):
    """
    Dispatches to the pandas or polars preparation pipeline.

    Args:
        include_data: If False, rows are NOT converted to Python lists
            (used by render_ajax(), which never embeds rows in the HTML).

    Returns:
        tuple: (data_arrays, columns_defs, search_columns, df_prepared)

    Raises:
        ValueError: On invalid precision or unsupported DataFrame type.
    """
    if not isinstance(precision, int) or precision < 0:
        raise ValueError(f"precision must be an integer, got: {type(precision).__name__}")

    mod_name = type(df).__module__
    if "pandas" in mod_name:
        return process_pandas(
            df,
            precision,
            final_opts["load_column_control"],
            final_opts["dropdown_select_threshold"],
            include_data=include_data,
        )
    if "polars" in mod_name:
        return _load_tablepl().process_pl(
            df,
            precision,
            final_opts["load_column_control"],
            final_opts["dropdown_select_threshold"],
            include_data=include_data,
        )
    raise ValueError(
        f"Unsupported DataFrame type: {type(df).__name__} from module {mod_name}. "
        "Expected pandas or polars DataFrame."
    )


def get_cols_with_neg(df):
    col_indexes = []
    for i, col in enumerate(df.columns):
        try:
            if (df[col] < 0).any():
                col_indexes.append(i)
        except (TypeError, NotImplementedError, ValueError):
            # ValueError: ambiguous truth value (e.g. duplicate column names)
            pass
    return col_indexes


def _apply_format_negatives(df_prepared, columns_defs, format_negatives):
    """
    Marks columns for the num-html negative-number renderer.

    format_negatives=True auto-detects columns containing negative values;
    a list/tuple/set is matched against the ORIGINAL column names (and, as a
    convenience, against the displayed title). Matching original names avoids
    the old title-mangling collisions ("a b" vs "a_b").

    Raises:
        TypeError: If format_negatives is not False/None/True or a collection.
    """
    if format_negatives is False or format_negatives is None:
        return
    if format_negatives is True:
        for idx in get_cols_with_neg(df_prepared):
            columns_defs[idx]["render"] = RENDER_NUM_FUNC
            columns_defs[idx]["type"] = "num-html"
        return
    if isinstance(format_negatives, (list, tuple, set)):
        wanted = {str(name) for name in format_negatives}
        for idx, col in enumerate(df_prepared.columns):
            if col in wanted or columns_defs[idx]["title"] in wanted:
                columns_defs[idx]["render"] = RENDER_NUM_FUNC
                columns_defs[idx]["type"] = "num-html"
        return
    raise TypeError(
        "format_negatives must be False, True, or a list/tuple/set of column "
        f"names, got: {type(format_negatives).__name__}"
    )


def _base_template_vars(final_opts, title, precision):
    """
    Template vars shared by every template (regular and ajax): title, table
    identity/markup, scrolling, precision, locale formatting and logo.
    """
    table_id = final_opts.get("table_id") or DEFAULT_RENDER_OPTS["table_id"]
    if final_opts.get("unique_id"):
        table_id = f"id_{uuid.uuid4().hex}"

    template_vars = {
        "title": str(title),
        "table_id": json.dumps(table_id),
        "table_markup": html_tag(
            "table",
            attrs={
                "id": table_id,
                "style": "width:100%;",
                "class": final_opts.get(
                    "default_table_class", DEFAULT_RENDER_OPTS["default_table_class"]
                ),
            },
        ),
        "scroll_x": json.dumps(bool(final_opts.get("scroll_x", True))),
        "scroll_y": json.dumps(final_opts.get("scroll_y", "70vh")),
        "scroll_collapse": json.dumps(bool(final_opts.get("scroll_collapse", True))),
    }

    if precision != 2:
        template_vars["precision"] = json.dumps(int(precision))
    if final_opts.get("locale_fmt", False):
        template_vars["locale_fmt"] = json.dumps(True)
    if not final_opts.get("display_logo", False):
        template_vars["datatables_logo"] = ""
    if final_opts.get("add_expand_btn") is False:
        template_vars["add_expand_btn"] = json.dumps(False)
    return template_vars


def _merge_buttons(js_opts, buttons):
    """
    Validates js_opts/buttons (raising TypeError instead of assert, which
    would vanish under python -O) and merges DataTables buttons into the
    layout. Returns a copy - the caller's js_opts is never mutated.
    """
    if js_opts is None:
        js_opts = {}
    if not isinstance(js_opts, dict):
        raise TypeError(f"js_opts must be a dict or None, got {type(js_opts).__name__}")
    if any(not isinstance(key, str) for key in js_opts):
        raise TypeError("js_opts keys must be strings")

    if not buttons:
        return js_opts
    if not isinstance(buttons, (list, tuple)):
        raise TypeError(
            f"buttons must be a list of DataTables button names, got {type(buttons).__name__}"
        )

    butt_obj = {"buttons": list(buttons)}
    layout = dict(js_opts.get("layout") or {})
    layout.update({"topStart": ["pageLength", [butt_obj]]})
    return {**js_opts, "layout": layout}


def _emit(html_content, to_file, startfile):
    """
    Writes the rendered HTML to to_file (or returns it as a string when
    to_file is empty). Write errors propagate to the caller instead of being
    printed and swallowed.
    """
    if not to_file:
        return html_content
    with open(to_file, "w", encoding="utf-8") as outfile:
        outfile.write(html_content)
    print(f"Successfully created DataTable at: {to_file}")
    if startfile:
        open_file(to_file)
    return to_file


def _apply_reorder(final_opts, columns_defs):
    if final_opts.get("reorder") and final_opts.get("load_column_control"):
        for col_def in columns_defs:
            col_def.setdefault("columnControl", []).append("reorder")


def render(
    df,
    to_file="datatable.html",
    title="",
    startfile=True,
    precision=2,
    format_negatives=False,
    buttons=False,
    render_opts=None,
    js_opts=None,
    templ_path=TEMPLATE_PATH,
    **kwargs,
):
    """
    Renders a pandas or polars DataFrame as an interactive HTML DataTable.

    Args:
        to_file: output file path; if None/empty, the HTML string is returned
        title: page/table title (may contain HTML, e.g. "Example <b>df</b>")
        startfile: open the generated file in the browser after writing
        precision: rounding precision for float columns
        format_negatives: False / True (auto-detect) / list of original column names
        buttons: list of DataTables buttons, e.g. ["colvis", "copy", "excel"]
        render_opts: dict overriding DEFAULT_RENDER_OPTS
        js_opts: dict of extra DataTables options, deep-merged into table opts
        templ_path: path to the HTML template

    Returns:
        str: file path if to_file is set, otherwise the HTML string

    Raises:
        ValueError: If precision is invalid or the DataFrame type is unsupported
        TypeError: If render_opts/js_opts/buttons/format_negatives have wrong types
        FileNotFoundError: If the HTML template cannot be found
        RuntimeError: If the HTML template cannot be read or rendered
        OSError: If the output file cannot be written
    """
    final_opts, num_html = _resolve_render_opts(render_opts, kwargs, "render()")
    if num_html is not _UNSET:
        format_negatives = num_html

    data_arrays, columns_defs, search_columns, df_prepared = _process_dataframe(
        df, precision, final_opts
    )
    _apply_reorder(final_opts, columns_defs)
    _apply_format_negatives(df_prepared, columns_defs, format_negatives)

    template_vars = _base_template_vars(final_opts, title, precision)
    template_vars["tab_data"] = json.dumps(
        _strict_json_safe(data_arrays), cls=DataJSONEncoder, separators=(",", ":")
    )
    template_vars["tab_columns"] = _columns_to_json(columns_defs)
    template_vars["search_columns"] = json.dumps(search_columns, separators=(",", ":"))

    template_vars["js_opts"] = json.dumps(_merge_buttons(js_opts, buttons))

    html_content = _render_html_template(templ_path, template_vars)
    # render() never uses the AJAX loader - strip its regions from the
    # output (render_ajax() generates its variant from the same template).
    html_content = _strip_ajax_blocks(html_content)
    return _emit(html_content, to_file, startfile)


def render_inline(df, table_attrs=None, add_scripts=False, **kwargs):
    """
    Renders a DataFrame as inline HTML for embedding in existing pages.

    Each call generates a unique table id by default, so several tables can
    be embedded on one page without DOM id collisions (pass an explicit
    'id' via table_attrs to control it yourself).

    Args:
        df: DataFrame to render (pandas or polars)
        table_attrs: Custom HTML attributes for the table element (default: None)
        add_scripts: include the DataTables <script> dependencies
        **kwargs: Additional arguments passed to render() (except 'to_file' and 'title')

    Returns:
        str: Minimal HTML content for embedding (table + scripts)

    Example:
        >>> html = render_inline(df, table_attrs={'id': 'my-table', 'class': 'custom'})
    """
    if kwargs.pop("to_file", None):
        warnings.warn(
            "'to_file' argument is ignored in render_inline - output is always returned as string"
        )
    if kwargs.pop("title", None):
        warnings.warn(
            "'title' argument is ignored in render_inline - no page title in inline mode"
        )

    # Always render without file output
    html = render(df, to_file=None, **kwargs)
    attrs = {
        "class": DEFAULT_RENDER_OPTS["default_table_class"],
        **(table_attrs or {}),
    }
    if not attrs.get("id"):
        # Unique per call: two tables on one page must not share a DOM id.
        attrs["id"] = f"dt_{uuid.uuid4().hex[:8]}"

    base_table = html_tag("table", attrs=attrs)

    # Update JavaScript to reference correct table ID
    html = comnt.render(html, {"table_id": f'"{attrs["id"]}"'})

    # Extract minimal content needed for embedding
    if add_scripts:
        base_table = comnt.get_tag_content("scripts", html) + base_table

    min_content = base_table + comnt.get_tag_content("min_content", html)
    return min_content


def to_js_array(df, precision=2, raw=False):
    """
    Converts a pandas/polars DataFrame to a JavaScript array-of-arrays
    (strict JSON), exactly in the shape consumed by pages rendered with
    render_ajax().

    Intended for Flask/FastAPI endpoints serving data to those pages.
    NaN/inf cells are emitted as null, so the output always passes
    JSON.parse.

    Args:
        df: pandas or polars DataFrame
        precision: rounding precision for float columns (same as render())
        raw: if True, returns the plain (already NaN-cleaned) Python list
             instead of a JSON string - safe to pass to Flask's jsonify()

    Returns:
        str or list: JSON string like '[[1,"a",3.5],[2,"b",4.1]]' (default),
                     or the underlying list of lists when raw=True

    Example (Flask):
        @app.route("/api/table")
        def api_table():
            return Response(to_js_array(df), mimetype="application/json")
    """
    data_arrays, _, _, _ = _process_dataframe(df, precision, DEFAULT_RENDER_OPTS.copy())
    data_arrays = _strict_json_safe(data_arrays)
    if raw:
        return data_arrays
    # allow_nan=False: a non-finite value that slipped through the cleaner
    # (e.g. Decimal("NaN")) raises loudly instead of shipping invalid JSON.
    return json.dumps(
        data_arrays, cls=DataJSONEncoder, separators=(",", ":"), allow_nan=False
    )


def render_ajax(
    df,
    data_url,
    to_file=None,
    title="",
    startfile=True,
    precision=2,
    format_negatives=False,
    buttons=False,
    button_label="Load data",
    autoload=False,
    fetch_opts=None,
    render_opts=None,
    js_opts=None,
    templ_path=TEMPLATE_PATH,
    full_page=False,
    add_scripts=False,
    table_attrs=None,
    **kwargs,
):
    """
    Renders a DataFrame as a DataTable whose rows are fetched at runtime
    from `data_url` (Fetch API) - generated from the SAME template as
    render(): the AJAX loader lives in comnt regions (ajax_js / ajax_css)
    that render() strips from its output and render_ajax() keeps and
    configures. No separate AJAX template is maintained on disk.

    By default returns an INLINE FRAGMENT, exactly like render_inline():
    the loader <style>, the <table> skeleton and the initialization
    <script>, ready to embed into an existing page next to other content.
    Several fragments may live on one page (each call gets a unique table
    id unless you pin one). With full_page=True a complete standalone
    HTML document is produced instead.

    With autoload=False a button labelled `button_label` fetches the rows
    on click; with autoload=True there is no button at all - a subtle
    pulsing "Loading data..." indicator shows while the rows arrive (a
    Retry button appears only on failure).

    The endpoint at `data_url` should return JSON in one of two shapes:
        - a bare array of rows:   [[1, "a", 3.5], [2, "b", 4.1]]
        - an object with 'data':  {"data": [[1, "a", 3.5], ...]}
    Use to_js_array(df) (or the plain list from to_js_array(df, raw=True))
    to produce this payload.

    Args:
        df: pandas or polars DataFrame (used to derive columns and options)
        data_url: URL of the endpoint returning the row data as JSON
        to_file: output file path; if None/empty, the HTML is returned
        title: page title (full_page mode only; ignored in fragments)
        startfile: open the generated file in the browser after writing
        precision: rounding precision for float columns
        format_negatives: False / True / list of column names (see render())
        buttons: list of DataTables buttons, e.g. ["colvis", "copy", "excel"]
        button_label: label of the load-data button (autoload=False only)
        autoload: fetch data immediately, without any button
        fetch_opts: dict merged into the fetch() options (defaults to
                    {"credentials": "same-origin"})
        render_opts: dict overriding DEFAULT_RENDER_OPTS (see render())
        js_opts: dict of extra DataTables options, deep-merged into table opts
        templ_path: HTML template - must contain the same comnt tags as
                    datatable_templ.html, including the ajax_js / ajax_css
                    regions and the data_url / button_label / autoload /
                    fetch_opts tags
        full_page: return a complete standalone HTML document instead of
                   the inline fragment
        add_scripts: prepend the DataTables CDN <link>/<script> block
                     (inline mode only; the host page usually provides it)
        table_attrs: extra HTML attributes for the <table> element
                     (inline mode only)

    Returns:
        str: file path if to_file is set, otherwise the fragment / document

    Raises:
        TypeError: If data_url is not a string, or opts/buttons have wrong types
        ValueError: If precision is invalid or the DataFrame type is unsupported
        FileNotFoundError / RuntimeError: template problems
        OSError: If the output file cannot be written

    Example (Flask):
        @app.route("/")
        def index():
            frag = render_ajax(df, "/api/table")   # inline fragment
            return f"<html><body>{frag}</body></html>"

        @app.route("/api/table")
        def api_table():
            return Response(to_js_array(df), mimetype="application/json")
    """
    final_opts, num_html = _resolve_render_opts(render_opts, kwargs, "render_ajax()")
    if num_html is not _UNSET:
        format_negatives = num_html

    if not isinstance(data_url, (str, Path)):
        raise TypeError(f"data_url must be a str, got {type(data_url).__name__}")

    if not full_page:
        # Inline fragment (default, render_inline-style): every embedded
        # table needs its own DOM id unless the caller pinned one.
        explicit_id = (render_opts or {}).get("table_id") or (table_attrs or {}).get("id")
        if explicit_id:
            final_opts["table_id"] = explicit_id
            final_opts["unique_id"] = False
        else:
            final_opts["unique_id"] = True

    # Rows are intentionally NOT materialized here - only columns/search
    # definitions are baked into the page (include_data=False).
    _, columns_defs, search_columns, df_prepared = _process_dataframe(
        df, precision, final_opts, include_data=False
    )
    _apply_reorder(final_opts, columns_defs)
    _apply_format_negatives(df_prepared, columns_defs, format_negatives)

    template_vars = _base_template_vars(final_opts, title, precision)
    template_vars["tab_data"] = "[]"  # rows arrive via fetch(), never embedded
    template_vars["tab_columns"] = _columns_to_json(columns_defs)
    template_vars["search_columns"] = json.dumps(search_columns, separators=(",", ":"))
    template_vars["data_url"] = json.dumps(str(data_url), ensure_ascii=False)
    template_vars["button_label"] = json.dumps(str(button_label), ensure_ascii=False)
    template_vars["autoload"] = json.dumps(bool(autoload))
    template_vars["fetch_opts"] = json.dumps(fetch_opts or {}, separators=(",", ":"))
    template_vars["js_opts"] = json.dumps(_merge_buttons(js_opts, buttons))

    # NOTE: ajax_js / ajax_css are deliberately NOT passed - those regions
    # of the single template stay alive here (render() strips them instead).
    html_content = _render_html_template(templ_path, template_vars)

    if full_page:
        return _emit(html_content, to_file, startfile)

    # --- inline fragment (default), in the spirit of render_inline() ---
    # The loader CSS travels with the fragment (self-contained look), the
    # DataTables assets are the host page's job unless add_scripts=True.
    table_id = json.loads(template_vars["table_id"])
    fragment = "<style>" + comnt.get_tag_content("ajax_css", html_content) + "</style>"
    if add_scripts:
        fragment += comnt.get_tag_content("scripts", html_content)
    attrs = {
        "style": "width:100%;",
        "class": final_opts.get(
            "default_table_class", DEFAULT_RENDER_OPTS["default_table_class"]
        ),
        **(table_attrs or {}),
        "id": table_id,
    }
    fragment += html_tag("table", attrs=attrs)
    fragment += comnt.get_tag_content("min_content", html_content)

    if to_file:
        warnings.warn(
            "to_file writes the inline fragment; pass full_page=True for a "
            "standalone page."
        )
        return _emit(fragment, to_file, startfile)
    return fragment


def get_sample_df(df_type="pandas", size=50):
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
        "timestamp": [
            (datetime.datetime.now() - datetime.timedelta(days=i)) for i in range(size)
        ],
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
            [-0.333, 1, -9, 4, 2, np.nan, random.randint(-1000, 10000)], size
        )

        # Include edge cases: NaT, HTML, nested structures, NA values
        base_data["description"] = random_choice(
            [
                np.datetime64("NaT"),
                "<b>HTML content</b> is allowed",
                {"A": [1, 2, 3, [4, 5]]},
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
        base_data["measurement"] = random_choice(
            [-0.333, 1, -9, 4, 2, None, 1111.111], size
        )

        # Polars-compatible edge cases
        base_data["description"] = random_choice(
            [
                "Lorem ipsum dolor sit amet",
                "<b>HTML content</b> is allowed",
                {"A": [1, 2, 3, [4, 5]]},
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


def render_nb(df, iframe=True, height=500, **kwargs):
    """
    Render a DataFrame as interactive HTML within a notebook environment.
    """
    if "render_opts" in kwargs:
        render_opts = dict(kwargs.get("render_opts") or {})
        render_opts.update({"unique_id": True, "display_logo": False})
        kwargs["render_opts"] = render_opts
    html_content = render(
        df,
        to_file=None,
        **kwargs,
    )
    # Escape quotes only for the srcdoc attribute (the browser decodes them
    # back when parsing the iframe). Replacing quotes in the raw HTML breaks
    # the <script> blocks, where character references are not decoded.
    iframe_content = None
    if iframe:
        escaped = html_content.replace('"', "&quot;")
        iframe_content = (
            f'<!--silence iframe --><iframe srcdoc="{escaped}" '
            f'style="width:100%;height:{height}px;border:none;"></iframe>'
        )

    try:
        import IPython.display as disp

        if iframe:
            disp.display(disp.HTML(iframe_content))
        else:
            disp.display(disp.HTML(html_content))

    except ImportError:
        try:
            import marimo

            return marimo.Html(iframe_content if iframe else html_content)
        except ImportError:
            print("Notebook expected.")
            return None
    return None


show = render_nb


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
        title=f"Example <b>{df_type.capitalize()}</b> DataFrame",
        precision=3,
        format_negatives=["measurement"],
        buttons=["colvis", "copy", "excel"],
        render_opts={
            "locale_fmt": False,
            "unique_id": 1,
            "add_expand_btn": 1,
            "reorder": 1,
            "load_column_control": 1,
            "dropdown_select_threshold": 12,
        },
        js_opts={
            "language": {
                "decimal": "#",
            },
            "fixedColumns": {"start": 1, "end": False},
        },
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
