#!/usr/bin/python
# coding=utf8
import json
import math
import os
import subprocess
import sys
from functools import partial
from html import escape

import numpy as np
import pandas as pd

TEMPLATE_FILE = "datatable_templ.html"
try:
    # python 3.9+
    from importlib import resources

    TEMPLATE_PATH = str(resources.files("df2tables").joinpath(TEMPLATE_FILE))
except ImportError:
    TEMPLATE_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), TEMPLATE_FILE
    )

try:
    from .comnt import get_tag_content
    from .comnt import render as c_render
except ImportError:
    from comnt import get_tag_content
    from comnt import render as c_render

__all__ = [
    "TEMPLATE_PATH",
    "render",
    "render_inline",
    "render_sample_df",
    "get_sample_df",
]


def open_file(filename):
    if sys.platform.startswith("win"):
        os.startfile(filename)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])


class DataJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder with fallback to string representation"""

    def default(self, obj):
        try:
            obj_type = str(type(obj))
            if "str" in obj_type:
                return obj.strip()
            elif "nan" in repr(obj).lower():
                return None
            elif "date" in obj_type or "Timestamp" in obj_type:
                return obj.isoformat()
            elif "int" in obj_type:
                return int(obj)
            elif "float" in obj_type:
                return round(float(obj), 2)
            elif "bool" in obj_type:
                return bool(obj)
            elif isinstance(obj, (np.void)):
                return 0
            return super().default(obj)
        except BaseException:
            print("json error: ", repr(obj), sys.exc_info()[1])
            # Fallback to string representation for any problematic objects
            return escape(repr(obj))


def html_tag(tag, content="", attrs=None, self_closing=False):
    attrs = attrs or {}
    # Escape attribute values
    

    attr_str = "".join(f' {k}="{escape(str(v), quote=True)}"' for k, v in attrs.items())
    if self_closing:
        return f"<{tag}{attr_str} />"
    return f"<{tag}{attr_str}>{content}</{tag}>"


def fix_df_columns(df):
    for col in df.columns:
        try:
            test_val = (
                df[col].dropna().values.tolist() if not df[col].isna().all() else None
            )
            json.dumps(test_val, cls=DataJSONEncoder)
        except BaseException:
            print(f"! column error: {col}", sys.exc_info())
            df[col] = df[col].apply(lambda x: repr(x) if not pd.isna(x) else None)
    return df


def to_none(val):
    try:
        if math.isnan(val):
            return None
    except TypeError:
        return val
    return val


def render(
    df,
    to_file=None,
    title="Title",
    precision=2,
    num_html=[],
    startfile=True,
    templ_path=TEMPLATE_PATH,
    load_column_control=True,
    dropdown_select_threshold=9,
    display_logo=True,
):
    if isinstance(df, pd.Series):
        print("Converting Series do DataFrame...")
        df = df.to_frame(name="col").reset_index()
    assert isinstance(df, pd.DataFrame)
    assert isinstance(title, str)
    assert isinstance(load_column_control, bool)

    df.columns = df.columns.astype(str)
    if "MultiIndex" in repr(df.columns):  # experimental
        df.columns = ["_".join(str(x)) for x in df.columns]

    missing_cols = set(num_html).difference(df.columns)
    if missing_cols:
        raise AssertionError(f"column(s): {missing_cols} not found in dataframe")

    float_cols = df.select_dtypes(include=[np.float16, np.float32, np.float64])
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    df.loc[:, float_cols.columns] = np.round(float_cols, precision)

    try:
        # data_arrays = df.values.tolist()
        data_arrays = [list(map(to_none, row)) for row in df.values.tolist()]
        data_json = json.dumps(data_arrays, cls=DataJSONEncoder)

    except BaseException:
        print(" json error", sys.exc_info())
        df = fix_df_columns(df)
        data_arrays = df.values.tolist()
        data_json = json.dumps(data_arrays, cls=DataJSONEncoder)

    columns = []
    for i, col in enumerate(df.columns):
        try:
            nunique = df[col].nunique()
        except TypeError:
            # for nested rows unhashable types
            df[col] = df[col].map(repr)
            nunique = df[col].nunique()

        col_cleaned = col.replace("_", " ")

        if nunique < dropdown_select_threshold:
            col_def = {"title": col_cleaned, "orderable": True}
            if load_column_control:
                col_def["columnControl"] = ["order", ["title","searchList"]]

        else:
            col_def = {"title": col_cleaned, "searchable": True, "orderable": True}
            if load_column_control:
                col_def["columnControl"] = ["order", ["title","search"]]

        if col in num_html:
            col_def["render"] = "#render_num"
            col_def["type"] = "num-html"
        columns.append(col_def)
    columns_json = json.dumps(columns)
    if num_html:
        #  we need properly refer to javascript function defined in template
        # json must have string so get rid of the quotes
        columns_json = columns_json.replace('"#render_num"', "render_num")

    auto_width = True if len(df.index) < 100 or len(df.columns) > 10 else False

    template_vars = {
        "title": str(title),
        "auto_width": json.dumps(auto_width),
        "tab_data": data_json,
        "tab_columns": columns_json,
        "search_columns": json.dumps(list(str_cols)),
    }
    if not display_logo:
        template_vars["datatables_logo"] = ""
    if not load_column_control:
        template_vars["column_control"] = ""

    with open(templ_path, encoding="utf-8") as op_file:
        instr = op_file.read()
    html = c_render(instr, template_vars)
    if not to_file:
        return html
    assert templ_path != to_file and templ_path not in to_file
    assert ".html" in to_file
    with open(to_file, "w", encoding="utf8") as outfile:
        outfile.write(html)
    if startfile:
        open_file(to_file)
    return outfile


_render_str = partial(render, to_file=None)


def render_inline(df, **kwargs):
    if "to_file" in kwargs:
        print(
            f"! wrong argument:[to_file] {
                kwargs.pop('to_file')
            } is not allowed in render_inline"
        )
    html = _render_str(df, **kwargs)
    min_content = get_tag_content("min_content", html)
    return min_content


def get_sample_df():
    import datetime
    import random

    healthcare = ["Low priority", "Medium priority", "High priority", "Emergency"]
    product = ["Premium", "Standard", "Budget"]
    grades = ["A", "B", "C", "D", "F"]
    return pd.DataFrame(
        {
            "col_1a": [
                datetime.datetime.now(),
                "Lorem ipsum dolor sit amet, consectetur adipiscing",
                "<b>Integer</b> laoreet odio et.",
                np.nan,
                datetime.datetime,
                pd.NA,  # lambda x: 1 / x,
                ["C", {'a' : 1}],
            ],
            "col_2": [0.09, -0.591, 0.201, -0.487, -0.175, -0.797, -0.519],
            "C 3": [random.choice(grades) for x in range(7)],
            # "col3": [["ZZ","AA"], {'BB' : 1, 'BB' : 2}, "CC", "CC","CC", "ZZ", "ZZ"], #error rows
            "col4": [-0.333, 1, -9, 4, 2, 3, 1111.111],
            "col5": [-2000, -1, 2, 3, 4, 5, 70_000],
            "col6": [random.choice(product) for x in range(7)],
            "col7": ["1", "0", "1", "0", "1", "0", "0"],
            "col8": [-1, 1, 2, 1, 1, 0, 0],
            "col9": [random.choice(healthcare) for x in range(7)],
        }
    )


def render_sample_df(to_file="df_table.html"):
    df = get_sample_df()
    result = render(
        df,  # .reset_index(),
        to_file=to_file,
        title="Example dataframe",
        num_html=["col5", "col4", "col_2"],
        load_column_control=True,
        dropdown_select_threshold=5,
        display_logo=True,
    )
    return result


def main():
    print(render_sample_df(to_file="1test.html"))


if __name__ == "__main__":
    main()
