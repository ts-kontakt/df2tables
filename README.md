# df2tables: Pandas DataFrames to Interactive DataTables

`df2tables` is a Python utility for exporting `pandas.DataFrame` objects to interactive HTML tables using [DataTables](https://datatables.net/)—an excellent JavaScript library for table functionality. It generates standalone `.html` files viewable in any browser without Jupyter notebooks, servers, or frameworks.

Useful for data inspection, feature engineering workflows, and sharing results, especially with large datasets that need interactive exploration.

## Features

- Converts `pandas.DataFrame` to interactive standalone HTML tables
- Self-contained HTML files with embedded data—no external dependencies at runtime
- Works independently of Jupyter or web servers—viewable offline in any browser, portable and easy to share
- Color-coded formatting for numeric columns with customizable precision
- Easy customizable HTML (minimal template system using [comnt](https://github.com/ts-kontakt/comnt) included)
- **Useful for some training dataset inspection and feature engineering**: Quickly browse through large datasets, identify outliers, and data quality issues interactively


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
    templ_path: str = TEMPLATE_PATH
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

**Returns:**
- HTML string if `to_file=None`
- File object if `to_file` is specified

### sample_df

Generates and renders a built-in example DataFrame for testing:

```python
html_string = df2t.sample_df()
```

## Feature Engineering Example

```python
import pandas as pd
import df2tables as df2t

# Load your training dataset
df = pd.read_csv("training_data.csv")

# Quick inspection of the entire dataset
df2t.render(
    df, 
    title="Training Dataset Overview",
    to_file="dataset_overview.html"
)

# Focus on specific numeric features with color coding
numeric_features = ["feature1", "feature2", "target_variable"]
df2t.render(
    df[numeric_features + ["id", "category"]], 
    title="Key Numeric Features",
    precision=3,
    num_html=numeric_features,
    to_file="numeric_features.html"
)

# Inspect feature correlations or engineered features
feature_stats = df.describe().T
df2t.render(
    feature_stats,
    title="Feature Statistics",
    precision=4,
    num_html=["mean", "std", "min", "max"],
    to_file="feature_stats.html"
)
```

## Requirements

- Python 3.7+
- pandas
- numpy

## Installation

```bash
pip install df2tables
```

## License

MIT License  
© ts-kontakt

## Appendix: Template Customization

### Offline Usage
*Note: "Offline" viewing assumes internet connectivity for CDN resources (DataTables, jQuery, PureCSS). For truly offline usage, modify the template to reference local copies of these libraries instead of CDN links.*

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
- JavaScript enhancements for sorting HTML-formatted numbers and coloring negative values


While [comnt](https://github.com/ts-kontakt/comnt) is used to ensure that the HTML template just works independently, you can also use other templating systems like Jinja2 by rendering the final content after.

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

# Handle MultiIndex columns (experimental)
# MultiIndex columns are automatically flattened with underscore separation
```
