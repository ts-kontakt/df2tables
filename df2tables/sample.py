#!/usr/bin/python
# coding=utf8
"""
Sample/demo data for df2tables.

get_sample_df()     - a small DataFrame with diverse dtypes and edge cases
render_sample_df()  - render that frame as a demo page
main()              - tiny CLI demo (python -m df2tables.sample)

Kept in its own module so df2tables.py stays focused on the conversion
pipeline. Dependency direction is strictly one-way: the core is imported only
INSIDE render_sample_df(), so this module can never create a circular import.
The names remain re-exported from df2tables for API compatibility.
"""

import os
import sys
from pathlib import Path


def get_sample_df(df_type="pandas", size=50, seed=None):
    """
    Generates a sample DataFrame with diverse data types for testing.

    seed=None keeps the historical behaviour (global random + current time);
    pass an int for a reproducible frame (fixed base timestamp + seeded rng).
    """
    import datetime
    import random

    rng = random.Random(seed) if seed is not None else random
    base_time = (
        datetime.datetime(2024, 1, 1) if seed is not None else datetime.datetime.now()
    )

    if df_type not in ["pandas", "polars"]:
        raise ValueError(f"Invalid df_type '{df_type}': must be 'pandas' or 'polars'")

    # Common sample data configuration
    healthcare = ["Low priority", "Medium priority", "High priority", "Emergency"]
    product = ["Premium", "Standard", "Budget"]
    grades = ["A", "B", "C", "D", "F"]

    # Helper functions for random data generation
    def random_choice(options, k):
        return [rng.choice(options) for _ in range(k)]

    def random_bools(k):
        return [rng.choice([True, False]) for _ in range(k)]

    # Base data common to both DataFrame types
    base_data = {
        "timestamp": [
            (base_time - datetime.timedelta(days=i)) for i in range(size)
        ],
        "grade": random_choice(grades, size),
        "revenue": [rng.randint(-2000, 70000) for _ in range(size)],
        "product_type": random_choice(product, size),
        "is_active": random_bools(size),
        "priority": random_choice(healthcare, size),
    }

    # Generate pandas DataFrame with NumPy support
    if df_type == "pandas":
        import numpy as np
        import pandas as pd

        base_data["value"] = (
            np.random.default_rng(seed).standard_normal(size)
            if seed is not None
            else np.random.randn(size)
        )
        base_data["measurement"] = random_choice(
            [-0.333, 1, -9, 4, 2, np.nan, rng.randint(-1000, 10000)], size
        )

        # Include edge cases: NaT, HTML, nested structures, NA values
        base_data["description"] = random_choice(
            [
                np.datetime64("NaT"),
                "<b>HTML content</b> is allowed",
                {"A": [1, 2, 3, [4, 5]]},
                np.timedelta64("NaT"),
                pd.NaT,
                pd.NA,
                np.datetime64(base_time),
            ],
            size,
        )

        return pd.DataFrame(base_data)

    # Generate polars DataFrame (no NumPy dependency)
    if df_type == "polars":
        import polars as pl

        # Generate normally distributed random values without NumPy
        base_data["value"] = [rng.gauss(0, 1) for _ in range(size)]
        base_data["measurement"] = random_choice(
            [-0.333, 1, -9, 4, 2, None, 1111.111], size
        )

        # Polars-compatible edge cases
        base_data["description"] = random_choice(
            [
                "Lorem ipsum dolor sit amet",
                "<b>HTML content</b> is allowed",
                {"A": [1, 2, 3, [4, 5]]},
                100.12345,
                None,
                float("nan"),
                False,
            ],
            size,
        )

        return pl.DataFrame(base_data, strict=False)


def render_sample_df(df_type="pandas", to_file="df_table.html"):
    """
    Creates and renders a sample DataFrame for demonstration.
    """
    # core import stays function-local: no module-level dependency on the
    # pipeline, no circular-import risk (see module docstring)
    try:
        from .df2tables import render
    except ImportError:  # plain source-dir usage
        from df2tables import render

    df = get_sample_df(df_type)
    # Default to home directory if no path separator provided
    if os.sep not in to_file:
        to_file = str(Path.home() / to_file)

    return render(
        df,
        to_file=to_file,
        title=f"Example <b>{df_type.capitalize()}</b> DataFrame",
        precision=3,
        format_negatives=["measurement"],
        buttons=["colvis", "copy", "excel"],
        render_opts={
            "locale_fmt": False,
            "unique_id": 1,
            "reorder": 1,
            "load_column_control": 1,
            "dropdown_select_threshold": 12,
        },
        js_opts={
            "language": {
                "decimal": "#",
            },
            "fixedColumns": {"start": 1, "end": False},
        },
    )


def main():
    # df_type = "pandas"
    df_type = "polars"
    output_path = render_sample_df(df_type, to_file="test_datatable.html")
    if output_path:
        print(f"Sample table generation complete: {output_path}")
    else:
        print("Failed to generate sample table")
        sys.exit(1)


if __name__ == "__main__":
    main()
