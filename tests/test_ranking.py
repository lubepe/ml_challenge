import math

import pytest

from wands_search import ranking

LABELS = {
    1: {10: "Exact", 20: "Irrelevant", 30: "Partial"},
    2: {50: "Irrelevant"},
}
RUN = {1: [10, 40, 20, 30], 2: [50, 60]}


def test_candidate_table_columns_and_labels():
    candidates = ranking.candidate_table(RUN, LABELS)
    assert list(candidates.columns) == ["query_id", "product_id", "retrieval_rank", "label", "gain"]
    query_1 = candidates[candidates["query_id"] == 1]
    assert query_1["product_id"].tolist() == [10, 40, 20, 30]
    assert query_1["retrieval_rank"].tolist() == [1, 2, 3, 4]
    assert query_1["label"].tolist() == ["Exact", ranking.NO_LABEL, "Irrelevant", "Partial"]
    gains = query_1["gain"].tolist()
    assert gains[0] == 2 and math.isnan(gains[1]) and gains[2:] == [0, 1]


def test_candidate_table_cuts_at_k():
    candidates = ranking.candidate_table(RUN, LABELS, k=2)
    assert candidates.groupby("query_id").size().tolist() == [2, 2]


def test_candidate_table_query_without_labels():
    candidates = ranking.candidate_table({3: [10, 20]}, LABELS)
    assert candidates["label"].tolist() == [ranking.NO_LABEL] * 2


def test_candidate_table_rejects_repeated_products():
    with pytest.raises(ValueError):
        ranking.candidate_table({1: [10, 10]}, LABELS)


def test_training_examples_drop_removes_unlabeled_and_queries_without_positive():
    examples = ranking.training_examples(ranking.candidate_table(RUN, LABELS), unlabeled="drop")
    # Query 2 has only an Irrelevant pair and is removed.
    assert examples["query_id"].unique().tolist() == [1]
    assert examples["product_id"].tolist() == [10, 20, 30]
    assert examples["gain"].tolist() == [2, 0, 1]


def test_training_examples_zero_keeps_unlabeled_with_gain_0():
    examples = ranking.training_examples(ranking.candidate_table(RUN, LABELS), unlabeled="zero")
    assert examples["product_id"].tolist() == [10, 40, 20, 30]
    assert examples["gain"].tolist() == [2, 0, 0, 1]


def test_training_examples_rejects_unknown_rule():
    with pytest.raises(ValueError):
        ranking.training_examples(ranking.candidate_table(RUN, LABELS), unlabeled="keep")


def test_rerank_orders_top_k_and_keeps_the_rest():
    assert ranking.rerank([1, 2, 3, 4, 5], [0.1, 0.9, 0.5], k=3) == [2, 3, 1, 4, 5]


def test_rerank_ties_keep_retrieval_order():
    assert ranking.rerank([1, 2, 3], [0.5, 0.5, 0.7]) == [3, 1, 2]


def test_rerank_short_list():
    assert ranking.rerank([7, 8], [0.0, 1.0], k=100) == [8, 7]


def test_rerank_rejects_wrong_number_of_scores():
    with pytest.raises(ValueError):
        ranking.rerank([1, 2, 3], [0.1, 0.2], k=3)
