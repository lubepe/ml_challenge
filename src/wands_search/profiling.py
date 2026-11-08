"""Data quality diagnostics used during exploration and data preparation."""

import re
from pathlib import Path

import pandas as pd

from wands_search.data import PAIR_COLUMNS
from wands_search.metrics import bootstrap_mean_ci  # noqa: F401 (kept here for notebooks/01_eda.ipynb)
from wands_search.text import tokenize

LABEL_NAMES = ["Exact", "Partial", "Irrelevant"]


def simple_tokens(text: str) -> set[str]:
    """Return the distinct tokens of ``text`` (see ``wands_search.text.tokenize``)."""
    return set(tokenize(text))


def token_overlap(query_tokens: set[str], text_tokens: set[str]) -> float:
    """Return the share of ``query_tokens`` found in ``text_tokens``."""
    if not query_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / len(query_tokens)


def query_group_key(query: str) -> str:
    """Build a key shared by queries that differ only in case, word order or a plural ``s``.

    This is a simple heuristic to find near-duplicate queries, not a linguistic stemmer.
    """
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    singular = [t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t for t in tokens]
    return " ".join(sorted(singular))


def count_data_lines(path: Path) -> int:
    """Count the lines of a text file, excluding the header line."""
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def column_overview(df: pd.DataFrame) -> pd.DataFrame:
    """Return dtype, null count, null percentage and distinct count per column."""
    return pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "nulls": df.isna().sum(),
        "null_pct": (df.isna().mean() * 100).round(2),
        "distinct": df.nunique(),
    })


def label_pair_stats(labels: pd.DataFrame) -> pd.DataFrame:
    """Count rows and distinct labels for each (query_id, product_id) pair.

    Returns a frame indexed by the pair, with columns ``n_rows`` and ``n_labels``.
    A pair with ``n_rows > 1`` is repeated; one with ``n_labels > 1`` is conflicting.
    """
    return labels.groupby(PAIR_COLUMNS).agg(
        n_rows=("label", "size"),
        n_labels=("label", "nunique"),
    )


def conflicting_label_rows(labels: pd.DataFrame) -> pd.DataFrame:
    """Return all label rows whose (query_id, product_id) pair has more than one distinct label."""
    stats = label_pair_stats(labels)
    conflicting_pairs = stats[stats["n_labels"] > 1].reset_index()[PAIR_COLUMNS]
    return labels.merge(conflicting_pairs, on=PAIR_COLUMNS).sort_values(PAIR_COLUMNS, ignore_index=True)


def query_label_profile(labels: pd.DataFrame) -> pd.DataFrame:
    """Summarize deduplicated labels per query.

    Returns a frame indexed by ``query_id`` with one count column per label, plus
    ``n_judged`` and ``exact_fraction``.
    """
    counts = (
        labels.groupby(["query_id", "label"]).size().unstack(fill_value=0)
        .reindex(columns=LABEL_NAMES, fill_value=0)
    )
    counts.columns.name = None
    counts["n_judged"] = counts[LABEL_NAMES].sum(axis=1)
    counts["exact_fraction"] = counts["Exact"] / counts["n_judged"]
    return counts


LABEL_ORDER = {"Irrelevant": 0, "Partial": 1, "Exact": 2}


def within_query_spearman(pairs: pd.DataFrame, value_column: str, min_pairs: int = 20) -> pd.Series:
    """Spearman correlation between ``label`` order and ``value_column``, computed inside each query.

    Pairs with a missing value are dropped first. Queries left with fewer than ``min_pairs``
    pairs, or where either side is constant, are omitted. Spearman is the Pearson correlation
    of the average ranks, so ties are handled. Returns a Series indexed by ``query_id``.
    """
    known = pairs.dropna(subset=[value_column]).assign(label_order=lambda df: df["label"].map(LABEL_ORDER))
    known = known.groupby("query_id").filter(lambda g: len(g) >= min_pairs)

    def spearman(group: pd.DataFrame) -> float:
        return group["label_order"].rank().corr(group[value_column].rank())

    return known.groupby("query_id").apply(spearman, include_groups=False).dropna()
