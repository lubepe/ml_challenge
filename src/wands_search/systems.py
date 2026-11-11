"""The retrieval systems chosen on the train set, built with the parameters of docs/EVALUATION.md.

BM25 v2: ``k1`` and ``b`` from notebooks/02_bm25.ipynb, Etapa 4.2. Semantic search:
long text with the bge query prefix, notebooks/03_semantic_hybrid.ipynb, Etapa 3.1. Hybrid
search: weighted RRF, k and w from the same notebook, Etapa 5.3.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from wands_search import embeddings, retrieval, text

V2_K1 = 1.2
V2_B = 0.5
HYBRID_RRF_K = 60
HYBRID_BM25_WEIGHT = 0.5


@dataclass
class Systems:
    """BM25 v2, semantic search and hybrid search over the same catalog."""

    v2_index: retrieval.BM25Index
    semantic_index: embeddings.DenseIndex
    hybrid_index: retrieval.HybridRetriever


def build_v2_index(products: pd.DataFrame) -> retrieval.BM25Index:
    """BM25 v2 single field index: plurals removed and cleaned ``product_features``."""
    return retrieval.build_single_field_index(products, **retrieval.V2_TEXT, k1=V2_K1, b=V2_B)


def build_semantic_index(
    products: pd.DataFrame,
    encoder: embeddings.FastEmbedEncoder | None = None,
    cache_dir: Path | None = embeddings.DEFAULT_CACHE_DIR,
) -> embeddings.DenseIndex:
    """Semantic index over the long text, with the bge query prefix. Product vectors come from the cache when present."""
    encoder = encoder or embeddings.FastEmbedEncoder()
    field_texts = text.product_field_texts(products, clean_features=True)
    long_texts = text.single_field_text(field_texts)
    return embeddings.DenseIndex.from_texts(long_texts, encoder.with_query_prefix(embeddings.BGE_QUERY_PREFIX), cache_dir)


def build_systems(products: pd.DataFrame, encoder: embeddings.FastEmbedEncoder | None = None,
                  cache_dir: Path | None = embeddings.DEFAULT_CACHE_DIR) -> Systems:
    """The three retrieval systems; the hybrid search fuses the other two."""
    v2_index = build_v2_index(products)
    semantic_index = build_semantic_index(products, encoder, cache_dir)
    hybrid_index = retrieval.HybridRetriever(
        [v2_index, semantic_index], k=HYBRID_RRF_K, weights=[HYBRID_BM25_WEIGHT, 1 - HYBRID_BM25_WEIGHT]
    )
    return Systems(v2_index, semantic_index, hybrid_index)
