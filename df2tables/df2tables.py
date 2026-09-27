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

import functools
import json
import logging
import math
import os
import reprlib
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

# sample/demo helpers live in sample.py; re-exported here so the public
# API (df2tables.get_sample_df / render_sample_df, from-imports) is unchanged
try:
    from .sample import get_sample_df, render_sample_df
except ImportError:  # plain source-dir usage
    from sample import get_sample_df, render_sample_df

# Configuration constants
RENDER_NUM_FUNC = "#render_num"  # Placeholder for JS function injection

log = logging.getLogger(__name__)

__all__ = [
    "TEMPLATE_PATH",
    "render",
    "render_inline",
    "render_ajax",
    "to_js_array",
    "render_sample_df",
    "get_sample_df",
    "render_nb",
    "show",
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
        log.warning("failed to open file '%s': %s", filepath, detail)
    except FileNotFoundError:
        log.warning("could not find system opener; open '%s' manually", filepath)
    except Exception as e:
        log.warning(
            "unexpected error opening file '%s': %s: %s", filepath, type(e).__name__, e
        )


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
                number = float(obj)
                if math.isfinite(number):
                    return number
                return _nonfinite_label(number)  # never a bare NaN/Infinity token
            return super().default(obj)
        except (TypeError, ValueError):
            # Fallback: plain repr (e.g. bytes -> b'\x00\x01'). No HTML
            # escaping here - the value goes into a JS string literal, not into
            # markup, and entities (b&#x27;..&#x27;) only corrupted what the
            # cell showed, what was copied out and what was exported. '<'
            # safety is _js_json()'s job.
            return repr(obj)


# --- complex cells & missing values: speed-first, basic previews ------------
# Directive (2026-09-26): showing every special value by name is NOT critical
# and nested structures only need a basic preview - both features are
# implemented for SPEED. Hard floor (never compromised): no bare NaN/Infinity
# token may reach a payload (invalid JSON), and to_js_array(raw=True) stays
# Flask-jsonify-safe.
DEFAULT_LIST_PREVIEW = 5
LIST_PREVIEW = DEFAULT_LIST_PREVIEW  # historical name (former tablepl)
_MISSING_LABEL = "NA"  # ONE label for every missing flavour (None/pd.NA/NaT/...)
_CONTAINERS = (list, tuple, dict, set, frozenset)


def _is_sequence(value):
    """
    True for sequence-like cells (list/tuple/set/ndarray/...), never for
    str/bytes/dict - those keep their repr().
    """
    if isinstance(value, (str, bytes, bytearray, dict)):
        return False
    return isinstance(value, (list, tuple, set, frozenset)) or (
        hasattr(value, "__len__") and hasattr(value, "__getitem__")
    )


_REPR_CACHE = {}


def _repr_for(limit):
    """One reprlib.Repr per preview limit (bounded repr, cached)."""
    rep = _REPR_CACHE.get(limit)
    if rep is None:
        rep = reprlib.Repr()
        rep.maxlist = rep.maxtuple = rep.maxdict = rep.maxset = rep.maxfrozenset = limit
        _REPR_CACHE[limit] = rep
    return rep


def _preview(value, limit):
    """
    BASIC preview for one container cell, e.g. '[0, 1, 2, 3, 4, ...]'.

    reprlib gives bounded output in (near-)constant time whatever the
    container size - no len(), no per-element repr(), no full materialisation
    (str(v)[:N] would already be O(n) for a big list). Below the limit this is
    exactly repr(); above it reprlib elides the tail with '...'.
    """
    return _repr_for(limit).repr(value)


def _cell_text(value, limit):
    """
    Display text for one complex cell (pandas unhashable columns): containers
    get the basic preview, everything else its full repr().
    """
    if isinstance(value, _CONTAINERS) or _is_sequence(value):
        return _preview(value, limit)
    return repr(value)


def _nonfinite_label(value):
    """'NaN' / 'inf' / '-inf' for one non-finite float (JSON must never see it bare)."""
    if value != value:
        return "NaN"
    return "inf" if value > 0 else "-inf"


def _label_float_col(values, np_arr):
    """
    One float column: vectorized non-finite mask, only bad cells are touched.
    NaN/inf/-inf are VALUES and keep distinct names - this is payload
    validity, not display.
    """
    import numpy as np

    for i in np.flatnonzero(~np.isfinite(np_arr)):
        values[i] = _nonfinite_label(np_arr[i])
    return values


def _label_mixed_col(values, limit, missing_idx=()):
    """
    One mixed/object column: missing -> _MISSING_LABEL (mask-driven where the
    backend can supply one), non-finite floats -> their names, containers ->
    basic preview. Scalars that JSON handles natively pass through untouched;
    exotic scalars are left to DataJSONEncoder.default (isoformat/decimal/repr).
    """
    for i in missing_idx:
        values[i] = _MISSING_LABEL
    for i, value in enumerate(values):
        kind = type(value)
        if kind is str or kind is int or kind is bool:
            continue
        if value is None:
            values[i] = _MISSING_LABEL
        elif isinstance(value, float):
            if not math.isfinite(value):
                values[i] = _nonfinite_label(value)
        elif isinstance(value, _CONTAINERS):
            values[i] = _preview(value, limit)
    return values


def _label_nested_col(values, limit):
    """
    One polars Array column: cells STAY JSON arrays (contract), only their
    scalars are cleaned (missing / non-finite floats).
    """
    for cell in values:
        if type(cell) is list:
            for j, item in enumerate(cell):
                if item is None:
                    cell[j] = _MISSING_LABEL
                elif isinstance(item, float) and not math.isfinite(item):
                    cell[j] = _nonfinite_label(item)
    return values


def _prepare_dataframe(df, precision, list_preview=DEFAULT_LIST_PREVIEW):
    """
    Prepares a DataFrame for rendering without modifying the original.
    """
    import pandas as pd

    # Convert Series to DataFrame with proper naming
    if isinstance(df, pd.Series):
        df = df.to_frame(name=df.name or "value").reset_index()

    
    df_copy = df.copy() # Work on a copy to avoid modifying the original

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

    # Unhashable columns (lists, dicts, sets) have no nunique() and cannot be
    # indexed, so each cell becomes its display text: containers get the
    # bounded basic preview (see _preview), other values their repr().
    # The n_unique computed here for detection is REUSED by the column-def
    # builder - one scan per column, not three.
    nunique_map = {}
    for col in df_copy.columns:
        try:
            nunique_map[col] = df_copy[col].nunique()
        except TypeError:
            df_copy[col] = df_copy[col].map(
                lambda value: _cell_text(value, list_preview)
            )
            nunique_map[col] = df_copy[col].nunique()

    return df_copy, nunique_map


def _column_def(title, is_float, n_unique, threshold, load_control):
    """
    ONE shared policy function for DataTables column definitions (both
    backends). Float columns always get a text search; every other column
    uses the threshold (dropdown below it, text search at/above). n_unique
    None means "unknown/unhashable" -> text search. The canonical dict key
    order lives HERE so pandas and polars emit byte-identical column defs.
    """
    col_def = {"title": title, "orderable": True}
    if not is_float and n_unique is not None and n_unique < threshold:
        if load_control:
            col_def["columnControl"] = ["order", ["title", "searchList"]]
    else:
        col_def["searchable"] = True
        if load_control:
            col_def["columnControl"] = ["order", ["title", "search"]]
    return col_def


def _pandas_kind(series):
    """
    Cleaning strategy for one pandas column: 'float' (vectorized non-finite
    mask), 'plain' (JSON-native numpy int/uint/bool - provably no sentinel,
    ZERO work), 'mixed' (everything else: nullable/extension/object/datetime).
    Search policy is decided separately via pd.api.types.is_float_dtype.
    """
    import pandas as pd

    if pd.api.types.is_extension_array_dtype(series):
        return "mixed"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_integer_dtype(series) or pd.api.types.is_bool_dtype(series):
        return "plain"
    return "mixed"


def process_pandas(
    df,
    precision,
    load_column_control,
    dropdown_select_threshold,
    include_data=True,
    list_preview=DEFAULT_LIST_PREVIEW,
):
    """
    Complete processing pipeline for pandas DataFrames.

    Args:
        include_data: If False, skip the (potentially expensive) conversion of
            all rows to a Python list. Only the prepared DataFrame and column
            definitions are returned. Used by render_ajax(), where the rows
            are fetched later via AJAX.
        list_preview: How many elements of a list cell are shown before it
            switches to the basic preview (see _preview).
    """
    import numpy as np
    import pandas as pd

    df_prepared, nunique_map = _prepare_dataframe(df, precision, list_preview)
    columns_defs = [
        _column_def(
            str(col).replace("_", " "),
            pd.api.types.is_float_dtype(df_prepared[col]),
            nunique_map.get(col),
            dropdown_select_threshold,
            load_column_control,
        )
        for col in df_prepared.columns
    ]
    data_arrays = []
    if include_data:
        cols = []
        for col in df_prepared.columns:
            series = df_prepared[col]
            values = series.tolist()
            kind = _pandas_kind(series)
            if kind == "float":
                _label_float_col(values, series.to_numpy())
            elif kind == "mixed":
                missing = np.flatnonzero(series.isna().to_numpy())
                _label_mixed_col(values, list_preview, missing)
            cols.append(values)
        data_arrays = [list(row) for row in zip(*cols)] if cols else []
    # "category" is included for parity with the polars backend.
    search_columns = list(
        df_prepared.select_dtypes(include=["object", "string", "category"]).columns
    )

    return data_arrays, columns_defs, search_columns, df_prepared


# --- polars backend (folded in from the former tablepl.py; polars imports
# stay function-local so `import df2tables` never requires polars) -----------


def _complex_cell_text(value, list_preview):
    """
    Basic preview for one complex Polars cell (List -> pl.Series, Struct ->
    dict, Object -> str). A List element arrives as a pl.Series whose str() is
    the internal debug repr ("shape: (2,)\nSeries: '' [i64]..."), so it can
    never be the cell's content: only a bounded head is converted (a big List
    cell is NEVER materialised fully) and reprlib bounds the text. Duck-typed
    on purpose - no polars import needed here.
    """
    if hasattr(value, "to_list") and hasattr(value, "head"):
        return _preview(value.head(list_preview + 1).to_list(), list_preview)
    if isinstance(value, (dict, set, frozenset)):
        return _preview(value, list_preview)
    return str(value)


def _prepare_dataframe_pl(df, precision, list_preview=LIST_PREVIEW):
    """
    Prepares a Polars df for rendering. Handles Series, data type conversions,
    and complex types without modifying the original df.
    """
    import polars as pl
    from polars.selectors import numeric

    if isinstance(df, pl.Series):
        df = df.to_frame(name=df.name or "value")

    return df.clone().with_columns(
        numeric().round(precision),
        pl.col(pl.List, pl.Struct, pl.Object).map_elements(
            functools.partial(_complex_cell_text, list_preview=list_preview),
            return_dtype=pl.String,
        ),
    )


def _polars_kind(series):
    """Cleaning strategy for one polars column (see _pandas_kind)."""
    import polars as pl

    if series.dtype == pl.Array:
        return "nested"  # cells stay JSON arrays; only inner scalars are cleaned
    if series.null_count():
        return "mixed"
    return "float" if series.dtype.is_float() else "plain"


def _get_search_cols(df):
    import polars as pl

    # String + Categorical + Enum: an Enum column used to be silently excluded
    # here while the pandas 'category' equivalent was included (drift bug).
    return list(df.select(pl.col(pl.String, pl.Categorical, pl.Enum)).columns)


def process_pl(
    df,
    precision=2,
    load_column_control=True,
    dropdown_select_threshold=9,
    include_data=True,
    list_preview=LIST_PREVIEW,
):
    """
    Prepares a polars df and builds the JSON-ready pieces for the templates.

    include_data=False skips converting all rows to Python lists - used by
    render_ajax(), where rows are fetched later via AJAX.

    list_preview is how many elements of a List cell are shown before the cell
    switches to the basic preview (see _preview).
    """
    df_prepared = _prepare_dataframe_pl(df, precision, list_preview)
    columns_defs = []
    for col_name in df_prepared.columns:
        series = df_prepared[col_name]
        is_float = series.dtype.is_float()
        n_unique = None
        if not is_float:
            try:
                n_unique = series.n_unique()
            except Exception:  # unhashable/exotic dtype (e.g. Array) -> text search
                n_unique = None
        columns_defs.append(
            _column_def(
                col_name.replace("_", " "),
                is_float,
                n_unique,
                dropdown_select_threshold,
                load_column_control,
            )
        )
    data_arrays = []
    if include_data:
        cols = []
        for col_name in df_prepared.columns:
            series = df_prepared[col_name]
            values = series.to_list()
            kind = _polars_kind(series)
            if kind == "float":
                _label_float_col(values, series.to_numpy())
            elif kind == "mixed":
                _label_mixed_col(values, list_preview)
            elif kind == "nested":
                _label_nested_col(values, list_preview)
            cols.append(values)
        data_arrays = [list(row) for row in zip(*cols)] if cols else []
    search_columns = _get_search_cols(df_prepared)
    return data_arrays, columns_defs, search_columns, df_prepared


def _js_json(obj, **kwargs):
    """
    json.dumps() + HTML-safe escaping for every payload embedded into a
    <script> block of the generated page.

    json.dumps never escapes '<', so raw cell data containing '</script>'
    would terminate the script element early (broken page / script
    injection). In JSON output '<' can only occur inside string literals,
    so replacing it with the \\u003c escape is always valid and decodes
    back to '<' on the JS side; it also defuses the '<!--' script-data
    parsing edge case. Existing backslash escapes are unaffected because
    json.dumps escapes backslashes itself.

    Note: to_js_array() deliberately does NOT use this - its output is
    consumed by JSON.parse over HTTP, where raw '</script>' is valid JSON
    and harmless.
    """
    return json.dumps(obj, **kwargs).replace("<", "\\u003c")


def _columns_to_json(columns_defs):
    """Serializes column definitions, injecting the JS render_num function reference."""
    return _js_json(
        columns_defs, separators=(",", ":"), ensure_ascii=False
    ).replace(f'"{RENDER_NUM_FUNC}"', RENDER_NUM_FUNC.strip("#"))


_TEMPLATE_CACHE = {}


def _template_text(template_path):
    """
    Read one template, cached by (path, mtime_ns, size) so a regenerated file
    is picked up while a stable one is read only once. read_text() works for
    BOTH pathlib.Path and importlib Traversables (zip installs) - builtin
    open() only accepts Path-likes.
    """
    try:
        path = (
            Path(template_path)
            if isinstance(template_path, (str, os.PathLike))
            else template_path
        )
        try:
            st = path.stat()
            key = (str(template_path), getattr(st, "st_mtime_ns", 0), st.st_size)
        except (AttributeError, OSError):
            key = (str(template_path), 0, 0)
        cached = _TEMPLATE_CACHE.get(key)
        if cached is None:
            cached = path.read_text(encoding="utf-8")
            _TEMPLATE_CACHE[key] = cached
        return cached
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Template file not found at: {template_path}. "
            "Ensure the template exists or provide a custom path via 'templ_path' parameter."
        ) from None
    except Exception as e:
        raise RuntimeError(
            f"Error reading template: {type(e).__name__}: {e}"
        ) from e


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
    template_str = _template_text(template_path)

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
    "list_preview": DEFAULT_LIST_PREVIEW,
    "paging_warn_limit": None,  # None = the template default (500) stands
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
        for key in render_opts:
            if key not in DEFAULT_RENDER_OPTS:
                warnings.warn(
                    f"Unknown render_opts key '{key}' passed to {func_name}; "
                    "it has no effect.",
                    UserWarning,
                    stacklevel=3,
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
            list_preview=final_opts["list_preview"],
        )
    if "polars" in mod_name:
        return process_pl(
            df,
            precision,
            final_opts["load_column_control"],
            final_opts["dropdown_select_threshold"],
            include_data=include_data,
            list_preview=final_opts["list_preview"],
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
        "table_id": _js_json(table_id),
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
        "scroll_x": _js_json(bool(final_opts.get("scroll_x", True))),
        "scroll_y": _js_json(final_opts.get("scroll_y", "70vh")),
        "scroll_collapse": _js_json(bool(final_opts.get("scroll_collapse", True))),
    }

    if precision != 2:
        template_vars["precision"] = _js_json(int(precision))
    if final_opts.get("locale_fmt", False):
        template_vars["locale_fmt"] = _js_json(True)
    if not final_opts.get("display_logo", False):
        template_vars["datatables_logo"] = ""
    if final_opts.get("add_expand_btn") is False:
        template_vars["add_expand_btn"] = _js_json(False)
    if final_opts.get("paging_warn_limit") is not None:
        template_vars["paging_warn_limit"] = _js_json(
            int(final_opts["paging_warn_limit"])
        )
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
    # only FILL an empty topStart; a caller-provided slot always wins
    if "topStart" not in layout:
        layout["topStart"] = ["pageLength", [butt_obj]]
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
    log.info("created DataTable at: %s", to_file)
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
    # rows are already cleaned/labelled by the backend pipeline
    template_vars["tab_data"] = _js_json(
        data_arrays, cls=DataJSONEncoder, separators=(",", ":"), allow_nan=False
    )
    template_vars["tab_columns"] = _columns_to_json(columns_defs)
    template_vars["search_columns"] = _js_json(search_columns, separators=(",", ":"))

    template_vars["js_opts"] = _js_json(_merge_buttons(js_opts, buttons))

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

    # Update JavaScript to reference correct table ID. JSON-encode it:
    # a hand-built '"%s"' would let an id containing '"' or '</script>'
    # break out of the JS string / the <script> element.
    html = comnt.render(html, {"table_id": _js_json(attrs["id"])})

    # Extract minimal content needed for embedding
    if add_scripts:
        base_table = comnt.get_tag_content("scripts", html) + base_table

    min_content = base_table + comnt.get_tag_content("min_content", html)
    return min_content


def to_js_array(df, precision=2, raw=False, list_preview=DEFAULT_LIST_PREVIEW):
    """
    Converts a pandas/polars DataFrame to a JavaScript array-of-arrays
    (strict JSON), exactly in the shape consumed by pages rendered with
    render_ajax().

    Intended for Flask/FastAPI endpoints serving data to those pages.
    Missing cells carry the single 'NA' label and non-finite floats keep
    their names ('NaN', 'inf', '-inf') - exactly what render() shows in the
    table. No bare NaN/Infinity token is ever emitted, so the output always
    passes JSON.parse(). Complex cells get the same basic preview as in
    render(): "[0, 1, 2, 3, 4, ...]".

    Args:
        df: pandas or polars DataFrame
        precision: rounding precision for float columns (same as render())
        raw: if True, returns the plain (already sentinel-labelled) Python
             list instead of a JSON string - safe to pass to Flask's jsonify()
        list_preview: how many elements of a list cell are shown before the
             cell switches to the explicit preview (same meaning as the
             render_opts option)

    Returns:
        str or list: JSON string like '[[1,"a",3.5],[2,"b",4.1]]' (default),
                     or the underlying list of lists when raw=True

    """
    opts = {**DEFAULT_RENDER_OPTS, "list_preview": list_preview}
    data_arrays, _, _, _ = _process_dataframe(df, precision, opts)
    if raw:
        return data_arrays
    # allow_nan=False: the pipeline leaves nothing non-finite behind, so
    # this only fires if some exotic object still hands a NaN back from
    # default() - then it fails loudly instead of shipping invalid JSON.
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
    from `data_url` (Fetch API). Same single template as render(); by
    default an INLINE FRAGMENT is returned - pass full_page=True for a
    complete standalone page.

    Rows are never embedded in the page: `df` only supplies columns and
    options; the endpoint returns a bare JSON array of rows (or an object
    with a 'data' array) - to_js_array(df) produces exactly that payload.
    With autoload=False a button labelled `button_label` fetches the rows on
    click; with autoload=True they load immediately.

    Non-obvious arguments: fetch_opts is merged into fetch() (defaults to
    {"credentials": "same-origin"}); add_scripts prepends the DataTables CDN
    assets in fragment mode; table_attrs adds <table> attributes. Every
    render() option (precision, format_negatives, buttons, render_opts,
    js_opts, ...) applies unchanged. Full parameter docs and a Flask
    example live in README.md.
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
    template_vars["search_columns"] = _js_json(search_columns, separators=(",", ":"))
    template_vars["data_url"] = _js_json(str(data_url), ensure_ascii=False)
    template_vars["button_label"] = _js_json(str(button_label), ensure_ascii=False)
    template_vars["autoload"] = _js_json(bool(autoload))
    template_vars["fetch_opts"] = _js_json(fetch_opts or {}, separators=(",", ":"))
    template_vars["js_opts"] = _js_json(_merge_buttons(js_opts, buttons))

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
    # Escape for the srcdoc attribute: '&' first, so character references
    # already present in the page (&quot;, &lt;, &#8230;, ...) survive the
    # one round of attribute decoding the browser performs - escaping only
    # quotes let them decode one level too early and corrupted (or killed)
    # the iframe document for entity-bearing data. The browser decodes
    # &amp; and &quot; back when parsing the attribute, so the iframe
    # receives the original HTML unchanged.
    iframe_content = None
    if iframe:
        escaped = html_content.replace("&", "&amp;").replace('"', "&quot;")
        iframe_content = (
            f'<iframe srcdoc="{escaped}" '
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
            log.warning("Notebook expected.")
            return None
    return None


show = render_nb


if __name__ == "__main__":
    try:
        from .sample import main as _sample_main
    except ImportError:  # plain source-dir usage
        from sample import main as _sample_main
    _sample_main()
