import math

import pandas as pd
import pytest

from wands_search import text


def test_tokenize_lowercases_and_splits_on_punctuation():
    assert text.tokenize('Fawkes 36" Blue-Vanity') == ["fawkes", "36", "blue", "vanity"]


def test_tokenize_keeps_order_and_repetitions():
    assert text.tokenize("chair, accent chair") == ["chair", "accent", "chair"]


def test_tokenize_removes_accents():
    assert text.tokenize("Wall Décor") == ["wall", "decor"]


def test_inch_marks_of_queries_and_products_give_the_same_tokens():
    # queries write 36", product_name writes 36 ''
    assert text.tokenize('writing desk 48"') == text.tokenize("writing desk 48 ''")


def test_decimals_and_fractions_are_split():
    # Documented behavior of the baseline; keeping them whole is a variant to test.
    assert text.tokenize("zachary 72.5") == ["zachary", "72", "5"]
    assert text.tokenize("3-3/4") == ["3", "3", "4"]


@pytest.mark.parametrize("value", [None, math.nan, "", "   ", "&/()"])
def test_tokenize_without_tokens(value):
    assert text.tokenize(value) == []


def test_strip_accents():
    assert text.strip_accents("décor café") == "decor cafe"


def make_products():
    return pd.DataFrame({
        "product_id": [7, 8],
        "product_name": ["Leather Accent Chair", "Ottoman"],
        "product_class": ["Accent Chairs", None],
        "category_hierarchy": ["Furniture / Living Room", None],
        "product_description": [None, "soft ottoman"],
        "product_features": ["color : caramel|overallwidth-sidetoside:64.7", None],
        "rating_count": [1.0, None],
    })


def test_feature_values_text_drops_keys():
    assert text.feature_values_text("color : caramel|overallwidth-sidetoside:64.7") == "caramel 64.7"
    assert text.feature_values_text(None) == ""


def test_product_field_texts_one_row_per_product_and_empty_for_missing():
    texts = text.product_field_texts(make_products())
    assert list(texts.index) == [7, 8]
    assert list(texts.columns) == text.SEARCH_FIELDS
    assert texts.loc[7, "product_features"] == "caramel 64.7"
    assert texts.loc[8, "product_class"] == ""
    assert texts.loc[7, "product_description"] == ""


def test_single_field_text_joins_all_fields():
    single = text.single_field_text(text.product_field_texts(make_products()))
    assert text.tokenize(single.loc[7]) == [
        "leather", "accent", "chair", "accent", "chairs", "furniture", "living", "room", "caramel", "64", "7",
    ]
    assert text.tokenize(single.loc[8]) == ["ottoman", "soft", "ottoman"]


@pytest.mark.parametrize(
    ("token", "stem"),
    [
        ("chairs", "chair"),
        ("tables", "table"),
        ("bodies", "body"),
        ("mattresses", "mattress"),
        ("benches", "bench"),
        ("boxes", "box"),
        ("dishes", "dish"),
        ("mattress", "mattress"),
        ("glass", "glass"),
        ("cactus", "cactus"),
        ("toes", "toe"),
        ("series", "sery"),
        ("36", "36"),
    ],
)
def test_s_stem_rules(token, stem):
    assert text.s_stem(token) == stem


def test_singular_and_plural_give_the_same_token():
    for singular, plural in [("chair", "chairs"), ("mattress", "mattresses"), ("bench", "benches"),
                             ("box", "boxes"), ("table", "tables"), ("body", "bodies")]:
        assert text.s_stem(singular) == text.s_stem(plural)


def test_tokenize_with_stem():
    assert text.tokenize("Leather Chairs", stem=True) == ["leather", "chair"]


@pytest.mark.parametrize(
    ("value", "droppable"),
    [("yes", True), ("No", True), ("64.7", True), ("600 ; 276 ; 456", True), ("1/4", True),
     ("5 years", False), ("caramel", False), ("queen", False), ("e12", False)],
)
def test_droppable_feature_values(value, droppable):
    assert text.is_droppable_feature_value(value) == droppable


def test_clean_feature_values_text():
    value = "color : caramel|footboard : no|weightcapacity:500|warrantylength:5 years"
    assert text.feature_values_text(value) == "caramel no 500 5 years"
    assert text.feature_values_text(value, clean=True) == "caramel 5 years"
