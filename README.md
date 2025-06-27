# df2tables: Pandas DataFrames to Interactive DataTables

`df2tables` is a Python utility for exporting `pandas.DataFrame` objects to interactive HTML tables using [DataTables](https://datatables.net/)—an excellent JavaScript library for table functionality. It generates standalone `.html` files viewable in any browser without Jupyter notebooks, servers, or frameworks.

Perfect for data inspection and sharing results, even with large datasets.

## Features

- Converts `pandas.DataFrame` to interactive standalone HTML tables
- Interactive sorting, filtering, and pagination via DataTables
- Self-contained HTML files with embedded data—no external dependencies at runtime
- Works independently of Jupyter or web servers—viewable offline in any browser, portable and easy to share
- Handles large datasets efficiently
- Color-coded formatting for numeric columns
- Easy customizable HTML (minimal template system using [comnt](https://github.com/ts-kontakt/comnt) included)

## Quick Start

```python
import pandas as pd
import df2tables as df2t

df = pd.DataFrame({
    "Name": ["Alice", "Bob", "Carol"],
    "Score": [92.5, -78.3, 85.0],
    "Joined": pd.to_datetime(["2021-01-05", "2021-02-10", "2021-03-15"])
})

df2t.to_html(
    df,
    outfile="output.html",
    title="User Scores",
    precision=1,
    html_cols=["Score"],
    startfile=True
)
```

## Basic Function

### to_html

```python
df2t.to_html(
    df: pd.DataFrame,
    outfile: str = "table.html",
    title: str = "Title",
    precision: int = 2,
    html_cols: Optional[List[str]] = None,
    startfile: bool = True,
    templ_path: Optional[str] = None,
    render_str: bool = False
) -> str
```

- `outfile`: Path to the output HTML file
- `html_cols`: List of numeric columns to render as color-coded HTML
- `templ_path`: Path to a custom HTML template (optional)
- `render_str`: If True, returns the HTML string instead of writing a file

### sample_df

Renders a built-in example DataFrame:

```python
html = df2t.sample_df()
```

## Default Template Features

The default HTML template includes:
- PureCSS (CDN) for responsive styling
- DataTables 2.3.2 (CDN) for table interactivity
- jQuery 3.7.1 (slim) (CDN)
- JavaScript enhancements for sorting HTML-formatted numbers and coloring negative values
- Efficient rendering of large tables (easily 100k + rows)

## Requirements

- Python 3.7+
- pandas
- numpy

## License

MIT License  
© ts-kontakt

## Appendix: Template Customization

Offline Usage
*Note: "Offline" viewing assumes internet connectivity for CDN resources (DataTables, jQuery, PureCSS). For truly offline usage, modify the template to reference local copies of these libraries instead of CDN links.

Templates use [comnt](https://github.com/ts-kontakt/comnt), a minimal markup system based on HTML/js comments.

```html
<!--[title-->
My Table Title
<!--title]-->

const data = /*[tab_data*/ [...] /*tab_data]*/;
```
While comnt is used to ensure that the html template works independently, it is still possible to place other types of templates, e.g. nijna, and render the final content

Copy and modify `datatable_templ.html` to apply custom styling or libraries, then pass the new template path to `templ_path`.
