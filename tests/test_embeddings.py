import shutil

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


def release_file(tmp_path, monkeypatch, vectors, published_sha256=None):
    """Publish ``vectors`` as a fake Release file for the texts ["chair", "sofa"]; returns its cache name."""
    source = tmp_path / "release" / "vectors.npy"
    source.parent.mkdir()
    np.save(source, vectors)
    encoder = BagOfWordsEncoder()
    digest = embeddings.hashlib.sha256(
        f"{encoder.cache_key}|{embeddings.texts_digest([1, 2], ['chair', 'sofa'])}".encode()
    ).hexdigest()[:20]
    monkeypatch.setattr(
        embeddings, "RELEASE_FILES", {digest: published_sha256 or embeddings.file_sha256(source)}
    )
    monkeypatch.setattr(embeddings, "fetch_url", lambda url, destination: shutil.copy(source, destination))
    return digest


def test_missing_cache_file_is_downloaded_from_the_release(tmp_path, monkeypatch):
    published = np.full((2, len(VOCABULARY)), 7, dtype=np.float32)
    digest = release_file(tmp_path, monkeypatch, published)
    encoder = BagOfWordsEncoder()
    vectors = embeddings.cached_document_vectors([1, 2], ["chair", "sofa"], encoder, tmp_path / "cache")
    assert encoder.documents_encoded == 0
    assert np.array_equal(vectors, published)
    assert (tmp_path / "cache" / "embeddings" / f"{digest}.npy").exists()


def test_download_with_wrong_sha256_falls_back_to_local_encoding(tmp_path, monkeypatch):
    digest = release_file(tmp_path, monkeypatch, np.zeros((2, len(VOCABULARY))), published_sha256="0" * 64)
    encoder = BagOfWordsEncoder()
    vectors = embeddings.cached_document_vectors([1, 2], ["chair", "sofa"], encoder, tmp_path / "cache")
    assert encoder.documents_encoded == 2
    assert vectors[0].tolist() == [0, 1, 0, 0, 0]
    assert not (tmp_path / "cache" / "embeddings" / f"{digest}.part").exists()


def test_failed_download_falls_back_to_local_encoding(tmp_path, monkeypatch):
    release_file(tmp_path, monkeypatch, np.zeros((2, len(VOCABULARY))))

    def fail(url, destination):
        raise OSError("no network")

    monkeypatch.setattr(embeddings, "fetch_url", fail)
    encoder = BagOfWordsEncoder()
    embeddings.cached_document_vectors([1, 2], ["chair", "sofa"], encoder, tmp_path / "cache")
    assert encoder.documents_encoded == 2


def test_download_can_be_turned_off(tmp_path, monkeypatch):
    release_file(tmp_path, monkeypatch, np.zeros((2, len(VOCABULARY))))
    encoder = BagOfWordsEncoder()
    embeddings.cached_document_vectors([1, 2], ["chair", "sofa"], encoder, tmp_path / "cache", download=False)
    assert encoder.documents_encoded == 2


def test_release_files_list_the_two_published_embeddings():
    assert embeddings.RELEASE_URL.endswith("/releases/download/embeddings-v1")
    assert len(embeddings.RELEASE_FILES) == 2
    assert all(len(sha256) == 64 for sha256 in embeddings.RELEASE_FILES.values())


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        embeddings.DenseIndex([1, 2], np.ones((3, 2)), BagOfWordsEncoder())
