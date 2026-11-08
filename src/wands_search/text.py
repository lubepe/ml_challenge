"""Text processing shared by queries and products, so that both are tokenized the same way."""

import re
import unicodedata

import pandas as pd

from wands_search.data import parse_product_features

# A token is a run of lowercase ASCII letters or digits. Everything else separates tokens,
# so '36"' and "36 ''" both give "36", and "72.5" gives "72" and "5".
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def strip_accents(text: str) -> str:
    """Remove diacritics, so that ``décor`` and ``decor`` become the same word."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str | None) -> list[str]:
    """Return the tokens of ``text`` in order, keeping repetitions (BM25 counts them).

    Removes accents, lowercases and splits on anything that is not a letter or digit.
    No stemming and no stopword removal. Missing text gives no tokens.
    """
    if not isinstance(text, str):
        return []
    return TOKEN_PATTERN.findall(strip_accents(text).lower())


# Product columns that become searchable text, in this order.
SEARCH_FIELDS = [
    "product_name",
    "product_class",
    "category_hierarchy",
    "product_description",
    "product_features",
]


def feature_values_text(value: str | None) -> str:
    """Join the values of ``product_features``, dropping the keys (``color : caramel`` gives ``caramel``)."""
    return " ".join(val for _, val in parse_product_features(value))


def product_field_texts(products: pd.DataFrame) -> pd.DataFrame:
    """Searchable text of each field in ``SEARCH_FIELDS``, one row per ``product_id``.

    Missing values become empty strings, and ``product_features`` keeps only its values.
    """
    texts = products.set_index("product_id")[SEARCH_FIELDS].copy()
    texts["product_features"] = texts["product_features"].map(feature_values_text)
    return texts.fillna("").astype(str)


def single_field_text(field_texts: pd.DataFrame) -> pd.Series:
    """Join every field of ``product_field_texts`` into one text per product, separated by spaces."""
    return field_texts[SEARCH_FIELDS].agg(" ".join, axis=1)
