import uuid
import pandas as pd
import df2tables as df2t
from flask import Flask, render_template_string
from numpy.random import default_rng

app = Flask(__name__)

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flask DataTables Demo</title>
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <link href="https://cdn.datatables.net/2.3.2/css/dataTables.dataTables.min.css" rel="stylesheet">
    <script src="https://cdn.datatables.net/2.3.2/js/dataTables.min.js"></script>
    <style>
        body {
            background-color: #f4f4f4;
            font-family: system-ui, sans-serif;
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
    </style>
</head>
<body>
    <h1>Multiple DataFrames</h1>
    <div class="table-container">{{ html1 | safe }}</div>
    <div class="table-container">{{ html2 | safe }}</div>
</body>
</html>
"""

@app.route("/")
def home():
    # --- Table 1 ---
    df1 = df2t.get_sample_df()
    title1 = "<b>First</b> DataFrame"
    html1 = df2t.render_inline(df1, title=title1, load_column_control=False)

    # --- Table 2 ---
    rng = default_rng(42)
    df2 = pd.DataFrame(rng.random((100, 4)), columns=[f"Col{i}" for i in range(1, 5)])
    title2 = "<b>Second</b> DataFrame"
    html2 = df2t.render_inline(df2, title=title2, load_column_control=True)

    # **IMPORTANT**: replace df2tables hardcoded the ID 'pd_datatab' in both the HTML table
    # tag and its initializing JavaScript. This replacement is CRITICAL to ensure
    # each table and its script have a unique ID, preventing conflicts.
    html1 = html1.replace('pd_datatab', uuid.uuid4().hex)
    html2 = html2.replace('pd_datatab', uuid.uuid4().hex)
    
    return render_template_string(PAGE_TEMPLATE, html1=html1, html2=html2)

if __name__ == "__main__":
    app.run(debug=True)