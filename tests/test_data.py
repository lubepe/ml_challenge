from pathlib import Path

import pandas as pd

from wands_search import data


def write_tsv(path: Path, rows: list[list[str]]) -> None:
    path.write_text("\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8")


def test_load_tsv_renames_category_hierarchy(tmp_path):
    path = tmp_path / "product.csv"
    write_tsv(path, [
        ["product_id", "product_name", "category hierarchy"],
        ["0", "bed", "Furniture / Beds"],
    ])

    df = data.load_tsv(path)

    assert "category_hierarchy" in df.columns
    assert "category hierarchy" not in df.columns


def test_load_tsv_keeps_commas_inside_fields(tmp_path):
    path = tmp_path / "product.csv"
    write_tsv(path, [
        ["product_id", "product_description"],
        ["0", "solid , sturdy , and simple"],
    ])

    df = data.load_tsv(path)

    assert df.shape == (1, 2)
    assert df.loc[0, "product_description"] == "solid , sturdy , and simple"


def test_load_all_returns_the_three_tables(tmp_path):
    write_tsv(tmp_path / "product.csv", [["product_id"], ["0"]])
    write_tsv(tmp_path / "query.csv", [["query_id", "query"], ["0", "chair"]])
    write_tsv(tmp_path / "label.csv", [["id", "query_id", "product_id", "label"], ["0", "0", "0", "Exact"]])

    tables = data.load_all(tmp_path)

    assert set(tables) == {"product", "query", "label"}
    assert all(isinstance(df, pd.DataFrame) for df in tables.values())


def test_split_product_classes_handles_multiple_values_and_null():
    assert data.split_product_classes("Sofas|Sectionals") == ["Sofas", "Sectionals"]
    assert data.split_product_classes("Vases, Urns, Jars, & Bottles") == ["Vases, Urns, Jars, & Bottles"]
    assert data.split_product_classes(float("nan")) == []


def test_split_category_hierarchy_keeps_order_and_handles_null():
    assert data.split_category_hierarchy("Furniture / Bedroom Furniture / Beds") == [
        "Furniture",
        "Bedroom Furniture",
        "Beds",
    ]
    assert data.split_category_hierarchy(None) == []


def test_parse_product_features_splits_on_first_colon():
    parsed = data.parse_product_features("color : caramel|weightcapacity:500|timedisplay : analog : numerical")

    assert parsed == [
        ("color", "caramel"),
        ("weightcapacity", "500"),
        ("timedisplay", "analog : numerical"),
    ]


def test_parse_product_features_keeps_repeated_keys_and_drops_fragments():
    parsed = data.parse_product_features("color : red|color : blue| loose text without separator")

    assert parsed == [("color", "red"), ("color", "blue")]
    assert data.parse_product_features(float("nan")) == []


def test_deduplicate_labels_removes_copies_and_conflicting_pairs():
    labels = pd.DataFrame({
        "id": [0, 1, 2, 3, 4, 5],
        "query_id": [0, 0, 0, 1, 1, 1],
        "product_id": [10, 10, 11, 20, 20, 21],
        "label": ["Exact", "Exact", "Partial", "Exact", "Partial", "Irrelevant"],
    })

    result = data.deduplicate_labels(labels)

    assert result["id"].tolist() == [0, 2, 5]  # copy of id 0 removed, pair (1, 20) dropped


def test_deduplicate_labels_drops_conflicting_pair_even_with_a_majority():
    labels = pd.DataFrame({
        "id": [0, 1, 2],
        "query_id": [0, 0, 0],
        "product_id": [10, 10, 10],
        "label": ["Exact", "Partial", "Partial"],
    })

    assert data.deduplicate_labels(labels).empty


def test_default_data_dir_points_to_repository_dataset():
    assert data.DEFAULT_DATA_DIR.name == "dataset"
    assert (data.DEFAULT_DATA_DIR.parent / "pyproject.toml").exists()
