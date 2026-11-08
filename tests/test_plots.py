import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import pandas as pd  # noqa: E402

from wands_search import plots  # noqa: E402


def test_difference_plot_draws_one_row_per_label():
    fig, ax = plt.subplots()
    plots.difference_plot(ax, ["a", "b"], [0.05, 0.0], [0.01, -0.02], [0.09, 0.02])
    positions = {tick.get_text(): y for tick, y in zip(ax.get_yticklabels(), ax.get_yticks())}
    assert positions["a"] > positions["b"]  # the first label is drawn at the top
    plt.close(fig)


def test_table_shows_title_note_and_rounded_values():
    html = plots.table(pd.DataFrame({"share": [0.123456]}), "Share of <products>", note="A note.", precision=2).to_html()
    assert "Share of &lt;products&gt;" in html  # the title is escaped
    assert "A note." in html
    assert "0.12" in html and "0.1234" not in html


def test_table_accepts_a_series():
    html = plots.table(pd.Series([1234567], name="rows"), "Rows").to_html()
    assert "1,234,567" in html


def test_table_cuts_long_texts():
    html = plots.table(pd.DataFrame({"text": ["a" * 200]}), "Texts", max_text_length=10).to_html()
    assert "aaaaaaa..." in html and "a" * 11 not in html
