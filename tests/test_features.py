import math

import numpy as np
import pandas as pd
import pytest

from wands_search import embeddings, features, ranking, retrieval, systems, text

VOCABULARY = ["leather", "chair", "sofa", "wood", "ottoman", "2", "seater"]


class BagOfWordsEncoder:
    """Deterministic encoder for tests: one dimension per word of VOCABULARY, no model download."""

    cache_key = "bag-of-words"

    def vector(self, value: str) -> np.ndarray:
        words = text.tokenize(value)
        return np.array([words.count(word) for word in VOCABULARY], dtype=np.float32)

    def encode_documents(self, texts):
        return np.stack([self.vector(value) for value in texts])

    def encode_query(self, value):
        return self.vector(value)


class LengthCrossEncoder:
    """Fake cross-encoder: the score is the number of characters of the product text."""

    def __init__(self):
        self.calls = []

    def score(self, query, texts):
        self.calls.append((query, list(texts)))
        return np.array([len(value) for value in texts], dtype=float)


PRODUCTS = pd.DataFrame({
    "product_id": [10, 20, 30, 40],
    "product_name": ["leather accent chair", "2 seater leather sofa", "wood dining chair", "chair cushion"],
    "product_class": ["Accent Chairs", "Sofas", None, "Chair Cushions"],
    "category_hierarchy": ["Furniture / Chairs", "Furniture / Sofas", "Furniture / Chairs", None],
    "product_description": ["a soft leather chair", None, "solid wood", "a cushion"],
    "product_features": ["color : brown|upholstered : yes", "seats : 2", None, "material : cotton"],
    "rating_count": [10.0, None, 3.0, 1.0],
    "average_rating": [4.5, None, 4.0, 5.0],
    "review_count": [8.0, None, 2.0, 0.0],
})
QUERIES = pd.DataFrame({"query_id": [1, 2], "query": ["leather chair", "2 seater sofa"]})


@pytest.fixture(scope="module")
def retrievers():
    v2_index = retrieval.build_single_field_index(PRODUCTS, **retrieval.V2_TEXT, k1=systems.V2_K1, b=systems.V2_B)
    long_texts = text.single_field_text(text.product_field_texts(PRODUCTS, clean_features=True))
    semantic_index = embeddings.DenseIndex.from_texts(long_texts, BagOfWordsEncoder(), cache_dir=None)
    hybrid_index = retrieval.HybridRetriever([v2_index, semantic_index], k=60, weights=[0.5, 0.5])
    return systems.Systems(v2_index, semantic_index, hybrid_index)


@pytest.fixture(scope="module")
def builder(retrievers):
    return features.build_feature_builder(PRODUCTS, retrievers, LengthCrossEncoder(), cache_dir=None)


def test_feature_groups_cover_every_feature_once_and_exclude_ids():
    assert len(features.ALL_FEATURES) == len(set(features.ALL_FEATURES))
    assert not {"product_id", "query_id", "query_class", "label", "gain"} & set(features.ALL_FEATURES)
    assert set(features.RATING_FEATURES) <= set(features.FEATURE_GROUPS["numeric"])


def test_query_features_columns_and_row_order(builder):
    result = builder.query_features("leather chair", [30, 10, 40])
    assert list(result.columns) == features.ALL_FEATURES
    assert result.index.tolist() == [30, 10, 40]


def test_retrieval_features_match_the_retrievers(builder, retrievers):
    product_ids = [10, 20, 30, 40]
    result = builder.query_features("leather chair", product_ids)
    expected_bm25 = retrievers.v2_index.scores(["leather", "chair"])
    assert result["bm25_v2_score"].tolist() == pytest.approx(list(expected_bm25))
    hybrid = retrievers.hybrid_index.search("leather chair", k=10).set_index("product_id")
    assert result["rrf_score"].tolist() == pytest.approx(hybrid["score"].reindex(product_ids).tolist())
    assert result["rrf_rank"].tolist() == hybrid["rank"].reindex(product_ids).tolist()
    # Product 10 has both query words: first in BM25 and in cosine similarity.
    assert result.loc[10, "bm25_v2_rank"] == 1 and result.loc[10, "semantic_rank"] == 1


def test_catalog_ranks_count_higher_scores():
    scores = np.array([0.5, 0.9, 0.5, 0.1])
    assert features.catalog_ranks(scores, np.array([1, 0, 2, 3])).tolist() == [1, 2, 2, 4]


def test_text_features(builder):
    result = builder.query_features("leather chair", [10, 20, 30])
    assert result.loc[10, "coverage_product_name"] == 1.0
    assert result.loc[20, "coverage_product_name"] == 0.5
    assert result.loc[30, "coverage_product_class"] == 0.0  # null product_class
    assert result["query_in_product_name"].tolist() == [0.0, 0.0, 0.0]  # "leather accent chair" breaks the sequence
    assert result["number_match"].isna().all()  # no number in the query


def test_query_in_product_name_and_number_match(builder):
    result = builder.query_features("2 seater sofa", [20, 10])
    assert result.loc[20, "query_in_product_name"] == 0.0  # "2 seater leather sofa"
    assert result.loc[20, "number_match"] == 1.0
    assert result.loc[10, "number_match"] == 0.0
    assert builder.query_features("2 seater", [20]).loc[20, "query_in_product_name"] == 1.0


def test_contains_sequence():
    assert features.contains_sequence(["a", "b", "c"], ["b", "c"])
    assert not features.contains_sequence(["a", "b", "c"], ["a", "c"])
    assert not features.contains_sequence(["a"], [])


def test_numeric_and_query_features(builder):
    result = builder.query_features("leather chair", [10, 20, 30])
    assert result.loc[10, "log_rating_count"] == pytest.approx(math.log1p(10))
    assert result.loc[20, "no_rating"] == 1.0 and math.isnan(result.loc[20, "average_rating"])
    assert result.loc[20, "description_words"] == 0.0
    assert result.loc[10, "feature_pairs"] == 2.0
    assert result.loc[30, "product_class_null"] == 1.0
    assert result["query_tokens"].tolist() == [2.0] * 3
    assert result["query_has_number"].tolist() == [0.0] * 3


def test_cross_encoder_gets_the_short_text(builder):
    result = builder.query_features("leather chair", [10])
    query, texts = builder.cross_encoder.calls[-1]
    assert query == "leather chair"
    assert texts == ["leather accent chair Accent Chairs Furniture / Chairs"]
    assert result.loc[10, "cross_encoder_score"] == len(texts[0])


def test_without_cross_encoder_the_score_is_null(retrievers):
    builder = features.build_feature_builder(PRODUCTS, retrievers, cross_encoder=None, cache_dir=None)
    assert builder.query_features("leather chair", [10, 20])["cross_encoder_score"].isna().all()


def test_build_joins_features_to_candidates(builder):
    run = {1: [10, 30, 40], 2: [20, 10]}
    candidates = ranking.candidate_table(run, {1: {10: "Exact"}})
    built = builder.build(candidates, QUERIES)
    assert built[["query_id", "product_id"]].values.tolist() == candidates[["query_id", "product_id"]].values.tolist()
    assert set(features.ALL_FEATURES) <= set(built.columns)
    assert built.loc[built["query_id"] == 2, "query_has_number"].eq(1.0).all()


def test_embedding_features_are_the_ones_that_use_vectors():
    assert set(features.EMBEDDING_FEATURES) <= set(features.ALL_FEATURES)
    assert not set(features.EMBEDDING_FEATURES) & set(features.FEATURE_GROUPS["cross_encoder"])


class CountingEncoder(BagOfWordsEncoder):
    def __init__(self):
        self.queries = 0

    def encode_query(self, value):
        self.queries += 1
        return super().encode_query(value)


def test_without_embeddings_the_encoder_is_not_called_and_the_rest_is_unchanged():
    encoder = CountingEncoder()
    v2_index = retrieval.build_single_field_index(PRODUCTS, **retrieval.V2_TEXT, k1=systems.V2_K1, b=systems.V2_B)
    long_texts = text.single_field_text(text.product_field_texts(PRODUCTS, clean_features=True))
    semantic_index = embeddings.DenseIndex.from_texts(long_texts, encoder, cache_dir=None)
    retrievers = systems.Systems(v2_index, semantic_index, retrieval.HybridRetriever([v2_index, semantic_index]))
    builder = features.build_feature_builder(PRODUCTS, retrievers, LengthCrossEncoder(), cache_dir=None)
    full = builder.query_features("leather chair", [10, 20])
    calls = encoder.queries
    lexical = builder.query_features("leather chair", [10, 20], use_embeddings=False)
    assert encoder.queries == calls
    assert lexical[features.EMBEDDING_FEATURES].isna().all().all()
    pd.testing.assert_frame_equal(lexical[features.LEXICAL_RERANKER_FEATURES], full[features.LEXICAL_RERANKER_FEATURES])
    assert len(features.LEXICAL_RERANKER_FEATURES) == len(features.ALL_FEATURES) - len(features.EMBEDDING_FEATURES)


def test_ablation_feature_sets_remove_each_used_group():
    sets = features.ablation_feature_sets(features.LEXICAL_RERANKER_FEATURES)
    assert "without cross_encoder" in sets and "without rating" in sets
    assert not set(features.FEATURE_GROUPS["text"]) & set(sets["without text"])
    assert "short_cosine" not in sets["without numeric"]  # never in the lexical base
    full = features.ablation_feature_sets(features.ALL_FEATURES)
    assert len(full) == len(features.FEATURE_GROUPS) + 1


def test_candidate_features_joins_the_same_features_to_every_retrieval(builder, retrievers):
    query_frame = QUERIES.head(1)
    indexes = {"BM25 v2": retrievers.v2_index, "hybrid": retrievers.hybrid_index}
    runs, tables, n_pairs = features.candidate_features(indexes, builder, query_frame, {1: {10: "Exact"}})
    assert set(runs) == set(tables) == set(indexes)
    both = tables["BM25 v2"].merge(tables["hybrid"], on=["query_id", "product_id"], suffixes=("_a", "_b"))
    assert np.allclose(both["bm25_v2_score_a"], both["bm25_v2_score_b"])
    assert n_pairs == len(pd.concat(tables.values()).drop_duplicates(["query_id", "product_id"]))
