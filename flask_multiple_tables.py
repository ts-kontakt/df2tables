import random
import uuid
from datetime import datetime, timedelta

import df2tables as df2t
import pandas as pd
from flask import Flask, render_template_string

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
           
        }
        table.dataTable td {
            white-space: nowrap;
            font-size: 0.875rem;
        }
    </style>
    <!-- CSS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/2.3.8/css/dataTables.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/buttons/3.2.6/css/buttons.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/colreorder/2.1.2/css/colReorder.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/columncontrol/1.2.1/css/columnControl.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/fixedcolumns/5.0.5/css/fixedColumns.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/fixedheader/4.0.6/css/fixedHeader.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/scroller/2.4.3/css/scroller.dataTables.min.css">
    <!-- JS -->
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/2.3.8/js/dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.6/js/dataTables.buttons.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.6/js/buttons.html5.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.6/js/buttons.colVis.min.js"></script>
    <script src="https://cdn.datatables.net/colreorder/2.1.2/js/dataTables.colReorder.min.js"></script>
    <script src="https://cdn.datatables.net/columncontrol/1.2.1/js/dataTables.columnControl.min.js"></script>
    <script src="https://cdn.datatables.net/fixedcolumns/5.0.5/js/dataTables.fixedColumns.min.js"></script>
    <script src="https://cdn.datatables.net/fixedheader/4.0.6/js/dataTables.fixedHeader.min.js"></script>
    <script src="https://cdn.datatables.net/scroller/2.4.3/js/dataTables.scroller.min.js"></script>
</head>
<body>
    <h1>Multiple DataFrames</h1>
    <div class="table-container">{{ html_table1 | safe }}</div>
    <div class="table-container" style="width:fit-content">{{ html_table2 | safe }}</div>
</body>
</html>
"""


def generate_orders_dataframe(num_rows=200):
    """Generate a synthetic orders DataFrame: dates, customers, items, amounts."""
    tiers = ["Bronze", "Silver", "Gold", "Platinum"]
    statuses = ["new", "paid", "shipped", "refunded"]
    start = datetime(2024, 1, 1)

    rows = []
    for i in range(num_rows):
        items = random.randint(1, 12)
        unit_price = round(random.uniform(3, 250), 2)
        rows.append([
            (start + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
            f"customer_{i:04d}",
            random.choice(tiers),
            items,
            round(items * unit_price, 2),
            random.choice(statuses),
        ])
    return pd.DataFrame(
        rows, columns=["date", "customer", "tier", "items", "amount", "status"]
    )


@app.route("/")
def home():
    """Render two sample DataFrames as interactive DataTables."""
    # Table 1: the bundled sample DataFrame (mixed edge-case data types)
    df1 = df2t.get_sample_df()
    html_table1 = df2t.render_inline(
        df1,
        format_negatives=["value", "measurement"],
        table_attrs={"id": uuid.uuid4().hex, "class": "display"},
    )

    # Table 2: synthetic orders dataset - different column types and
    # dropdown filters for the low-cardinality columns
    df2 = generate_orders_dataframe()
    html_table2 = df2t.render_inline(
        df2,
        precision=2,
        table_attrs={"id": uuid.uuid4().hex, "class": "display compact"},
        js_opts={
            "pageLength": 10,
            "language": {"searchPlaceholder": "Filter orders..."},
        },
    )

    return render_template_string(
        PAGE_TEMPLATE,
        html_table1=html_table1,
        html_table2=html_table2,
    )


if __name__ == "__main__":
    app.run(debug=True)
