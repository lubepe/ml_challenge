"""Candidates and training examples of the reranker, and the final list after reranking.

Decisions in docs/EVALUATION.md, section "Reranker (learning-to-rank)": the reranker reorders
the top ``CANDIDATES_K`` products of one retrieval; the products below keep the retrieval order.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

import numpy as np
import pandas as pd

from wands_search.metrics import GAINS, QueryLabels

CANDIDATES_K = 100
NO_LABEL = "no label"

# How candidates without a label become training examples: "drop" keeps only judged
# candidates, "zero" gives them gain 0, as the metrics do.
UnlabeledRule = Literal["drop", "zero"]
UNLABELED_RULES: tuple[UnlabeledRule, ...] = ("drop", "zero")


def candidate_table(
    run: Mapping[int, Sequence[int]], labels: Mapping[int, QueryLabels], k: int = CANDIDATES_K
) -> pd.DataFrame:
    """Top ``k`` products of each query of ``run``, one row per (query, product).

    Columns: ``query_id``, ``product_id``, ``retrieval_rank`` (from 1), ``label`` (``NO_LABEL``
    when the pair was not judged) and ``gain`` (NaN without label). Ordered by query and rank.
    """
    frames = []
    for query_id, ranking in run.items():
        top = list(ranking)[:k]
        if len(set(top)) != len(top):
            raise ValueError(f"query {query_id}: the ranking repeats a product_id")
        query_labels = labels.get(query_id, {})
        frames.append(pd.DataFrame({
            "query_id": np.full(len(top), query_id, dtype=np.int64),
            "product_id": np.asarray(top, dtype=np.int64),
            "retrieval_rank": np.arange(1, len(top) + 1, dtype=np.int64),
            "label": [query_labels.get(product_id, NO_LABEL) for product_id in top],
        }))
    columns = ["query_id", "product_id", "retrieval_rank", "label"]
    candidates = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    candidates["gain"] = candidates["label"].map(GAINS).astype(float)
    return candidates.sort_values(["query_id", "retrieval_rank"], ignore_index=True)


def training_examples(candidates: pd.DataFrame, unlabeled: UnlabeledRule) -> pd.DataFrame:
    """Rows of ``candidate_table`` used to train the reranker.

    ``unlabeled="drop"`` removes candidates without label; ``"zero"`` gives them gain 0. Queries
    left without any candidate of positive gain are removed, since they give no pair to compare.
    """
    if unlabeled not in UNLABELED_RULES:
        raise ValueError(f"unlabeled must be one of {UNLABELED_RULES}, got {unlabeled!r}")
    examples = candidates.copy()
    if unlabeled == "drop":
        examples = examples[examples["label"] != NO_LABEL]
    else:
        examples["gain"] = examples["gain"].fillna(0.0)
    has_positive = examples.groupby("query_id")["gain"].transform("max") > 0
    return examples[has_positive].sort_values(["query_id", "retrieval_rank"], ignore_index=True)


def rerank(ranking: Sequence[int], scores: Sequence[float], k: int = CANDIDATES_K) -> list[int]:
    """Final list: the top ``k`` of ``ranking`` ordered by ``scores`` (higher first), then the rest in the retrieval order.

    ``scores`` has one value per reranked product, in the order of ``ranking``. Ties keep the retrieval order.
    """
    ranking = list(ranking)
    top = ranking[:k]
    scores = np.asarray(scores, dtype=float)
    if len(scores) != len(top):
        raise ValueError(f"expected {len(top)} scores, got {len(scores)}")
    order = np.argsort(-scores, kind="stable")
    return [top[i] for i in order] + ranking[k:]
