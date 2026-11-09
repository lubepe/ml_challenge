"""Train the final reranker models on the train set and save them to ``models/``.

Run with ``uv run python -m wands_search.train_reranker``. Each model of ``reranker.SAVED_MODELS``
is trained on the 287 train queries with the combination chosen by GroupKFold
(``reranker.CHOSEN_COMBINATIONS``; notebooks/04_reranker.ipynb, Etapa 3.1). The validation and
test sets are not used. Takes a few minutes on a CPU, mostly in the cross-encoder.
"""

import argparse
import time
from pathlib import Path

from wands_search import data, evaluate, features, metrics, ranking, reranker, systems


def train_saved_models(model_dir: Path = reranker.DEFAULT_MODEL_DIR) -> dict[str, Path]:
    """Train every model of ``reranker.SAVED_MODELS`` and save it with its metadata."""
    products = data.load_products()
    queries = data.load_queries()
    labels_by_query = metrics.labels_by_query(data.deduplicate_labels(data.load_labels()))
    train_queries = evaluate.split_queries(queries, evaluate.load_split(), "train")

    retrievers = systems.build_systems(products)
    builder = features.build_feature_builder(products, retrievers, features.FastEmbedCrossEncoder())
    indexes = {"BM25 v2": retrievers.v2_index, "hybrid": retrievers.hybrid_index}
    _, tables, _ = features.candidate_features(indexes, builder, train_queries, labels_by_query)

    paths = {}
    for name, spec in reranker.SAVED_MODELS.items():
        combination = reranker.CHOSEN_COMBINATIONS[spec["retrieval"]]
        params = {key: combination[key] for key in reranker.PARAM_GRID}
        examples = ranking.training_examples(tables[spec["retrieval"]], combination["unlabeled"])
        model = reranker.fit(examples, spec["features"], params, combination["n_estimators"])
        paths[name] = reranker.save_model(model, model_dir, name, {
            "retrieval": spec["retrieval"],
            "selected": name == reranker.SELECTED_MODEL,
            "combination": combination,
            "objective": "lambdarank",
            "label_gain": reranker.LABEL_GAIN,
            "seed": reranker.RANKER_SEED,
            "train_queries": int(train_queries["query_id"].nunique()),
            "training_examples": int(len(examples)),
            "candidates_per_query": ranking.CANDIDATES_K,
            "cross_encoder_model": features.CROSS_ENCODER_MODEL if "cross_encoder_score" in spec["features"] else None,
        })
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=reranker.DEFAULT_MODEL_DIR)
    args = parser.parse_args()
    start = time.perf_counter()
    paths = train_saved_models(args.model_dir)
    for name, path in paths.items():
        print(f"saved {name}: {path}")
    print(f"done in {time.perf_counter() - start:.0f} s")


if __name__ == "__main__":
    main()
