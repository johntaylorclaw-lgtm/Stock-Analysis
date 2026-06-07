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


def variable(variables: dict, table_name: str, field_name: str) -> dict:
    return next(
        item
        for item in variables["variables"]
        if item.get("table") == table_name and item.get("name") == field_name
    )


def test_ownership_governance_tables_are_registered() -> None:
    schema = load_json("config/schema_registry.json")

    assert len(table(schema, "derived_ownership_governance")["fields"]) == 63
    assert len(table(schema, "derived_ownership_governance_full_v")["fields"]) == 98
    assert len(table(schema, "ownership_governance_event_timeline_v")["fields"]) == 12
    assert len(table(schema, "ownership_holder_concentration_v")["fields"]) == 10


def test_ownership_governance_boundary_fields_are_registered() -> None:
    schema = load_json("config/schema_registry.json")
    fields = field_names(table(schema, "derived_ownership_governance"))

    assert {"pledge_ratio_ge_10_flag", "pledge_ratio_ge_30_flag", "pledge_ratio_ge_50_flag"} <= fields
    assert {"holder_num_to_total_share", "holder_num_to_free_share"} <= fields
    assert "high_pledge_ratio_flag" not in fields
    assert "holder_dispersion_proxy_latest" not in fields


def test_ownership_governance_variable_alignment_and_churn_formula() -> None:
    schema = load_json("config/schema_registry.json")
    variables = load_json("config/variables/derived_variables.json")
    module_variables = {
        "variables": [
            item
            for item in variables["variables"]
            if item.get("module") == "ownership_governance"
        ]
    }

    assert validate_variable_schema_alignment(module_variables, schema) == []
    assert "是否变动" in variable(
        variables,
        "derived_ownership_governance_full_v",
        "top10_holder_name_churn_1report",
    )["formula_zh"]
    assert "是否变动" in variable(
        variables,
        "derived_ownership_governance_full_v",
        "top10_float_holder_name_churn_1report",
    )["formula_zh"]
