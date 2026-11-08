"""Query-level stratified splitting into train, validation and test.

Each query goes entirely into one part, so validation and test simulate searches the
system has never seen. Queries that differ only in case, word order or a plural ``s``
(see ``profiling.query_group_key``) are kept together in the same part.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from wands_search.profiling import query_group_key

SPLIT_FRACTIONS = {"train": 0.60, "validation": 0.20, "test": 0.20}
SPLIT_SEED = 87
DEFAULT_SPLIT_PATH = Path(__file__).resolve().parents[2] / "splits" / "query_split.csv"

# Bands of ``Exact / (Exact + Partial)`` per query: exactly 0, then up to 5%, 5% to 25%, over 25%.
EXACT_SHARE_EDGES = [-0.001, 0.0, 0.05, 0.25, 1.0]
EXACT_SHARE_NAMES = ["none", "up_to_5pct", "5_to_25pct", "over_25pct"]
N_JUDGED_NAMES = ["low", "medium", "high"]


def relevant_queries(profile: pd.DataFrame) -> pd.DataFrame:
    """Keep the queries with at least one Exact or Partial product.

    Without a relevant product, Recall@K, MRR and NDCG@K are undefined or always 0, so
    these queries are excluded before the split. ``profile`` is the output of
    ``profiling.query_label_profile``.
    """
    return profile[(profile["Exact"] + profile["Partial"]) > 0]


def exact_share(profile: pd.DataFrame) -> pd.Series:
    """Return ``Exact / (Exact + Partial)`` per query, the share of Exact among the relevant products.

    Irrelevant products are left out because their number depends on how many candidates
    were judged. The result is undefined (NaN) for queries without relevant products.
    """
    relevant = profile["Exact"] + profile["Partial"]
    return profile["Exact"] / relevant.where(relevant > 0)


def stratification_groups(profile: pd.DataFrame) -> pd.Series:
    """Combine the ``Exact / (Exact + Partial)`` and ``n_judged`` bands into one label per query.

    ``profile`` is the output of ``profiling.query_label_profile``, already restricted to
    queries with a relevant product. ``n_judged`` is cut into three bands holding a similar
    number of queries.
    """
    exact_band = pd.cut(exact_share(profile), EXACT_SHARE_EDGES, labels=EXACT_SHARE_NAMES)
    judged_band = pd.qcut(profile["n_judged"], len(N_JUDGED_NAMES), labels=N_JUDGED_NAMES)
    return exact_band.astype(str) + "|" + judged_band.astype(str)


def stratified_split(groups: pd.Series, fractions: dict[str, float], seed: int) -> pd.Series:
    """Assign each index of ``groups`` to a part, keeping ``fractions`` within each group.

    Rounding leftovers are carried from one group to the next, so the total of each part
    stays within one item of ``fractions`` and no part absorbs all the rounding. The last
    part in ``fractions`` receives whatever remains of each group.
    """
    if not np.isclose(sum(fractions.values()), 1.0):
        raise ValueError(f"fractions must sum to 1, got {fractions}")

    rng = np.random.default_rng(seed)
    names = list(fractions)
    assigned = {name: 0 for name in names}
    seen = 0
    assignment = pd.Series(index=groups.index, dtype=object)
    for _, members in groups.groupby(groups, sort=True):
        shuffled = rng.permutation(members.index.to_numpy())
        seen += len(shuffled)
        start = 0
        for name in names[:-1]:
            target_total = int(np.floor(round(seen * fractions[name], 9) + 0.5))
            size = min(max(target_total - assigned[name], 0), len(shuffled) - start)
            assignment.loc[shuffled[start:start + size]] = name
            assigned[name] += size
            start += size
        assignment.loc[shuffled[start:]] = names[-1]
        assigned[names[-1]] += len(shuffled) - start
    return assignment


def split_queries(profile: pd.DataFrame, queries: pd.DataFrame,
                  fractions: dict[str, float] = SPLIT_FRACTIONS, seed: int = SPLIT_SEED) -> pd.Series:
    """Assign each query with a relevant product to a part.

    Queries without Exact or Partial products are excluded. Near-duplicate queries (same
    ``profiling.query_group_key``) are treated as one block that goes to a single part; the
    block takes the stratification group of its lowest ``query_id``. Returns a series
    indexed by ``query_id``.
    """
    profile = relevant_queries(profile)
    texts = queries.set_index("query_id")["query"].reindex(profile.index)
    block_key = texts.map(query_group_key)
    representatives = block_key.reset_index().drop_duplicates(subset="query", keep="first")["query_id"]

    groups = stratification_groups(profile)
    block_assignment = stratified_split(groups.loc[representatives], fractions, seed)

    key_to_part = pd.Series(block_assignment.to_numpy(), index=block_key.loc[representatives].to_numpy())
    assignment = pd.Series(block_key.map(key_to_part).to_numpy(), index=profile.index, name="split")
    assignment.index.name = "query_id"
    return assignment


def main() -> None:
    """Build the split from the dataset and write it to ``DEFAULT_SPLIT_PATH``."""
    from wands_search import data, profiling

    tables = data.load_all()
    profile = profiling.query_label_profile(data.deduplicate_labels(tables["label"]))
    assignment = split_queries(profile, tables["query"])
    DEFAULT_SPLIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    assignment.sort_index().to_csv(DEFAULT_SPLIT_PATH)
    print(f"wrote {len(assignment)} queries to {DEFAULT_SPLIT_PATH}")
    print(assignment.value_counts().reindex(list(SPLIT_FRACTIONS)).to_string())


if __name__ == "__main__":
    main()
