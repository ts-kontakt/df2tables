#!/usr/bin/python
# coding=utf8
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

TEMPLATE_FILE = "datatable_templ.html"
try:
    # python 3.9+
    from importlib import resources
    TEMPLATE_PATH = str(resources.files("df2tables").joinpath(TEMPLATE_FILE))
except ImportError:
    print('error')
    TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), TEMPLATE_FILE)

try:
    from .comnt import render, write_from_template
except ImportError:
    from comnt import render, write_from_template

__all__ = ["TEMPLATE_PATH", "sample_df", "to_html"]


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
            elif "date" in obj_type:
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


def to_html(df,
            outfile,
            title="Title",
            precision=2,
            html_cols=[],
            startfile=True,
            templ_path=TEMPLATE_PATH,
            render_str=False):
    if "MultiIndex" in repr(df.columns):  # experimental
        df.columns = ["_".join(x) for x in df.columns]

    assert isinstance(df, pd.DataFrame)

    missing_cols = set(html_cols).difference(df.columns)
    if missing_cols:
        raise AssertionError(f"column(s): {missing_cols} not found in dataframe")

    for col in df.columns:
        try:
            test_val = df[col].dropna().iloc[0] if not df[col].isna().all() else None
            json.dumps(test_val, cls=DataJSONEncoder)
        except BaseException:
            print(f"! column error: {col}", sys.exc_info())
            df[col] = df[col].apply(lambda x: repr(x) if not pd.isna(x) else None)

    float_cols = df.select_dtypes(include=[np.float16, np.float32, np.float64])

    df.loc[:, float_cols.columns] = np.round(float_cols, precision)
    data_arrays = df.values.tolist()
    data_json = json.dumps(data_arrays, cls=DataJSONEncoder)

    # Get string column indices
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    str_col_indices = [list(df.columns).index(col) for col in str_cols]

    # Get column names and create column definitions for DataTable
    columns = []
    for i, col in enumerate(df.columns):
        is_text = i in str_col_indices
        col_def = {"title": col, "searchable": is_text}
        if col in html_cols:
            col_def["render"] = "#render_num"
            col_def["type"] = "num-html"
        columns.append(col_def)

    columns_json = json.dumps(columns)
    if html_cols:
        #  we need properly refer to javascript function - json can have string so get rid of the quotes
        columns_json = columns_json.replace('"#render_num"', "render_num")

    search_cols_json = json.dumps(list(str_cols))

    template_vars = {
        "title": title,
        "tab_data": data_json,
        "tab_columns": columns_json,
        "search_columns": search_cols_json,
    }
    if render_str:
        with open(templ_path, encoding="utf-8") as op_file:
            instr = op_file.read()
            return render(instr, template_vars)
    else:
        write_from_template(templ_path, outfile, template_vars)
        if startfile:
            open_file(outfile)
        return outfile


def sample_df():
    import datetime

    df = pd.DataFrame({
        "col1": [
            datetime.datetime.now(),
            "Lorem ipsum dolor sit amet, consectetur adipiscing",
            "<b>Integer</b> laoreet odio et.",
            np.nan,
            datetime.datetime,
            lambda x: 1 / x,
            "C",
        ],
        "col2": [0.09, -0.591, 0.201, -0.487, -0.175, -0.797, -0.519],
        "col3": [2.11, 1, 9, 8, 7, 4, True],
        "col4": [-0.333, 1, -9, 4, 2, 3, 1111.111],
        "col5": [-1000, 1, 2, 3, 4, 5, 70_000],
        "col6": ["a", "B", "c", "D", "e", "F", "X   "],
    })

    outfile = "df_table.html"
    result = to_html(df,
                     outfile=outfile,
                     title="Example dataframe",
                     html_cols=["col5", "col4", "col2"],
                     render_str=True)
    return result


if __name__ == "__main__":
    print(sample_df())
