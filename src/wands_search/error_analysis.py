"""Helpers of the error analysis of the selected system (notebooks/07_error_analysis.ipynb).

Every helper works on one query at a time or on the judged pairs of a set, and never reads the
test set by itself: the caller chooses the queries.
"""

import math
from collections.abc import Callable, Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from wands_search import data, text

OK_NDCG = 0.9  # a query with NDCG@10 at or above this value is left out of the error analysis
MOSTLY_NO_LABEL = 5  # products without label in the top 10 from which the loss is put on the evaluation

STAGE_OK = "ok (NDCG@10 >= 0.9)"
STAGE_EVALUATION = "evaluation (top 10 mostly no label)"
STAGE_RETRIEVAL = "retrieval"
STAGE_RANKING = "ranking"

FULL_TEXT_FIELDS = ["product_name", "product_class", "category_hierarchy", "product_description", "product_features"]


def main_loss_stage(ndcg: float, retrieval_loss: float, ranking_loss: float, no_label_in_top10: int) -> str:
    """Where most of the NDCG@10 loss of one query comes from.

    In order: ``STAGE_OK`` when NDCG@10 >= ``OK_NDCG``; ``STAGE_EVALUATION`` when at least
    ``MOSTLY_NO_LABEL`` of the top 10 have no label; otherwise the larger of the retrieval loss
    (1 - oracle) and the ranking loss (oracle - NDCG@10), with ties going to the ranking.
    """
    if ndcg >= OK_NDCG:
        return STAGE_OK
    if no_label_in_top10 >= MOSTLY_NO_LABEL:
        return STAGE_EVALUATION
    return STAGE_RETRIEVAL if retrieval_loss > ranking_loss else STAGE_RANKING


def shares_product_class(query_class: str | None, product_class: str | None) -> bool:
    """True when the product has at least one of the classes of ``query_class`` (both split on ``|``)."""
    return bool(set(data.split_product_classes(query_class)) & set(data.split_product_classes(product_class)))


def has_feature_value(product_features: str | None, keys: Iterable[str], predicate: Callable[[str], bool]) -> bool:
    """True when one key:value pair of ``product_features`` has a key in ``keys`` and a value
    (stripped, lowercased) for which ``predicate`` is true."""
    keys = set(keys)
    return any(key in keys and predicate(value.strip().lower())
               for key, value in data.parse_product_features(product_features))


def label_disagreement_rate(query_labels: Sequence[str]) -> tuple[int, int]:
    """Pairs of judged products of one query with different labels, and all pairs.

    Returns ``(different, total)``, so that rates can be pooled over queries.
    """
    counts = pd.Series(list(query_labels)).value_counts()
    total = math.comb(len(query_labels), 2)
    same = sum(math.comb(int(n), 2) for n in counts)
    return total - same, total


def full_text(products: pd.DataFrame) -> pd.Series:
    """The five text fields of each product joined by a space, indexed by ``product_id``."""
    return (products.set_index("product_id")[FULL_TEXT_FIELDS].fillna("").astype(str)
            .agg(" ".join, axis=1))


def near_duplicate_pairs(texts: pd.Series, labels: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Pairs of products judged for the same query whose TF-IDF cosine is at least ``threshold``.

    ``texts`` is indexed by ``product_id`` (all the catalog, so that the IDF comes from the
    catalog); ``labels`` has ``query_id``, ``product_id`` and ``label``. The TF-IDF uses the
    tokens of ``text.tokenize``. Columns of the result: ``query_id``, ``product_a``,
    ``product_b``, ``label_a``, ``label_b``, ``cosine`` and ``different`` (labels differ).
    """
    vectorizer = TfidfVectorizer(tokenizer=text.tokenize, lowercase=False, token_pattern=None)
    matrix = vectorizer.fit_transform(texts.to_numpy())
    row_of = pd.Series(np.arange(len(texts)), index=texts.index)
    frames = []
    for query_id, group in labels.groupby("query_id"):
        product_ids = group["product_id"].to_numpy()
        query_labels = group["label"].to_numpy()
        vectors = matrix[row_of[product_ids].to_numpy()]
        similarity = (vectors @ vectors.T).toarray()
        first, second = np.triu_indices(len(product_ids), k=1)
        cosine = similarity[first, second]
        keep = cosine >= threshold
        frames.append(pd.DataFrame({
            "query_id": query_id,
            "product_a": product_ids[first[keep]], "product_b": product_ids[second[keep]],
            "label_a": query_labels[first[keep]], "label_b": query_labels[second[keep]],
            "cosine": cosine[keep],
        }))
    columns = ["query_id", "product_a", "product_b", "label_a", "label_b", "cosine"]
    pairs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    pairs["different"] = pairs["label_a"] != pairs["label_b"]
    return pairs
