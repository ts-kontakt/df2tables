# df2tables - Pandas & Polars DataFrames to Interactive HTML Tables

[![PyPI version](https://img.shields.io/pypi/v/df2tables.svg)](https://pypi.org/project/df2tables/)

`df2tables` is a Python utility for exporting **Pandas** and **Polars** DataFrames into interactive HTML tables using [DataTables](https://datatables.net/) - a powerful JavaScript library.  
It’s built to embed seamlessly into Flask, Django, FastAPI, or any web framework.

By rendering tables directly from JavaScript arrays, this tool delivers **fast performance and compact file sizes**, enabling smooth browsing of large datasets while maintaining full responsiveness.

**Minimal dependencies**: only `pandas` ***or*** `polars` (you don’t need pandas installed if using polars).

Converting a DataFrame to an interactive table takes just one function call:

```python
render(df, **kwargs) 
# or for web frameworks:
render_inline(df, **kwargs)
```

## Features

- Converts `pandas` and `polars` dataframes interactive standalone HTML tables
- **Web Framework Ready**: Specifically designed for easy embedding in Flask, Django, FastAPI, and other web frameworks
- Browse **large datasets** using filters and sorting 
- Works **independently of Jupyter**  or live server (though [notebook](#rendering-in-notebook) rendering  is supported) 
- Useful for training dataset inspection and feature engineering: Quickly browse through large datasets, identify outliers, and data quality issues interactively
- **Customization**: [Configuring DataTables from Python](#customization-configuring-datatables-from-python) *(new)*

## Screenshots

![df2tables demo with 1,000,000 rows](https://github.com/ts-kontakt/df2tables/blob/main/df2tables-big.gif?raw=true)

A standalone HTML file containing a JavaScript array as data source for DataTables has several advantages. For example, you can browse quite large datasets locally.

The column control feature provides dropdown filters for categorical data and search functionality for text columns, enhancing data exploration capabilities through the excellent [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/).

*Note: By default, filtering is enabled for all non-numeric columns.*

## Quick Start

The simplest function call with default arguments is:

```python
df2tables.render(df, to_file='df.html')
```

## Installation

```bash
pip install df2tables
```

### Sample DataFrame

```python
#render sample DataFrame
html_string = df2t.render_sample_df(to_file="sample_table.html")
```
### Rendering in notebook
```python
from df2tables import  render_nb

render_nb(df) #show interactive table in jupyter notebook
```
*Note: Notebook rendering is currently supported in Jupyter,  VS Code notebooks and marimo*
## Main Functions

### render

```python
df2t.render(
    df: pd.DataFrame | pl.DataFrame,
    to_file: str = "datatable.html",
    title: str = "",
    startfile: bool = True,
    precision: int = 2,
    format_negatives: Union[bool, List[str], Tuple[str], Set[str]] = False,
    buttons: Optional[List[str]] = None,
    render_opts: Optional[dict] = None,
    js_opts: Optional[dict] = None,
    templ_path: str = TEMPLATE_PATH,
    **kwargs
) -> Union[str, None]
```

**Parameters:**

- `df`: Input pandas or polars DataFrame
- `to_file`: Output HTML file path (default: "datatable.html"). If `None`, returns HTML string instead of writing file
- `title`: Title for the HTML table (default: "")
- `startfile`: If `True`, automatically opens the generated HTML file in default browser (default: True)
- `precision`: Number of decimal places for floating-point numbers. Must be a non-negative integer (default: 2)
- `format_negatives`: Configure negative number formatting with color-coded HTML (negative values in red):
  - `False`: No special formatting (default)
  - `True`: Auto-detect and format all numeric columns containing negative values
  - `List/Tuple/Set[str]`: Format only specified column names (spaces in column names should be replaced with underscores)
- `buttons`: List of DataTables button types to add to the toolbar (e.g., `['copy', 'csv', 'excel', 'pdf']`). Requires DataTables Buttons extension (default: None)
- `render_opts`: Dictionary of additional rendering configuration options (see below for available options)
- `js_opts`: Dictionary of [DataTables configuration options](https://datatables.net/reference/option/) to customize table behavior (e.g., pagination, scrolling, layout, language) (default: None)
- `templ_path`: Path to custom HTML template (uses default if not specified)
- `**kwargs`: **Deprecated** - Passing `load_column_control` and `display_logo` directly is deprecated and will be removed in a future version. Use `render_opts` dictionary instead

**Available `render_opts` options:**

- `locale_fmt` (bool): Enable locale-based number formatting (default: False)
- `reorder` (bool): Enable column reordering functionality. Requires `load_column_control=True` (default: False)
- `dropdown_select_threshold` (int): Maximum unique values for dropdown filters. Columns with more unique values will use text input instead (default: 9)
- `table_id` (str): HTML ID for the table element (default: "pd_datatab")
- `unique_id` (bool): Generate unique UUID-based table ID for multiple tables on one page (default: False)
- `default_table_class` (str): CSS classes for table styling (default: "display compact hover order-column")
- `add_expand_btn` (bool): Add expand/collapse button for row details (default: True)
- `display_logo` (bool): Display DataTables logo (default: False)

**Returns:**

- File path (str) if `to_file` is specified and file is successfully written
- HTML string if `to_file=None`
- `None` on error (file write failure or invalid input)

**Raises:**

- `ValueError`: If `precision` is not a non-negative integer, DataFrame is empty/unsupported type, or DataFrame cannot be processed
- `UserWarning`: For unknown keyword arguments passed to the function


---

### render_inline

```python
df2t.render_inline(
    df: pd.DataFrame | pl.DataFrame,
    table_attrs: Dict = None,
    **kwargs
) -> str
```

**Parameters:**

This function is designed for integration with web applications and has the following characteristics:

- Returns only the `<table>` markup and the associated JavaScript
- Excludes `<html>`, `<head>`, and `<body>` tags
- Useful for pages with multiple tables, as you can assign unique IDs via the `table_attrs` dictionary (e.g., `{'id': 'my-unique-table'}`)
- **Important**: This function does not include jQuery or DataTables library dependencies. You must include them manually in your host HTML page for the table to function correctly

The **`table_attrs`** argument accepts a dictionary of HTML table attributes, such as an ID or CSS class. This is especially useful for multiple tables on a single page (each must have a different ID).

**Note:** Some arguments from `render()` are not applicable here, such as `title`, `display_logo`, or `startfile`, because the returned HTML contains only the table element and its initialization script.

**Example:**

See an example of multiple tables with different configuration options placed in separate tabs (jQuery UI Tabs): [flask_multiple_tables_tabs.py](https://github.com/ts-kontakt/df2tables/blob/main/flask_multiple_tables_tabs.py)

### Minimal Flask Example
Here's a complete, minimal **working** Flask application that demonstrates how to properly embed a DataTable with all required dependencies:

```python
import df2tables as df2t
from flask import Flask, render_template_string

app = Flask(__name__)

@app.route("/")
def home():
    # Generate sample data (or use your own DataFrame)
    df = df2t.get_sample_df()
    df_title = "DataFrame Rendered as DataTable inline in <strong>Flask</strong>"

    string_datatable = df2t.render_inline(df)

    # Embed in a complete HTML template with all required dependencies
    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
        <style>
        body {
            font-size: 0.875rem;line-height: 1.4;font-family: "Helvetica Neue",Arial,sans-serif;
            }
        </style>
            <title>Flask Data Dashboard</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.datatables.net/v/dt/jq-3.7.0/dt-2.3.4/b-3.2.5/b-colvis-3.2.5/b-html5-3.2.5/cr-2.1.2/cc-1.1.1/datatables.min.css" rel="stylesheet" integrity="sha384-wSlKDmHlZXDO0o5ZHsloB4i8j/JsaA8Jx0uiAW7ECdNdWBoJZXeLnYbh7yCB09Os" crossorigin="anonymous">
        <script src="https://cdn.datatables.net/v/dt/jq-3.7.0/dt-2.3.4/b-3.2.5/b-colvis-3.2.5/b-html5-3.2.5/cr-2.1.2/cc-1.1.1/datatables.min.js" integrity="sha384-Db6ik1fBYSPYBHoWXu+DJTvPGs+KGoiEMJC36Hp2uJfaHwUWOCZvWxaCnc/4rEBs" crossorigin="anonymous"></script>
        </head>
        <body style="background-color: #f4f4f4;">
            <div style="background-color: #fff; padding: 20px; margin: 20px;">
                <h1>My Flask Data Dashboard</h1>
                {{ inline_datatable | safe }}
            </div>
        </body>
        </html>
        """,
        inline_datatable=string_datatable,
    )

if __name__ == "__main__":
    app.run(debug=True)
```
*Note: Pandas DataFrame indexes are not rendered by default. If you want to enable indexes in an HTML table, simply call `df2tables.render(df.reset_index(), args...)`*

## Customization: Configuring DataTables from Python

You can now customize DataTables behavior directly from Python by passing configuration options through the new `js_opts` parameter. This allows you to control [DataTables options](https://datatables.net/reference/option/) and [features](https://datatables.net/reference/feature/) without modifying the HTML template. 

### Basic Usage

Simply pass a dictionary of DataTables options to the `js_opts` parameter in the `render` or `render_inline` function.

### Examples


#### 1.  Customize Layout and Language

Rearrange control elements (such as the search bar and info display) using the `layout` option, or localize text:
```python
custom_cfg = {
    "language": {
        "searchPlaceholder": "Search in all text columns"
    },
    "pageLength": 25, # number of table rows showing
    "layout": {
        "topStart": "info",
        "top1Start": "pageLength",
        "topEnd": "search", 
        "bottomEnd": "paging"
    }
}
df2t.render(df, js_opts=custom_cfg, to_file="localized_table.html")

```
#### 2. Replace Paging with Scrolling

Disable pagination and enable vertical and horizontal scrolling for easier navigation of large datasets.

_Note_: Using `scrollY` with disabled `paging` can be slow for large DataFrames.
```python
scroll_cfg = {
    "paging": False, # slow for large tables
    "scrollCollapse": False,
    "scrollY": '50vh',  
    "scrollX": "70vw"
}
df2t.render(df, js_opts=scroll_cfg, to_file="scrolling_table.html")
```

### Error Handling

Invalid keys are ignored by DataTables, so malformed or non-existent options **usually** will not break table rendering.

**Note**: While invalid keys should be ignored, using a valid key with an incorrect *value type* may still cause an error in the browser's JavaScript console.

### Available Configuration Options

**Important Notes**

Some configuration options require additional DataTables extensions or plugins (e.g., Buttons, FixedHeader). At this time, such plugin-dependent options are not yet supported.

For best results, start with core features such as `layout` or `language` options before exploring more advanced configurations.

For a complete list of available settings, refer to the official DataTables documentation and:
https://datatables.net/examples/

It’s best to start with the core DataTables Features before adding advanced configurations.

  * [Feature Reference](https://datatables.net/reference/feature/)
  * [Configuration Options Reference](https://datatables.net/reference/option/)
  * [Layout Configuration](https://datatables.net/reference/option/layout)
  * [Language configuration ](https://datatables.net/reference/option/language)


### Column Name Formatting

For better readability in table headers, `df2tables` automatically converts underscores to spaces in column names. This improves word wrapping and prevents excessively wide columns.

To disable this automatic word wrapping behavior, add the following CSS to your custom template:

```css
span.dt-column-title { 
    white-space: nowrap; 
}
```

### Bulk Dataset Processing

For exploratory data analysis across multiple datasets, you can generate tables programmatically. 
The example below uses the [vega_datasets](https://github.com/altair-viz/vega_datasets) package, which provides easy access to a variety of sample datasets commonly used in data visualization and analysis.

*Note: Install vega_datasets with `pip install vega_datasets` to run this example.*

[Quick Browse First 10 Vega Datasets](https://github.com/ts-kontakt/df2tables/blob/main/bulk_dataset_processing.py)



### Error Handling

The module includes error handling for:

- **JSON serialization**: Custom encoder handles complex pandas or Python data types
- **Column compatibility**: Automatically converts problematic column types to string representation

### Offline Usage
*Note: "Offline" viewing assumes internet connectivity for CDN resources (DataTables, jQuery, PureCSS, [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/)). For truly offline usage, modify the template to reference local copies of these libraries instead of CDN links.*

## Appendix: Template Customization

Templates use [comnt](https://github.com/ts-kontakt/comnt), a minimal markup system based on HTML/JS comments.

### Custom Templates

Copy and modify `datatable_templ.html` to apply custom styling or libraries, then pass the new template path to `templ_path`.

### Handle Pandas MultiIndex Columns (Experimental)

MultiIndex columns are automatically flattened with underscore separation.

## License

MIT License  
© Tomasz Sługocki
