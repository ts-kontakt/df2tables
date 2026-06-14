import uuid

import df2tables as df2t
import pandas as pd
from flask import Flask, render_template_string
from numpy.random import default_rng

app = Flask(__name__)

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flask DataTables Demo</title>
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
    <!-- CSS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/2.3.8/css/dataTables.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/buttons/3.2.6/css/buttons.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/colreorder/2.1.0/css/colReorder.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/columncontrol/1.1.0/css/columnControl.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/fixedcolumns/5.0.5/css/fixedColumns.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/scroller/2.4.3/css/scroller.dataTables.min.css">
    <!-- JS -->
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/2.3.8/js/dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.6/js/dataTables.buttons.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.6/js/buttons.html5.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.6/js/buttons.colVis.min.js"></script>
    <script src="https://cdn.datatables.net/colreorder/2.1.0/js/dataTables.colReorder.min.js"></script>
    <script src="https://cdn.datatables.net/columncontrol/1.1.0/js/dataTables.columnControl.min.js"></script>
    <script src="https://cdn.datatables.net/fixedcolumns/5.0.5/js/dataTables.fixedColumns.min.js"></script>
    <script src="https://cdn.datatables.net/scroller/2.4.3/js/dataTables.scroller.min.js"></script>
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
    """Render two sample DataFrames as interactive DataTables."""
    df1 = df2t.get_sample_df()
    html_table1 = df2t.render_inline(
        df1,
        num_html=["value", "measurement"],
        table_attrs={"id": uuid.uuid4().hex, "class": "display"},
    )

    rng = default_rng(seed=42)
    df2 = pd.DataFrame(
        rng.random((1000, 4)),
        columns=[f"Col{i}" for i in range(1, 5)],
    )
    html_table2 = df2t.render_inline(
        df2,
        table_attrs={"id": uuid.uuid4().hex, "class": "display compact"},
    )

    return render_template_string(
        PAGE_TEMPLATE,
        html_table1=html_table1,
        html_table2=html_table2,
    )


if __name__ == "__main__":
    app.run(debug=True)
