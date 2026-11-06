import pandas as pd

from wands_search import profiling


def make_labels() -> pd.DataFrame:
    return pd.DataFrame({
        "id": [0, 1, 2, 3, 4, 5],
        "query_id": [0, 0, 0, 1, 1, 1],
        "product_id": [10, 10, 11, 20, 20, 21],
        "label": ["Exact", "Exact", "Partial", "Exact", "Partial", "Irrelevant"],
    })


def test_simple_tokens_lowercases_and_drops_punctuation():
    assert profiling.simple_tokens("Fawkes 36\" Blue-Vanity") == {"fawkes", "36", "blue", "vanity"}


def test_simple_tokens_removes_accents():
    assert profiling.simple_tokens("Wall Décor") == {"wall", "decor"}


def test_token_overlap_is_the_share_of_query_tokens_found():
    assert profiling.token_overlap({"salon", "chair"}, {"chair", "wood"}) == 0.5
    assert profiling.token_overlap(set(), {"chair"}) == 0.0


def test_query_group_key_matches_plural_case_and_word_order():
    assert profiling.query_group_key("Salon Chairs") == profiling.query_group_key("chair salon")


def test_query_group_key_keeps_different_queries_apart():
    assert profiling.query_group_key("glass table") != profiling.query_group_key("glass lamp")
    assert profiling.query_group_key("glass") == "glass"  # "ss" is not a plural


def test_count_data_lines_excludes_header(tmp_path):
    path = tmp_path / "file.csv"
    path.write_text("a\tb\n1\t2\n3\t4\n", encoding="utf-8")

    assert profiling.count_data_lines(path) == 2


def test_column_overview_counts_nulls_and_distinct():
    df = pd.DataFrame({"a": [1, None, 1, 2], "b": ["x", "y", "z", "w"]})

    overview = profiling.column_overview(df)

    assert overview.loc["a", "nulls"] == 1
    assert overview.loc["a", "null_pct"] == 25.0
    assert overview.loc["a", "distinct"] == 2
    assert overview.loc["b", "nulls"] == 0


def test_label_pair_stats_separates_repeated_and_conflicting():
    stats = profiling.label_pair_stats(make_labels())

    assert len(stats) == 4
    assert stats.loc[(0, 10), "n_rows"] == 2
    assert stats.loc[(0, 10), "n_labels"] == 1  # repeated, same label
    assert stats.loc[(1, 20), "n_rows"] == 2
    assert stats.loc[(1, 20), "n_labels"] == 2  # repeated, conflicting


def test_conflicting_label_rows_returns_only_conflicting_pairs():
    rows = profiling.conflicting_label_rows(make_labels())

    assert set(rows["id"]) == {3, 4}
    assert set(rows["label"]) == {"Exact", "Partial"}


def test_query_label_profile_counts_labels_and_exact_fraction():
    labels = pd.DataFrame({
        "query_id": [0, 0, 0, 0, 1],
        "product_id": [1, 2, 3, 4, 1],
        "label": ["Exact", "Partial", "Partial", "Irrelevant", "Partial"],
    })

    profile = profiling.query_label_profile(labels)

    assert profile.loc[0, "n_judged"] == 4
    assert profile.loc[0, "exact_fraction"] == 0.25
    assert profile.loc[1, "Exact"] == 0
    assert profile.loc[1, "exact_fraction"] == 0.0

