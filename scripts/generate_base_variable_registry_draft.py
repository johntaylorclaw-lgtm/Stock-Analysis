from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
OUTPUT_PATH = ROOT / "outputs" / "phase2" / "base_variables_draft.json"

SKIP_TABLE_PREFIXES = ("metadata_",)
SKIP_FIELDS = {"updated_at", "payload_json", "record_key", "error_message"}


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    raw_items = []
    for table in schema["tables"]:
        if table["name"].startswith(SKIP_TABLE_PREFIXES):
            continue
        for field in table.get("fields", []):
            if field["name"] in SKIP_FIELDS:
                continue
            raw_items.append((table, field))
    name_counts: dict[str, int] = {}
    for _, field in raw_items:
        name_counts[field["name"]] = name_counts.get(field["name"], 0) + 1
    variables = [variable_from_field(table, field, name_counts) for table, field in raw_items]
    payload = {
        "note": "Draft generated from schema_registry.json. Review label_zh and unit before promoting to base_variables.json.",
        "variables": variables,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT_PATH)
    print(len(variables))


def variable_from_field(table: dict, field: dict, name_counts: dict[str, int]) -> dict:
    source_api = field.get("source_api") or table.get("source_api") or "local_derived"
    variable_name = field["name"] if name_counts[field["name"]] == 1 else f"{table['name']}_{field['name']}"
    return {
        "name": variable_name,
        "label_zh": field.get("description", variable_name),
        "table": table["name"],
        "module": suggest_module(table["name"], source_api),
        "category": suggest_category(table["name"], field["name"], source_api),
        "tier": "p0" if table.get("phase") == "P0" else "core",
        "dtype": field["dtype"],
        "unit": suggest_unit(field["name"], field["dtype"]),
        "frequency": suggest_frequency(table["name"]),
        "grain": table.get("primary_key", []),
        "source_type": "derived" if source_api == "local_derived" else "tushare",
        "source_api": source_api,
        "source_field": field.get("source_field", field["name"]),
        "price_basis": suggest_price_basis(table["name"], field["name"]),
        "point_in_time": True,
        "missing_policy": "required" if field.get("nullable") is False else "source_optional",
        "validation": default_validation(field),
    }


def suggest_module(table: str, source_api: str) -> str:
    if table.startswith("financial_"):
        return "base_financial"
    if table == "stock_daily_basic":
        return "base_valuation"
    if table in {"stock_daily", "stock_adj_factor", "stock_limit_price"}:
        return "base_price"
    if table.startswith("stock_moneyflow") or table.startswith("margin") or table.startswith("northbound") or table.startswith("top_"):
        return "base_capital_flow"
    if table.startswith("index_"):
        return "base_index"
    if table.startswith("concept_") or table.startswith("sw_industry"):
        return "base_sector"
    if table == "trade_calendar":
        return "base_calendar"
    if source_api in {"stock_basic", "stock_company"}:
        return "base_security"
    return "base_misc"


def suggest_category(table: str, field: str, source_api: str) -> str:
    if table == "stock_daily":
        return "ohlcv"
    if table == "stock_daily_basic":
        return "valuation"
    if table == "stock_adj_factor":
        return "adjustment"
    if table == "stock_limit_price":
        return "limit_price"
    if table.startswith("financial_income"):
        return "income_statement"
    if table.startswith("financial_balance"):
        return "balance_sheet"
    if table.startswith("financial_cashflow"):
        return "cashflow_statement"
    if table.startswith("financial_indicator"):
        return "financial_indicator"
    if table.startswith("financial_event"):
        return "financial_event"
    if table.startswith("stock_moneyflow"):
        return "moneyflow"
    if table.startswith("margin"):
        return "margin"
    if table.startswith("northbound"):
        return "northbound"
    if table.startswith("top_"):
        return "top_list"
    if table.startswith("index_weight"):
        return "constituent"
    if table.startswith("index_daily"):
        return "index_ohlcv"
    if table.startswith("concept"):
        return "concept"
    if table.startswith("sw_industry"):
        return "industry"
    if source_api in {"stock_basic", "stock_company"}:
        return "security_master"
    return "base"


def suggest_frequency(table: str) -> str:
    if "daily" in table or table in {"stock_adj_factor", "stock_limit_price", "margin_detail", "northbound_holding"}:
        return "daily"
    if table.startswith("financial_income") or table.startswith("financial_balance") or table.startswith("financial_cashflow") or table.startswith("financial_indicator"):
        return "quarterly"
    if "event" in table or "member" in table or "weight" in table or table.startswith("top_"):
        return "event"
    return "snapshot"


def suggest_unit(field: str, dtype: str) -> str:
    if dtype in {"VARCHAR", "DATE", "TIMESTAMP", "BOOLEAN"}:
        return "none"
    if any(token in field for token in ["ratio", "rate", "pct", "margin", "roe", "roa", "weight"]):
        return "percent_or_ratio"
    if field in {"open", "high", "low", "close", "pre_close", "up_limit", "down_limit"}:
        return "yuan"
    if "vol" in field or "volume" in field or "share" in field:
        return "share_or_lot"
    if any(token in field for token in ["amount", "profit", "asset", "liab", "cash", "revenue", "cost", "fee", "mv", "balance", "buy", "sell"]):
        return "yuan"
    return "none"


def suggest_price_basis(table: str, field: str) -> str:
    if table in {"stock_daily", "stock_daily_basic"} and field in {"open", "high", "low", "close", "pre_close"}:
        return "raw"
    if table == "stock_adj_factor":
        return "adjustment_factor"
    return "not_price"


def default_validation(field: dict) -> dict:
    validation: dict = {"constant_allowed": True}
    if field["dtype"] in {"DOUBLE", "BIGINT", "INTEGER"} and any(
        token in field["name"] for token in ["price", "amount", "volume", "share", "asset", "liab", "cash", "balance", "factor"]
    ):
        validation["min_value"] = 0
    return validation


if __name__ == "__main__":
    main()
