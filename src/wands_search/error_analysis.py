"""Helpers of the error analysis of the selected system (notebooks/07_error_analysis.ipynb).

Every helper works on one query at a time or on the judged pairs of a set, and never reads the
test set by itself: the caller chooses the queries.
"""

import math
from collections.abc import Callable, Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from wands_search import data, metrics, text

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


POPULARITY_BANDS = ((1, 10), (11, 25), (26, 50), (51, 100))  # positions of the ranked list, inclusive


def product_popularity(products: pd.DataFrame) -> pd.DataFrame:
    """Return ``log_rating_count`` (log(1 + rating_count), 0 without rating) and ``no_rating`` per ``product_id``.

    Same definitions as the reranker features of the same name (``features.product_numeric_features``).
    """
    rating_count = products.set_index("product_id")["rating_count"].astype(float)
    return pd.DataFrame({
        "log_rating_count": np.log1p(rating_count.fillna(0)),
        "no_rating": rating_count.isna().astype(float),
    })


def popularity_profile(ranking: Sequence[int], popularity: pd.DataFrame, top_k: int = 10,
                       pool_k: int = 100) -> dict[str, float]:
    """Describe how popular the products of one ranked list are, at the top and in the whole list.

    ``ranking`` is cut to its first ``pool_k`` products (the pool). ``spearman_position`` is the
    Spearman correlation between the position (1 = top) and ``log_rating_count`` in the pool:
    negative when more popular products sit closer to the top, NaN when every product has the
    same ``log_rating_count``.
    """
    pool = list(ranking[:pool_k])
    values = popularity.loc[pool, "log_rating_count"].reset_index(drop=True)
    no_rating = popularity.loc[pool, "no_rating"].reset_index(drop=True)
    positions = pd.Series(np.arange(1, len(pool) + 1, dtype=float))
    spearman = positions.corr(values, method="spearman") if values.nunique() > 1 else math.nan
    return {
        "median_log_rating_count_top": float(values.iloc[:top_k].median()),
        "median_log_rating_count_pool": float(values.median()),
        "no_rating_share_top": float(no_rating.iloc[:top_k].mean()),
        "no_rating_share_pool": float(no_rating.mean()),
        "spearman_position": float(spearman),
    }


def popularity_by_band(ranking: Sequence[int], popularity: pd.DataFrame,
                       bands: Sequence[tuple[int, int]] = POPULARITY_BANDS) -> pd.DataFrame:
    """Median ``log_rating_count`` and share without rating in each band of positions of one ranked list."""
    rows = []
    for first, last in bands:
        band_ids = list(ranking[first - 1:last])
        band = popularity.loc[band_ids]
        rows.append({
            "band": f"{first}-{last}",
            "median_log_rating_count": float(band["log_rating_count"].median()),
            "no_rating_share": float(band["no_rating"].mean()),
        })
    return pd.DataFrame(rows).set_index("band")


def judged_pair_inversions(ranking: Sequence[int], query_labels: dict[int, str], popularity: pd.DataFrame,
                           pool_k: int = 100) -> pd.DataFrame:
    """One row per pair of judged products with different labels among the first ``pool_k`` of ``ranking``.

    ``inverted`` is True when the product with the worse label is above the other one.
    ``worse_more_popular`` is True when the product with the worse label has the higher
    ``log_rating_count``. Pairs with the same ``log_rating_count`` are left out.
    """
    log_rating_count = popularity["log_rating_count"]
    judged = [(product_id, metrics.GAINS[query_labels[product_id]]) for product_id in ranking[:pool_k]
              if product_id in query_labels]
    rows = []
    for upper_index, (upper_id, upper_gain) in enumerate(judged):
        for lower_id, lower_gain in judged[upper_index + 1:]:
            if upper_gain == lower_gain:
                continue
            worse_id, better_id = (upper_id, lower_id) if upper_gain < lower_gain else (lower_id, upper_id)
            if log_rating_count[worse_id] == log_rating_count[better_id]:
                continue
            rows.append({"inverted": upper_gain < lower_gain,
                         "worse_more_popular": log_rating_count[worse_id] > log_rating_count[better_id]})
    return pd.DataFrame(rows, columns=["inverted", "worse_more_popular"]).astype(bool)


def inversion_counts(pairs: pd.DataFrame) -> dict[str, int]:
    """Count pairs and inverted pairs of ``judged_pair_inversions``, split by which product is more popular."""
    more = pairs[pairs["worse_more_popular"]]
    less = pairs[~pairs["worse_more_popular"]]
    return {
        "inverted_worse_more_popular": int(more["inverted"].sum()),
        "pairs_worse_more_popular": len(more),
        "inverted_worse_less_popular": int(less["inverted"].sum()),
        "pairs_worse_less_popular": len(less),
    }


def exact_positions_by_rating(ranking: Sequence[int], query_labels: dict[int, str], popularity: pd.DataFrame,
                              top_k: int = 10, pool_k: int = 100) -> dict[str, float]:
    """Positions (1 = top) of the Exact products among the first ``pool_k``, split by having a rating or not.

    Returns the number of Exact products of each group, how many are in the top ``top_k`` and
    their mean position (NaN when the group is empty).
    """
    positions = {"rated": [], "no_rating": []}
    for position, product_id in enumerate(ranking[:pool_k], start=1):
        if query_labels.get(product_id) == "Exact":
            group = "no_rating" if popularity.at[product_id, "no_rating"] else "rated"
            positions[group].append(position)
    result = {}
    for group, group_positions in positions.items():
        result[f"exact_{group}"] = len(group_positions)
        result[f"exact_{group}_top"] = sum(position <= top_k for position in group_positions)
        result[f"mean_position_{group}"] = float(np.mean(group_positions)) if group_positions else math.nan
    return result


def bootstrap_pooled(counts: pd.DataFrame, statistic: Callable[[pd.Series], float], seed: int,
                     n_resamples: int = 2000, level: float = 0.95) -> tuple[float, float, float]:
    """Statistic of counts pooled over queries, with a percentile bootstrap interval that resamples the queries.

    ``counts`` has one row per query and additive columns (for example, pairs and inverted pairs);
    ``statistic`` receives the column sums. Returns the value on all queries and the interval.
    """
    rng = np.random.default_rng(seed)
    values = counts.to_numpy(dtype=float)
    resampled = [statistic(pd.Series(values[rng.integers(0, len(values), len(values))].sum(axis=0), index=counts.columns))
                 for _ in range(n_resamples)]
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(resampled, [tail, 100 - tail])
    return float(statistic(counts.sum())), float(low), float(high)
