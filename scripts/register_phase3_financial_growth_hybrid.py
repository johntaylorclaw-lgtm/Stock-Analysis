from __future__ import annotations

import json

from financial_growth_hybrid_config import DERIVED_VARIABLES_PATH, SCHEMA_PATH, is_core_growth_field
from register_phase3_financial_growth import build_growth_definitions, field, variable


FULL_VIEW_NAME = "derived_financial_growth_full_v"
CORE_TABLE_NAME = "derived_financial_growth"


def build_fields(definitions: list[tuple[str, str, str, str, str]], *, core_only: bool) -> list[dict]:
    fields = [
        field("ts_code", "VARCHAR", "股票代码", False),
        field("trade_date", "DATE", "交易日期", False),
    ]
    for name, _label, dtype, formula, category in definitions:
        if name in {"ts_code", "trade_date"}:
            continue
        if core_only and not is_core_growth_field(name, category):
            continue
        fields.append(field(name, dtype, formula, True))
    fields.append(field("updated_at", "TIMESTAMP", "本地更新时间", False))
    return fields


def upsert_table(schema: dict, table_payload: dict) -> None:
    for index, table in enumerate(schema["tables"]):
        if table["name"] == table_payload["name"]:
            schema["tables"][index] = table_payload
            return
    schema["tables"].append(table_payload)


def main() -> None:
    definitions = build_growth_definitions()
    core_fields = build_fields(definitions, core_only=True)
    full_fields = build_fields(definitions, core_only=False)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    core_table = next(table for table in schema["tables"] if table["name"] == CORE_TABLE_NAME)
    core_table["description"] = (
        "Phase 3 财务成长核心物理表。仅落库高频使用字段，完整字段由 derived_financial_growth_full_v 视图按需计算。"
    )
    core_table.pop("table_type", None)
    core_table["fields"] = core_fields

    upsert_table(
        schema,
        {
            "name": FULL_VIEW_NAME,
            "description": "Phase 3 财务成长完整视图，覆盖二阶段设计的全部成长变量，按需从基础表和核心表计算。",
            "phase": "phase3",
            "table_type": "view",
            "primary_key": ["ts_code", "trade_date"],
            "fields": full_fields,
        },
    )
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = json.loads(DERIVED_VARIABLES_PATH.read_text(encoding="utf-8"))
    registry["variables"] = [
        item
        for item in registry["variables"]
        if item.get("table") not in {CORE_TABLE_NAME, FULL_VIEW_NAME}
    ]
    registry["variables"].extend(
        variable(name, label, dtype, formula, category)
        for name, label, dtype, formula, category in definitions
        if name not in {"ts_code", "trade_date"} and is_core_growth_field(name, category)
    )
    DERIVED_VARIABLES_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"registered {CORE_TABLE_NAME} physical fields: {len(core_fields)}")
    print(f"registered {FULL_VIEW_NAME} view fields: {len(full_fields)}")
    print(f"registered {CORE_TABLE_NAME} variables: {len(core_fields) - 3}")


if __name__ == "__main__":
    main()
