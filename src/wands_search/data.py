"""Loading utilities for the WANDS dataset.

The raw files in ``dataset/`` are tab-separated despite the ``.csv`` extension
and are never modified. Column renames happen here, at load time.
"""

from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "dataset"

FILENAMES = {
    "product": "product.csv",
    "query": "query.csv",
    "label": "label.csv",
}

COLUMN_RENAMES = {"category hierarchy": "category_hierarchy"}

PAIR_COLUMNS = ["query_id", "product_id"]


def split_product_classes(value: str | None) -> list[str]:
    """Split a ``product_class`` value into its classes (separated by ``|``)."""
    if not isinstance(value, str):
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def split_category_hierarchy(value: str | None) -> list[str]:
    """Split a ``category_hierarchy`` value into its levels, from broadest to most specific."""
    if not isinstance(value, str):
        return []
    return [part.strip() for part in value.split(" / ") if part.strip()]


def parse_product_features(value: str | None) -> list[tuple[str, str]]:
    """Parse ``product_features`` into (key, value) pairs, keeping repeated keys.

    Pairs are separated by ``|``, and the first ``:`` separates key from value, since
    values may contain ``:`` themselves. Fragments without ``:`` are free text left over
    from a ``|`` inside a value, and are dropped.
    """
    if not isinstance(value, str):
        return []
    pairs = []
    for fragment in value.split("|"):
        key, separator, val = fragment.partition(":")
        if separator and key.strip():
            pairs.append((key.strip(), val.strip()))
    return pairs


def load_tsv(path: Path) -> pd.DataFrame:
    """Load a tab-separated file and normalize its column names."""
    return pd.read_csv(path, sep="\t").rename(columns=COLUMN_RENAMES)


def load_products(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the product catalog."""
    return load_tsv(Path(data_dir) / FILENAMES["product"])


def load_queries(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the search queries."""
    return load_tsv(Path(data_dir) / FILENAMES["query"])


def load_labels(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the raw (query, product) relevance judgments, without deduplication."""
    return load_tsv(Path(data_dir) / FILENAMES["label"])


def load_all(data_dir: Path = DEFAULT_DATA_DIR) -> dict[str, pd.DataFrame]:
    """Load all three tables, keyed by ``product``, ``query`` and ``label``."""
    return {
        "product": load_products(data_dir),
        "query": load_queries(data_dir),
        "label": load_labels(data_dir),
    }


def deduplicate_labels(labels: pd.DataFrame) -> pd.DataFrame:
    """Keep one row per (query_id, product_id) pair, without inventing a label.

    Exact copies (same pair and label, different ``id``) are reduced to the first row.
    Pairs with more than one distinct label are dropped entirely, since there is no
    business rule to choose between them; they count as unjudged for that query.
    """
    unique_rows = labels.drop_duplicates(subset=[*PAIR_COLUMNS, "label"])
    labels_per_pair = unique_rows.groupby(PAIR_COLUMNS)["label"].transform("size")
    return unique_rows[labels_per_pair == 1].reset_index(drop=True)
