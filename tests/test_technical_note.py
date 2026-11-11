from wands_search import technical_note


def test_build_figures_writes_every_figure(tmp_path):
    paths = technical_note.build_figures(tmp_path)
    assert [path.name for path in paths] == list(technical_note.FIGURES)
    assert all(path.stat().st_size > 0 for path in paths)


def test_markdown_to_html_keeps_raw_html_and_tables():
    page = technical_note.markdown_to_html("<div class='x'>\n\n**bold**\n\n</div>\n\n| a |\n|---|\n| 1 |\n",
                                           "body {}", "Title")
    assert "<div class='x'>" in page and "<strong>bold</strong>" in page and "<table>" in page
    assert page.startswith("<!doctype html>") and "<title>Title</title>" in page


def test_decimal_comma():
    assert technical_note.comma(0.776) == "0,776"
    assert technical_note.decimal_comma(1)(0.25, None) == "0,2"


def test_recorded_numbers_are_consistent():
    # The selected system has the best NDCG@10 of the test set.
    test_means = {name: values["test"][0] for name, values in technical_note.NDCG_AT_10.items()}
    assert max(test_means, key=test_means.get) == technical_note.SELECTED
    # The error analysis and the results history use the same validation value of the selected system.
    assert technical_note.LOSS_LADDER["sistema escolhido"] == technical_note.NDCG_AT_10[technical_note.SELECTED]["validation"][0]
    # The ladder adds up.
    assert round(1 - technical_note.LOSS_LADDER["melhor ordem dos 100 candidatos"], 3) == 0.067
