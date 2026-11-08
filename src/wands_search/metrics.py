"""Per-query evaluation metrics, as defined in ``docs/EVALUATION.md``.

Every metric takes the ranked list of ``product_id`` returned for one query and the
judged labels of that query (``{product_id: label}``). A product without a label for
the query is unjudged: it has gain 0 and is never relevant.
"""

import math
from collections.abc import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

GAINS = {"Exact": 2, "Partial": 1, "Irrelevant": 0}
EXACT_ONLY = frozenset({"Exact"})
EXACT_AND_PARTIAL = frozenset({"Exact", "Partial"})

QueryLabels = Mapping[int, str]


def _check_ranking(ranking: Sequence[int]) -> None:
    if len(set(ranking)) != len(ranking):
        raise ValueError("ranking contains the same product_id more than once")


def dcg(gains: Iterable[float]) -> float:
    """Discounted cumulative gain with linear gains: sum of gain / log2(position + 1)."""
    return sum(gain / math.log2(position + 1) for position, gain in enumerate(gains, start=1))


def ndcg_at_k(ranking: Sequence[int], labels: QueryLabels, k: int = 10) -> float:
    """NDCG@k with gains Exact = 2, Partial = 1, Irrelevant = 0 and unjudged = 0.

    The ideal ordering uses every judged product of the query. Returns NaN when the
    query has no product with positive gain, since the metric is undefined there.
    """
    _check_ranking(ranking)
    ideal = dcg(sorted((GAINS[label] for label in labels.values()), reverse=True)[:k])
    if ideal == 0:
        return math.nan
    gains = [GAINS.get(labels.get(product_id), 0) for product_id in ranking[:k]]
    return dcg(gains) / ideal


def condensed_ndcg_at_k(ranking: Sequence[int], labels: QueryLabels, k: int = 10) -> float:
    """NDCG@k on the condensed list: unjudged products are removed before cutting at k.

    Shows how much the main NDCG@k depends on giving gain 0 to unjudged products
    (Sakai, 2007, "Alternatives to Bpref").
    """
    _check_ranking(ranking)
    judged = [product_id for product_id in ranking if product_id in labels]
    return ndcg_at_k(judged, labels, k)


def mrr_at_k(
    ranking: Sequence[int], labels: QueryLabels, k: int = 10, relevant: frozenset[str] = EXACT_ONLY
) -> float:
    """Reciprocal rank of the first relevant product in the top k (0 if none).

    Returns NaN when the query has no relevant product, so it is left out of the mean.
    """
    _check_ranking(ranking)
    if not any(label in relevant for label in labels.values()):
        return math.nan
    for position, product_id in enumerate(ranking[:k], start=1):
        if labels.get(product_id) in relevant:
            return 1 / position
    return 0.0


def capped_recall_at_k(
    ranking: Sequence[int], labels: QueryLabels, k: int = 100, relevant: frozenset[str] = EXACT_ONLY
) -> float:
    """Relevant products in the top k divided by min(k, number of relevant products).

    Returns NaN when the query has no relevant product, so it is left out of the mean.
    """
    _check_ranking(ranking)
    n_relevant = sum(label in relevant for label in labels.values())
    if n_relevant == 0:
        return math.nan
    hits = sum(labels.get(product_id) in relevant for product_id in ranking[:k])
    return hits / min(k, n_relevant)


def judged_at_k(ranking: Sequence[int], labels: QueryLabels, k: int = 10) -> float:
    """Share of the returned products in the top k that have a label for the query.

    The denominator is the number of products returned in the top k, which is below k
    only when the system returns fewer than k products. Returns NaN for an empty ranking.
    """
    _check_ranking(ranking)
    top = ranking[:k]
    if not top:
        return math.nan
    return sum(product_id in labels for product_id in top) / len(top)


def query_metrics(ranking: Sequence[int], labels: QueryLabels) -> dict[str, float]:
    """All metrics of the evaluation protocol for one query."""
    return {
        "ndcg@10": ndcg_at_k(ranking, labels, 10),
        "mrr@10": mrr_at_k(ranking, labels, 10),
        "capped_recall@50": capped_recall_at_k(ranking, labels, 50),
        "capped_recall@100": capped_recall_at_k(ranking, labels, 100),
        "capped_recall@200": capped_recall_at_k(ranking, labels, 200),
        "capped_recall@100_exact_partial": capped_recall_at_k(
            ranking, labels, 100, relevant=EXACT_AND_PARTIAL
        ),
        "judged@10": judged_at_k(ranking, labels, 10),
        "condensed_ndcg@10": condensed_ndcg_at_k(ranking, labels, 10),
    }


def labels_by_query(labels: pd.DataFrame) -> dict[int, dict[int, str]]:
    """Group a deduplicated label table into ``{query_id: {product_id: label}}``."""
    return {
        query_id: dict(zip(group["product_id"], group["label"]))
        for query_id, group in labels.groupby("query_id")
    }


def evaluate_run(
    run: Mapping[int, Sequence[int]], labels: Mapping[int, QueryLabels]
) -> pd.DataFrame:
    """One row per query of ``run`` with every metric. NaN marks a metric undefined for the query."""
    rows = {query_id: query_metrics(ranking, labels.get(query_id, {})) for query_id, ranking in run.items()}
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("query_id")


def summarize(per_query: pd.DataFrame) -> pd.DataFrame:
    """Mean over queries and number of queries where each metric is defined."""
    return pd.DataFrame({"mean": per_query.mean(), "n_queries": per_query.count()})


def bootstrap_mean_ci(
    values: pd.Series, seed: int, n_resamples: int = 2000, level: float = 0.95
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval of the mean, resampling ``values`` with replacement."""
    rng = np.random.default_rng(seed)
    array = values.to_numpy()
    means = rng.choice(array, size=(n_resamples, len(array))).mean(axis=1)
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(means, [tail, 100 - tail])
    return float(low), float(high)
