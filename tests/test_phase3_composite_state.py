import json
from pathlib import Path

from stock_maintainance.validate import validate_variable_schema_alignment


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def table(schema: dict, name: str) -> dict:
    return next(item for item in schema["tables"] if item["name"] == name)


def field_names(table_payload: dict) -> set[str]:
    return {field["name"] for field in table_payload["fields"]}


def test_composite_state_tables_are_registered_without_scores() -> None:
    schema = load_json("config/schema_registry.json")
    core = table(schema, "derived_composite_state")

    assert len(core["fields"]) == 92
    assert len(table(schema, "derived_composite_state_full_v")["fields"]) == 115
    assert len(table(schema, "composite_state_condition_detail_v")["fields"]) == 10
    assert len(table(schema, "composite_state_module_coverage_v")["fields"]) == 8
    assert not any("score" in field["name"] for field in core["fields"])
    assert "value_quality_score" not in field_names(core)


def test_composite_state_boundary_fields_are_registered() -> None:
    schema = load_json("config/schema_registry.json")
    fields = field_names(table(schema, "derived_composite_state"))

    assert {"state_condition_count", "state_condition_available_count", "multi_domain_condition_count"} <= fields
    assert {"value_quality_pair_state", "momentum_flow_pair_state", "growth_quality_pair_state"} <= fields
    assert {"pledge_ratio_state", "unlock_future_state", "audit_opinion_state"} <= fields


def test_composite_state_variable_alignment() -> None:
    schema = load_json("config/schema_registry.json")
    variables = load_json("config/variables/derived_variables.json")
    module_variables = {
        "variables": [
            item
            for item in variables["variables"]
            if item.get("module") == "composite_state"
        ]
    }

    assert validate_variable_schema_alignment(module_variables, schema) == []
    assert not any(item["name"].endswith("_score") for item in module_variables["variables"])
