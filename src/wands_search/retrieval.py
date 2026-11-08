"""Lexical retrieval with BM25 (``bm25s``) over the searchable text of the products."""

import time
from collections.abc import Sequence
from dataclasses import dataclass

import bm25s
import numpy as np
import pandas as pd

from wands_search.text import product_field_texts, single_field_text, tokenize

# BM25 parameters of the baseline. "lucene" is the bm25s default variant: idf =
# log(1 + (N - n + 0.5) / (n + 0.5)) and no (k1 + 1) factor, which scales every score by the
# same constant and does not change the order. k1 = 1.2 and b = 0.75 are common defaults;
# they are tuned on the training queries later (docs/EVALUATION.md).
BM25_K1 = 1.2
BM25_B = 0.75
BM25_METHOD = "lucene"

# Input limits. Queries in the dataset have at most 11 tokens; longer inputs are cut, not
# rejected, so that a pasted product title still returns results.
MAX_QUERY_CHARS = 500
MAX_QUERY_TOKENS = 32

# Text options of each BM25 version (see notebooks/02_bm25.ipynb, Etapa 4).
BASELINE_TEXT = {"stem": False, "clean_features": False, "yes_keys": False}
V2_TEXT = {"stem": True, "clean_features": True, "yes_keys": False}
V3_TEXT = {"stem": True, "clean_features": True, "yes_keys": True}


class InvalidQueryError(ValueError):
    """Raised when a query cannot be searched: not a string, or empty after removing spaces."""


@dataclass(frozen=True)
class PreparedQuery:
    """Tokens of a query after validation, and whether the input had to be cut."""

    tokens: list[str]
    truncated: bool


def prepare_query(query: object, stem: bool = False) -> PreparedQuery:
    """Validate a raw query and turn it into tokens.

    - not a string, or empty or only spaces: ``InvalidQueryError``;
    - longer than ``MAX_QUERY_CHARS`` characters or ``MAX_QUERY_TOKENS`` tokens: cut, with
      ``truncated=True``;
    - only special characters (``"&/()"``): valid, with no tokens, so the search returns nothing.

    ``stem`` must match the index, so that query and products go through the same rules.
    """
    if not isinstance(query, str):
        raise InvalidQueryError(f"query must be a string, got {type(query).__name__}")
    if not query.strip():
        raise InvalidQueryError("query is empty")
    truncated = len(query) > MAX_QUERY_CHARS
    tokens = tokenize(query[:MAX_QUERY_CHARS], stem=stem)
    if len(tokens) > MAX_QUERY_TOKENS:
        tokens, truncated = tokens[:MAX_QUERY_TOKENS], True
    return PreparedQuery(tokens=tokens, truncated=truncated)


class BM25Index:
    """BM25 index over one text per product, keyed by ``product_id``."""

    def __init__(
        self,
        product_ids: Sequence[int],
        token_lists: Sequence[list[str]],
        k1: float = BM25_K1,
        b: float = BM25_B,
        method: str = BM25_METHOD,
        stem: bool = False,
    ):
        if len(product_ids) != len(token_lists):
            raise ValueError("product_ids and token_lists must have the same length")
        self.product_ids = np.asarray(product_ids)
        self.stem = stem
        self.params = {"k1": k1, "b": b, "method": method}
        self._bm25 = bm25s.BM25(k1=k1, b=b, method=method)
        self._bm25.index(list(token_lists), show_progress=False)

    @classmethod
    def from_texts(cls, texts: pd.Series, stem: bool = False, **params) -> "BM25Index":
        """Build an index from a Series of texts indexed by ``product_id``."""
        tokens = texts.map(lambda value: tokenize(value, stem=stem))
        return cls(tokens.index.to_list(), tokens.to_list(), stem=stem, **params)

    @property
    def vocabulary_size(self) -> int:
        """Distinct tokens in the index, including the empty token that bm25s adds."""
        return len(self._bm25.vocab_dict)

    @property
    def index_bytes(self) -> int:
        """Memory of the stored score matrix (one value per token and product where it occurs)."""
        return sum(array.nbytes for array in self._bm25.scores.values() if hasattr(array, "nbytes"))

    def scores(self, tokens: list[str]) -> np.ndarray:
        """BM25 score of every product for ``tokens``, in the order of ``product_ids``.

        Tokens outside the vocabulary add nothing. A repeated token counts once per occurrence.
        """
        if not tokens:
            return np.zeros(len(self.product_ids), dtype=np.float32)
        return self._bm25.get_scores(tokens)

    def search_tokens(self, tokens: list[str], k: int) -> pd.DataFrame:
        """Top ``k`` products with a positive score, by score and then by ``product_id`` (ties)."""
        scores = self.scores(tokens)
        matched = np.flatnonzero(scores > 0)
        order = np.lexsort((self.product_ids[matched], -scores[matched]))[:k]
        top = matched[order]
        return pd.DataFrame({
            "rank": np.arange(1, len(top) + 1),
            "product_id": self.product_ids[top],
            "score": scores[top].astype(float),
        })

    def search(self, query: object, k: int = 100) -> pd.DataFrame:
        """Validate ``query`` and return its top ``k`` products (see ``prepare_query``)."""
        return self.search_tokens(prepare_query(query, self.stem).tokens, k)


def single_field_tokens(
    products: pd.DataFrame, stem: bool = False, clean_features: bool = False, yes_keys: bool = False
) -> pd.Series:
    """Tokens of the single field text of each product, indexed by ``product_id``."""
    texts = single_field_text(product_field_texts(products, clean_features=clean_features, yes_keys=yes_keys))
    return texts.map(lambda value: tokenize(value, stem=stem))


def build_single_field_index(
    products: pd.DataFrame, stem: bool = False, clean_features: bool = False, yes_keys: bool = False, **params
) -> BM25Index:
    """Index over every field of ``text.SEARCH_FIELDS`` joined into one text per product."""
    tokens = single_field_tokens(products, stem=stem, clean_features=clean_features, yes_keys=yes_keys)
    return BM25Index(tokens.index.to_list(), tokens.to_list(), stem=stem, **params)


def timed_build(products: pd.DataFrame, **options) -> tuple[BM25Index, float]:
    """Build the single field index and return it with the build time in seconds."""
    start = time.perf_counter()
    index = build_single_field_index(products, **options)
    return index, time.perf_counter() - start


# Reciprocal Rank Fusion (Cormack, Clarke and Büttcher, SIGIR 2009). k = 60 is the value of
# the paper, fixed without tuning; each list contributes its top RRF_DEPTH products
# (docs/EVALUATION.md, "Retrieval vetorial e híbrido").
RRF_K = 60
RRF_DEPTH = 200


def rrf_fuse(rankings: Sequence[Sequence[int]], k: int = RRF_K, weights: Sequence[float] | None = None) -> pd.DataFrame:
    """Fuse ranked lists of ``product_id``: each product scores the sum of weight / (k + rank) over the lists.

    Ranks start at 1, and a list where the product is missing adds nothing. Without ``weights``,
    every list weighs 1 (the standard RRF). Ties are broken by ``product_id``. Returns the same
    columns as ``BM25Index.search``.
    """
    weights = [1.0] * len(rankings) if weights is None else list(weights)
    if len(weights) != len(rankings):
        raise ValueError("weights and rankings must have the same length")
    scores: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, product_id in enumerate(ranking, start=1):
            scores[product_id] = scores.get(product_id, 0.0) + weight / (k + rank)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return pd.DataFrame({
        "rank": np.arange(1, len(ordered) + 1, dtype=int),
        "product_id": np.array([product_id for product_id, _ in ordered], dtype=np.int64),
        "score": np.array([score for _, score in ordered], dtype=float),
    })


class HybridRetriever:
    """Weighted RRF of several retrievers, each with a ``search(query, k)`` that returns a ``product_id`` column."""

    def __init__(self, retrievers: Sequence, k: int = RRF_K, depth: int = RRF_DEPTH, weights: Sequence[float] | None = None):
        if not retrievers:
            raise ValueError("at least one retriever is needed")
        if weights is not None and len(weights) != len(retrievers):
            raise ValueError("weights and retrievers must have the same length")
        self.retrievers = list(retrievers)
        self.k = k
        self.depth = depth
        self.weights = weights

    def search(self, query: object, k: int = 100) -> pd.DataFrame:
        """Top ``k`` products of the fusion. Invalid queries raise ``InvalidQueryError``, as in each retriever."""
        prepare_query(query)
        rankings = [retriever.search(query, self.depth)["product_id"].tolist() for retriever in self.retrievers]
        return rrf_fuse(rankings, self.k, self.weights).head(k)
