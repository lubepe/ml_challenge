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
