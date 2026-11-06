"""Query-level stratified splitting into train, validation and test.

Each query goes entirely into one part, so validation and test simulate searches the
system has never seen.
"""

import numpy as np
import pandas as pd

EXACT_FRACTION_EDGES = [-0.001, 0.0, 0.02, 0.10, 1.0]
EXACT_FRACTION_NAMES = ["none", "up_to_2pct", "2_to_10pct", "over_10pct"]
N_JUDGED_NAMES = ["low", "medium", "high"]


def stratification_groups(profile: pd.DataFrame) -> pd.Series:
    """Combine ``exact_fraction`` and ``n_judged`` bands into one group label per query.

    ``profile`` is the output of ``profiling.query_label_profile``. ``n_judged`` is cut
    into three bands holding a similar number of queries.
    """
    exact_band = pd.cut(profile["exact_fraction"], EXACT_FRACTION_EDGES, labels=EXACT_FRACTION_NAMES)
    judged_band = pd.qcut(profile["n_judged"], len(N_JUDGED_NAMES), labels=N_JUDGED_NAMES)
    return exact_band.astype(str) + "|" + judged_band.astype(str)


def stratified_split(groups: pd.Series, fractions: dict[str, float], seed: int) -> pd.Series:
    """Assign each index of ``groups`` to a part, keeping ``fractions`` within each group.

    The last part in ``fractions`` receives whatever remains after rounding.
    """
    if not np.isclose(sum(fractions.values()), 1.0):
        raise ValueError(f"fractions must sum to 1, got {fractions}")

    rng = np.random.default_rng(seed)
    names = list(fractions)
    assignment = pd.Series(index=groups.index, dtype=object)
    for _, members in groups.groupby(groups, sort=True):
        shuffled = rng.permutation(members.index.to_numpy())
        start = 0
        for name in names[:-1]:
            size = round(len(shuffled) * fractions[name])
            assignment.loc[shuffled[start:start + size]] = name
            start += size
        assignment.loc[shuffled[start:]] = names[-1]
    return assignment
