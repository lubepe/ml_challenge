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


def make_profile() -> pd.DataFrame:
    return pd.DataFrame({
        "Exact": [0, 1, 1, 10, 0, 5, 0],
        "Partial": [5, 99, 9, 10, 5, 5, 0],
        "Irrelevant": [0, 0, 0, 0, 1, 0, 1],
        "n_judged": [5, 100, 20, 20, 6, 10, 1],
    }, index=pd.Index([10, 11, 12, 13, 14, 15, 16], name="query_id"))


def test_relevant_queries_drops_queries_without_exact_or_partial():
    kept = split.relevant_queries(make_profile())

    assert 16 not in kept.index
    assert len(kept) == 6


def test_exact_share_ignores_irrelevant_and_is_nan_without_relevant_products():
    shares = split.exact_share(make_profile())

    assert shares.loc[11] == pytest.approx(0.01)
    assert shares.loc[14] == 0.0  # the Irrelevant product does not change the share
    assert pd.isna(shares.loc[16])


def test_stratification_groups_uses_exact_share_of_relevant_not_irrelevant():
    profile = make_profile()

    groups = split.stratification_groups(split.relevant_queries(profile))

    assert groups.loc[10].startswith("none|")
    assert groups.loc[11].startswith("up_to_5pct|")  # 1 / 100
    assert groups.loc[12].startswith("5_to_25pct|")  # 1 / 10
    assert groups.loc[13].startswith("over_25pct|")  # 10 / 20
    # an extra Irrelevant product does not change the band
    assert groups.loc[14].startswith("none|")


def test_stratified_split_carries_rounding_across_groups():
    groups = pd.Series([f"g{i}" for i in range(10) for _ in range(7)], index=range(70))
    fractions = {"train": 0.6, "validation": 0.2, "test": 0.2}

    assignment = split.stratified_split(groups, fractions, seed=0)

    counts = assignment.value_counts()
    assert abs(counts["train"] - 42) <= 1
    assert abs(counts["validation"] - 14) <= 1
    assert abs(counts["test"] - 14) <= 1


def make_queries_and_profile() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for i in range(1, 121):
        rows.append({"query_id": i, "query": f"query {i}",
                     "Exact": i % 5, "Partial": 10 + i % 7, "Irrelevant": 2, "n_judged": 12 + i % 5 + i % 7 + (i % 3) * 40})
    rows.append({"query_id": 200, "query": "leather chair", "Exact": 2, "Partial": 8, "Irrelevant": 0, "n_judged": 10})
    rows.append({"query_id": 201, "query": "Leather Chairs", "Exact": 2, "Partial": 8, "Irrelevant": 0, "n_judged": 10})
    rows.append({"query_id": 300, "query": "no relevant", "Exact": 0, "Partial": 0, "Irrelevant": 3, "n_judged": 3})
    frame = pd.DataFrame(rows)
    return frame[["query_id", "query"]], frame.set_index("query_id")[["Exact", "Partial", "Irrelevant", "n_judged"]]


def test_split_queries_is_disjoint_complete_and_excludes_queries_without_relevant():
    queries, profile = make_queries_and_profile()

    assignment = split.split_queries(profile, queries, seed=87)

    assert assignment.index.is_unique
    assert 300 not in assignment.index
    assert set(assignment.index) == set(profile.index) - {300}
    assert set(assignment) == set(split.SPLIT_FRACTIONS)


def test_split_queries_keeps_near_duplicates_in_the_same_part():
    queries, profile = make_queries_and_profile()

    for seed in range(20):
        assignment = split.split_queries(profile, queries, seed=seed)
        assert assignment.loc[200] == assignment.loc[201]


def test_split_queries_is_reproducible():
    queries, profile = make_queries_and_profile()

    first = split.split_queries(profile, queries, seed=87)

    assert first.equals(split.split_queries(profile, queries, seed=87))


def test_default_fractions_sum_to_one_and_seed_is_fixed():
    assert sum(split.SPLIT_FRACTIONS.values()) == pytest.approx(1.0)
    assert split.SPLIT_SEED == 87
