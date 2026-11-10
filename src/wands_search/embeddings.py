"""Dense (vector) retrieval with a pre-trained embedding model, without fine-tuning.

The model runs on ONNX Runtime through ``fastembed`` (``torch`` does not install on the
development machine; see docs/EVALUATION.md). Each product text becomes a normalized vector
once, and a query is scored against every product by cosine similarity (exact search).
"""

import copy
import hashlib
import json
import shutil
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from wands_search.retrieval import MAX_QUERY_CHARS, prepare_query

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
# Instruction the model card recommends for short queries against long passages.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
BATCH_SIZE = 64
# Inputs longer than this many wordpieces are cut by the model.
MODEL_MAX_WORDPIECES = 512
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"

# Product embeddings published in the GitHub Release "embeddings-v1", keyed by the cache file
# name of cached_document_vectors, with the sha256 of each file.
RELEASE_URL = "https://github.com/lubepe/ml_challenge/releases/download/embeddings-v1"
RELEASE_FILES = {
    # Long text: semantic search and hybrid search.
    "a69ae5a32d14c0466cb7": "17a2f13764753531a9145c3d8f2c44771276221394e171543dc2ad24e1e26bda",
    # Short text: reranker feature short_cosine.
    "c22b318b1b827f635905": "2ef8c1e976a4c719975f8b682637aeab8284d2d43af60d04d3cd2164aeecfbcf",
}
DOWNLOAD_TIMEOUT_SECONDS = 60


class Encoder(Protocol):
    """Turns product texts and queries into vectors of the same space."""

    @property
    def cache_key(self) -> str:
        """Identifies the model and options that produce the product vectors."""
        ...

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        """One row per text."""
        ...

    def encode_query(self, text: str) -> np.ndarray:
        """One vector."""
        ...


def normalize(vectors: np.ndarray) -> np.ndarray:
    """Scale each row to length 1, so that the dot product is the cosine similarity. Zero rows stay zero."""
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)


def encode_by_length(embed: Callable[[list[str]], Iterable[np.ndarray]], texts: Sequence[str]) -> np.ndarray:
    """Call ``embed`` on the texts sorted by length and return the vectors in the original order.

    Batches are padded to their longest text, so sorting first puts texts of similar length
    together and cuts the padding. The vectors do not depend on the order.
    """
    texts = list(texts)
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    order = np.argsort([len(text) for text in texts], kind="stable")
    sorted_vectors = np.asarray(list(embed([texts[i] for i in order])), dtype=np.float32)
    vectors = np.empty_like(sorted_vectors)
    vectors[order] = sorted_vectors
    return vectors


class FastEmbedEncoder:
    """``fastembed`` model. ``query_prefix`` is added to the query only, never to products."""

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL,
        query_prefix: str = "",
        cache_dir: Path = DEFAULT_CACHE_DIR,
        batch_size: int = BATCH_SIZE,
        threads: int | None = None,
    ):
        from fastembed import TextEmbedding

        self.model_name = model_name
        self.query_prefix = query_prefix
        self.batch_size = batch_size
        self._model = TextEmbedding(model_name, cache_dir=str(Path(cache_dir) / "fastembed"), threads=threads)

    @property
    def cache_key(self) -> str:
        # The prefix is left out: it changes only the query vectors.
        import fastembed

        return f"{self.model_name}|fastembed-{fastembed.__version__}"

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return normalize(encode_by_length(lambda batch: self._model.embed(batch, batch_size=self.batch_size), texts))

    def encode_query(self, text: str) -> np.ndarray:
        return normalize(next(iter(self._model.embed([self.query_prefix + text]))))

    def with_query_prefix(self, query_prefix: str) -> "FastEmbedEncoder":
        """The same loaded model with another query prefix (product vectors do not change)."""
        other = copy.copy(self)
        other.query_prefix = query_prefix
        return other

    def wordpiece_counts(self, texts: Sequence[str]) -> np.ndarray:
        """Wordpieces of each text in the model tokenizer, without the cut at ``MODEL_MAX_WORDPIECES``.

        Includes the two special wordpieces the model adds to every input ([CLS] and [SEP]).
        """
        tokenizer = copy.deepcopy(self._model.model.tokenizer)
        tokenizer.no_padding()
        tokenizer.no_truncation()
        return np.array([len(encoding.ids) for encoding in tokenizer.encode_batch(list(texts))])


def texts_digest(product_ids: Sequence[int], texts: Sequence[str]) -> str:
    """Hash of the product ids and their texts, in order."""
    payload = json.dumps([[int(pid), text] for pid, text in zip(product_ids, texts)], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    """sha256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_url(url: str, destination: Path) -> None:
    """Download ``url`` into ``destination``."""
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response, open(destination, "wb") as file:
        shutil.copyfileobj(response, file)


def download_release_file(name: str, path: Path) -> bool:
    """Download the Release file ``name`` into ``path`` and check its sha256.

    Returns False, leaving nothing at ``path``, when ``name`` is not in RELEASE_FILES, the
    download fails or the sha256 does not match.
    """
    expected_sha256 = RELEASE_FILES.get(name)
    if expected_sha256 is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    url = f"{RELEASE_URL}/{name}.npy"
    print(f"Downloading product embeddings from {url}")
    try:
        fetch_url(url, partial)
    except OSError as error:
        partial.unlink(missing_ok=True)
        print(f"Download failed ({error}); encoding the products locally")
        return False
    if file_sha256(partial) != expected_sha256:
        partial.unlink()
        print("Downloaded file has the wrong sha256; encoding the products locally")
        return False
    partial.replace(path)
    return True


def cached_document_vectors(
    product_ids: Sequence[int],
    texts: Sequence[str],
    encoder: Encoder,
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    download: bool = True,
) -> np.ndarray:
    """Product vectors, read from ``cache_dir/embeddings`` when the same encoder already saw the same texts.

    The file name holds a hash of the encoder key, the product ids and the texts, so any change
    in one of them makes a new file. When the file is missing but published in the GitHub Release
    (RELEASE_FILES) and ``download`` is True, it is downloaded and checked by sha256; if that
    fails, the products are encoded locally. ``cache_dir=None`` disables the cache.
    """
    if cache_dir is None:
        return encoder.encode_documents(texts)
    digest = hashlib.sha256(f"{encoder.cache_key}|{texts_digest(product_ids, texts)}".encode()).hexdigest()[:20]
    path = Path(cache_dir) / "embeddings" / f"{digest}.npy"
    if path.exists():
        return np.load(path)
    if download and download_release_file(digest, path):
        return np.load(path)
    vectors = encoder.encode_documents(texts)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, vectors)
    return vectors


class DenseIndex:
    """Normalized vectors of the products, keyed by ``product_id``, with exact cosine search."""

    def __init__(self, product_ids: Sequence[int], vectors: np.ndarray, encoder: Encoder):
        vectors = np.asarray(vectors, dtype=np.float32)
        if len(product_ids) != len(vectors):
            raise ValueError("product_ids and vectors must have the same length")
        self.product_ids = np.asarray(product_ids)
        self.vectors = normalize(vectors)
        self.encoder = encoder

    @classmethod
    def from_texts(cls, texts: pd.Series, encoder: Encoder, cache_dir: Path | None = DEFAULT_CACHE_DIR) -> "DenseIndex":
        """Build an index from a Series of texts indexed by ``product_id``."""
        product_ids, values = texts.index.to_list(), texts.to_list()
        return cls(product_ids, cached_document_vectors(product_ids, values, encoder, cache_dir), encoder)

    @property
    def index_bytes(self) -> int:
        """Memory of the vector matrix."""
        return self.vectors.nbytes

    def scores(self, query_vector: np.ndarray) -> np.ndarray:
        """Cosine similarity of every product to ``query_vector``, in the order of ``product_ids``."""
        return self.vectors @ normalize(query_vector)

    def search_vector(self, query_vector: np.ndarray, k: int) -> pd.DataFrame:
        """Top ``k`` products by score and then by ``product_id`` (ties), same columns as ``BM25Index``."""
        scores = self.scores(query_vector)
        k = min(k, len(scores))
        if k <= 0:
            return pd.DataFrame({
                "rank": np.zeros(0, dtype=int),
                "product_id": self.product_ids[:0],
                "score": np.zeros(0, dtype=float),
            })
        # Keep every product tied with the k-th score, so that ties are broken by product_id.
        threshold = np.partition(scores, len(scores) - k)[len(scores) - k]
        candidates = np.flatnonzero(scores >= threshold)
        order = np.lexsort((self.product_ids[candidates], -scores[candidates]))[:k]
        top = candidates[order]
        return pd.DataFrame({
            "rank": np.arange(1, len(top) + 1),
            "product_id": self.product_ids[top],
            "score": scores[top].astype(float),
        })

    def search(self, query: object, k: int = 100) -> pd.DataFrame:
        """Validate ``query`` with the BM25 rules and return its top ``k`` products.

        A query without any token (only special characters) returns nothing, as in the BM25.
        The text is cut at ``MAX_QUERY_CHARS``; the model then cuts it at its own token limit.
        """
        if not prepare_query(query).tokens:
            return self.search_vector(np.zeros(self.vectors.shape[1], dtype=np.float32), 0)
        return self.search_vector(self.encoder.encode_query(query.strip()[:MAX_QUERY_CHARS]), k)
