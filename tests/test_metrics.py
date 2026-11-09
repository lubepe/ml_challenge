import math

import pandas as pd
import pytest

from wands_search import metrics

# One query with four judged products; "x" and "y" are unjudged.
LABELS = {1: "Exact", 2: "Partial", 3: "Irrelevant", 4: "Exact"}
# Ideal gains [2, 2, 1, 0]: 2/log2(2) + 2/log2(3) + 1/log2(4) + 0
IDEAL_DCG = 2 + 2 / math.log2(3) + 0.5
UNJUDGED_X, UNJUDGED_Y = 98, 99


def test_dcg_uses_linear_gains_and_log2_discount():
    assert metrics.dcg([2, 1, 1]) == pytest.approx(2 + 1 / math.log2(3) + 0.5)


def test_ndcg_hand_computed_example():
    # ranking: Partial, unjudged, Exact -> 1/log2(2) + 0 + 2/log2(4) = 2
    ranking = [2, UNJUDGED_X, 1]
    assert metrics.ndcg_at_k(ranking, LABELS) == pytest.approx(2 / IDEAL_DCG)


def test_ndcg_is_one_for_ideal_order():
    assert metrics.ndcg_at_k([1, 4, 2, 3], LABELS) == pytest.approx(1.0)


def test_ndcg_cuts_at_k():
    # Only the first position counts with k=1: gain 1 against ideal 2.
    assert metrics.ndcg_at_k([2, 1, 4], LABELS, k=1) == pytest.approx(0.5)


def test_ndcg_empty_ranking_is_zero():
    assert metrics.ndcg_at_k([], LABELS) == 0.0


def test_ndcg_is_nan_without_positive_gain():
    assert math.isnan(metrics.ndcg_at_k([3], {3: "Irrelevant"}))


def test_condensed_ndcg_removes_unjudged_before_cut():
    # condensed list: Partial, Exact -> 1 + 2/log2(3)
    ranking = [2, UNJUDGED_X, 1]
    expected = (1 + 2 / math.log2(3)) / IDEAL_DCG
    assert metrics.condensed_ndcg_at_k(ranking, LABELS) == pytest.approx(expected)


def test_condensed_ndcg_brings_judged_products_into_top_k():
    # With k=1 the unjudged first product is skipped and the Exact one counts.
    assert metrics.condensed_ndcg_at_k([UNJUDGED_X, 1], LABELS, k=1) == pytest.approx(1.0)


def test_mrr_first_exact_position():
    assert metrics.mrr_at_k([2, UNJUDGED_X, 1], LABELS) == pytest.approx(1 / 3)


def test_mrr_ignores_partial_by_default():
    assert metrics.mrr_at_k([2, 3], LABELS) == 0.0


def test_mrr_with_partial_as_relevant():
    assert metrics.mrr_at_k([2, 1], LABELS, relevant=metrics.EXACT_AND_PARTIAL) == 1.0


def test_mrr_zero_when_exact_below_k():
    assert metrics.mrr_at_k([2, 3, 1], LABELS, k=2) == 0.0


def test_mrr_is_nan_without_exact():
    assert math.isnan(metrics.mrr_at_k([1], {1: "Partial"}))


def test_capped_recall_divides_by_number_of_exact_when_below_k():
    # 2 Exact in the query, 1 found in the top 3.
    assert metrics.capped_recall_at_k([2, UNJUDGED_X, 1], LABELS, k=3) == pytest.approx(0.5)


def test_capped_recall_divides_by_k_when_more_exact_than_k():
    labels = {product_id: "Exact" for product_id in range(10)}
    assert metrics.capped_recall_at_k([0, 1, UNJUDGED_X], labels, k=3) == pytest.approx(2 / 3)


def test_capped_recall_is_one_when_all_exact_found():
    assert metrics.capped_recall_at_k([4, 2, 1], LABELS, k=100) == 1.0


def test_capped_recall_with_partial_as_relevant():
    # 3 relevant (2 Exact + 1 Partial), 2 found.
    value = metrics.capped_recall_at_k([2, 1], LABELS, relevant=metrics.EXACT_AND_PARTIAL)
    assert value == pytest.approx(2 / 3)


def test_capped_recall_is_nan_without_exact():
    assert math.isnan(metrics.capped_recall_at_k([1], {1: "Partial"}))


def test_judged_share_of_returned_products():
    assert metrics.judged_at_k([2, UNJUDGED_X, 1], LABELS) == pytest.approx(2 / 3)


def test_judged_cuts_at_k():
    assert metrics.judged_at_k([UNJUDGED_X, UNJUDGED_Y, 1], LABELS, k=2) == 0.0


def test_judged_is_nan_for_empty_ranking():
    assert math.isnan(metrics.judged_at_k([], LABELS))


@pytest.mark.parametrize(
    "metric",
    [metrics.ndcg_at_k, metrics.condensed_ndcg_at_k, metrics.mrr_at_k,
     metrics.capped_recall_at_k, metrics.judged_at_k],
)
def test_duplicate_product_in_ranking_raises(metric):
    with pytest.raises(ValueError):
        metric([1, 1], LABELS)


def test_labels_by_query_groups_pairs():
    labels = pd.DataFrame(
        {"query_id": [0, 0, 1], "product_id": [10, 11, 10], "label": ["Exact", "Partial", "Irrelevant"]}
    )
    assert metrics.labels_by_query(labels) == {0: {10: "Exact", 11: "Partial"}, 1: {10: "Irrelevant"}}


def test_evaluate_run_and_summarize():
    labels = {0: LABELS, 1: {5: "Partial"}}
    run = {0: [1, 4, 2, 3], 1: [5]}
    per_query = metrics.evaluate_run(run, labels)
    assert list(per_query.index) == [0, 1]
    assert per_query.loc[0, "ndcg@10"] == pytest.approx(1.0)
    assert math.isnan(per_query.loc[1, "mrr@10"])  # query 1 has no Exact
    summary = metrics.summarize(per_query)
    assert summary.loc["ndcg@10", "n_queries"] == 2
    assert summary.loc["mrr@10", "n_queries"] == 1
    assert summary.loc["mrr@10", "mean"] == pytest.approx(1.0)


def test_union_capped_recall_counts_exact_found_by_either_ranking():
    # 8 Exact (1-8); one ranking finds 1-4, the other 3-6: the union finds 6 of 8.
    labels = {product_id: "Exact" for product_id in range(1, 9)} | {50: "Partial"}
    first, second = [1, 2, 3, 4, 50], [3, 4, 5, 6, 99]
    assert metrics.union_capped_recall_at_k([first, second], labels, k=100) == pytest.approx(6 / 8)


def test_union_capped_recall_is_limited_to_k_products():
    labels = {product_id: "Exact" for product_id in range(10)}
    assert metrics.union_capped_recall_at_k([[0, 1, 2], [3, 4, 5]], labels, k=4) == pytest.approx(4 / 4)


def test_union_capped_recall_uses_only_the_first_depth_products():
    labels = {1: "Exact", 2: "Exact"}
    assert metrics.union_capped_recall_at_k([[9, 1], [8, 2]], labels, k=100, depth=1) == 0.0


def test_union_capped_recall_is_nan_without_exact():
    assert math.isnan(metrics.union_capped_recall_at_k([[1]], {1: "Partial"}, k=100))


def test_evaluate_run_extra_ndcg_cutoffs():
    run = {1: [1, 2, 3]}
    labels = {1: {1: "Partial", 3: "Exact"}}
    per_query = metrics.evaluate_run(run, labels, extra_ndcg_cutoffs=(1, 5))
    assert per_query.loc[1, "ndcg@1"] == pytest.approx(1 / 2)
    assert per_query.loc[1, "ndcg@5"] == pytest.approx(metrics.ndcg_at_k([1, 2, 3], labels[1], 5))
    assert "ndcg@5" not in metrics.evaluate_run(run, labels).columns
