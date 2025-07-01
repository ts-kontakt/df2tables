import random
from datetime import datetime, timedelta

import matplotlib
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

import df2tables as df2t


def random_data(num_rows=100):

    def get_rdylgn_colors(num_colors=100):
        cmap = matplotlib.colormaps["YlGnBu"]
        color_indices = np.linspace(0, 1, num_colors)
        colors = []
        half = len(color_indices) / 2
        for cnt, i in enumerate(color_indices):
            rgba_color = cmap(i)
            hex_color = mcolors.rgb2hex(rgba_color[:3])

            fstyle = "color:white;" if cnt > half else ""
            colors.append(
                f"<code style='width:100%;{fstyle}background-color:{hex_color}'>{hex_color}</code>")
        return colors

    healthcare = ["Low priority", "Medium priority", "High priority", "Emergency"]
    credit_ratings = ["Excellent", "Good", "Average", "Fair", "Poor"]
    job = ["Senior", "Mid-level", "Junior", "Entry-level"]
    product = ["Premium", "Standard", "Budget"]

    def gen_datetime(min_year=1990, max_year=datetime.now().year):
        # generate a datetime in format yyyy-mm-dd hh:mm:ss.000000
        start = datetime(min_year, 1, 1, 00, 00, 00)
        years = max_year - min_year + 1
        end = start + timedelta(days=365 * years)
        return start + (end - start) * random.random()

    lorem_ipsum_text = """
    Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis at ipsum ut ex venenatis tempor. Cras fermentum metus nec massa viverra cursus. Integer pretium massa non mauris tincidunt, at porttitor massa pretium. Nulla vel felis justo. Pellentesque vel eros nec metus varius laoreet. Mauris accumsan ornare pellentesque. Maecenas gravida urna mollis gravida iaculis. Aenean a nunc vel sapien tempor scelerisque. Donec vitae hendrerit enim.
    Integer in aliquet urna, sit amet vestibulum ante. Aliquam vitae convallis ante. Donec ut arcu et lacus condimentum maximus eget quis nunc. Sed eu ornare justo. Suspendisse ligula tellus, condimentum quis vulputate quis, ornare id enim. Pellentesque at ante mattis felis pulvinar aliquet ut at urna. Nunc a libero ac sem posuere tempor eget et nisi. Maecenas nunc purus, consequat eu faucibus at, volutpat vitae nunc. Pellentesque quis odio magna. Mauris suscipit a tortor et volutpat. Nam id ex quis ligula ultricies iaculis vitae sit amet nisl. Curabitur et mauris vel sem congue imperdiet sed sit amet orci.
    """
    words = [x for x in set(map(lambda x: x.strip(), lorem_ipsum_text.split(" "))) if len(x) > 3]

    result = []
    colors = get_rdylgn_colors(num_rows)
    for i in range(num_rows):
        row = [
            random.choice(words),
            random.randint(100, 100000),
            random.uniform(-10, 10),
            random.uniform(-1, 1),
            random.choice(healthcare),
            random.choice(job),
            random.choice(product),
            random.choice(credit_ratings),
            repr(random.choice([True, False])),
            str(gen_datetime()),
            colors[i],
        ]
    
        result.append(row)
    columns = [f"col{i}" for i in range(len(result[0]))]
    df = pd.DataFrame(result, columns=columns)

    import sys
    sys_info = f'<br><small style="color:gray">{sys.platform}</small>'

    outfile = "rnd_table2.html"
    df2t.render(
        df,
        to_file=outfile,
        title=f"Example Diverse Random Data <b>{num_rows} rows</b>! {sys_info}",
        num_html=["col1", "col2"],
    )
    return result


def pkg_test():

    def get_packages():
        try:
            import pkg_resources

            dists = [repr(d).split(" ") for d in sorted(pkg_resources.working_set)]
            dists = sorted(dists, key=lambda x: x[0].lower())
        except ModuleNotFoundError:
            print("Error loading module pkg_resources - using random data")
            dists = random_data(num_rows=100)
        return dists

    header_list = ["name        ", "ver  ", "full package path"]
    df = pd.DataFrame(get_packages(), columns=header_list)

    outfile = "pkg_table.html"
    df2t.render(df, to_file=outfile)


if __name__ == "__main__":
    # testitables()
    # pkg_test()
    random_data(50000)
