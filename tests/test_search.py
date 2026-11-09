import numpy as np
import pytest

from test_features import PRODUCTS, BagOfWordsEncoder, LengthCrossEncoder
from wands_search import embeddings, features, retrieval, search, systems, text


class ScoreFeatureModel:
    """Fake reranker: the score is minus the BM25 v2 position, so it keeps the BM25 order."""

    def predict(self, rows, num_iteration=None):
        return -rows["bm25_v2_rank"].to_numpy()


def make_pipeline(feature_columns, cross_encoder=None):
    v2_index = retrieval.build_single_field_index(PRODUCTS, **retrieval.V2_TEXT, k1=systems.V2_K1, b=systems.V2_B)
    long_texts = text.single_field_text(text.product_field_texts(PRODUCTS, clean_features=True))
    semantic_index = embeddings.DenseIndex.from_texts(long_texts, BagOfWordsEncoder(), cache_dir=None)
    retrievers = systems.Systems(v2_index, semantic_index, retrieval.HybridRetriever([v2_index, semantic_index]))
    builder = features.build_feature_builder(PRODUCTS, retrievers, cross_encoder, cache_dir=None)
    return search.SearchPipeline(PRODUCTS, retrievers.hybrid_index, builder, ScoreFeatureModel(), feature_columns)


@pytest.fixture(scope="module")
def pipeline():
    return make_pipeline(["bm25_v2_rank", "semantic_cosine"])


def test_search_returns_top_k_with_names(pipeline):
    response = pipeline.search("leather chair", k=2)
    assert response.results["rank"].tolist() == [1, 2]
    assert response.results.loc[0, "product_id"] == 10  # "leather accent chair": first in BM25 v2
    assert response.results.loc[0, "product_name"] == "leather accent chair"
    assert response.results["reranked"].all()
    assert response.retrieval_ms >= 0 and response.ranking_ms >= 0 and not response.truncated


@pytest.mark.parametrize("query", ["", "   ", None, 42, ["leather"]])
def test_invalid_queries_raise(pipeline, query):
    with pytest.raises(retrieval.InvalidQueryError):
        pipeline.search(query)


def test_only_special_characters_returns_nothing(pipeline):
    response = pipeline.search("&/()!?")
    assert response.results.empty
    assert list(response.results.columns) == search.RESULT_COLUMNS


def test_long_query_is_cut_and_flagged(pipeline):
    response = pipeline.search("leather chair " * 100)
    assert response.truncated
    assert not response.results.empty


@pytest.mark.parametrize("k", [0, -1, 201, 2.5, "10", True])
def test_invalid_k_raises(pipeline, k):
    with pytest.raises(ValueError):
        pipeline.search("leather chair", k=k)


def test_cross_encoder_is_dropped_when_the_model_does_not_use_it():
    cross_encoder = LengthCrossEncoder()
    pipeline = make_pipeline(["bm25_v2_rank"], cross_encoder=cross_encoder)
    pipeline.search("leather chair")
    assert pipeline.builder.cross_encoder is None and cross_encoder.calls == []
    assert not pipeline.use_embeddings


def test_cross_encoder_runs_when_the_model_uses_it():
    cross_encoder = LengthCrossEncoder()
    pipeline = make_pipeline(["bm25_v2_rank", "cross_encoder_score"], cross_encoder=cross_encoder)
    pipeline.search("leather chair")
    assert len(cross_encoder.calls) == 1


def test_scores_are_missing_only_below_the_reranked_candidates(pipeline):
    response = pipeline.search("chair", k=4)
    assert not np.isnan(response.results["score"]).any()
