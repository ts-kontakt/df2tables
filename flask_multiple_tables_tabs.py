import random
import uuid
from datetime import datetime, timedelta

import pandas as pd
from flask import Flask, render_template_string

import df2tables

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>df2tables - Multiple Tables Demo</title>

    <!-- jQuery and jQuery UI -->
    <link rel="stylesheet" href="https://code.jquery.com/ui/1.14.1/themes/base/jquery-ui.min.css">
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://code.jquery.com/ui/1.14.1/jquery-ui.min.js"></script>

    <!-- DataTables -->
    <link href="https://cdn.datatables.net/2.3.2/css/dataTables.dataTables.min.css" rel="stylesheet">
    <script src="https://cdn.datatables.net/2.3.2/js/dataTables.min.js"></script>

    <!-- DataTables ColumnControl Extension -->
    <link href="https://cdn.datatables.net/columncontrol/1.1.1/css/columnControl.dataTables.min.css" rel="stylesheet">
    <script src="https://cdn.datatables.net/columncontrol/1.1.1/js/dataTables.columnControl.min.js"></script>

    <!-- DataTables Buttons Extension -->
    <link href="https://cdn.datatables.net/buttons/3.2.5/css/buttons.dataTables.min.css" rel="stylesheet">
    <script src="https://cdn.datatables.net/buttons/3.2.5/js/dataTables.buttons.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.5/js/buttons.html5.min.js"></script>



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
         table.dataTable  td {
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
            <li><a href="#tabs-3">Scrollable View</a></li>
            <li><a href="#tabs-4">Compact Format</a></li>
        </ul>

        <div id="tabs-1">
            <div class="tab-description">
                <h3>Basic Display with Column Control</h3>
                <p>This table demonstrates the standard DataTables appearance using the <code>display</code> CSS class, 
                which provides a clean, professional look with striped rows and hover effects. The table width is constrained 
                to fit its content, preventing unnecessary horizontal stretching.</p>
                <ul class="feature-list">
                    <li><strong>CSS Class:</strong> <code>display</code> - Applies stripe, hover, order-column, and row-border styles 
                    (<a href="https://datatables.net/examples/styling/display.html" target="_blank">learn more</a>)</li>
                    <li><strong>Wrapper Width:</strong> <code>fit-content</code> - Table adapts to content width</li>
                    <li><strong>Copy</strong> button - copy table data to clipboard</li>
                </ul>
            </div>
            <div class="fit-content-wrapper">
                {{ table1_html | safe }}
            </div>
        </div>

        <div id="tabs-2">
            <div class="tab-description">
                <h3>Custom Layout with Numeric Formatting</h3>
                <p>This configuration showcases advanced customization options including a reorganized control layout 
                and enhanced numeric formatting. The compact styling reduces row height for displaying more data in 
                less space, while maintaining readability.</p>
                <ul class="feature-list">
                    <li><strong>CSS Class:</strong> <code>display compact hover</code> - Combines standard display with reduced padding</li>
                    <li><strong>Wrapper Width:</strong> <code>fit-content</code> - Optimized for content dimensions</li>
                    <li><strong>Column Control:</strong> Enabled - Dynamic column visibility</li>
                    <li><strong>Numeric Formatting:</strong> Applied to <code>percentage</code> and <code>change</code> columns with 4 decimal places</li>
                    <li><strong>Custom Layout:</strong> Controls repositioned - info at top-left, page length selector below, search at top-right</li>
                </ul>
            </div>
            <div class="fit-content-wrapper">
                {{ table2_html | safe }}
            </div>
        </div>

        <div id="tabs-3">
            <div class="tab-description">
                <h3>Scrollable View Without Pagination</h3>
                <p>This table replaces traditional pagination with vertical scrolling, ideal for continuously browsing 
                data without page breaks. The scrollable container maintains a fixed viewport height while allowing 
                seamless data exploration. A custom search placeholder demonstrates text localization capabilities.</p>
                <ul class="feature-list">
                    <li><strong>CSS Class:</strong> <code>display</code> - Standard DataTables styling</li>
                    <li><strong>Wrapper Width:</strong> Automatic (full width)</li>
                    <li><strong>Column Control:</strong> Disabled - Fixed column set</li>
                    <li><strong>Pagination:</strong> Disabled - Replaced with vertical scrolling</li>
                    <li><strong>Scroll Height:</strong> <code>50vh</code> (50% of viewport height) with collapse enabled</li>
                    <li><strong>Custom Placeholder:</strong> Modified search input text for better user guidance</li>
                </ul>
            </div>
            {{ table3_html | safe }}
        </div>

        <div id="tabs-4">
            <div class="tab-description">
                <h3>Compact Format with Numeric Precision</h3>
                <p>This minimal configuration prioritizes density and simplicity. The compact display style maximizes 
                visible rows while numeric formatting ensures consistent presentation of decimal values. Column control 
                is disabled to maintain a streamlined interface focused on data consumption.</p>
                <ul class="feature-list">
                    <li><strong>CSS Class:</strong> <code>display compact</code> - Space-efficient presentation</li>
                    <li><strong>Wrapper Width:</strong> Automatic (full width)</li>
                    <li><strong>Column Control:</strong> Disabled - Simplified interface</li>
                    <li><strong>Numeric Formatting:</strong> Applied to <code>percentage</code> and <code>change</code> columns</li>
                    <li><strong>Use Case:</strong> Best for embedded tables or dashboards where space is limited</li>
                </ul>
            </div>
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
    """
    Renders four DataFrames with different styling and feature configurations.
    Each table demonstrates a distinct use case:
    - Table 1: Standard display with column control
    - Table 2: Custom layout with numeric formatting
    - Table 3: Scrollable view without pagination
    - Table 4: Compact format for space-constrained environments
    """
    sample_df = generate_random_dataframe()

    # Table 1: Default DataTables styling with ColumnControl enabled
    table1_html = df2tables.render_inline(
        sample_df.copy(),
        table_attrs={"id": uuid.uuid4().hex, "class": "display"},
        buttons=['copy']
    )

    # Table 2: Compact styling with custom layout and numeric formatting
    cfg2 = {
        'caption': 'Example of layout control - Custom options passed to table',
         "pageLength": 25,
        "layout": {
            "topStart": "info",
            "top1Start": 'pageLength',
            "topEnd": "search", 
        },
    }    
    table2_html = df2tables.render_inline(
        sample_df.copy(),
        precision=4,
        table_attrs={"id": uuid.uuid4().hex, "class": "display compact hover"},
        num_html=["percentage", "change"],
        js_opts=cfg2
    )

    # Table 3: Scrollable view with custom search placeholder, no pagination
    cfg3 = {
        "language": {
            "searchPlaceholder": "Custom search text"
        },
        'caption': 'Custom options passed to table',
        "paging": False,
        "scrollCollapse": True,
        "scrollY": '60vh',
        "scrollX": '50vw',
    }
    table3_html = df2tables.render_inline(
        sample_df.copy(),
        table_attrs={"id": uuid.uuid4().hex, "class": "display"},
        render_opts= {'load_column_control' : False },  
        js_opts=cfg3
    )

    # Table 4: Compact display with numeric formatting, no column control
    table4_html = df2tables.render_inline(
        sample_df.copy(),
        num_html=["percentage", "change"],
        table_attrs={"id": uuid.uuid4().hex, "class": "display compact"},
        render_opts = {'load_column_control' : False },
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
