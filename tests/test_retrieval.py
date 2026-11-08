import math

import pandas as pd
import pytest

from wands_search import retrieval

# Toy catalog of docs/explanations: product_name only, so the scores can be checked by hand.
TEXTS = pd.Series(
    ["leather accent chair", "leather ottoman", "wood dining chair", "chair cushion"],
    index=[10, 20, 30, 40],
)
K1, B = 1.2, 0.75


def lucene_score(tf: int, n: int, length: int, n_docs: int = 4, avg_length: float = 2.5) -> float:
    idf = math.log(1 + (n_docs - n + 0.5) / (n + 0.5))
    return idf * tf / (tf + K1 * (1 - B + B * length / avg_length))


@pytest.fixture(scope="module")
def index():
    return retrieval.BM25Index.from_texts(TEXTS, k1=K1, b=B)


def test_scores_match_the_formula(index):
    # "leather chair" on product 10: leather (n=2) and chair (n=3), length 3.
    expected = lucene_score(1, 2, 3) + lucene_score(1, 3, 3)
    assert index.scores(["leather", "chair"])[0] == pytest.approx(expected, rel=1e-5)


def test_search_orders_by_score_and_returns_only_matches(index):
    result = index.search("leather chair", k=10)
    assert result["product_id"].tolist() == [10, 20, 40, 30]
    assert result["rank"].tolist() == [1, 2, 3, 4]
    assert result["score"].is_monotonic_decreasing


def test_search_cuts_at_k(index):
    assert len(index.search("leather chair", k=2)) == 2


def test_products_without_query_tokens_are_not_returned(index):
    assert index.search("ottoman", k=10)["product_id"].tolist() == [20]


def test_ties_are_broken_by_product_id():
    texts = pd.Series(["red chair", "red chair", "blue sofa"], index=[7, 3, 5])
    tied = retrieval.BM25Index.from_texts(texts)
    assert tied.search("chair", k=10)["product_id"].tolist() == [3, 7]


def test_query_uses_the_same_tokenization_as_products(index):
    assert index.search("LEATHER-Chair!!", k=10)["product_id"].tolist() == [10, 20, 40, 30]


def test_query_without_known_tokens_returns_nothing(index):
    assert index.search("minnestrista", k=10).empty


def test_query_with_only_special_characters_returns_nothing(index):
    assert index.search('&/()"', k=10).empty


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_empty_query_is_rejected(index, query):
    with pytest.raises(retrieval.InvalidQueryError):
        index.search(query)


@pytest.mark.parametrize("query", [None, 42, ["chair"]])
def test_non_string_query_is_rejected(index, query):
    with pytest.raises(retrieval.InvalidQueryError):
        index.search(query)


def test_long_query_is_truncated():
    prepared = retrieval.prepare_query("chair " * 1000)
    assert prepared.truncated
    assert len(prepared.tokens) == retrieval.MAX_QUERY_TOKENS


def test_short_query_is_not_truncated():
    prepared = retrieval.prepare_query("leather chair")
    assert prepared == retrieval.PreparedQuery(tokens=["leather", "chair"], truncated=False)


def test_long_query_still_searches(index):
    assert not index.search("leather chair " * 1000, k=10).empty


def test_single_field_index_uses_all_fields():
    products = pd.DataFrame({
        "product_id": [1, 2],
        "product_name": ["sofa", "lamp"],
        "product_class": ["Sofas", "Table Lamps"],
        "category_hierarchy": [None, "Lighting / Lamps"],
        "product_description": ["comfortable", None],
        "product_features": ["color : caramel", "material : brass"],
    })
    index = retrieval.build_single_field_index(products)
    assert index.search("caramel", k=10)["product_id"].tolist() == [1]
    assert index.search("lighting", k=10)["product_id"].tolist() == [2]


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        retrieval.BM25Index([1, 2], [["a"]])


def test_index_size_properties(index):
    # 7 distinct tokens plus the empty token that bm25s adds.
    assert index.vocabulary_size == 8
    assert index.index_bytes > 0
