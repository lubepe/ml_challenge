import pandas as pd
import pytest

from wands_search import evaluate

QUERIES = pd.DataFrame({"query_id": [3, 1, 2, 4], "query": ["c", "a", "b", "d"]})
SPLIT = pd.Series(["train", "validation", "validation", "test"], index=pd.Index([1, 2, 3, 4], name="query_id"), name="split")
LABELS = {2: {20: "Exact", 21: "Partial"}, 3: {30: "Partial"}}


def fake_search(query: str, k: int) -> list[int]:
    return {"b": [20, 21, 99], "c": [99, 30]}.get(query, [])[:k]


def test_split_queries_returns_one_part_in_query_id_order():
    part = evaluate.split_queries(QUERIES, SPLIT, "validation")
    assert part["query_id"].tolist() == [2, 3]


def test_test_part_is_locked_by_default():
    with pytest.raises(evaluate.TestSetLockedError):
        evaluate.split_queries(QUERIES, SPLIT, "test")


def test_test_part_opens_only_when_allowed():
    assert evaluate.split_queries(QUERIES, SPLIT, "test", allow_test=True)["query_id"].tolist() == [4]


def test_unknown_part_raises():
    with pytest.raises(ValueError):
        evaluate.split_queries(QUERIES, SPLIT, "dev")


def test_load_split_reads_the_versioned_file():
    split = evaluate.load_split()
    assert split.index.name == "query_id"
    assert set(split) == {"train", "validation", "test"}


def test_run_system_keeps_rankings_and_times_each_query():
    queries = evaluate.split_queries(QUERIES, SPLIT, "validation")
    run, latencies = evaluate.run_system(fake_search, queries, k=10)
    assert run == {2: [20, 21, 99], 3: [99, 30]}
    assert list(latencies.index) == [2, 3]
    assert (latencies >= 0).all()


def test_evaluate_system_has_metrics_and_latency():
    queries = evaluate.split_queries(QUERIES, SPLIT, "validation")
    per_query = evaluate.evaluate_system(fake_search, queries, LABELS, k=10)
    assert per_query.loc[2, "ndcg@10"] == pytest.approx(1.0)
    assert per_query.loc[2, "mrr@10"] == 1.0
    assert pd.isna(per_query.loc[3, "mrr@10"])  # no Exact for query 3
    assert "latency_ms" in per_query


def test_summary_table_reports_mean_interval_n_and_latency():
    per_query = pd.DataFrame({"ndcg@10": [0.2, 0.4, 0.6], "mrr@10": [1.0, None, 0.5], "latency_ms": [1.0, 2.0, 3.0]})
    table = evaluate.summary_table(per_query)
    assert table.loc["ndcg@10", "mean"] == pytest.approx(0.4)
    assert table.loc["ndcg@10", "ci_low"] <= 0.4 <= table.loc["ndcg@10", "ci_high"]
    assert table.loc["mrr@10", "n_queries"] == 2
    assert table.loc["latency_ms_p50", "mean"] == 2.0


def test_paired_bootstrap_detects_a_constant_improvement():
    index = pd.Index(range(50), name="query_id")
    base = pd.DataFrame({"ndcg@10": [i / 100 for i in range(50)]}, index=index)
    better = base + 0.05
    result = evaluate.paired_bootstrap(better, base, "ndcg@10")
    assert result["mean_difference"] == pytest.approx(0.05)
    assert result["ci_low"] == pytest.approx(0.05) and result["ci_high"] == pytest.approx(0.05)
    assert result["share_a_better"] == 1.0
    assert result["n_queries"] == 50


def test_paired_bootstrap_is_reproducible():
    index = pd.Index(range(30), name="query_id")
    a = pd.DataFrame({"m": [(i * 7) % 10 / 10 for i in range(30)]}, index=index)
    b = pd.DataFrame({"m": [(i * 3) % 10 / 10 for i in range(30)]}, index=index)
    assert evaluate.paired_bootstrap(a, b, "m") == evaluate.paired_bootstrap(a, b, "m")


def test_paired_bootstrap_requires_the_same_queries():
    a = pd.DataFrame({"m": [0.1, 0.2]}, index=[1, 2])
    b = pd.DataFrame({"m": [0.1, 0.2]}, index=[1, 3])
    with pytest.raises(ValueError):
        evaluate.paired_bootstrap(a, b, "m")


def test_select_tuned_uses_tie_break_within_tolerance():
    results = pd.DataFrame({
        "k1": [0.9, 1.2, 1.5],
        "b": [0.5, 0.5, 0.5],
        "capped_recall@100": [0.700, 0.698, 0.650],
        "ndcg@10": [0.60, 0.65, 0.90],
    })
    chosen = evaluate.select_tuned(results)
    assert (chosen["k1"], chosen["b"]) == (1.2, 0.5)  # 0.698 is within 0.005 of 0.700; 0.650 is not


def test_select_tuned_picks_best_metric_when_no_tie():
    results = pd.DataFrame({"k1": [0.9, 1.2], "b": [0.5, 0.5], "capped_recall@100": [0.70, 0.60], "ndcg@10": [0.1, 0.9]})
    assert evaluate.select_tuned(results)["k1"] == 0.9


def test_tune_bm25_returns_one_row_per_combination():
    tokens = pd.Series([["leather", "chair"], ["wood", "table"], ["chair", "cushion"]], index=[20, 21, 30])
    queries = evaluate.split_queries(pd.DataFrame({"query_id": [2], "query": ["leather chair"]}),
                                     pd.Series(["train"], index=pd.Index([2], name="query_id")), "train")
    results, per_query = evaluate.tune_bm25(tokens, False, queries, LABELS, k1_grid=(0.9, 1.2), b_grid=(0.5, 0.75), k=10)
    assert len(results) == 4
    assert {"k1", "b", "capped_recall@100", "ndcg@10"} <= set(results.columns)
    assert set(per_query) == {(0.9, 0.5), (0.9, 0.75), (1.2, 0.5), (1.2, 0.75)}
    assert list(per_query[(0.9, 0.5)].index) == [2]


def test_format_ci():
    assert evaluate.format_ci(0.6534, 0.5891, 0.7183) == "0.653 [0.589; 0.718]"


def test_compare_systems_reports_both_systems_and_the_difference():
    index = pd.Index(range(40), name="query_id")
    base = pd.DataFrame({"ndcg@10": [i / 50 for i in range(40)]}, index=index)
    better = base + 0.05
    table = evaluate.compare_systems(better, base, ["ndcg@10"], name_a="v2", name_b="baseline")
    row = table.loc["ndcg@10"]
    assert row["difference"] == pytest.approx(0.05)
    assert row["interval_excludes_0"]
    assert row["difference_ci"] == "0.050 [0.050; 0.050]"
    assert row["share_v2_better"] == 1.0
    assert {"v2_ci", "baseline_ci"} <= set(table.columns)
