# df2tables

[![PyPI version](https://img.shields.io/pypi/v/df2tables.svg)](https://pypi.org/project/df2tables/)

`df2tables` is a Python utility for exporting `pandas.DataFrame` objects to interactive HTML tables using [DataTables](https://datatables.net/)—an excellent JavaScript library for table functionality.

The table is rendered from a JavaScript array, resulting in smaller file sizes and allowing for viewing quite large datasets while maintaining responsiveness.

## Features

- Converts `pandas.DataFrame` to interactive standalone HTML tables
- Browse **large datasets** using filters and sorting
- No need to export to Excel—explore and filter your data directly in the browser, which is faster and more convenient
- Works independently of Jupyter or web servers—viewable offline in any browser, portable and easy to share
- **Useful for training dataset inspection and feature engineering**: Quickly browse through large datasets, identify outliers, and data quality issues interactively
- **Minimal HTML snippet generation**: Generate embeddable HTML content for Flask or other web frameworks
- **Smart column detection**: Automatically identifies categorical columns (≤9 unique values by default) for dropdown filtering

## Screenshots

![df2tables demo with 1,000,000 rows](https://github.com/ts-kontakt/df2tables/blob/main/df2tables-big.gif?raw=true)

A standalone HTML file containing a JavaScript array as data source for DataTables has several advantages. For example, you can browse quite large datasets locally (something you don't usually do on a server).

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
import df2tables as df2t
# Get sample DataFrame for testing
sample_df = df2t.get_sample_df()

# Generate and render sample DataFrame
df2t.render_sample_df(to_file="sample_table.html")
```
*Note: DataFrame indexes are not rendered by default. If you want to enable indexes in an HTML table, simply call `df2tables.render(df.reset_index(), args...)`*

## Main Functions

### render

```python
df2t.render(
    df: pd.DataFrame,
    to_file: Optional[str] = None,
    title: str = "Title",
    precision: int = 2,
    num_html: List[str] = [],
    startfile: bool = True,
    templ_path: str = TEMPLATE_PATH,
    load_column_control: bool = True,
    display_logo: bool = True
) -> Union[str, file_object]
```

**Parameters:**

- `df`: Input pandas DataFrame
- `to_file`: Output HTML file path. If None, returns HTML string instead of writing file
- `title`: Title for the HTML table
- `precision`: Number of decimal places for floating-point numbers
- `num_html`: List of numeric column names to render with color-coded HTML formatting (negative values in red)
- `startfile`: If True, automatically opens the generated HTML file in default browser
- `templ_path`: Path to custom HTML template (uses default if not specified)
- `load_column_control`: If True, integrates the [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/) programmatically for enhanced filtering and search capabilities (default: True)
- `dropdown_select_threshold`: Maximum number of unique values in a column to qualify for dropdown filtering (default: 9)
- `display_logo`: If True, displays DataTables logo (default: True)

**Returns:**

- HTML string if `to_file=None`
- File object if `to_file` is specified

### render_inline

```python
df2t.render_inline(
    df: pd.DataFrame, 
    table_attrs: Dict,
    **kwargs
) -> str
```

**Parameters:**

This function is designed for integration with web applications and has the following characteristics:

- Returns only the `<table>` markup and the associated JavaScript
- Excludes `<html>`, `<head>`, and `<body>` tags
- Useful for pages with multiple tables, as you can assign unique IDs via the `table_attrs` dictionary (e.g., `{'id': 'my-unique-table'}`)
- **Important**: This function does not include jQuery or DataTables library dependencies. You must include them manually in your host HTML page for the table to function correctly

Some key arguments are not applicable, such as `title` or `display_logo`, because the returned HTML contains only the table and JavaScript.

The **new** additional **`table_attrs`** argument accepts a dictionary of HTML table attributes, such as an ID or CSS class. This is especially useful for multiple tables on a single page (each must have a different ID).

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
    # For larger datasets, you might use:
    # df = generate_large_dataframe(10000)  # Your data source
    
    df_title = "DataFrame Rendered as DataTable inline in <strong>Flask</strong>"
    
    # Generate the embeddable DataTable HTML
    string_datatable = df2t.render_inline(
        df,
        title=df_title)
    
    # Embed in a complete HTML template with all required dependencies
    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Flask Data Dashboard</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            
            <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
            <link href="https://cdn.datatables.net/2.3.4/css/dataTables.dataTables.min.css" rel="stylesheet">
            <script src="https://cdn.datatables.net/2.3.4/js/dataTables.min.js"></script><!--[column_control-->
            <link href="https://cdn.datatables.net/columncontrol/1.1.0/css/columnControl.dataTables.min.css" rel="stylesheet">
            <script src="https://cdn.datatables.net/columncontrol/1.1.0/js/dataTables.columnControl.min.js"></script><!--column_control]-->

            <!-- Optional: PureCSS for styling -->
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/purecss@3.0.0/build/pure-min.css">
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


### Column Name Formatting

For better readability in table headers, `df2tables` automatically converts underscores to spaces in column names. This improves word wrapping and prevents excessively wide columns.

To disable this automatic word wrapping behavior, add the following CSS to your custom template:

```css
span.dt-column-title { 
    white-space: nowrap; 
}
```

## Fast Dataset Browsing

One of the key strengths of `df2tables` is its ability to quickly generate interactive HTML tables for rapid dataset exploration. The combination of standalone HTML files and the [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/) makes it exceptionally fast to browse through multiple datasets.

### Bulk Dataset Processing

For exploratory data analysis across multiple datasets, you can generate tables programmatically. The example below uses the [vega_datasets](https://github.com/altair-viz/vega_datasets) package, which provides easy access to a variety of sample datasets commonly used in data visualization and analysis.

*Note: Install vega_datasets with `pip install vega_datasets` to run this example.*

### Quick Browse First 10 Vega Datasets

```python
import df2tables as df2t
from vega_datasets import data

# WARNING: This will open many browser tabs! Use with caution.
# Consider setting startfile=False for bulk processing.

for dataset_name in sorted(dir(data))[:10]:
    dataset_func = getattr(data, dataset_name)
    try:
        df = dataset_func()
        print(f"{dataset_name}: {len(df.index)} rows")
        
        # df2tables can handle datasets above 100k rows, but we limit to smaller datasets 
        # for this demo to avoid generating too many large files
        if len(df.index) < 100_000:
            df2t.render(
                df, 
                title=f'Dataset: {dataset_name}',
                to_file=f'{dataset_name}.html',
                startfile=True  
            )
    except Exception as e:
        print(f'Error processing {dataset_name}: {e}')
```

**⚠️ Important Note**: When `startfile=True` (default), each generated HTML file opens automatically in your default browser. For bulk processing, set `startfile=False` to avoid opening dozens of browser tabs simultaneously.

### DataTables Column Control Extension Integration

The `load_column_control` parameter enables smart integration with the [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/), bringing professional-grade filtering capabilities to your data tables:

- **Categorical columns** (≤ `dropdown_select_threshold` unique values): Get elegant dropdown select filters (`searchList`) for intuitive data filtering
- **Text/numeric columns**: Benefit from sophisticated search functionality (`searchDropdown`) and ordering controls
- **Intelligent detection**: The module automatically identifies column types and applies the most appropriate Column Control features

```python
# Disable Column Control for simpler tables
df2t.render(df, load_column_control=False, to_file="simple_table.html")

# Customize dropdown threshold
df2t.render(df, dropdown_select_threshold=10, to_file="custom_table.html")
```

## Requirements

- Python 3.7+
- pandas

### Error Handling

The module includes error handling for:

- **JSON serialization**: Custom encoder handles complex pandas or Python data types
- **Column compatibility**: Automatically converts problematic column types to string representation
- **Missing columns**: Validates `num_html` column names against DataFrame columns

## TODO / Future Enhancements

### DataTables Configuration Expansion

Currently, `df2tables` uses a predefined set of DataTables configuration options. Future versions could expose more DataTables initialization parameters directly from Python.

## License

MIT License  
© Tomasz Sługocki

## Appendix: Template Customization

### Offline Usage

*Note: "Offline" viewing assumes internet connectivity for CDN resources (DataTables, jQuery, PureCSS, [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/)). For truly offline usage, modify the template to reference local copies of these libraries instead of CDN links.*

Templates use [comnt](https://github.com/ts-kontakt/comnt), a minimal markup system based on HTML/JS comments.

One practical benefit: you can inject actual JavaScript-ready values from Python—not just strings:

```html
<!--[title-->
My Table Title
<!--title]-->

const data = /*[tab_data*/ [...] /*tab_data]*/;
```

While [comnt](https://github.com/ts-kontakt/comnt) is used to ensure that the HTML template works independently (and avoid `JSON.parse`), you can also use other templating systems like Jinja2 by rendering the final content afterward.

### Custom Templates

Copy and modify `datatable_templ.html` to apply custom styling or libraries, then pass the new template path to `templ_path`.

### Handle MultiIndex Columns (Experimental)

MultiIndex columns are automatically flattened with underscore separation.

## License

MIT License  
© Tomasz Sługocki
