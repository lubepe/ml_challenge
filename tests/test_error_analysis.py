import math

import pandas as pd
import pytest

from wands_search import error_analysis, metrics

LABELS = {1: "Exact", 2: "Partial", 3: "Irrelevant", 4: "Exact"}


def test_oracle_puts_exact_first():
    # Candidates hold one Exact and one Partial: the best order is Exact, Partial.
    expected = metrics.ndcg_at_k([1, 2], LABELS)
    assert metrics.oracle_ndcg_at_k([3, 2, 99, 1], LABELS) == pytest.approx(expected)


def test_oracle_is_one_when_all_relevant_products_are_candidates():
    assert metrics.oracle_ndcg_at_k([3, 2, 4, 1], LABELS) == pytest.approx(1.0)


def test_oracle_is_never_below_the_ranking():
    ranking = [99, 3, 2, 1]
    assert metrics.oracle_ndcg_at_k(ranking, LABELS) >= metrics.ndcg_at_k(ranking, LABELS)


def test_oracle_is_nan_without_positive_gain():
    assert math.isnan(metrics.oracle_ndcg_at_k([3], {3: "Irrelevant"}))


@pytest.mark.parametrize("args, expected", [
    ((0.95, 0.0, 0.05, 9), error_analysis.STAGE_OK),
    ((0.10, 0.0, 0.90, 5), error_analysis.STAGE_EVALUATION),
    ((0.50, 0.30, 0.20, 0), error_analysis.STAGE_RETRIEVAL),
    ((0.50, 0.20, 0.30, 4), error_analysis.STAGE_RANKING),
    ((0.50, 0.25, 0.25, 0), error_analysis.STAGE_RANKING),
])
def test_main_loss_stage(args, expected):
    assert error_analysis.main_loss_stage(*args) == expected


def test_shares_product_class_splits_on_pipe():
    assert error_analysis.shares_product_class("Beds", "Headboards|Beds")
    assert not error_analysis.shares_product_class("Beds", "Headboards")
    assert not error_analysis.shares_product_class(None, "Beds")


def test_has_feature_value_checks_key_and_value():
    features = "legcolor : Gold|color : black"
    assert error_analysis.has_feature_value(features, ["legcolor"], lambda value: "gold" in value)
    assert not error_analysis.has_feature_value(features, ["color"], lambda value: "gold" in value)
    assert not error_analysis.has_feature_value(None, ["color"], lambda value: True)


def test_label_disagreement_rate_counts_pairs():
    # 3 products: Exact, Exact, Partial -> 3 pairs, 2 with different labels.
    assert error_analysis.label_disagreement_rate(["Exact", "Exact", "Partial"]) == (2, 3)
    assert error_analysis.label_disagreement_rate(["Exact"]) == (0, 0)


def test_near_duplicate_pairs_finds_identical_texts_only_within_a_query():
    texts = pd.Series({10: "blue velvet bed", 11: "blue velvet bed", 12: "glass coffee table", 13: "blue velvet bed"})
    labels = pd.DataFrame({
        "query_id": [1, 1, 1, 2],
        "product_id": [10, 11, 12, 13],
        "label": ["Exact", "Partial", "Exact", "Exact"],
    })
    pairs = error_analysis.near_duplicate_pairs(texts, labels, threshold=0.95)
    assert len(pairs) == 1
    pair = pairs.iloc[0]
    assert (pair.query_id, pair.product_a, pair.product_b) == (1, 10, 11)
    assert pair.cosine == pytest.approx(1.0)
    assert pair.different


POPULARITY_PRODUCTS = pd.DataFrame({
    "product_id": [1, 2, 3, 4],
    "rating_count": [100.0, 10.0, 1.0, None],
})


def test_product_popularity_uses_log_and_flags_missing_rating():
    popularity = error_analysis.product_popularity(POPULARITY_PRODUCTS)
    assert popularity.loc[1, "log_rating_count"] == pytest.approx(math.log1p(100))
    assert popularity.loc[4, "log_rating_count"] == 0.0
    assert popularity["no_rating"].tolist() == [0.0, 0.0, 0.0, 1.0]


def test_popularity_profile_is_negative_when_popular_products_are_on_top():
    popularity = error_analysis.product_popularity(POPULARITY_PRODUCTS)
    profile = error_analysis.popularity_profile([1, 2, 3, 4], popularity, top_k=2)
    assert profile["spearman_position"] == pytest.approx(-1.0)
    assert profile["median_log_rating_count_top"] == pytest.approx((math.log1p(100) + math.log1p(10)) / 2)
    assert profile["no_rating_share_top"] == 0.0
    assert profile["no_rating_share_pool"] == 0.25


def test_popularity_profile_reverses_with_the_order():
    popularity = error_analysis.product_popularity(POPULARITY_PRODUCTS)
    profile = error_analysis.popularity_profile([4, 3, 2, 1], popularity, top_k=2)
    assert profile["spearman_position"] == pytest.approx(1.0)
    assert profile["no_rating_share_top"] == 0.5


def test_popularity_profile_is_nan_when_all_values_are_equal():
    popularity = error_analysis.product_popularity(pd.DataFrame({"product_id": [1, 2], "rating_count": [None, None]}))
    assert math.isnan(error_analysis.popularity_profile([1, 2], popularity)["spearman_position"])


def test_popularity_by_band_splits_the_list():
    popularity = error_analysis.product_popularity(POPULARITY_PRODUCTS)
    bands = error_analysis.popularity_by_band([1, 2, 3, 4], popularity, bands=((1, 2), (3, 4)))
    assert bands.index.tolist() == ["1-2", "3-4"]
    assert bands.loc["3-4", "no_rating_share"] == 0.5


# Products 1-4 with rating_count 100, 10, 1 and none (POPULARITY_PRODUCTS).
PAIR_LABELS = {1: "Irrelevant", 2: "Exact", 3: "Partial", 4: "Exact"}


def test_judged_pair_inversions_marks_worse_product_above():
    popularity = error_analysis.product_popularity(POPULARITY_PRODUCTS)
    pairs = error_analysis.judged_pair_inversions([1, 2], PAIR_LABELS, popularity)
    # Irrelevant (1, more popular) above Exact (2): inverted, and the worse product is the more popular.
    assert pairs.to_dict("records") == [{"inverted": True, "worse_more_popular": True}]


def test_judged_pair_inversions_skips_same_label_and_unjudged():
    popularity = error_analysis.product_popularity(POPULARITY_PRODUCTS)
    pairs = error_analysis.judged_pair_inversions([2, 99, 4], PAIR_LABELS | {99: "Exact"}, popularity)
    assert pairs.empty


def test_inversion_counts_split_by_popularity():
    popularity = error_analysis.product_popularity(POPULARITY_PRODUCTS)
    # Order 2, 3, 1: Exact > Partial (correct, worse 3 less popular), Exact > Irrelevant (correct, worse 1 more popular),
    # Partial above Irrelevant (correct, worse 1 more popular).
    counts = error_analysis.inversion_counts(error_analysis.judged_pair_inversions([2, 3, 1], PAIR_LABELS, popularity))
    assert counts == {"inverted_worse_more_popular": 0, "pairs_worse_more_popular": 2,
                      "inverted_worse_less_popular": 0, "pairs_worse_less_popular": 1}


def test_exact_positions_by_rating():
    popularity = error_analysis.product_popularity(POPULARITY_PRODUCTS)
    result = error_analysis.exact_positions_by_rating([1, 2, 3, 4], PAIR_LABELS, popularity, top_k=2)
    assert result["exact_rated"] == 1 and result["exact_rated_top"] == 1 and result["mean_position_rated"] == 2
    assert result["exact_no_rating"] == 1 and result["exact_no_rating_top"] == 0 and result["mean_position_no_rating"] == 4


def test_bootstrap_pooled_returns_value_on_all_queries():
    counts = pd.DataFrame({"hits": [1, 3], "total": [2, 4]})
    value, low, high = error_analysis.bootstrap_pooled(counts, lambda sums: sums["hits"] / sums["total"], seed=0, n_resamples=200)
    assert value == pytest.approx(4 / 6)
    assert 0.5 <= low <= value <= high <= 0.75
