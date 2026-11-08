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


# Endings where the plural adds "es" to a word that ends in s, x, z, ch or sh.
SIBILANT_ES_ENDINGS = ("sses", "xes", "zes", "ches", "shes")


def s_stem(token: str) -> str:
    """Plural removal: the S-stemmer (Harman, 1991) with one extra rule of ours, checked first.

    0. (ours) ends in ``sses``, ``xes``, ``zes``, ``ches`` or ``shes``: ``es`` is removed
       (``mattresses`` → ``mattress``, ``benches`` → ``bench``, ``boxes`` → ``box``);
    1. ends in ``ies`` but not ``eies`` or ``aies``: ``ies`` becomes ``y`` (``bodies`` → ``body``);
    2. ends in ``es`` but not ``aes``, ``ees`` or ``oes``: ``es`` becomes ``e`` (``tables`` → ``table``);
    3. ends in ``s`` but not ``us`` or ``ss``: the ``s`` is removed (``chairs`` → ``chair``).

    Only the first matching rule applies. Without rule 0, ``mattresses`` would become
    ``mattresse`` and never match ``mattress``. The output is not always a word (``series`` →
    ``sery``), but singular and plural map to the same token when both follow the rules.
    """
    if token.endswith(SIBILANT_ES_ENDINGS):
        return token[:-2]
    if token.endswith("ies") and not token.endswith(("eies", "aies")):
        return token[:-3] + "y"
    if token.endswith("es") and not token.endswith(("aes", "ees", "oes")):
        return token[:-1]
    if token.endswith("s") and not token.endswith(("us", "ss")):
        return token[:-1]
    return token


def tokenize(text: str | None, stem: bool = False) -> list[str]:
    """Return the tokens of ``text`` in order, keeping repetitions (BM25 counts them).

    Removes accents, lowercases and splits on anything that is not a letter or digit. With
    ``stem=True``, each token goes through ``s_stem``. No stopword removal. Missing text gives
    no tokens.
    """
    if not isinstance(text, str):
        return []
    tokens = TOKEN_PATTERN.findall(strip_accents(text).lower())
    return [s_stem(token) for token in tokens] if stem else tokens


# Product columns that become searchable text, in this order.
SEARCH_FIELDS = [
    "product_name",
    "product_class",
    "category_hierarchy",
    "product_description",
    "product_features",
]

# Values of product_features that carry no meaning without their key.
YES_NO_VALUES = frozenset({"yes", "no"})
# Only digits and number separators, with at least one digit: "64.7", "600 ; 276 ; 456", "1/4".
NUMERIC_VALUE = re.compile(r"[\d\s.,;/\-]*\d[\d\s.,;/\-]*")


def is_droppable_feature_value(value: str) -> bool:
    """True for a ``product_features`` value that is ``yes``, ``no`` or only numbers."""
    stripped = value.strip()
    return stripped.lower() in YES_NO_VALUES or NUMERIC_VALUE.fullmatch(stripped) is not None


def feature_values_text(value: str | None, clean: bool = False, yes_keys: bool = False) -> str:
    """Join the values of ``product_features``, dropping the keys (``color : caramel`` gives ``caramel``).

    With ``clean=True``, values that are ``yes``, ``no`` or only numbers are dropped too. With
    ``yes_keys=True``, a pair whose value is ``yes`` contributes its key instead
    (``upholstered : yes`` gives ``upholstered``).
    """
    parts = []
    for key, val in parse_product_features(value):
        if yes_keys and val.strip().lower() == "yes":
            parts.append(key)
        elif not (clean and is_droppable_feature_value(val)):
            parts.append(val)
    return " ".join(parts)


def product_field_texts(products: pd.DataFrame, clean_features: bool = False, yes_keys: bool = False) -> pd.DataFrame:
    """Searchable text of each field in ``SEARCH_FIELDS``, one row per ``product_id``.

    Missing values become empty strings, and ``product_features`` keeps only its values
    (see ``feature_values_text`` for ``clean_features`` and ``yes_keys``).
    """
    texts = products.set_index("product_id")[SEARCH_FIELDS].copy()
    texts["product_features"] = texts["product_features"].map(
        lambda value: feature_values_text(value, clean_features, yes_keys)
    )
    return texts.fillna("").astype(str)


def single_field_text(field_texts: pd.DataFrame, fields: list[str] = SEARCH_FIELDS) -> pd.Series:
    """Join ``fields`` of ``product_field_texts`` into one text per product, separated by spaces.

    Empty fields are skipped, so that a missing ``product_class`` leaves no extra space.
    """
    return field_texts[fields].agg(lambda row: " ".join(value for value in row if value), axis=1)


# Fields of the short product text of the dense retrieval (docs/EVALUATION.md).
SHORT_TEXT_FIELDS = ["product_name", "product_class", "category_hierarchy"]
