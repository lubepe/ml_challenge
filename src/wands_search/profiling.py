"""Data quality diagnostics used during exploration and data preparation."""

import re
import unicodedata
from pathlib import Path

import pandas as pd

from wands_search.data import PAIR_COLUMNS

LABEL_NAMES = ["Exact", "Partial", "Irrelevant"]


def strip_accents(text: str) -> str:
    """Remove diacritics, so that ``décor`` and ``decor`` become the same word."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def simple_tokens(text: str) -> set[str]:
    """Return the distinct lowercase alphanumeric tokens of ``text``, without accents."""
    return set(re.findall(r"[a-z0-9]+", strip_accents(text).lower()))


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
