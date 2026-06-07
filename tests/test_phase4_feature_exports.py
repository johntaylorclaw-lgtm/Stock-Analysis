import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_schema() -> dict:
    return json.loads((ROOT / "config/schema_registry.json").read_text(encoding="utf-8"))


def table(schema: dict, name: str) -> dict:
    return next(item for item in schema["tables"] if item["name"] == name)


def test_feature_export_views_are_registered() -> None:
    schema = load_schema()

    assert table(schema, "stock_features_core")["table_type"] == "view"
    assert table(schema, "stock_features_plus")["table_type"] == "view"
    assert table(schema, "stock_features_full")["table_type"] == "view"
    assert len(table(schema, "stock_features_core")["fields"]) == 318
    assert len(table(schema, "stock_features_plus")["fields"]) == 1198
    assert len(table(schema, "stock_features_full")["fields"]) == 1602


def test_feature_export_views_do_not_expose_scores() -> None:
    schema = load_schema()

    for name in ["stock_features_core", "stock_features_plus", "stock_features_full"]:
        field_names = {field["name"] for field in table(schema, name)["fields"]}
        assert not any("score" in field.lower() for field in field_names)
        assert "value_quality_score" not in field_names


def test_feature_export_views_have_stable_primary_key() -> None:
    schema = load_schema()

    for name in ["stock_features_core", "stock_features_plus", "stock_features_full"]:
        assert table(schema, name)["primary_key"] == ["ts_code", "trade_date"]
