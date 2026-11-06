import pandas as pd
import pytest

from wands_search import split

FRACTIONS = {"train": 0.7, "validation": 0.15, "test": 0.15}


def make_groups() -> pd.Series:
    return pd.Series(["a"] * 60 + ["b"] * 40, index=range(100))


def test_every_query_gets_exactly_one_part():
    assignment = split.stratified_split(make_groups(), FRACTIONS, seed=0)

    assert assignment.index.equals(make_groups().index)
    assert assignment.notna().all()
    assert set(assignment) == set(FRACTIONS)


def test_split_is_reproducible_with_same_seed_and_changes_with_other_seed():
    groups = make_groups()

    first = split.stratified_split(groups, FRACTIONS, seed=7)

    assert first.equals(split.stratified_split(groups, FRACTIONS, seed=7))
    assert not first.equals(split.stratified_split(groups, FRACTIONS, seed=8))


def test_fractions_are_kept_within_each_group():
    groups = make_groups()

    assignment = split.stratified_split(groups, FRACTIONS, seed=0)

    assert (assignment[groups == "a"] == "train").sum() == 42
    assert (assignment[groups == "b"] == "train").sum() == 28
    assert (assignment[groups == "a"] == "test").sum() == 9
    assert (assignment[groups == "b"] == "test").sum() == 6


def test_invalid_fractions_raise():
    with pytest.raises(ValueError):
        split.stratified_split(make_groups(), {"train": 0.5, "test": 0.2}, seed=0)


def test_stratification_groups_combines_both_bands():
    profile = pd.DataFrame({
        "exact_fraction": [0.0, 0.01, 0.05, 0.5, 0.0, 0.5],
        "n_judged": [1, 2, 3, 4, 5, 6],
    })

    groups = split.stratification_groups(profile)

    assert groups.iloc[0] == "none|low"
    assert groups.iloc[1] == "up_to_2pct|low"
    assert groups.iloc[2] == "2_to_10pct|medium"
    assert groups.iloc[5] == "over_10pct|high"
