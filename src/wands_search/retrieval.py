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


class InvalidQueryError(ValueError):
    """Raised when a query cannot be searched: not a string, or empty after removing spaces."""


@dataclass(frozen=True)
class PreparedQuery:
    """Tokens of a query after validation, and whether the input had to be cut."""

    tokens: list[str]
    truncated: bool


def prepare_query(query: object) -> PreparedQuery:
    """Validate a raw query and turn it into tokens.

    - not a string, or empty or only spaces: ``InvalidQueryError``;
    - longer than ``MAX_QUERY_CHARS`` characters or ``MAX_QUERY_TOKENS`` tokens: cut, with
      ``truncated=True``;
    - only special characters (``"&/()"``): valid, with no tokens, so the search returns nothing.
    """
    if not isinstance(query, str):
        raise InvalidQueryError(f"query must be a string, got {type(query).__name__}")
    if not query.strip():
        raise InvalidQueryError("query is empty")
    truncated = len(query) > MAX_QUERY_CHARS
    tokens = tokenize(query[:MAX_QUERY_CHARS])
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
    ):
        if len(product_ids) != len(token_lists):
            raise ValueError("product_ids and token_lists must have the same length")
        self.product_ids = np.asarray(product_ids)
        self.params = {"k1": k1, "b": b, "method": method}
        self._bm25 = bm25s.BM25(k1=k1, b=b, method=method)
        self._bm25.index(list(token_lists), show_progress=False)

    @classmethod
    def from_texts(cls, texts: pd.Series, **params) -> "BM25Index":
        """Build an index from a Series of texts indexed by ``product_id``."""
        return cls(texts.index.to_list(), texts.map(tokenize).to_list(), **params)

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
        return self.search_tokens(prepare_query(query).tokens, k)


def build_single_field_index(products: pd.DataFrame, **params) -> BM25Index:
    """Baseline index: every field of ``text.SEARCH_FIELDS`` joined into one text per product."""
    return BM25Index.from_texts(single_field_text(product_field_texts(products)), **params)


def timed_build(products: pd.DataFrame, **params) -> tuple[BM25Index, float]:
    """Build the single field index and return it with the build time in seconds."""
    start = time.perf_counter()
    index = build_single_field_index(products, **params)
    return index, time.perf_counter() - start
