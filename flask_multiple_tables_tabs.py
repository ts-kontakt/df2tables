import random
import uuid
from datetime import datetime, timedelta

import df2tables
import pandas as pd
from flask import Flask, render_template_string

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>df2tables - Multiple Tables Demo</title>

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

    <!-- jQuery UI for tabs -->
    <link rel="stylesheet" href="https://code.jquery.com/ui/1.14.2/themes/base/jquery-ui.min.css">
    <script src="https://code.jquery.com/ui/1.14.2/jquery-ui.min.js"></script>

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
        table.dataTable td {
            white-space: nowrap;
            font-size: 0.875rem;
        }
        .tab-description {
            background-color: #f9f9f9;
            border-left: 3px solid rgb(13 110 253 / 43%);
            padding: 1em;
            margin-bottom: 1.5em;
            border-radius: 3px;
        }
        .feature-list {
            margin: 0.5em 0;
            padding-left: 1.5em;
        }
        .feature-list li {
            margin: 0.3em 0;
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
    <p>Explore different configurations and styling options for rendering pandas DataFrames as interactive DataTables.</p>

    <div id="tabs">
        <ul>
            <li><a href="#tabs-1">Basic Display</a></li>
            <li><a href="#tabs-2">Custom Layout</a></li>
            <li><a href="#tabs-3">Scrollable + Fixed Column</a></li>
            <li><a href="#tabs-4">Compact Format</a></li>
        </ul>

        <div id="tabs-1">
            <div class="tab-description">
                <h3>Basic Display with Column Reorder</h3>
                <p>Standard DataTables look with striped rows, hover highlight, and draggable column headers.
                Negative values are coloured red.</p>
                <ul class="feature-list">
                    <li><strong>CSS class:</strong> <code>display</code> - stripe, hover, order-column, row-border</li>
                    <li><strong>Column reorder:</strong> enabled - drag any header left or right to rearrange columns</li>
                    <li><strong>Negative formatting:</strong> enabled - negative values rendered in red</li>
                    <li><strong>Wrapper:</strong> <code>fit-content</code> - table width adapts to content</li>
                </ul>
            </div>
            <div class="fit-content-wrapper">
                {{ table1_html | safe }}
            </div>
        </div>

        <div id="tabs-2">
            <div class="tab-description">
                <h3>Custom Layout with Numeric Formatting</h3>
                <p>Reorganised control bar and compact styling; numeric columns rendered with 4-decimal precision.</p>
                <ul class="feature-list">
                    <li><strong>CSS class:</strong> <code>display compact hover</code> - reduced row padding, hover highlight</li>
                    <li><strong>Numeric formatting:</strong> <code>percentage</code> and <code>change</code> - 4 decimal places, negatives in red</li>
                    <li><strong>Page length:</strong> 25 rows</li>
                    <li><strong>Custom layout:</strong> info top-left, page-length selector below, search top-right</li>
                    <li><strong>Column control:</strong> enabled</li>
                    <li><strong>Wrapper:</strong> <code>fit-content</code></li>
                </ul>
            </div>
            <div class="fit-content-wrapper">
                {{ table2_html | safe }}
            </div>
        </div>

        <div id="tabs-3">
            <div class="tab-description">
                <h3>Scrollable View with Fixed Column</h3>
                <p>Vertical and horizontal scrolling replace pagination; the leftmost column stays pinned
                while the rest scroll freely.</p>
                <ul class="feature-list">
                    <li><strong>Fixed columns:</strong> 1 column pinned left - stays visible while scrolling right</li>
                    <li><strong>Scroll area:</strong> <code>scrollY: 60vh</code> vertical, <code>scrollX: 50vw</code> horizontal</li>
                    <li><strong>Scroll collapse:</strong> enabled - viewport shrinks when rows are fewer than the scroll height</li>
                    <li><strong>Pagination:</strong> disabled - all rows in one scrollable block</li>
                    <li><strong>Column control:</strong> disabled</li>
                    <li><strong>CSS class:</strong> <code>display</code></li>
                    <li><strong>Custom placeholder:</strong> search input text overridden via <code>language.searchPlaceholder</code></li>
                </ul>
            </div>
            <div>
                {{ table3_html | safe }}
            </div>
        </div>

        <div id="tabs-4">
            <div class="tab-description">
                <h3>Compact Format with Numeric Precision</h3>
                <p>Minimal, space-efficient presentation with formatted numeric columns and no column control panel.</p>
                <ul class="feature-list">
                    <li><strong>CSS class:</strong> <code>display compact</code> - reduced cell padding, standard styling</li>
                    <li><strong>Numeric formatting:</strong> <code>percentage</code> and <code>change</code> columns</li>
                    <li><strong>Column control:</strong> disabled</li>
                    <li><strong>Wrapper:</strong> full width</li>
                </ul>
            </div>
            {{ table4_html | safe }}
        </div>
    </div>

</body>
</html>
"""


def generate_random_dataframe(num_rows=100):
    """Generate a synthetic DataFrame with mixed column types."""
    healthcare_priorities = [
        "Low priority",
        "Medium priority",
        "High priority",
        "Emergency",
    ]
    credit_ratings = ["Excellent", "Good", "Average", "Fair", "Poor"]
    lorem_ipsum_words = [
        word.strip()
        for word in """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis at ipsum ut ex venenatis tempor.
        Cras fermentum metus nec massa viverra cursus. Integer pretium massa non mauris tincidunt,
        at porttitor massa pretium.
        """.split()
        if len(word.strip()) > 3
    ]

    def get_random_date(min_year=1990):
        """Generate a random date between min_year and the current year."""
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
        "date",
        "description",
        "quantity",
        "change",
        "percentage",
        "priority",
        "rating",
        "is_active",
    ]
    return pd.DataFrame(data, columns=columns)


app = Flask(__name__)


@app.route("/")
def display_tables():
    """Render four DataFrames each with a different styling configuration."""
    sample_df = generate_random_dataframe()

    # Table 1: default styling with column reorder
    table1_html = df2tables.render_inline(
        sample_df.copy(),
        table_attrs={"id": uuid.uuid4().hex, "class": "display"},
        format_negatives=True,
        render_opts={"reorder": 1},
    )

    # Table 2: compact styling with custom layout and numeric formatting
    cfg2 = {
        "caption": "Example of layout control - custom options passed to table",
        "pageLength": 25,
        "layout": {
            "topStart": "info",
            "top1End": "pageLength",
            "topEnd": "search",
        },
    }
    table2_html = df2tables.render_inline(
        sample_df.copy(),
        precision=4,
        table_attrs={"id": uuid.uuid4().hex, "class": "display compact hover"},
        num_html=["percentage", "change"],
        js_opts=cfg2,
    )

    # Table 3: fixed first column, scrollable, no pagination
    cfg3 = {
        "fixedColumns": {"left": 1},
        "language": {"searchPlaceholder": "Custom search text"},
        "caption": "Custom options passed to table",
        "paging": False,
        "responsive": False,
        "scrollCollapse": True,
        "scrollY": "60vh",
        "scrollX": "50vw",
    }
    table3_html = df2tables.render_inline(
        sample_df.copy(),
        table_attrs={"id": uuid.uuid4().hex, "class": "display"},
        render_opts={"load_column_control": False},
        js_opts=cfg3,
    )

    # Table 4: compact display with numeric formatting, no column control
    table4_html = df2tables.render_inline(
        sample_df.copy(),
        num_html=["percentage", "change"],
        table_attrs={"id": uuid.uuid4().hex, "class": "display compact"},
        render_opts={"load_column_control": False},
    )

    return render_template_string(
        PAGE_TEMPLATE,
        table1_html=table1_html,
        table2_html=table2_html,
        table3_html=table3_html,
        table4_html=table4_html,
    )


if __name__ == "__main__":
    app.run(debug=True)
