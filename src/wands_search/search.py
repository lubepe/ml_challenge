"""End-to-end product search: retrieval, then the saved reranker.

``SearchPipeline.load()`` builds the selected system of docs/EVALUATION.md (hybrid search +
reranker without the cross-encoder) from the saved model in ``models/``. It reads the model
metadata and builds only what the model needs: the cross-encoder is loaded only when
``cross_encoder_score`` is one of the model features, and the query embedding is computed only
when the model uses the hybrid search or an embedding feature.

Invalid inputs follow ``retrieval.prepare_query``: a query that is not a string, or is empty,
raises ``InvalidQueryError``; a query with only special characters returns no results; a query
longer than ``retrieval.MAX_QUERY_CHARS`` characters or ``retrieval.MAX_QUERY_TOKENS`` tokens is
cut, and the response says so.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from wands_search import embeddings, features, ranking, reranker, systems
from wands_search.retrieval import prepare_query

MAX_RESULTS = 200  # the retrieval returns the top 200; the reranker orders the top 100
RESULT_COLUMNS = ["rank", "product_id", "product_name", "product_class", "score", "reranked"]


@dataclass
class SearchResponse:
    """Results of one search and the time of each step."""

    query: str
    results: pd.DataFrame
    truncated: bool
    retrieval_ms: float
    ranking_ms: float


class SearchPipeline:
    """Retrieval of the top ``retrieval_k`` products, then a reranker over the top ``ranking.CANDIDATES_K``."""

    def __init__(self, products: pd.DataFrame, retriever, builder: features.FeatureBuilder, model, feature_columns: list[str],
                 retrieval_k: int = MAX_RESULTS):
        self.retriever = retriever
        self.builder = builder
        self.model = model
        self.feature_columns = list(feature_columns)
        self.retrieval_k = retrieval_k
        self.use_embeddings = bool(set(self.feature_columns) & set(features.EMBEDDING_FEATURES))
        if "cross_encoder_score" not in self.feature_columns:
            builder.cross_encoder = None  # never run a model that the reranker does not read
        self.catalog = products.set_index("product_id")[["product_name", "product_class"]]

    @classmethod
    def load(cls, products: pd.DataFrame, model_name: str = reranker.SELECTED_MODEL,
             model_dir: Path = reranker.DEFAULT_MODEL_DIR, cache_dir: Path = embeddings.DEFAULT_CACHE_DIR) -> "SearchPipeline":
        """Build the retrieval and the features that the saved model ``model_name`` needs.

        The product embeddings come from ``cache_dir``; without them, they are computed on the
        first call (about half an hour on a CPU).
        """
        model, metadata = reranker.load_model(model_name, model_dir)
        retrievers = systems.build_systems(products, cache_dir=cache_dir)
        needs_cross_encoder = "cross_encoder_score" in metadata["feature_columns"]
        cross_encoder = features.FastEmbedCrossEncoder(cache_dir=cache_dir) if needs_cross_encoder else None
        builder = features.build_feature_builder(products, retrievers, cross_encoder, cache_dir)
        retriever = {"hybrid": retrievers.hybrid_index, "BM25 v2": retrievers.v2_index}[metadata["retrieval"]]
        return cls(products, retriever, builder, model, metadata["feature_columns"])

    def search(self, query: object, k: int = 10) -> SearchResponse:
        """Top ``k`` products for ``query`` (1 <= k <= ``retrieval_k``). Raises ``InvalidQueryError`` for invalid queries."""
        if isinstance(k, bool) or not isinstance(k, (int, np.integer)) or not 1 <= k <= self.retrieval_k:
            raise ValueError(f"k must be an integer from 1 to {self.retrieval_k}, got {k!r}")
        prepared = prepare_query(query)  # raises InvalidQueryError before any work
        start = time.perf_counter()
        retrieved = self.retriever.search(query, self.retrieval_k)["product_id"].tolist()
        retrieval_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        top = retrieved[:ranking.CANDIDATES_K]
        if top:
            rows = self.builder.query_features(query, top, use_embeddings=self.use_embeddings)
            scores = reranker.predict(self.model, rows, self.feature_columns)
            ordered = ranking.rerank(retrieved, scores)
            score_of = dict(zip(top, scores))
        else:
            ordered, score_of = [], {}
        ranking_ms = (time.perf_counter() - start) * 1000

        shown = ordered[:k]
        results = pd.DataFrame({
            "rank": np.arange(1, len(shown) + 1),
            "product_id": np.asarray(shown, dtype=np.int64),
            "product_name": self.catalog["product_name"].reindex(shown).to_numpy(),
            "product_class": self.catalog["product_class"].reindex(shown).to_numpy(),
            "score": [score_of.get(product_id, np.nan) for product_id in shown],
            "reranked": [product_id in score_of for product_id in shown],
        }, columns=RESULT_COLUMNS)
        return SearchResponse(query=query, results=results, truncated=prepared.truncated,
                              retrieval_ms=retrieval_ms, ranking_ms=ranking_ms)
