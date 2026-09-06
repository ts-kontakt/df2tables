#!/usr/bin/python
# coding=utf8
"""
Demo: both render_ajax() loading modes embedded DIRECTLY in one page -
no iframes. render_ajax() returns an inline fragment by default (just
like render_inline()), and both the regular and the AJAX variant are
generated from the SINGLE template (datatable_templ.html): the AJAX
loader is a comnt region that render() strips and render_ajax()
configures - there is no second template file.

  TAB 1 - "Load data" button (autoload=False)
      Fragment embedded at page render: table skeleton + button only.
      Rows are fetched from /data/button AFTER the click.

  TAB 2 - automatic load with animation (autoload=True)
      The fragment is fetched from /table-auto and injected on FIRST tab
      activation (jQuery .html() executes its <script>), so the big
      download - and its pulsing "Loading data..." animation - starts
      exactly when you open the tab, not on page load.

Run:
    ~/pyenv/bin/python flask_multiple_tables_ajax.py
    then open http://127.0.0.1:5057/
"""

import sys
from pathlib import Path

# Pin the fresh (fixed, 0.3.0) module copy from the test directory.
# Remove this block to test the df2tables installed in the system.
_FINAL_DIR = Path("/home/tom/Documents/0_tests/1test-v2")
if (_FINAL_DIR / "df2tables").is_dir():
    sys.path.insert(0, str(_FINAL_DIR))

from flask import Flask, Response, render_template_string  # noqa: E402

import df2tables as df2t  # noqa: E402

app = Flask(__name__)

BUTTON_ROWS = 5_000     # small dataset - the click responds instantly
AUTO_ROWS = 250_000     # large dataset - slow endpoint => visible animation

print(f"Generating DataFrames ({BUTTON_ROWS:,} + {AUTO_ROWS:,} rows) ...")
DF_BUTTON = df2t.get_sample_df("pandas", size=BUTTON_ROWS)
DF_AUTO = df2t.get_sample_df("pandas", size=AUTO_ROWS)
print("DataFrames ready.")

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>df2tables.render_ajax() - two loading modes</title>

    <!-- CSS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/2.3.8/css/dataTables.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/buttons/3.2.6/css/buttons.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/colreorder/2.1.2/css/colReorder.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/columncontrol/1.2.1/css/columnControl.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/fixedcolumns/5.0.5/css/fixedColumns.dataTables.min.css">
    <!-- JS -->
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/2.3.8/js/dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.6/js/dataTables.buttons.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.6/js/buttons.html5.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/3.2.6/js/buttons.colVis.min.js"></script>
    <script src="https://cdn.datatables.net/colreorder/2.1.2/js/dataTables.colReorder.min.js"></script>
    <script src="https://cdn.datatables.net/columncontrol/1.2.1/js/dataTables.columnControl.min.js"></script>
    <script src="https://cdn.datatables.net/fixedcolumns/5.0.5/js/dataTables.fixedColumns.min.js"></script>

    <!-- jQuery UI for tabs -->
    <link rel="stylesheet" href="https://code.jquery.com/ui/1.14.2/themes/base/jquery-ui.min.css">
    <script src="https://code.jquery.com/ui/1.14.2/jquery-ui.min.js"></script>

    <style>
        :root {
            --ink: #0a2540;          /* df2tables navy */
            --muted: #5b6b7f;
            --card-border: #e5eaf1;
        }
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                         Arial, sans-serif;
            padding: 2em;
            background: linear-gradient(180deg, #f5f7fa 0%, #edf1f6 100%);
            color: #1f2937;
        }
        h1 { margin: 0 0 6px; font-size: 1.5rem; letter-spacing: -0.02em;
             color: var(--ink); }
        p.lead { margin: 0 0 20px; color: var(--muted); font-size: .95rem; }
        p.lead code, .tab-description code {
            background: #eef2f7; border: 1px solid var(--card-border);
            padding: 1px 6px; border-radius: 5px;
            font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
            font-size: .8rem; color: var(--ink);
        }

        /* Tabs */
        #tabs { background: transparent; border: none; border-radius: 12px;
                font-family: inherit; }
        #tabs ul.ui-tabs-nav {
            border: none; background: transparent; padding: 0 0 0 8px;
            border-bottom: 2px solid var(--card-border); border-radius: 0;
            display: flex; gap: 6px; margin-bottom: 18px;
        }
        #tabs .ui-tabs-tab {
            border: 1px solid var(--card-border); border-bottom: none;
            background: #fff; border-radius: 10px 10px 0 0 !important;
            margin-bottom: -2px !important;
        }
        #tabs .ui-tabs-anchor {
            padding: 10px 18px !important; font-size: .92rem;
            color: var(--muted) !important; font-weight: 600; outline: none;
        }
        #tabs .ui-tabs-active .ui-tabs-anchor { color: var(--ink) !important; }
        #tabs .ui-tabs-active {
            border-color: var(--ink) !important;
            box-shadow: inset 0 -2px 0 var(--ink);
        }
        .ui-widget.ui-widget-content { border: none; }

        .tab-panel {
            background: #fff;
            border: 1px solid var(--card-border);
            border-radius: 14px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, .06);
            padding: 22px 24px 24px;
        }
        .tab-description {
            background: #f8fafc;
            border-left: 3px solid var(--ink);
            padding: 1em 1.2em;
            margin-bottom: 1.4em;
            border-radius: 6px;
        }
        .tab-description h3 { margin: 0 0 8px; font-size: 1.05rem;
                              color: var(--ink); }
        .tab-description p { margin: 0 0 8px; color: #475569;
                             font-size: .9rem; line-height: 1.55; }
        .feature-list { margin: .4em 0 0; padding-left: 1.3em;
                        font-size: .88rem; color: #475569; }
        .feature-list li { margin: .3em 0; }
        .badge { display: inline-block; padding: 2px 10px; border-radius: 999px;
                 font-size: .72rem; font-weight: 700; letter-spacing: .04em; }
        .badge.wait { background: #fef3c7; color: #92400e; }
        .badge.auto { background: #d1fae5; color: #065f46; }

        .table-host table.dataTable td {
            white-space: nowrap;
            font-size: 0.875rem;
        }
        .table-host table.dataTable td span { float: right; }
        .table-host { overflow-x: auto; }
    </style>

    <script>
        // Tab 2 starts loading its big AJAX table only when the user opens
        // the tab: the fragment is fetched once and injected - jQuery .html()
        // executes the fragment's <script>, whose autoload=True fires the
        // data fetch immediately.
        (function ($) {
            $(function () {
                $("#tabs").tabs({
                    activate: function (event, ui) {
                        if (ui.newPanel.attr("id") === "tab-2") {
                            const host = document.getElementById("tab2-host");
                            if (host && !host.dataset.loaded) {
                                host.dataset.loaded = "1";
                                $.get("/table-auto").done(function (fragment) {
                                    $(host).html(fragment);
                                });
                            }
                        }
                    }
                });
            });
        })(jQuery);
    </script>
</head>
<body>
    <h1>df2tables.render_ajax() &mdash; two loading modes</h1>
    <p class="lead">
        Both tables are rendered with <code>render_ajax()</code> from the
        <b>single</b> template: the HTML never embeds the rows &mdash; they are
        fetched from a JSON endpoint at runtime. No iframes &mdash; the
        fragments are embedded directly, exactly like
        <code>render_inline()</code> output.
    </p>

    <div id="tabs">
        <ul>
            <li><a href="#tab-1">1 &middot; Load data button</a></li>
            <li><a href="#tab-2">2 &middot; Automatic load + animation</a></li>
        </ul>

        <div id="tab-1">
            <div class="tab-panel">
                <div class="tab-description">
                    <h3>Load data button <span class="badge wait">autoload=False</span></h3>
                    <p>
                        The data is <b>not fetched right away</b>: the panel shows only
                        the table skeleton and the button. Rows arrive <b>only after
                        you click</b> &mdash; then <code>fetch()</code> pulls
                        {{ button_rows }} rows from <code>/data/button</code> and the
                        DataTable is built. The button disappears after a successful
                        load and is replaced by &bdquo;Loaded N rows.&rdquo;.
                    </p>
                    <ul class="feature-list">
                        <li><strong>Dataset:</strong> {{ button_rows }} mixed-type rows (dates, categories, numbers, edge cases)</li>
                        <li><strong>No data in HTML:</strong> the fragment weighs a few kB regardless of row count</li>
                        <li><strong>Fetch on click:</strong> <code>/data/button</code> &rarr; bare JSON array from <code>to_js_array()</code></li>
                        <li><strong>After load:</strong> button hidden, status shows the row count</li>
                    </ul>
                </div>
                <div class="table-host">{{ ajax_button | safe }}</div>
            </div>
        </div>

        <div id="tab-2">
            <div class="tab-panel">
                <div class="tab-description">
                    <h3>Automatic load with animation <span class="badge auto">autoload=True</span></h3>
                    <p>
                        <b>No button at all.</b> Opening this tab <b>starts the load</b>:
                        the fragment is fetched and injected on first activation, and
                        the big dataset ({{ auto_rows }} rows, ~27&nbsp;MB of JSON) is
                        downloaded immediately. Serialization and transfer take a few
                        seconds, so you can watch the subtle pulsing &bdquo;Loading
                        data&#8230;&rdquo; indicator. When it finishes it is replaced by
                        &bdquo;Loaded N rows.&rdquo; and the table appears with a gentle
                        fade-in; on failure a <b>Retry</b> button appears instead.
                    </p>
                    <ul class="feature-list">
                        <li><strong>Dataset:</strong> {{ auto_rows }} rows &mdash; deliberately large so the animation is clearly visible</li>
                        <li><strong>Lazy activation:</strong> the fragment is fetched from <code>/table-auto</code> on the first tab click (nothing downloads before that)</li>
                        <li><strong>autoload=True:</strong> the fragment fetches <code>/data/auto</code> as soon as it is injected</li>
                        <li><strong>Loading state:</strong> pulsing spinner + &bdquo;Loading data&#8230;&rdquo;, then fade-in table</li>
                        <li><strong>Failure path:</strong> error message + <b>Retry</b> button (created only when needed)</li>
                    </ul>
                </div>
                <div class="table-host" id="tab2-host"></div>
            </div>
        </div>
    </div>
</body>
</html>
"""


@app.route("/")
def home():
    """Landing page: tab 1 fragment embedded, tab 2 injected on activation."""
    ajax_button = df2t.render_ajax(
        DF_BUTTON,
        data_url="/data/button",
        button_label="Load data",
        autoload=False,
        precision=2,
        format_negatives=["measurement"],
    )
    return render_template_string(
        PAGE,
        ajax_button=ajax_button,
        button_rows=f"{BUTTON_ROWS:,}",
        auto_rows=f"{AUTO_ROWS:,}",
    )


@app.route("/table-auto")
def table_auto():
    """Tab 2: inline fragment (default mode) - injected on first activation."""
    return df2t.render_ajax(
        DF_AUTO,
        data_url="/data/auto",
        autoload=True,
        precision=2,
        format_negatives=["measurement"],
    )


@app.route("/data/button")
def data_button():
    return Response(
        df2t.to_js_array(DF_BUTTON, precision=2),
        mimetype="application/json",
    )


@app.route("/data/auto")
def data_auto():
    # Recomputed on every request on purpose: serializing 250k rows takes
    # a while, which makes the loading animation clearly visible.
    return Response(
        df2t.to_js_array(DF_AUTO, precision=2),
        mimetype="application/json",
    )


if __name__ == "__main__":
    # Port 5057 to avoid clashing with other apps on 5000.
    # use_reloader=False: the reloader would generate the big DataFrame twice.
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
