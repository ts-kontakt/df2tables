# df2tables: Pandas DataFrames to Interactive DataTables

`df2tables` is a Python utility for exporting `pandas.DataFrame` objects to interactive HTML tables using [DataTables](https://datatables.net/)—an excellent JavaScript library for table functionality. It generates standalone `.html` files viewable in any browser without Jupyter notebooks, servers, or frameworks.

Useful for data inspection, feature engineering workflows, especially with large datasets that need interactive exploration.

## Features

- Converts `pandas.DataFrame` to interactive standalone HTML tables
- You can browse **quite large data sets** using filters and sorting
- **DataTables Column Control integration**: Smartly leverages the powerful [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/) for automatic dropdown filters and advanced search functionality, loaded programmatically via JavaScript
- Self-contained HTML files with embedded data—no external dependencies at runtime
- Works independently of Jupyter or web servers—viewable offline in any browser, portable and easy to share
- Color-coded formatting for numeric columns
- **Useful for some training dataset inspection and feature engineering**: Quickly browse through large datasets, identify outliers, and data quality issues interactively
- Easy customizable HTML 
- **Smart column detection**: Automatically identifies categorical columns (≤4 unique values) for dropdown filtering

## Screenshots
A standalone html file containing a js array as data source for datatables has several advantages, e.g. you can browse quite large datasets locally (something you don't usually do on a server). 
The column control feature provides dropdown filters for categorical data and search functionality for text columns, enhancing data exploration capabilities through the excellent [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/).
(By default, filtering is enabled for all non-numeric columns)
Below is an example of 100k rows with additional html rendering.

<p align="left">
<img src="https://github.com/ts-kontakt/df2tables/blob/main/df2tables-big.gif"   width="650" style="max-width: 100%;max-height: 100%;">
</p>

## Installation

```bash
pip install df2tables
```

## Quick Start

```python
import pandas as pd
import df2tables as df2t

df = pd.DataFrame({
    "Name": ["Alice", "Bob", "Carol"],
    "Score": [92.5, -78.3, 85.0],
    "Joined": pd.to_datetime(["2021-01-05", "2021-02-10", "2021-03-15"])
})

# Basic usage with color-coded numeric columns
df2t.render(
    df,
    title="User Scores",
    precision=1,
    num_html=["Score"],
    to_file="output.html",
    startfile=True
)
```

## Main Function

### render

```python
df2t.render(
    df: pd.DataFrame,
    title: str = "Title",
    precision: int = 2,
    num_html: List[str] = [],
    to_file: Optional[str] = None,
    startfile: bool = True,
    templ_path: str = TEMPLATE_PATH,
    load_column_control: bool = True
) -> Union[str, file_object]
```

**Parameters:**
- `df`: Input pandas DataFrame
- `title`: Title for the HTML table
- `precision`: Number of decimal places for floating-point numbers
- `num_html`: List of numeric column names to render with color-coded HTML formatting (negative values in red)
- `to_file`: Output HTML file path. If None, returns HTML string instead of writing file
- `startfile`: If True, automatically opens the generated HTML file in default browser
- `templ_path`: Path to custom HTML template (uses default if not specified)
- `load_column_control`: If True, smartly integrates the exceptional [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/) programmatically for enhanced filtering and search capabilities (default: True)

**Returns:**
- HTML string if `to_file=None`
- File object if `to_file` is specified

### DataTables Column Control Extension Integration

The `load_column_control` parameter enables smart integration with the remarkable [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/), bringing professional-grade filtering capabilities to your data tables:

- **Categorical columns** (≤4 unique values): Get elegant dropdown select filters for intuitive data filtering
- **Text/numeric columns**: Benefit from sophisticated search dropdown functionality and ordering controls
- **Intelligent detection**: The module automatically identifies column types and applies the most appropriate Column Control features
- **Seamless loading**: The outstanding [Column Control extension](https://datatables.net/extensions/columncontrol/) is loaded dynamically via JavaScript, ensuring optimal performance and compatibility

```python
# Enable smart integration with DataTables Column Control extension (default)
df2t.render(df, load_column_control=True, to_file="enhanced_table.html")

# Disable Column Control for simpler tables
df2t.render(df, load_column_control=False, to_file="simple_table.html")
```

### sample_df

Generates and renders a built-in example DataFrame for testing:

```python
html_string = df2t.sample_df()
```

## Fast Dataset Browsing

One of the key strengths of `df2tables` is its ability to quickly generate interactive HTML tables for rapid dataset exploration. The combination of standalone HTML files and the [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/) makes it exceptionally fast to browse through multiple datasets.

### Bulk Dataset Processing

For exploratory data analysis across multiple datasets, you can generate tables programmatically. The example below uses the [vega_datasets](https://github.com/altair-viz/vega_datasets) package, which provides easy access to a variety of sample datasets commonly used in data visualization and analysis.

**Note**: Install vega_datasets with `pip install vega_datasets` to run this example.

```python
import df2tables as df2t
from vega_datasets import data

# WARNING: This will open many browser tabs! Use with caution.
# Consider setting startfile=False for bulk processing.

for dataset_name in sorted(dir(data)):
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
                startfile=False  # Prevent opening all files automatically
            )
    except Exception as e:
        print(f'Error processing {dataset_name}: {e}')

print("Generated HTML files. Open them manually to browse datasets.")
```

**⚠️ Important Note**: When `startfile=True` (default), each generated HTML file opens automatically in your default browser. For bulk processing, set `startfile=False` to avoid opening dozens of browser tabs simultaneously.

### Benefits for Fast Browsing

- **Instant loading**: HTML files with embedded data load immediately without server dependencies
- **Interactive filtering**: The [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/) enables quick data exploration
- **Offline browsing**: Generated files work completely offline
- **Portable**: Share HTML files easily with colleagues for collaborative data exploration
- **No memory constraints**: Unlike Jupyter notebooks, these files don't consume Python memory after generation



- Python 3.7+
- pandas
- numpy

## Technical Details

### DataTables Column Control Extension Integration

The module smartly integrates with the exceptional [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/) for optimal user experience:

- **Select columns**: Columns with ≤4 unique values get sophisticated dropdown filters (`searchList`) via Column Control
- **Search columns**: Other columns benefit from Column Control's advanced search functionality and ordering controls
- **Dynamic loading**: The [Column Control extension](https://datatables.net/extensions/columncontrol/) JavaScript libraries are loaded programmatically to maintain clean templates
- **Robust fallback**: If the Column Control extension cannot be loaded, tables gracefully fall back to standard DataTables functionality

## TODO

- Support rendering a minimal HTML snippet (instead of full document) suitable for inclusion in Flask or Jinja2 templates:
  - The resulting string would only contain the table markup and JS data bindings.
  - All external dependencies (jQuery, DataTables, ColumnControl, styles) would be loaded dynamically via JavaScript, as is already supported by `load_column_control=True`.
  - Ideal for embedding data previews or interactive tables directly into existing web apps.



### Error Handling

The module includes robust error handling for:
- **JSON serialization**: Custom encoder handles complex pandas data types
- **Column compatibility**: Automatically converts problematic column types to string representation
- **Missing columns**: Validates `num_html` column names against DataFrame columns
- **Script loading**: Graceful fallback if the [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/) cannot be loaded

## License

MIT License  
© Tomasz Sługocki

## Appendix: Template Customization

### Offline Usage
*Note: "Offline" viewing assumes internet connectivity for CDN resources (DataTables, jQuery, PureCSS, [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/)). For truly offline usage, modify the template to reference local copies of these libraries instead of CDN links.*

Templates use [comnt](https://github.com/ts-kontakt/comnt), a minimal markup system based on HTML/JS comments.

```html
<!--[title-->
My Table Title
<!--title]-->

const data = /*[tab_data*/ [...] /*tab_data]*/;
```
The default HTML template includes:
- **PureCSS** (CDN) for responsive styling
- **DataTables 2.3.2** (CDN) for table interactivity
- **jQuery 3.7.1** (CDN)
- **[DataTables Column Control Extension](https://datatables.net/extensions/columncontrol/)** (CDN) - the outstanding Column Control extension loaded programmatically when enabled
- JavaScript enhancements for sorting HTML-formatted numbers and coloring negative values

### DataTables Column Control Extension CDN Resources

When `load_column_control=True`, the following resources from the excellent [DataTables Column Control extension](https://datatables.net/extensions/columncontrol/) are loaded dynamically:

```javascript
// JavaScript libraries loaded programmatically
const columncontrol_js = [
    "https://cdn.datatables.net/columncontrol/1.0.6/js/dataTables.columnControl.js",
    "https://cdn.datatables.net/columncontrol/1.0.6/js/columnControl.dataTables.js"
];

// CSS loaded after JavaScript initialization
const columncontrol_css = 
    "https://cdn.datatables.net/columncontrol/1.0.6/css/columnControl.dataTables.css";
```

While [comnt](https://github.com/ts-kontakt/comnt) is used to ensure that the HTML template just works independently (and avoid Json.parse), you can also use other templating systems like Jinja2 by rendering the final content after.

### Custom Templates

Copy and modify `datatable_templ.html` to apply custom styling or libraries, then pass the new template path to `templ_path`.

### Customization

```python
# Return HTML string for further processing
html_content = df2t.render(df, to_file=None)

# Use custom template
df2t.render(
    df,
    to_file="custom_output.html",
    templ_path="my_custom_template.html"
)

# Disable DataTables Column Control extension for custom implementations
df2t.render(
    df,
    to_file="basic_table.html",
    load_column_control=False
)

# Handle MultiIndex columns (experimental)
# MultiIndex columns are automatically flattened with underscore separation
```