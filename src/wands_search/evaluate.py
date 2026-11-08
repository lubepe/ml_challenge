"""Run a search system on one part of the split and compute the metrics of docs/EVALUATION.md.

The test part is locked: it runs only with ``allow_test=True``, once, at the end of the
project (see "Seleção e teste" in docs/EVALUATION.md).
"""

import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from wands_search import metrics
from wands_search.split import DEFAULT_SPLIT_PATH

# K candidates passed from retrieval to ranking, and the bootstrap of the protocol.
RETRIEVAL_K = 200  # metrics need the top 200 for Capped Recall@200; ranking uses the top 100
BOOTSTRAP_SEED = 0
BOOTSTRAP_RESAMPLES = 2000
WARMUP_QUERIES = 20

# A system takes the raw query text and K, and returns product_ids in rank order.
SearchFunction = Callable[[str, int], list[int]]


class TestSetLockedError(RuntimeError):
    """Raised when the test part is requested without ``allow_test=True``."""


def load_split(path: Path = DEFAULT_SPLIT_PATH) -> pd.Series:
    """Part (``train``, ``validation`` or ``test``) of each ``query_id``."""
    return pd.read_csv(path, index_col="query_id")["split"]


def split_queries(queries: pd.DataFrame, split: pd.Series, part: str, allow_test: bool = False) -> pd.DataFrame:
    """Queries of one part, ordered by ``query_id``. The test part needs ``allow_test=True``."""
    if part == "test" and not allow_test:
        raise TestSetLockedError("the test part runs once, at the end; pass allow_test=True")
    if part not in set(split):
        raise ValueError(f"unknown part {part!r}")
    query_ids = split.index[split == part]
    return queries[queries["query_id"].isin(query_ids)].sort_values("query_id").reset_index(drop=True)


def run_system(search: SearchFunction, queries: pd.DataFrame, k: int = RETRIEVAL_K) -> tuple[dict[int, list[int]], pd.Series]:
    """Run ``search`` on every query and time each call, after ``WARMUP_QUERIES`` untimed calls.

    Returns the ranking of each ``query_id`` and the latency of each call in milliseconds.
    """
    for query_text in queries["query"].head(WARMUP_QUERIES):
        search(query_text, k)
    run, latencies = {}, {}
    for query_id, query_text in zip(queries["query_id"], queries["query"]):
        start = time.perf_counter()
        run[query_id] = list(search(query_text, k))
        latencies[query_id] = (time.perf_counter() - start) * 1000
    return run, pd.Series(latencies, name="latency_ms").rename_axis("query_id")


def evaluate_system(
    search: SearchFunction,
    queries: pd.DataFrame,
    labels: dict[int, dict[int, str]],
    k: int = RETRIEVAL_K,
) -> pd.DataFrame:
    """Metrics and latency of ``search``, one row per query."""
    run, latencies = run_system(search, queries, k)
    return metrics.evaluate_run(run, labels).join(latencies)


def summary_table(per_query: pd.DataFrame, seed: int = BOOTSTRAP_SEED) -> pd.DataFrame:
    """Mean, 95% bootstrap interval and number of queries of each metric; p50 and p95 of latency."""
    rows = {}
    for column in per_query.columns.drop("latency_ms", errors="ignore"):
        values = per_query[column].dropna()
        low, high = metrics.bootstrap_mean_ci(values, seed=seed, n_resamples=BOOTSTRAP_RESAMPLES)
        rows[column] = {"mean": values.mean(), "ci_low": low, "ci_high": high, "n_queries": len(values)}
    table = pd.DataFrame.from_dict(rows, orient="index")
    if "latency_ms" in per_query:
        latency = per_query["latency_ms"]
        table.loc["latency_ms_p50", ["mean", "n_queries"]] = [latency.quantile(0.5), len(latency)]
        table.loc["latency_ms_p95", ["mean", "n_queries"]] = [latency.quantile(0.95), len(latency)]
    return table.astype({"n_queries": int})


def paired_bootstrap(
    per_query_a: pd.DataFrame,
    per_query_b: pd.DataFrame,
    metric: str,
    seed: int = BOOTSTRAP_SEED,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, float]:
    """Mean difference (a − b) of ``metric`` over the queries where both are defined, with a 95% interval.

    Both tables must cover the same queries. Resampling is over the per-query differences.
    """
    if not per_query_a.index.sort_values().equals(per_query_b.index.sort_values()):
        raise ValueError("both systems must be evaluated on the same queries")
    difference = (per_query_a[metric] - per_query_b[metric]).dropna()
    low, high = metrics.bootstrap_mean_ci(difference, seed=seed, n_resamples=n_resamples)
    return {
        "mean_difference": float(difference.mean()),
        "ci_low": low,
        "ci_high": high,
        "n_queries": len(difference),
        "share_a_better": float(np.mean(difference > 0)),
        "share_b_better": float(np.mean(difference < 0)),
    }
