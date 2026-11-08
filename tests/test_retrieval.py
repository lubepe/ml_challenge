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


def test_stemmed_index_matches_singular_query_with_plural_product():
    texts = pd.Series(["leather sofas", "wood benches", "mattresses"], index=[1, 2, 3])
    stemmed = retrieval.BM25Index.from_texts(texts, stem=True)
    assert stemmed.search("sofa", k=10)["product_id"].tolist() == [1]
    assert stemmed.search("bench", k=10)["product_id"].tolist() == [2]
    assert stemmed.search("mattress", k=10)["product_id"].tolist() == [3]
    plain = retrieval.BM25Index.from_texts(texts)
    assert plain.search("sofa", k=10).empty


def test_single_field_index_with_clean_features_drops_yes_no_and_numbers():
    products = pd.DataFrame({
        "product_id": [1, 2],
        "product_name": ["sofa", "lamp"],
        "product_class": [None, None],
        "category_hierarchy": [None, None],
        "product_description": [None, None],
        "product_features": ["footboard : no|width:500", "color : caramel"],
    })
    clean = retrieval.build_single_field_index(products, **retrieval.V2_TEXT)
    assert clean.search("no", k=10).empty
    assert clean.search("500", k=10).empty
    assert clean.search("caramel", k=10)["product_id"].tolist() == [2]


def test_rrf_score_is_the_sum_of_reciprocal_ranks():
    fused = retrieval.rrf_fuse([[1, 2], [2, 3]], k=60)
    assert fused["product_id"].tolist() == [2, 1, 3]
    assert fused["score"].tolist() == pytest.approx([1 / 62 + 1 / 61, 1 / 61, 1 / 62])


@pytest.mark.parametrize(("k", "winner"), [(60, "B"), (1, "A")])
def test_rrf_k_decides_between_top_of_one_list_and_agreement(k, winner):
    # A (id 1) is first in list one only; B (id 2) is fifth in both lists.
    list_one = [1, 11, 12, 13, 2]
    list_two = [21, 22, 23, 24, 2]
    fused = retrieval.rrf_fuse([list_one, list_two], k=k)
    position = {pid: rank for pid, rank in zip(fused["product_id"], fused["rank"])}
    assert (position[2] < position[1]) == (winner == "B")


def test_rrf_ties_are_broken_by_product_id():
    assert retrieval.rrf_fuse([[5, 3], [3, 5]])["product_id"].tolist() == [3, 5]


def test_rrf_of_empty_lists_is_empty():
    assert retrieval.rrf_fuse([[], []]).empty


class FixedRetriever:
    def __init__(self, ranking):
        self.ranking = ranking
        self.depths = []

    def search(self, query, k):
        self.depths.append(k)
        return pd.DataFrame({"product_id": self.ranking[:k]})


def test_hybrid_fuses_each_retriever_at_its_depth_and_cuts_at_k():
    first, second = FixedRetriever([1, 2, 3]), FixedRetriever([3, 4])
    hybrid = retrieval.HybridRetriever([first, second], depth=2)
    result = hybrid.search("chair", k=2)
    assert first.depths == second.depths == [2]
    assert result["product_id"].tolist() == [1, 3]


def test_hybrid_returns_bm25_results_when_the_other_list_is_empty(index):
    hybrid = retrieval.HybridRetriever([index, FixedRetriever([])])
    assert hybrid.search("ottoman", k=10)["product_id"].tolist() == [20]


@pytest.mark.parametrize("query", [None, "", "  "])
def test_hybrid_rejects_invalid_queries(query):
    with pytest.raises(retrieval.InvalidQueryError):
        retrieval.HybridRetriever([FixedRetriever([1])]).search(query)


def test_v3_index_finds_products_by_yes_keys():
    products = pd.DataFrame({
        "product_id": [1, 2],
        "product_name": ["armchair", "armchair"],
        "product_class": [None, None],
        "category_hierarchy": [None, None],
        "product_description": [None, None],
        "product_features": ["upholstered : yes", "upholstered : no"],
    })
    v3 = retrieval.build_single_field_index(products, **retrieval.V3_TEXT)
    assert v3.search("upholstered", k=10)["product_id"].tolist() == [1]
    v2 = retrieval.build_single_field_index(products, **retrieval.V2_TEXT)
    assert v2.search("upholstered", k=10).empty


def test_weighted_rrf_multiplies_each_list_contribution():
    fused = retrieval.rrf_fuse([[1], [2]], k=60, weights=[0.8, 0.2])
    assert fused["product_id"].tolist() == [1, 2]
    assert fused["score"].tolist() == pytest.approx([0.8 / 61, 0.2 / 61])


def test_equal_weights_give_the_order_of_standard_rrf():
    rankings = [[1, 2, 3], [3, 4, 1]]
    standard = retrieval.rrf_fuse(rankings)
    halves = retrieval.rrf_fuse(rankings, weights=[0.5, 0.5])
    assert standard["product_id"].tolist() == halves["product_id"].tolist()


@pytest.mark.parametrize(("weight", "winner"), [(0.8, 1), (0.2, 2)])
def test_the_weight_decides_between_the_tops_of_two_lists(weight, winner):
    fused = retrieval.rrf_fuse([[1, 2], [2, 1]], weights=[weight, 1 - weight])
    assert fused["product_id"].iloc[0] == winner


def test_weights_must_match_the_lists():
    with pytest.raises(ValueError):
        retrieval.rrf_fuse([[1], [2]], weights=[1.0])
    with pytest.raises(ValueError):
        retrieval.HybridRetriever([FixedRetriever([1])], weights=[0.5, 0.5])


def test_hybrid_uses_its_weights():
    hybrid = retrieval.HybridRetriever([FixedRetriever([1, 2]), FixedRetriever([2, 1])], weights=[0.2, 0.8])
    assert hybrid.search("chair", k=1)["product_id"].tolist() == [2]
