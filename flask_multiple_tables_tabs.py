"""
A Flask application demonstrating how to render multiple pandas DataFrames
as interactive HTML tables using the df2tables library.
"""

import uuid
import random
from datetime import datetime, timedelta
import pandas as pd
import df2tables
from flask import Flask, render_template_string

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>df2tables – Multiple Tables Demo</title>

    <!-- jQuery and jQuery UI -->
    <link rel="stylesheet" href="https://code.jquery.com/ui/1.14.1/themes/base/jquery-ui.min.css">
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://code.jquery.com/ui/1.14.1/jquery-ui.min.js"></script>

    <!-- DataTables -->
    <link href="https://cdn.datatables.net/2.3.2/css/dataTables.dataTables.min.css" rel="stylesheet">
    <script src="https://cdn.datatables.net/2.3.2/js/dataTables.min.js"></script>

    <!-- DataTables ColumnControl Extension -->
    <link href="https://cdn.datatables.net/columncontrol/1.1.0/css/columnControl.dataTables.min.css" rel="stylesheet">
    <script src="https://cdn.datatables.net/columncontrol/1.1.0/js/dataTables.columnControl.min.js"></script>

    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 2em;
            background-color: #f4f4f4;
        }
        #tabs {
            border-radius: 8px;
        }
        .fit-content-wrapper {
            width: fit-content;
            border: 1px solid #ddd;
            padding: 1em;
            margin-top: 1em;
            background-color: #fff;
            border-radius: 8px;
        }
        table.dataTable td span {
            float: right;
        }
    </style>

    <script>
        $(function() {
            $("#tabs").tabs();
        });
    </script>
</head>
<body>

    <h1>df2tables: Multiple DataFrame Rendering Demo</h1>

    <div id="tabs">
        <ul>
            <li><a href="#tabs-1">Table 1</a></li>
            <li><a href="#tabs-2">Table 2</a></li>
            <li><a href="#tabs-3">Table 3</a></li>
            <li><a href="#tabs-4">Table 4</a></li>
        </ul>

        <div id="tabs-1">
            <p><strong>CSS Class:</strong> <code>display</code> | 
               <strong>Wrapper Width:</strong> <code>fit-content</code> | 
               <strong>Column Control:</strong> Enabled</p>
            <div class="fit-content-wrapper">
                {{ table1_html | safe }}
            </div>
        </div>

        <div id="tabs-2">
            <p><strong>CSS Class:</strong> <code>compact</code> | 
               <strong>Wrapper Width:</strong> <code>fit-content</code> | 
               <strong>Column Control:</strong> Enabled | 
               <strong>Numeric Formatting:</strong> Applied to <code>percentage</code> and <code>change</code></p>
            <div class="fit-content-wrapper">
                {{ table2_html | safe }}
            </div>
        </div>

        <div id="tabs-3">
            <p><strong>CSS Class:</strong> <code>display</code> | 
               <strong>Wrapper Width:</strong> Automatic | 
               <strong>Column Control:</strong> Disabled</p>
            {{ table3_html | safe }}
        </div>

        <div id="tabs-4">
            <p><strong>CSS Class:</strong> <code>display compact</code> | 
               <strong>Wrapper Width:</strong> Automatic | 
               <strong>Numeric Formatting:</strong> Applied to <code>percentage</code> and <code>change</code> | 
               <strong>Column Control:</strong> Disabled</p>
            {{ table4_html | safe }}
        </div>
    </div>

</body>
</html>
"""


def generate_random_dataframe(num_rows: int = 100) -> pd.DataFrame:
    """
    Generates a pandas DataFrame with synthetic data for demonstration.

    Args:
        num_rows (int): Number of rows to generate.

    Returns:
        pd.DataFrame: A DataFrame containing randomized sample data.
    """
    healthcare_priorities = ["Low priority", "Medium priority", "High priority", "Emergency"]
    credit_ratings = ["Excellent", "Good", "Average", "Fair", "Poor"]
    lorem_ipsum_words = [
        word.strip() for word in """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis at ipsum ut ex venenatis tempor.
        Cras fermentum metus nec massa viverra cursus. Integer pretium massa non mauris tincidunt,
        at porttitor massa pretium.
        """.split() if len(word.strip()) > 3
    ]

    def get_random_date(min_year: int = 1990) -> datetime.date:
        """Generates a random date between min_year and the current year."""
        current_year = datetime.now().year
        start = datetime(min_year, 1, 1)
        end = datetime(current_year, 12, 31)
        delta = end - start
        random_days = random.randint(0, delta.days)
        return (start + timedelta(days=random_days)).date()

    data = []
    for _ in range(num_rows):
        row = [
            str(get_random_date()),
            random.choice(lorem_ipsum_words),
            random.randint(100, 100_000),
            random.uniform(-10, 10),
            random.uniform(-1, 1),
            random.choice(healthcare_priorities),
            random.choice(credit_ratings),
            str(random.choice([True, False])),
        ]
        data.append(row)

    columns = [
        "date", "description", "quantity", "change",
        "percentage", "priority", "rating", "is_active"
    ]
    return pd.DataFrame(data, columns=columns)


app = Flask(__name__)


@app.route("/")
def display_tables():
    """
    Renders four DataFrames with different styling and feature configurations.
    """
    sample_df = generate_random_dataframe()

    # Table 1: Default DataTables styling with ColumnControl enabled
    table1_attrs = {'id': uuid.uuid4().hex, 'class': 'display'}
    table1_html = df2tables.render_inline(
        sample_df.copy(),
        table_attrs=table1_attrs,
        load_column_control=True
    )

    # Table 2: Compact styling, numeric formatting, with ColumnControl
    table2_attrs = {'id': uuid.uuid4().hex, 'class': 'compact'}
    table2_html = df2tables.render_inline(
        sample_df.copy(),
        table_attrs=table2_attrs,
        num_html=['percentage', 'change'],
        load_column_control=True
    )

    # Table 3: Default styling without ColumnControl
    table3_attrs = {'id': uuid.uuid4().hex, 'class': 'display'}
    table3_html = df2tables.render_inline(
        sample_df.copy(),
        table_attrs=table3_attrs,
        load_column_control=False
    )

    # Table 4: Compact + display classes, numeric formatting, no ColumnControl
    table4_attrs = {'id': uuid.uuid4().hex, 'class': 'display compact'}
    table4_html = df2tables.render_inline(
        sample_df.copy(),
        num_html=['percentage', 'change'],
        table_attrs=table4_attrs,
        load_column_control=False
    )

    return render_template_string(
        PAGE_TEMPLATE,
        table1_html=table1_html,
        table2_html=table2_html,
        table3_html=table3_html,
        table4_html=table4_html
    )


if __name__ == "__main__":
    app.run(debug=True)