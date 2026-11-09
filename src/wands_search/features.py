"""Features of each (query, candidate product) pair for the reranker.

Groups and definitions in docs/EVALUATION.md, section "Reranker (learning-to-rank)". No feature
uses ``product_id``, ``query_class`` or the labels. Every feature is computed for every
candidate, whichever retrieval brought it.
"""

from collections.abc import Sequence
from typing import Protocol

import numpy as np
import pandas as pd

from wands_search import embeddings, retrieval, systems, text
from wands_search.data import parse_product_features
from wands_search.retrieval import MAX_QUERY_CHARS, prepare_query, rrf_fuse

CROSS_ENCODER_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
CROSS_ENCODER_BATCH_SIZE = 64

FIELD_FEATURES = [f"bm25_{field}" for field in text.SEARCH_FIELDS] + [f"coverage_{field}" for field in text.SEARCH_FIELDS]
FEATURE_GROUPS: dict[str, list[str]] = {
    "retrieval": ["bm25_v2_score", "bm25_v2_rank", "semantic_cosine", "semantic_rank", "rrf_score", "rrf_rank"],
    "text": FIELD_FEATURES + ["query_in_product_name", "number_match", "short_cosine"],
    "cross_encoder": ["cross_encoder_score"],
    "numeric": [
        "log_rating_count", "log_review_count", "average_rating", "no_rating",
        "description_words", "feature_pairs", "product_class_null", "category_hierarchy_null",
    ],
    "query": ["query_tokens", "query_has_number"],
}
ALL_FEATURES = [feature for group in FEATURE_GROUPS.values() for feature in group]
RATING_FEATURES = ["log_rating_count", "log_review_count", "average_rating", "no_rating"]
# Features that need the embedding model at search time (ablation of docs/EVALUATION.md).
EMBEDDING_FEATURES = ["semantic_cosine", "semantic_rank", "rrf_score", "rrf_rank", "short_cosine"]
# Features of the BM25 v2 reranker, which does not run the embedding model.
LEXICAL_RERANKER_FEATURES = [feature for feature in ALL_FEATURES if feature not in EMBEDDING_FEATURES]


class CrossEncoder(Protocol):
    """Scores (query, product text) pairs; a higher score means more relevant."""

    def score(self, query: str, texts: Sequence[str]) -> np.ndarray:
        ...


class FastEmbedCrossEncoder:
    """Pre-trained cross-encoder of ``fastembed``, without fine-tuning."""

    def __init__(self, model_name: str = CROSS_ENCODER_MODEL, cache_dir=embeddings.DEFAULT_CACHE_DIR,
                 batch_size: int = CROSS_ENCODER_BATCH_SIZE, threads: int | None = None):
        from pathlib import Path

        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.model_name = model_name
        self.batch_size = batch_size
        self._model = TextCrossEncoder(model_name, cache_dir=str(Path(cache_dir) / "fastembed"), threads=threads)

    def score(self, query: str, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros(0, dtype=float)
        return np.fromiter(self._model.rerank(query, list(texts), batch_size=self.batch_size), dtype=float, count=len(texts))


def catalog_ranks(scores: np.ndarray, positions: np.ndarray) -> np.ndarray:
    """Rank of the products at ``positions`` in the whole catalog: 1 + number of products with a higher score."""
    ascending = np.sort(scores)
    return len(scores) - np.searchsorted(ascending, scores[positions], side="right") + 1


def contains_sequence(tokens: Sequence[str], sequence: Sequence[str]) -> bool:
    """True if ``sequence`` appears in ``tokens`` as consecutive tokens. An empty sequence is never contained."""
    n = len(sequence)
    if n == 0 or n > len(tokens):
        return False
    first = sequence[0]
    return any(tokens[i] == first and list(tokens[i:i + n]) == list(sequence) for i in range(len(tokens) - n + 1))


def is_number_token(token: str) -> bool:
    return any(character.isdigit() for character in token)


def product_numeric_features(products: pd.DataFrame) -> pd.DataFrame:
    """Group ``numeric``, one row per ``product_id``. ``average_rating`` stays null when the product has no rating."""
    indexed = products.set_index("product_id")
    return pd.DataFrame({
        "log_rating_count": np.log1p(indexed["rating_count"].fillna(0)),
        "log_review_count": np.log1p(indexed["review_count"].fillna(0)),
        "average_rating": indexed["average_rating"].astype(float),
        "no_rating": indexed["rating_count"].isna().astype(float),
        "description_words": indexed["product_description"].fillna("").str.split().str.len().astype(float),
        "feature_pairs": indexed["product_features"].map(lambda value: len(parse_product_features(value))).astype(float),
        "product_class_null": indexed["product_class"].isna().astype(float),
        "category_hierarchy_null": indexed["category_hierarchy"].isna().astype(float),
    })


class FeatureBuilder:
    """Computes ``ALL_FEATURES`` for the candidates of one query.

    ``retrievers`` gives BM25 v2, the semantic index and the hybrid parameters; ``short_index``
    holds the vectors of the short text, with the same encoder as the semantic index. Without
    ``cross_encoder``, ``cross_encoder_score`` is null.
    """

    def __init__(self, products: pd.DataFrame, retrievers: systems.Systems, short_index: embeddings.DenseIndex,
                 cross_encoder: CrossEncoder | None = None):
        self.v2_index = retrievers.v2_index
        self.semantic_index = retrievers.semantic_index
        self.hybrid_index = retrievers.hybrid_index
        self.short_index = short_index
        self.cross_encoder = cross_encoder
        product_ids = self.v2_index.product_ids
        for other in (self.semantic_index, short_index):
            if not np.array_equal(other.product_ids, product_ids):
                raise ValueError("every index must list the products in the same order")
        self.position = pd.Series(np.arange(len(product_ids)), index=product_ids)

        field_texts = text.product_field_texts(products, clean_features=True).loc[product_ids]
        self.field_indexes = {
            field: retrieval.BM25Index.from_texts(field_texts[field], stem=True, **self.v2_index.params)
            for field in text.SEARCH_FIELDS
        }
        self.field_tokens = {
            field: [frozenset(text.tokenize(value, stem=True)) for value in field_texts[field]] for field in text.SEARCH_FIELDS
        }
        self.name_tokens = [text.tokenize(value, stem=True) for value in field_texts["product_name"]]
        self.all_tokens = [frozenset().union(*sets) for sets in zip(*self.field_tokens.values())]
        self.short_texts = text.single_field_text(field_texts, text.SHORT_TEXT_FIELDS).to_numpy()
        self.numeric = product_numeric_features(products).loc[product_ids].to_numpy()

    def query_features(self, query: str, product_ids: Sequence[int], use_embeddings: bool = True) -> pd.DataFrame:
        """One row per product of ``product_ids``, columns ``ALL_FEATURES``. Invalid queries raise ``InvalidQueryError``.

        With ``use_embeddings=False``, the embedding model is not run and ``EMBEDDING_FEATURES`` stay null.
        """
        tokens = prepare_query(query, stem=True).tokens
        positions = self.position.loc[list(product_ids)].to_numpy()
        features = pd.DataFrame(index=pd.Index(list(product_ids), name="product_id"), columns=ALL_FEATURES, dtype=float)
        if len(positions) == 0:
            return features

        # Group retrieval: scores over the whole catalog, so a product brought by one retrieval also gets the other's score.
        bm25_scores = self.v2_index.scores(tokens)
        features["bm25_v2_score"] = bm25_scores[positions]
        features["bm25_v2_rank"] = catalog_ranks(bm25_scores, positions)
        if use_embeddings:
            query_vector = self.semantic_index.encoder.encode_query(query.strip()[:MAX_QUERY_CHARS])
            cosines = self.semantic_index.scores(query_vector)
            features["semantic_cosine"] = cosines[positions]
            features["semantic_rank"] = catalog_ranks(cosines, positions)
            # The same lists as HybridRetriever.search: a query without tokens gets nothing from either retrieval.
            hybrid = self.hybrid_index
            depth = hybrid.depth if tokens else 0
            lists = [
                self.v2_index.search_tokens(tokens, depth)["product_id"].tolist(),
                self.semantic_index.search_vector(query_vector, depth)["product_id"].tolist(),
            ]
            fused = rrf_fuse(lists, hybrid.k, hybrid.weights).set_index("product_id")
            features["rrf_score"] = fused["score"].reindex(product_ids).fillna(0.0).to_numpy()
            features["rrf_rank"] = fused["rank"].reindex(product_ids).to_numpy(dtype=float)
            features["short_cosine"] = self.short_index.scores(query_vector)[positions]

        # Group text.
        query_set = frozenset(tokens)
        for field, index in self.field_indexes.items():
            features[f"bm25_{field}"] = index.scores(tokens)[positions]
            field_sets = self.field_tokens[field]
            features[f"coverage_{field}"] = [len(query_set & field_sets[p]) / len(query_set) if query_set else 0.0 for p in positions]
        features["query_in_product_name"] = [float(contains_sequence(self.name_tokens[p], tokens)) for p in positions]
        numbers = frozenset(token for token in tokens if is_number_token(token))
        features["number_match"] = [len(numbers & self.all_tokens[p]) / len(numbers) if numbers else np.nan for p in positions]

        # Group cross_encoder.
        if self.cross_encoder is not None:
            features["cross_encoder_score"] = self.cross_encoder.score(query, list(self.short_texts[positions]))

        # Groups numeric and query.
        features[FEATURE_GROUPS["numeric"]] = self.numeric[positions]
        features["query_tokens"] = float(len(tokens))
        features["query_has_number"] = float(bool(numbers))
        return features

    def build(self, candidates: pd.DataFrame, queries: pd.DataFrame) -> pd.DataFrame:
        """``candidates`` (from ``ranking.candidate_table``) with ``ALL_FEATURES`` added, in the same row order."""
        query_text = queries.set_index("query_id")["query"]
        frames = []
        for query_id, group in candidates.groupby("query_id", sort=False):
            features = self.query_features(query_text.loc[query_id], group["product_id"].tolist())
            frames.append(features.set_axis(group.index))
        return candidates.join(pd.concat(frames)) if frames else candidates.reindex(columns=[*candidates.columns, *ALL_FEATURES])


def build_feature_builder(products: pd.DataFrame, retrievers: systems.Systems,
                          cross_encoder: CrossEncoder | None = None,
                          cache_dir=embeddings.DEFAULT_CACHE_DIR) -> FeatureBuilder:
    """``FeatureBuilder`` with the short text index made from the semantic index encoder (vectors from the cache when present)."""
    field_texts = text.product_field_texts(products, clean_features=True)
    short_texts = text.single_field_text(field_texts, text.SHORT_TEXT_FIELDS)
    short_index = embeddings.DenseIndex.from_texts(short_texts, retrievers.semantic_index.encoder, cache_dir)
    return FeatureBuilder(products, retrievers, short_index, cross_encoder)


def ablation_feature_sets(base_features: Sequence[str]) -> dict[str, list[str]]:
    """Feature lists of the ablations of docs/EVALUATION.md: ``base_features`` without each group, and without the rating columns.

    Groups that ``base_features`` does not use are skipped.
    """
    sets = {}
    for group, group_features in FEATURE_GROUPS.items():
        kept = [feature for feature in base_features if feature not in group_features]
        if len(kept) < len(base_features):
            sets[f"without {group}"] = kept
    sets["without rating"] = [feature for feature in base_features if feature not in RATING_FEATURES]
    return sets


def candidate_features(retrievers: dict, builder: "FeatureBuilder", query_frame: pd.DataFrame,
                       labels: dict, retrieval_k: int = 200) -> tuple[dict, dict, int]:
    """Runs, candidate tables with features, and the number of distinct (query, product) pairs.

    ``retrievers`` maps a name to an index with ``search(query, k)``. Each run keeps the top
    ``retrieval_k`` products; the candidate table keeps the top ``ranking.CANDIDATES_K``. The
    features of a pair do not depend on the retrieval, so they are computed once for the union
    of all candidate tables.
    """
    from wands_search import ranking

    runs = {name: {query_id: index.search(query_text, retrieval_k)["product_id"].tolist()
                   for query_id, query_text in zip(query_frame["query_id"], query_frame["query"])}
            for name, index in retrievers.items()}
    candidates = {name: ranking.candidate_table(run, labels) for name, run in runs.items()}
    union = pd.concat(candidates.values()).drop_duplicates(["query_id", "product_id"])[["query_id", "product_id"]]
    union_features = builder.build(union.reset_index(drop=True), query_frame).set_index(["query_id", "product_id"])
    tables = {name: table.join(union_features, on=["query_id", "product_id"]) for name, table in candidates.items()}
    return runs, tables, len(union)
