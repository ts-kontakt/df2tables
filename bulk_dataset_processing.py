"""
Bulk dataset processing example for df2tables.

Iterates over built-in datasets from ``vega_datasets`` and renders each as
an interactive HTML DataTable. 

Requirements
------------
pip install vega_datasets

Note
----
df2tables can handle datasets above 100k rows, but this demo only processes
datasets with fewer than 100k rows to avoid generating overly large files.
"""

import df2tables as df2t
from vega_datasets import data

# WARNING: setting startfile=True will open many browser tabs at once.
# The default (False) writes the HTML file to disk without opening it.

for dataset_name in sorted(dir(data))[:10]:
    dataset_func = getattr(data, dataset_name)
    try:
        df = dataset_func()
        print(f"{dataset_name}: {len(df.index)} rows")

        if len(df.index) < 100_000:
            df2t.render(
                df,
                title=f"Dataset: {dataset_name}",
                to_file=f"{dataset_name}.html",
                startfile=True,  # set to True to open each file automatically
            )
    except Exception as e:
        print(f"Error processing {dataset_name}: {e}")
