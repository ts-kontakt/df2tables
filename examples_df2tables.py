import random
from datetime import datetime, timedelta
from pathlib import Path

import df2tables as df2t


def get_output_path(filename):
    """
    Return Path object for output file.
    If filename is just a filename (no path), save to user's home directory.
    If filename includes a path, use that path and create directories as needed.
    """
    filepath = Path(filename)
    if filepath.parent != Path("."):
        # User supplied a path - create directories if needed
        filepath.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Just a filename - save to home directory
        filepath = Path.home() / filepath

    return filepath


def create_random_dataframe(num_rows=100):
    import matplotlib
    import matplotlib.colors as mcolors
    import numpy as np
    import pandas as pd

    """Generate pandas DataFrame with diverse random data types and HTML color codes."""

    def get_color_gradient(num_colors=100):
        """Generate YlGnBu gradient color codes with contrasting text."""
        cmap = matplotlib.colormaps["YlGnBu"]
        color_indices = np.linspace(0, 1, num_colors)
        colors = []
        half = len(color_indices) / 2
        for cnt, i in enumerate(color_indices):
            rgba_color = cmap(i)
            hex_color = mcolors.rgb2hex(rgba_color[:3])
            text_style = "color:white;" if cnt > half else ""
            colors.append(
                f"<code style='width:100%;{text_style}background-color:{hex_color}'>{hex_color}</code>"
            )
        return colors

    priority_levels = ["Low priority", "Medium priority", "High priority", "Emergency"]
    credit_ratings = ["Excellent", "Good", "Average", "Fair", "Poor"]

    def generate_random_date(min_year=1990, max_year=datetime.now().year):
        """Generate random date between min_year and max_year."""
        start = datetime(min_year, 1, 1, 00, 00, 00)
        years = max_year - min_year + 1
        end = start + timedelta(days=365 * years)
        return (start + (end - start) * random.random()).date()

    lorem_ipsum_text = """
    Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis at ipsum ut ex venenatis tempor. Cras fermentum metus nec massa viverra cursus. Integer pretium massa non mauris tincidunt, at porttitor massa pretium. Nulla vel felis justo. Pellentesque vel eros nec metus varius laoreet. Mauris accumsan ornare pellentesque. Maecenas gravida urna mollis gravida iaculis. Aenean a nunc vel sapien tempor scelerisque. Donec vitae hendrerit enim.
    Integer in aliquet urna, sit amet vestibulum ante. Aliquam vitae convallis ante. Donec ut arcu et lacus condimentum maximus eget quis nunc. Sed eu ornare justo. Suspendisse ligula tellus, condimentum quis vulputate quis, ornare id enim. Pellentesque at ante mattis felis pulvinar aliquet ut at urna. Nunc a libero ac sem posuere tempor eget et nisi. Maecenas nunc purus, consequat eu faucibus at, volutpat vitae nunc. Pellentesque quis odio magna. Mauris suscipit a tortor et volutpat. Nam id ex quis ligula ultricies iaculis vitae sit amet nisl. Curabitur et mauris vel sem congue imperdiet sed sit amet orci.
    """
    words = [
        x
        for x in set(map(lambda x: x.strip(), lorem_ipsum_text.split(" ")))
        if len(x) > 3
    ]

    result = []
    colors = get_color_gradient(num_rows)
    for i in range(num_rows):
        row = [
            random.choice(words),
            random.randint(100, 100000),
            random.uniform(-10, 10),
            random.uniform(-1, 1),
            random.choice(priority_levels),
            random.choice(credit_ratings),
            repr(random.choice([True, False])),
            str(generate_random_date()),
            colors[i],
        ]
        result.append(row)

    columns = [f"col{i}" for i in range(len(result[0]))]
    df = pd.DataFrame(result, columns=columns)
    return df


def create_complex_polars_dataframe(num_rows=100):
    """Generate complex Polars DataFrame with diverse data types and variable-length nested structures."""
    try:
        import polars as pl
    except ImportError:
        print(" Warning: polars is not installed. Install with: pip install polars")
        return None

    base_date = datetime(2024, 1, 1)

    return pl.DataFrame(
        {
            "id": range(num_rows),
            "name": [f"user_{i}" for i in range(num_rows)],
            "age": [random.randint(18, 80) for _ in range(num_rows)],
            "score": [round(random.uniform(0, 100), 2) for _ in range(num_rows)],
            "active": [random.choice([True, False]) for _ in range(num_rows)],
            "category": [random.choice(["A", "B", "C", None]) for _ in range(num_rows)],
            "timestamp": [
                base_date + timedelta(days=random.randint(0, 365))
                for _ in range(num_rows)
            ],
            "value": [random.gauss(0, 1) for _ in range(num_rows)],
            "metadata": [
                {"key": i, "value": random.random()} if random.random() > 0.2 else None
                for i in range(num_rows)
            ],
            "duration": [
                pl.duration(seconds=random.randint(0, 3600)) for _ in range(num_rows)
            ],
        }
    )


def render_random_table(num_rows):
    """Render random DataFrame to HTML table file."""
    df = create_random_dataframe(num_rows=num_rows)
    sys_info = ""
    outfile = get_output_path("rnd_table2.html")
    df2t.render(
        df,
        to_file=str(outfile),
        precision=3,
        num_html=["col2", "col3"],
        title=f"Example Diverse Random Data {num_rows:,d} rows! {sys_info}".replace(
            ",", " "
        ),
    )
    print(f"Saved to: {outfile}")


def render_installed_packages():
    import pandas as pd

    """Render list of installed Python packages to HTML table."""

    def get_installed_packages():
        """Get list of installed packages or fallback to random data."""
        try:
            import pkg_resources

            header_list = ["name        ", "version", "full package path"]
            packages = [repr(d).split(" ") for d in sorted(pkg_resources.working_set)]
            packages = sorted(packages, key=lambda x: x[0].lower())
            df = pd.DataFrame(packages, columns=header_list)
        except ModuleNotFoundError:
            print("Error loading module pkg_resources - using random data")
            df = create_random_dataframe(num_rows=100)
        return df

    packages_df = get_installed_packages()

    outfile = get_output_path("pkg_table.html")
    df2t.render(packages_df, to_file=str(outfile))
    print(f"Saved to: {outfile}")


def render_stock_prices(primary_ticker, alternative_ticker, years_back=10):
    """Fetch and render historical daily closing prices for two tickers."""
    from datetime import date

    import yfinance as yf

    tickers = [alternative_ticker, primary_ticker]
    end_date = date.today()
    start_date = end_date - timedelta(days=years_back * 365)

    price_data = yf.download(tickers, start=start_date, end=end_date)

    outfile = get_output_path("price_data.html")
    df2t.render(price_data.reset_index(), to_file=str(outfile), title="Price data")
    print(f"Saved to: {outfile}")


def render_polars_dataframe(num_rows=100):
    """Create and render complex Polars DataFrame to HTML table."""
    polars_df = create_complex_polars_dataframe(num_rows)

    if polars_df is None:
        return

    outfile = get_output_path("polars_table.html")
    df2t.render(
        polars_df,
        to_file=str(outfile),
        num_html=["value", "score"],
        title=f"Complex Polars DataFrame - {num_rows:,d} rows".replace(",", " "),
    )
    print(f"Saved to: {outfile}")


if __name__ == "__main__":
    render_polars_dataframe(100)
    render_installed_packages()
    render_random_table(10_000)
    render_stock_prices("SPY", "GLD")
