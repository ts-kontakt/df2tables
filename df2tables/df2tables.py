#!/usr/bin/python
# coding=utf8
import json
import os
import subprocess
import sys
from functools import partial

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
            return repr(obj).replace("<", " ").replace(">", " ")


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


def render(
    df,
    title="Title",
    precision=2,
    num_html=[],
    to_file=None,
    startfile=True,
    templ_path=TEMPLATE_PATH,
    load_column_control=True,
    # the maximum number of unique values in a column that qualifies it as categorical
    # (and therefore eligible for a dropdown filter).
    dropdown_select_threshold=5,
):
    assert isinstance(df, pd.DataFrame)
    assert isinstance(title, str)
    assert isinstance(load_column_control, bool)

    if "MultiIndex" in repr(df.columns):  # experimental
        df.columns = ["_".join(x) for x in df.columns]

    missing_cols = set(num_html).difference(df.columns)
    if missing_cols:
        raise AssertionError(f"column(s): {missing_cols} not found in dataframe")

    float_cols = df.select_dtypes(include=[np.float16, np.float32, np.float64])
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    df.loc[:, float_cols.columns] = np.round(float_cols, precision)

    try:
        data_arrays = df.values.tolist()
        data_json = json.dumps(data_arrays, cls=DataJSONEncoder)
    except:
        print(" json error", sys.exc_info())
        df = fix_df_columns(df)
        data_arrays = df.values.tolist()
        data_json = json.dumps(data_arrays, cls=DataJSONEncoder)

    columns, select_cols = [], []
    for i, col in enumerate(df.columns):
        try:
            nunique = df[col].nunique()
        except TypeError:
            # for nested rows unhashable type ex: 'list'
            df[col] = df[col].apply(lambda x: repr(x))
            nunique = df[col].nunique()
        if nunique < dropdown_select_threshold:
            select_cols.append(i)  # columns when  dropdown select makes  sense
            col_def = {"title": col, "orderable": True}
        else:
            col_def = {"title": col, "searchable": True, "orderable": True}
        if col in num_html:
            col_def["render"] = "#render_num"
            col_def["type"] = "num-html"
        columns.append(col_def)
    column_control = [
        {
            "targets": select_cols,
            "columnControl": [["order", "searchList"]],
        },
        {
            "targets": list(set(range(len(df.columns))).difference(select_cols)),
            "columnControl": ["order", "searchDropdown"],
        },
    ]
    columns_json = json.dumps(columns)
    if num_html:
        #  we need properly refer to javascript function defined in template
        # json must have string so get rid of the quotes
        columns_json = columns_json.replace('"#render_num"', "render_num")

    auto_width = True if len(df.index) < 100 else False

    template_vars = {
        "title": str(title),
        "auto_width": json.dumps(auto_width),
        "tab_data": data_json,
        "tab_columns": columns_json,
        "search_columns": json.dumps(list(str_cols)),
        "select_cols": json.dumps(select_cols),
        "column_control": json.dumps(column_control),
        "load_column_control": json.dumps(load_column_control),
    }
    with open(templ_path, encoding="utf-8") as op_file:
        instr = op_file.read()
    html = c_render(instr, template_vars)
    if not to_file:
        return html
    assert templ_path != to_file and templ_path not in to_file
    with open(to_file, "w", encoding="utf8") as outfile:
        outfile.write(html)
    if startfile:
        open_file(to_file)
    return outfile


_render_str = partial(render, to_file=None)


def render_inline(df, **kwargs):
    if "to_file" in kwargs:
        print(
            f"wrong argument:[to_file] {kwargs.pop('to_file')} is not allowed in render_inline"
        )
        # del kwargs['to_file']
    html = _render_str(df, **kwargs)
    min_content = c_render(
        get_tag_content("min_content", html), {"render_inline": "true"}
    )
    return min_content


def get_sample_df():
    import datetime
    import random

    healthcare = ["Low priority", "Medium priority", "High priority", "Emergency"]
    product = ["Premium", "Standard", "Budget"]
    grades = ["A", "B", "C", "D", "F"]
    return pd.DataFrame(
        {
            "col1": [
                datetime.datetime.now(),
                "Lorem ipsum dolor sit amet, consectetur adipiscing",
                "<b>Integer</b> laoreet odio et.",
                np.nan,
                datetime.datetime,
                0,  # lambda x: 1 / x,
                "C",
            ],
            "col2": [0.09, -0.591, 0.201, -0.487, -0.175, -0.797, -0.519],
            "col3": [random.choice(grades) for x in range(7)],
            # "col3": [["ZZ","AA"], {'BB' : 1, 'BB' : 2}, "CC", "CC","CC", "ZZ", "ZZ"], #error rows
            "col4": [-0.333, 1, -9, 4, 2, 3, 1111.111],
            "col5": [-1000, 1, 2, 3, 4, 5, 70_000],
            "col6": [random.choice(product) for x in range(7)],
            "col7": ["1", "0", "1", "0", "1", "0", "0"],
            "col8": [-1, 1, 2, 1, 1, 0, 0],
            "col9": [random.choice(healthcare) for x in range(7)],
        }
    )


def render_sample_df(to_file="df_table.html"):
    df = get_sample_df()
    result = render(
        df,
        to_file=to_file,
        title="Example dataframe",
        num_html=["col5", "col4", "col2"],
        load_column_control=True,
        dropdown_select_threshold=5,
    )
    return result

def main():
    print(render_sample_df(to_file="1test.html"))

if __name__ == "__main__":
    main()




























