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



def test_within_query_spearman_is_computed_per_query():
    pairs = pd.DataFrame({
        "query_id": [1] * 4 + [2] * 4,
        "label": ["Irrelevant", "Partial", "Exact", "Exact"] * 2,
        "value": [1, 2, 3, 4, 4, 3, 2, 1],
    })
    result = profiling.within_query_spearman(pairs, "value", min_pairs=4)
    assert result[1] > 0.9
    assert result[2] < -0.9


def test_within_query_spearman_drops_small_and_constant_queries():
    pairs = pd.DataFrame({
        "query_id": [1, 1, 2, 2, 2, 2],
        "label": ["Exact", "Irrelevant", "Exact", "Partial", "Irrelevant", "Exact"],
        "value": [1, 2, 5, 5, 5, 5],
    })
    assert profiling.within_query_spearman(pairs, "value", min_pairs=3).empty


def test_within_query_spearman_ignores_missing_values():
    pairs = pd.DataFrame({
        "query_id": [1] * 5,
        "label": ["Irrelevant", "Partial", "Exact", "Exact", "Partial"],
        "value": [1.0, 2.0, 3.0, None, None],
    })
    assert profiling.within_query_spearman(pairs, "value", min_pairs=3).loc[1] == 1.0
    assert profiling.within_query_spearman(pairs, "value", min_pairs=4).empty


def test_bootstrap_mean_ci_brackets_the_mean_and_is_reproducible():
    values = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
    low, high = profiling.bootstrap_mean_ci(values, seed=0)
    assert low < values.mean() < high
    assert (low, high) == profiling.bootstrap_mean_ci(values, seed=0)


def test_query_token_descriptors_against_the_catalog():
    product_tokens = pd.Series([["leather", "chair"], ["leather", "sofa"], ["oak", "chair"]])
    queries = pd.Series(["Leather Chairs", "oak table", "36 sofa", "&/"], index=[5, 6, 7, 8])
    result = profiling.query_token_descriptors(queries, product_tokens, stem=True)
    assert result.loc[5].to_dict() == {"n_tokens": 2, "rarest_token_products": 2, "has_unknown_token": False, "has_number": False}
    assert result.loc[6].to_dict() == {"n_tokens": 2, "rarest_token_products": 1, "has_unknown_token": True, "has_number": False}
    assert result.loc[7].to_dict() == {"n_tokens": 2, "rarest_token_products": 1, "has_unknown_token": True, "has_number": True}
    assert result.loc[8].to_dict() == {"n_tokens": 0, "rarest_token_products": 0, "has_unknown_token": False, "has_number": False}
