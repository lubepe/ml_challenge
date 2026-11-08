import numpy as np
import pandas as pd
import pytest

from wands_search import embeddings, retrieval

VOCABULARY = ["leather", "chair", "sofa", "wood", "ottoman"]


class BagOfWordsEncoder:
    """Deterministic encoder for tests: one dimension per word of VOCABULARY, no model download."""

    cache_key = "bag-of-words"

    def __init__(self):
        self.documents_encoded = 0
        self.queries: list[str] = []

    def vector(self, text: str) -> np.ndarray:
        words = text.lower().split()
        return np.array([words.count(word) for word in VOCABULARY], dtype=np.float32)

    def encode_documents(self, texts):
        self.documents_encoded += len(texts)
        return np.stack([self.vector(text) for text in texts])

    def encode_query(self, text):
        self.queries.append(text)
        return self.vector(text)


TEXTS = pd.Series(["leather chair", "leather sofa", "wood chair", "ottoman"], index=[10, 20, 30, 40])


@pytest.fixture()
def index():
    return embeddings.DenseIndex.from_texts(TEXTS, BagOfWordsEncoder(), cache_dir=None)


def test_normalize_gives_unit_rows_and_keeps_zero_rows():
    vectors = embeddings.normalize(np.array([[3.0, 4.0], [0.0, 0.0]]))
    assert np.allclose(vectors, [[0.6, 0.8], [0.0, 0.0]])


def test_scores_are_cosine_similarities(index):
    # "leather chair" against "leather chair" (1), "leather sofa" and "wood chair" (0.5), "ottoman" (0).
    scores = index.scores(np.array([1, 1, 0, 0, 0], dtype=np.float32))
    assert scores == pytest.approx([1.0, 0.5, 0.5, 0.0])


def test_search_orders_by_score_and_breaks_ties_by_product_id(index):
    result = index.search("leather chair", k=10)
    assert result["product_id"].tolist() == [10, 20, 30, 40]
    assert result["rank"].tolist() == [1, 2, 3, 4]


def test_ties_at_the_cut_are_broken_by_product_id():
    texts = pd.Series(["chair", "chair", "chair"], index=[9, 2, 5])
    tied = embeddings.DenseIndex.from_texts(texts, BagOfWordsEncoder(), cache_dir=None)
    assert tied.search("chair", k=2)["product_id"].tolist() == [2, 5]


def test_dense_search_returns_products_without_query_words(index):
    # Unlike BM25, every product gets a score; the order is what matters.
    assert len(index.search("ottoman", k=10)) == 4


def test_search_cuts_at_k(index):
    assert len(index.search("leather chair", k=2)) == 2


@pytest.mark.parametrize("query", [None, 3, "", "   "])
def test_invalid_queries_raise(index, query):
    with pytest.raises(retrieval.InvalidQueryError):
        index.search(query)


def test_query_with_only_special_characters_returns_nothing(index):
    result = index.search("&/()", k=10)
    assert result.empty
    assert list(result.columns) == ["rank", "product_id", "score"]


def test_long_query_is_cut_before_encoding(index):
    index.search("chair " * 200, k=1)
    assert len(index.encoder.queries[-1]) == retrieval.MAX_QUERY_CHARS


def test_encode_by_length_returns_vectors_in_the_original_order():
    seen_batches = []

    def embed(batch):
        seen_batches.append(batch)
        return [np.array([len(text)], dtype=np.float32) for text in batch]

    vectors = embeddings.encode_by_length(embed, ["ccc", "a", "bb"])
    assert seen_batches == [["a", "bb", "ccc"]]
    assert vectors[:, 0].tolist() == [3, 1, 2]


def test_cache_reuses_vectors_of_the_same_texts(tmp_path):
    encoder = BagOfWordsEncoder()
    first = embeddings.cached_document_vectors([1, 2], ["chair", "sofa"], encoder, tmp_path)
    second = embeddings.cached_document_vectors([1, 2], ["chair", "sofa"], encoder, tmp_path)
    assert encoder.documents_encoded == 2
    assert np.array_equal(first, second)


def test_cache_encodes_again_when_texts_change(tmp_path):
    encoder = BagOfWordsEncoder()
    embeddings.cached_document_vectors([1, 2], ["chair", "sofa"], encoder, tmp_path)
    embeddings.cached_document_vectors([1, 2], ["chair", "wood"], encoder, tmp_path)
    assert encoder.documents_encoded == 4


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        embeddings.DenseIndex([1, 2], np.ones((3, 2)), BagOfWordsEncoder())
