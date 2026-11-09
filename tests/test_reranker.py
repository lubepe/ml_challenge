import numpy as np
import pandas as pd
import pytest

from wands_search import ranking, reranker

N_QUERIES, N_CANDIDATES = 20, 12
FEATURES = ["signal", "noise"]
SMALL_GRID = [{"num_leaves": 4, "learning_rate": 0.1, "min_data_in_leaf": 2}]


def synthetic():
    """Queries whose gain follows the feature "signal"; the retrieval order is random."""
    rng = np.random.default_rng(0)
    run, labels, rows = {}, {}, []
    for query_id in range(1, N_QUERIES + 1):
        product_ids = list(rng.permutation(np.arange(100, 100 + N_CANDIDATES)) + 1000 * query_id)
        run[query_id] = product_ids
        signal = rng.random(N_CANDIDATES)
        query_labels = {}
        for rank, (product_id, value) in enumerate(zip(product_ids, signal), start=1):
            label = "Exact" if value > 0.7 else "Partial" if value > 0.4 else "Irrelevant"
            if rank % 4 != 0:  # one candidate in four stays without label
                query_labels[int(product_id)] = label
            rows.append({"query_id": query_id, "product_id": int(product_id), "signal": value, "noise": rng.random()})
        labels[query_id] = query_labels
    candidates = ranking.candidate_table(run, labels).merge(pd.DataFrame(rows), on=["query_id", "product_id"])
    return run, labels, candidates


def test_model_grid_has_every_combination():
    grid = reranker.model_grid()
    assert len(grid) == 3 * 2 * 2
    assert len({tuple(sorted(params.items())) for params in grid}) == len(grid)


def test_fit_learns_the_signal_and_is_reproducible():
    _, _, candidates = synthetic()
    examples = ranking.training_examples(candidates, "drop")
    model = reranker.fit(examples, FEATURES, SMALL_GRID[0], n_estimators=50)
    again = reranker.fit(examples, FEATURES, SMALL_GRID[0], n_estimators=50)
    scores = reranker.predict(model, candidates, FEATURES)
    assert np.array_equal(scores, reranker.predict(again, candidates, FEATURES))
    assert np.corrcoef(scores, candidates["signal"])[0, 1] > 0.8


def test_fewer_trees_use_the_first_trees_of_the_model():
    _, _, candidates = synthetic()
    examples = ranking.training_examples(candidates, "drop")
    big = reranker.fit(examples, FEATURES, SMALL_GRID[0], n_estimators=30)
    small = reranker.fit(examples, FEATURES, SMALL_GRID[0], n_estimators=10)
    assert np.allclose(reranker.predict(big, candidates, FEATURES, 10), reranker.predict(small, candidates, FEATURES))


def test_rerank_run_orders_by_score_and_checks_candidates():
    run = {1: [5, 6, 7, 8]}
    candidates = ranking.candidate_table(run, {}, k=3)
    assert reranker.rerank_run(run, candidates, np.array([0.1, 0.3, 0.2]), k=3) == {1: [6, 7, 5, 8]}
    with pytest.raises(ValueError):
        reranker.rerank_run({1: [6, 5, 7, 8]}, candidates, np.array([0.1, 0.3, 0.2]), k=3)


def test_query_folds_keep_each_query_in_one_fold():
    folds = reranker.query_folds(range(1, 23), n_folds=5)
    assert folds.index.tolist() == list(range(1, 23))
    assert set(folds) == set(range(5))
    assert folds.value_counts().max() - folds.value_counts().min() <= 1
    assert folds.equals(reranker.query_folds(range(1, 23), n_folds=5))


def test_cross_validate_scores_every_held_out_query_once_per_combination():
    run, labels, candidates = synthetic()
    folds = reranker.query_folds(run, n_folds=4)
    per_query = reranker.cross_validate(candidates, run, labels, FEATURES, folds, grid=SMALL_GRID, n_estimators=[5, 20])
    assert len(per_query) == N_QUERIES * 2 * 2  # 2 rules x 2 tree counts
    assert per_query.groupby(reranker.COMBINATION_COLUMNS)["query_id"].nunique().eq(N_QUERIES).all()
    summary = reranker.summarize_cv(per_query)
    assert len(summary) == 4
    # The model beats the random retrieval order.
    random_order = np.mean([ranking_metric for ranking_metric in
                            reranker.metrics.evaluate_run(run, labels)["ndcg@10"]])
    assert summary["ndcg@10"].max() > random_order


def test_select_combination_prefers_fewer_trees_then_fewer_leaves_within_the_margin():
    summary = pd.DataFrame({
        "unlabeled": ["zero", "drop", "zero", "drop"],
        "num_leaves": [63, 15, 31, 15],
        "learning_rate": [0.1] * 4,
        "min_data_in_leaf": [20] * 4,
        "n_estimators": [500, 300, 100, 100],
        "ndcg@10": [0.800, 0.799, 0.797, 0.790],
    })
    chosen = reranker.select_combination(summary)
    assert (chosen["n_estimators"], chosen["num_leaves"]) == (100, 31)
    assert reranker.combination_params(chosen) == {"num_leaves": 31, "learning_rate": 0.1, "min_data_in_leaf": 20}


def test_pointwise_baseline_learns_the_signal():
    _, _, candidates = synthetic()
    examples = ranking.training_examples(candidates, "zero")
    model = reranker.fit(examples, FEATURES, SMALL_GRID[0], n_estimators=50, objective="regression")
    scores = reranker.predict(model, candidates, FEATURES)
    assert np.corrcoef(scores, candidates["signal"])[0, 1] > 0.8
    with pytest.raises(ValueError):
        reranker.make_model(SMALL_GRID[0], objective="binary")


def test_rerank_run_keeps_queries_without_results():
    run = {1: [5, 6], 2: []}
    candidates = ranking.candidate_table(run, {})
    assert reranker.rerank_run(run, candidates, np.array([0.1, 0.9])) == {2: [], 1: [6, 5]}


def test_out_of_fold_scores_match_cross_validate():
    run, labels, candidates = synthetic()
    folds = reranker.query_folds(run, n_folds=4)
    scores = reranker.out_of_fold_scores(candidates, FEATURES, folds, "zero", SMALL_GRID[0], 20)
    assert not np.isnan(scores).any()
    from_scores = reranker.metrics.evaluate_run(reranker.rerank_run(run, candidates, scores), labels)["ndcg@10"]
    per_query = reranker.cross_validate(candidates, run, labels, FEATURES, folds, unlabeled_rules=["zero"],
                                        grid=SMALL_GRID, n_estimators=[20]).set_index("query_id")["ndcg@10"]
    assert from_scores.sort_index().tolist() == pytest.approx(per_query.sort_index().tolist())


class FakeBuilder:
    def __init__(self):
        self.calls = []

    def query_features(self, query, product_ids, use_embeddings=True):
        self.calls.append((query, list(product_ids), use_embeddings))
        return pd.DataFrame({"signal": np.linspace(0, 1, len(product_ids)), "noise": 0.0})


def test_ranking_latency_times_every_query_and_skips_empty_runs():
    _, _, candidates = synthetic()
    model = reranker.fit(ranking.training_examples(candidates, "drop"), FEATURES, SMALL_GRID[0], n_estimators=5)
    builder = FakeBuilder()
    queries = pd.DataFrame({"query_id": [1, 2, 3], "query": ["a", "b", "c"]})
    run = {1: [10, 11, 12], 2: [], 3: [13]}
    latency = reranker.ranking_latency(builder, model, FEATURES, run, queries, use_embeddings=False, k=2, warmup_queries=1)
    assert latency.index.tolist() == [1, 2, 3] and (latency >= 0).all()
    assert builder.calls[0] == ("a", [10, 11], False)  # warm-up, cut at k
    assert [call[0] for call in builder.calls[1:]] == ["a", "c"]  # query 2 has no candidates


def test_evaluate_scores_adds_the_sensitivity_cutoffs():
    run, labels, candidates = synthetic()
    per_query = reranker.evaluate_scores(run, candidates, candidates["signal"].to_numpy(), labels)
    assert {"ndcg@5", "ndcg@10", "ndcg@15"} <= set(per_query.columns)
    assert len(per_query) == N_QUERIES


def test_save_and_load_model_give_the_same_scores(tmp_path):
    _, _, candidates = synthetic()
    model = reranker.fit(ranking.training_examples(candidates, "zero"), FEATURES, SMALL_GRID[0], n_estimators=10)
    reranker.save_model(model, tmp_path, "toy", {"retrieval": "toy"})
    booster, metadata = reranker.load_model("toy", tmp_path)
    assert metadata["feature_columns"] == FEATURES and metadata["retrieval"] == "toy"
    assert np.allclose(reranker.predict(booster, candidates, FEATURES), reranker.predict(model, candidates, FEATURES))


def test_load_model_rejects_mismatched_features(tmp_path):
    _, _, candidates = synthetic()
    model = reranker.fit(ranking.training_examples(candidates, "zero"), FEATURES, SMALL_GRID[0], n_estimators=5)
    reranker.save_model(model, tmp_path, "toy", {})
    path = tmp_path / "toy.json"
    path.write_text(path.read_text().replace('"noise"', '"other"'))
    with pytest.raises(ValueError):
        reranker.load_model("toy", tmp_path)


def test_saved_models_use_known_features_and_retrievals():
    assert reranker.SELECTED_MODEL in reranker.SAVED_MODELS
    for spec in reranker.SAVED_MODELS.values():
        assert spec["retrieval"] in reranker.CHOSEN_COMBINATIONS
        assert set(spec["features"]) <= set(reranker.features.ALL_FEATURES)
    assert "cross_encoder_score" not in reranker.SAVED_MODELS[reranker.SELECTED_MODEL]["features"]
