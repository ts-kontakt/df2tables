import uuid
import pandas as pd
import df2tables as df2t
from flask import Flask, render_template_string
from numpy.random import default_rng

app = Flask(__name__)

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flask DataTables Demo</title>
    <link href="https://cdn.datatables.net/v/dt/jq-3.7.0/dt-2.3.4/b-3.2.5/b-colvis-3.2.5/b-html5-3.2.5/cr-2.1.2/cc-1.1.1/datatables.min.css" rel="stylesheet" integrity="sha384-wSlKDmHlZXDO0o5ZHsloB4i8j/JsaA8Jx0uiAW7ECdNdWBoJZXeLnYbh7yCB09Os" crossorigin="anonymous">
    <script src="https://cdn.datatables.net/v/dt/jq-3.7.0/dt-2.3.4/b-3.2.5/b-colvis-3.2.5/b-html5-3.2.5/cr-2.1.2/cc-1.1.1/datatables.min.js" integrity="sha384-Db6ik1fBYSPYBHoWXu+DJTvPGs+KGoiEMJC36Hp2uJfaHwUWOCZvWxaCnc/4rEBs" crossorigin="anonymous"></script>
    
    <style>
        body {
            background-color: #f4f4f4;
            font-family: "Helvetica Neue", Arial, sans-serif;
            font-size: 0.9rem;
            margin: 0;
            padding: 20px;
        }
        .table-container {
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
            padding: 20px;
            margin-bottom: 30px;
            overflow-x: auto;
            width: fit-content;
        }
        table.dataTable td {
            white-space: nowrap;
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <h1>Multiple DataFrames</h1>
    <div class="table-container">{{ html_table1 | safe }}</div>
    <div class="table-container">{{ html_table2 | safe }}</div>
</body>
</html>
"""


@app.route("/")
def home():
    """Render a page displaying two sample DataFrames as interactive HTML tables."""
    # First table
    df1 = df2t.get_sample_df()
    html_table1 = df2t.render_inline(
        df1,
        num_html= ['value', 'measurement'],
        # The display class is a short-cut for specifying the stripe hover order-column row-border
        # https://datatables.net/examples/styling/display.html 
        table_attrs={"id": uuid.uuid4().hex, "class": "display"}
    )

    # Second table
    rng = default_rng(seed=42)
    df2 = pd.DataFrame(
        rng.random((1000, 4)),
        columns=[f"Col{i}" for i in range(1, 5)]
    )
    html_table2 = df2t.render_inline(
        df2,
        table_attrs={"id": uuid.uuid4().hex, "class": "display compact"}
    )

    return render_template_string(
        PAGE_TEMPLATE,
        html_table1=html_table1,
        html_table2=html_table2
    )


if __name__ == "__main__":
    app.run(debug=True)