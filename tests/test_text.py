import math

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
