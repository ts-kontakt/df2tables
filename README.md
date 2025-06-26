# df2tables

`df2tables` is a Python utility for exporting `pandas.DataFrame` objects to fully interactive, sortable, and searchable HTML tables using [DataTables](https://datatables.net/). It generates standalone `.html` files that can be viewed directly in any modern web browser—without the need for Jupyter notebooks, servers, or JavaScript frameworks.

## Features

- Converts `pandas.DataFrame` to interactive standalone HTML table
- Works independently of Jupyter or any web server
-  Interactive sorting, filtering, and pagination via DataTables
- Fully customizable HTML template system using [comnt](https://github.com/ts-kontakt/comnt)
- Handles large datasets efficiently
- Color-coded formatting for numeric columns


## Requirements

- Python 3.7+
- pandas
- numpy

```python
import pandas as pd
from df2tables import to_html

df = pd.DataFrame({
    "Name": ["Alice", "Bob", "Carol"],
    "Score": [92.5, -78.3, 85.0],
    "Joined": pd.to_datetime(["2021-01-05", "2021-02-10", "2021-03-15"])
})

to_html(
    df,
    outfile="output.html",
    title="User Scores",
    precision=1,
    html_cols=["Score"],
    startfile=True
)

```
Function Reference
to_html

to_html(
    df: pd.DataFrame,
    outfile: str = "table.html",
    title: str = "Title",
    precision: int = 2,
    html_cols: Optional[List[str]] = None,
    startfile: bool = True,
    templ_path: Optional[str] = None,
    render_str: bool = False
) -> str

    outfile: Path to the output HTML file

    html_cols: List of numeric columns to render as color-coded HTML

    templ_path: Path to a custom HTML template (optional)

    render_str: If True, returns the HTML string instead of writing a file

sample_df

Renders a built-in example DataFrame for testing:

from df2tables import sample_df
html = sample_df()

## The default HTML template (datatable_templ.html) is fully functional and ready for use or customization. It includes:
- PureCSS (CDN) for layout and responsive styling
-  DataTables 2.3.2 (CDN) for table interactivity
- jQuery 3.7.1 (slim) (CDN)
- JavaScript-based enhancements for:
- Sorting HTML-formatted numbers (num-html)
-  Coloring negative values
-  Auto-detection of searchable columns
- Efficient rendering of large tables (pageLength=600)

## Template Syntax
Templates use comnt, a minimal markup system based on HTML comments. This allows placeholder substitution without breaking HTML structure. Example markers:
```
<!--[title-->
My Table Title
<!--title]-->

const data = /*[tab_data*/ [...] /*tab_data]*/;
```
You can easily copy and modify datatable_templ.html to apply your own structure, styling, or libraries. Simply pass the new template path to the templ_path argument in to_html().
Output Format

* Produces a self-contained HTML file with:
* Embedded table data and column definitions
* No external Python, JSON, or JavaScript needed at runtime
* Can be viewed offline in any browser
* Portable and easy to share or archive

## License

MIT License
© ts-kontakt
