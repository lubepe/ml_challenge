"""LambdaMART reranker (LightGBM): training, tuning by GroupKFold on the train set, and reranking.

Decisions in docs/EVALUATION.md, section "Reranker (learning-to-rank)".
"""

import itertools
import json
import time
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from wands_search import features, metrics, ranking
from wands_search.metrics import QueryLabels

RANKER_SEED = 0
N_FOLDS = 5
LABEL_GAIN = [0, 1, 2]
TRUNCATION_LEVEL = 10
SIMPLER_MARGIN = 0.005

# Grid fixed before any number of the reranker. n_estimators is read from one model of
# MAX_ESTIMATORS trees, predicting with its first trees only.
PARAM_GRID = {
    "num_leaves": [15, 31, 63],
    "learning_rate": [0.05, 0.1],
    "min_data_in_leaf": [20, 50],
}
N_ESTIMATORS = [100, 300, 500]
MAX_ESTIMATORS = max(N_ESTIMATORS)


def model_grid() -> list[dict]:
    """Every combination of ``PARAM_GRID`` (the parameters that need their own training)."""
    keys = list(PARAM_GRID)
    return [dict(zip(keys, values)) for values in itertools.product(*PARAM_GRID.values())]


OBJECTIVES = ("lambdarank", "regression")


def make_model(params: Mapping, n_estimators: int = MAX_ESTIMATORS, seed: int = RANKER_SEED,
               objective: str = "lambdarank") -> lgb.LGBMModel:
    """LightGBM with the fixed settings of the protocol and the given ``params``.

    ``"lambdarank"`` is the LambdaMART reranker; ``"regression"`` is the pointwise baseline,
    which predicts the gain of each product alone.
    """
    if objective not in OBJECTIVES:
        raise ValueError(f"objective must be one of {OBJECTIVES}, got {objective!r}")
    common = dict(
        n_estimators=n_estimators,
        random_state=seed,
        deterministic=True,
        force_row_wise=True,
        n_jobs=1,
        verbose=-1,
        **params,
    )
    if objective == "regression":
        return lgb.LGBMRegressor(objective="regression", **common)
    return lgb.LGBMRanker(
        objective="lambdarank", label_gain=LABEL_GAIN, lambdarank_truncation_level=TRUNCATION_LEVEL, **common
    )


def fit(examples: pd.DataFrame, feature_columns: Sequence[str], params: Mapping,
        n_estimators: int = MAX_ESTIMATORS, seed: int = RANKER_SEED, objective: str = "lambdarank") -> lgb.LGBMModel:
    """Train on ``ranking.training_examples`` rows: the gain is the target, one group per query (LambdaMART only)."""
    examples = examples.sort_values(["query_id", "retrieval_rank"])
    model = make_model(params, n_estimators, seed, objective)
    if objective == "regression":
        model.fit(examples[list(feature_columns)], examples["gain"].astype(float))
    else:
        group_sizes = examples.groupby("query_id", sort=False).size().to_numpy()
        model.fit(examples[list(feature_columns)], examples["gain"].astype(int), group=group_sizes)
    return model


def predict(model: lgb.LGBMModel, rows: pd.DataFrame, feature_columns: Sequence[str],
            n_estimators: int | None = None) -> np.ndarray:
    """Score of each row; ``n_estimators`` uses only the first trees of the model."""
    return model.predict(rows[list(feature_columns)], num_iteration=n_estimators)


def rerank_run(run: Mapping[int, Sequence[int]], candidates: pd.DataFrame, scores: np.ndarray,
               k: int = ranking.CANDIDATES_K) -> dict[int, list[int]]:
    """Final list of each query of ``candidates``: the top ``k`` of ``run`` by ``scores``, then the rest of ``run``.

    ``candidates`` has the top ``k`` of ``run`` for each query, ordered by query and ``retrieval_rank``
    (as ``ranking.candidate_table``), and ``scores`` has one value per row.
    """
    scored = candidates[["query_id", "product_id"]].assign(score=scores)
    # A query whose retrieval returned nothing has no candidates; it keeps its empty list, so the
    # metrics count it (as 0) for the reranker too.
    reranked = {query_id: [] for query_id, ranking_list in run.items() if len(ranking_list) == 0}
    for query_id, group in scored.groupby("query_id", sort=False):
        ranking_list = list(run[query_id])
        if group["product_id"].tolist() != ranking_list[:k]:
            raise ValueError(f"query {query_id}: candidates do not match the top {k} of the run")
        reranked[query_id] = ranking.rerank(ranking_list, group["score"].to_numpy(), k)
    return reranked


def query_folds(query_ids: Sequence[int], n_folds: int = N_FOLDS, seed: int = RANKER_SEED) -> pd.Series:
    """Fold (0 to ``n_folds - 1``) of each query; each query stays whole in one fold."""
    query_ids = np.asarray(sorted(set(query_ids)))
    folds = pd.Series(-1, index=query_ids, name="fold")
    splitter = GroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    for fold, (_, held_out) in enumerate(splitter.split(query_ids, groups=query_ids)):
        folds.iloc[held_out] = fold
    return folds


def cross_validate(candidates: pd.DataFrame, run: Mapping[int, Sequence[int]], labels: Mapping[int, QueryLabels],
                   feature_columns: Sequence[str], folds: pd.Series,
                   unlabeled_rules: Sequence[ranking.UnlabeledRule] = ranking.UNLABELED_RULES,
                   grid: Sequence[Mapping] | None = None,
                   n_estimators: Sequence[int] = N_ESTIMATORS) -> pd.DataFrame:
    """Out-of-fold metrics of every combination, one row per (combination, query).

    For each fold, the model trains on the other folds (rows chosen by ``unlabeled``) and orders
    all the candidates of the held-out queries, unlabeled ones included.
    """
    grid = model_grid() if grid is None else list(grid)
    candidate_folds = candidates["query_id"].map(folds)
    if candidate_folds.isna().any():
        raise ValueError("every candidate query needs a fold")
    frames = []
    for fold in sorted(folds.unique()):
        held_out = candidates[candidate_folds == fold]
        for rule in unlabeled_rules:
            examples = ranking.training_examples(candidates[candidate_folds != fold], rule)
            for params in grid:
                model = fit(examples, feature_columns, params, n_estimators=max(n_estimators))
                for trees in n_estimators:
                    reranked = rerank_run(run, held_out, predict(model, held_out, feature_columns, trees))
                    per_query = metrics.evaluate_run(reranked, labels)
                    frames.append(per_query.reset_index().assign(
                        fold=fold, unlabeled=rule, n_estimators=trees, **params))
    return pd.concat(frames, ignore_index=True)


COMBINATION_COLUMNS = ["unlabeled", *PARAM_GRID, "n_estimators"]


def summarize_cv(per_query: pd.DataFrame) -> pd.DataFrame:
    """Mean of each metric over all held-out queries, one row per combination."""
    return (per_query.groupby(COMBINATION_COLUMNS)[["ndcg@10", "condensed_ndcg@10", "mrr@10"]]
            .mean().reset_index().sort_values("ndcg@10", ascending=False, ignore_index=True))


def select_combination(summary: pd.DataFrame, margin: float = SIMPLER_MARGIN) -> pd.Series:
    """Highest ``ndcg@10``; among combinations less than ``margin`` below it, the fewest trees, then the fewest leaves."""
    best = summary["ndcg@10"].max()
    close = summary[summary["ndcg@10"] > best - margin]
    return close.sort_values(["n_estimators", "num_leaves", "ndcg@10"], ascending=[True, True, False]).iloc[0]


def combination_params(combination: Mapping) -> dict:
    """LightGBM parameters of a row of ``summarize_cv``, without ``n_estimators`` and ``unlabeled``."""
    return {key: combination[key].item() if hasattr(combination[key], "item") else combination[key] for key in PARAM_GRID}


def out_of_fold_scores(candidates: pd.DataFrame, feature_columns: Sequence[str], folds: pd.Series,
                       unlabeled: ranking.UnlabeledRule, params: Mapping, n_estimators: int,
                       objective: str = "lambdarank") -> np.ndarray:
    """Score of every candidate from the model trained on the other folds, aligned with the rows of ``candidates``."""
    candidate_folds = candidates["query_id"].map(folds)
    if candidate_folds.isna().any():
        raise ValueError("every candidate query needs a fold")
    scores = np.full(len(candidates), np.nan)
    for fold in sorted(folds.unique()):
        held_out = (candidate_folds == fold).to_numpy()
        examples = ranking.training_examples(candidates[~held_out], unlabeled)
        model = fit(examples, feature_columns, params, n_estimators, objective=objective)
        scores[held_out] = predict(model, candidates[held_out], feature_columns)
    return scores


def ranking_latency(builder, model: lgb.LGBMModel, feature_columns: Sequence[str], run: Mapping[int, Sequence[int]],
                    queries: pd.DataFrame, use_embeddings: bool = True, k: int = ranking.CANDIDATES_K,
                    warmup_queries: int = 20) -> pd.Series:
    """Milliseconds to compute the features of the top ``k`` of ``run`` and score them, per query (retrieval not included).

    ``builder`` is a ``features.FeatureBuilder``; its ``cross_encoder`` decides whether the
    cross-encoder runs. The first ``warmup_queries`` queries run once untimed. A query without
    candidates takes no ranking time and is timed as such.
    """
    texts = dict(zip(queries["query_id"], queries["query"]))

    def rank_once(query_id):
        top = list(run[query_id])[:k]
        if top:
            rows = builder.query_features(texts[query_id], top, use_embeddings=use_embeddings)
            predict(model, rows, feature_columns)

    for query_id in list(texts)[:warmup_queries]:
        rank_once(query_id)
    latencies = {}
    for query_id in texts:
        start = time.perf_counter()
        rank_once(query_id)
        latencies[query_id] = (time.perf_counter() - start) * 1000
    return pd.Series(latencies, name="latency_ms").rename_axis("query_id")


def evaluate_scores(run: Mapping[int, Sequence[int]], candidates: pd.DataFrame, scores: np.ndarray,
                    labels: Mapping[int, QueryLabels],
                    extra_ndcg_cutoffs: Sequence[int] = metrics.SENSITIVITY_NDCG_CUTOFFS) -> pd.DataFrame:
    """Metrics of each query after reranking the candidates of ``run`` by ``scores`` (see ``rerank_run``)."""
    return metrics.evaluate_run(rerank_run(run, candidates, scores), labels, extra_ndcg_cutoffs)


# Combinations chosen by GroupKFold on the train set (notebooks/04_reranker.ipynb, Etapa 3.1).
CHOSEN_COMBINATIONS = {
    "BM25 v2": {"unlabeled": "zero", "num_leaves": 15, "learning_rate": 0.1, "min_data_in_leaf": 50, "n_estimators": 100},
    "hybrid": {"unlabeled": "zero", "num_leaves": 15, "learning_rate": 0.1, "min_data_in_leaf": 20, "n_estimators": 100},
}
_WITHOUT_CROSS_ENCODER = [f for f in features.ALL_FEATURES if f not in features.FEATURE_GROUPS["cross_encoder"]]
# Models saved by ``python -m wands_search.train_reranker``: name -> retrieval and feature columns.
# The selected system is hybrid_reranker_no_cross_encoder (docs/EVALUATION.md, "Seleção e teste").
SAVED_MODELS = {
    "bm25_v2_reranker": {"retrieval": "BM25 v2", "features": features.LEXICAL_RERANKER_FEATURES},
    "bm25_v2_reranker_no_cross_encoder": {
        "retrieval": "BM25 v2",
        "features": [f for f in features.LEXICAL_RERANKER_FEATURES if f not in features.FEATURE_GROUPS["cross_encoder"]],
    },
    "hybrid_reranker": {"retrieval": "hybrid", "features": features.ALL_FEATURES},
    "hybrid_reranker_no_cross_encoder": {"retrieval": "hybrid", "features": _WITHOUT_CROSS_ENCODER},
}
SELECTED_MODEL = "hybrid_reranker_no_cross_encoder"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[2] / "models"


def save_model(model: lgb.LGBMModel, directory: Path, name: str, metadata: Mapping) -> Path:
    """Write the LightGBM model to ``directory/name.txt`` and ``metadata`` (with the feature columns) to ``name.json``."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    booster = model.booster_ if hasattr(model, "booster_") else model
    booster.save_model(str(directory / f"{name}.txt"))
    full_metadata = {"name": name, "lightgbm_version": lgb.__version__, "saved_on": date.today().isoformat(), **metadata,
                     "feature_columns": list(booster.feature_name())}
    (directory / f"{name}.json").write_text(json.dumps(full_metadata, indent=2, ensure_ascii=False) + "\n")
    return directory / f"{name}.txt"


def load_model(name: str, directory: Path = DEFAULT_MODEL_DIR) -> tuple[lgb.Booster, dict]:
    """Model saved by ``save_model`` and its metadata. ``predict`` works with the returned ``lgb.Booster``."""
    directory = Path(directory)
    metadata = json.loads((directory / f"{name}.json").read_text())
    booster = lgb.Booster(model_file=str(directory / f"{name}.txt"))
    if list(booster.feature_name()) != metadata["feature_columns"]:
        raise ValueError(f"model {name}: the feature columns of the model and of the metadata differ")
    return booster, metadata
