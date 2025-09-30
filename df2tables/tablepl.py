import polars as pl
from polars.selectors import numeric

RENDER_NUM_FUNC = "#render_num"


def _prepare_dataframe_pl(df, precision):
    """
    Prepares a Polars df for rendering. Handles Series,
    data type conversions, and complex types without modifying the original
    df.
    """
    if isinstance(df, pl.Series):
        df = df.to_frame(name=df.name or "value")

    df_copy = df.clone()
    df_copy = df_copy.with_columns(
        numeric().round(precision),
        pl.col(pl.List, pl.Struct, pl.Object).map_elements(
            # escape does not allow html rendering
            str,
            return_dtype=pl.String,
            # lambda x : escape(repr(x)), return_dtype=pl.String
        ),
    )
    return df_copy


def _generate_column_defs_pl(
    df, num_html_cols=None, load_column_control=True, dropdown_select_threshold=9
):
    """
    Generates the column definitions list for DataTables from a Polars
    df.
    """
    if num_html_cols is None:
        num_html_cols = []

    columns = []
    for col_name in df.columns:
        try:
            n_unique = df[col_name].n_unique()
        except Exception:
            print("! unique error", df[col_name])
            n_unique = dropdown_select_threshold

        col_cleaned = col_name.replace("_", " ")

        if n_unique < dropdown_select_threshold:
            col_def = {"title": col_cleaned}
            if load_column_control:
                col_def["columnControl"] = ["order", ["title", "searchList"]]
        else:
            col_def = {"title": col_cleaned, "searchable": True}
            if load_column_control:
                col_def["columnControl"] = ["order", ["title", "search"]]

        col_def["orderable"] = True

        if col_name in num_html_cols:
            col_def["render"] = RENDER_NUM_FUNC
            col_def["type"] = "num-html"

        columns.append(col_def)

    return columns


def _get_data_arrays(df):
    return [list(row) for row in df.rows()]


def _get_search_cols(df):
    str_cols = df.select(pl.col(pl.Utf8, pl.Categorical)).columns
    return list(str_cols)


def process_pl(
    df,
    precision=2,
    num_html_cols=None,
    load_column_control=True,
    dropdown_select_threshold=9,
):
    df_prepared = _prepare_dataframe_pl(df, precision)
    data_arrays = _get_data_arrays(df_prepared)
    columns_defs = _generate_column_defs_pl(
        df_prepared, num_html_cols, load_column_control, dropdown_select_threshold
    )
    search_columns = _get_search_cols(df_prepared)
    return data_arrays, columns_defs, search_columns


if __name__ == "__main__":
    pass
