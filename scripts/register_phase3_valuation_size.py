from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"

MODULE = "valuation_size"
CORE_TABLE = "derived_valuation_size"
FULL_VIEW = "derived_valuation_size_full_v"
PCT_CACHE_TABLE = "derived_valuation_percentile_cache"

PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
MA_PERIODS = [20, 60, 120, 250]
PCT_WINDOWS = {"1y": 250, "3y": 750, "5y": 1250, "10y": 2500}


def f(name: str, dtype: str, desc: str, nullable: bool = True) -> dict:
    payload = {
        "name": name,
        "dtype": dtype,
        "nullable": nullable,
        "description": desc,
        "source_api": "local_derived",
    }
    if name == "updated_at":
        payload["nullable"] = False
        payload["default"] = "CURRENT_TIMESTAMP"
    return payload


PK = [
    f("ts_code", "VARCHAR", "股票代码", False),
    f("trade_date", "DATE", "交易日期", False),
]
UPDATED = [f("updated_at", "TIMESTAMP", "本地更新时间", False)]


CORE_FIELDS = PK + [
    f("pe", "DOUBLE", "pe = stock_daily_basic.pe"),
    f("pe_ttm", "DOUBLE", "pe_ttm = stock_daily_basic.pe_ttm"),
    f("pb", "DOUBLE", "pb = stock_daily_basic.pb"),
    f("ps", "DOUBLE", "ps = stock_daily_basic.ps"),
    f("ps_ttm", "DOUBLE", "ps_ttm = stock_daily_basic.ps_ttm"),
    f("dv_ratio", "DOUBLE", "dv_ratio = stock_daily_basic.dv_ratio"),
    f("dv_ttm", "DOUBLE", "dv_ttm = stock_daily_basic.dv_ttm"),
    f("total_share", "DOUBLE", "total_share = stock_daily_basic.total_share"),
    f("float_share", "DOUBLE", "float_share = stock_daily_basic.float_share"),
    f("free_share", "DOUBLE", "free_share = stock_daily_basic.free_share"),
    f("total_mv", "DOUBLE", "total_mv = stock_daily_basic.total_mv"),
    f("circ_mv", "DOUBLE", "circ_mv = stock_daily_basic.circ_mv"),
    f("free_float_mv", "DOUBLE", "free_float_mv = close_raw * free_share; unit=10k CNY"),
    f("log_total_mv", "DOUBLE", "log_total_mv = ln(total_mv) when total_mv > 0"),
    f("log_circ_mv", "DOUBLE", "log_circ_mv = ln(circ_mv) when circ_mv > 0"),
    f("log_free_float_mv", "DOUBLE", "log_free_float_mv = ln(free_float_mv) when free_float_mv > 0"),
    f("float_share_ratio", "DOUBLE", "float_share_ratio = float_share / total_share"),
    f("free_share_ratio", "DOUBLE", "free_share_ratio = free_share / total_share"),
    f("earnings_yield_ttm", "DOUBLE", "earnings_yield_ttm = 1 / pe_ttm when pe_ttm > 0"),
    f("book_to_price", "DOUBLE", "book_to_price = 1 / pb when pb > 0"),
    f("sales_yield_ttm", "DOUBLE", "sales_yield_ttm = 1 / ps_ttm when ps_ttm > 0"),
    f("dividend_yield_ttm", "DOUBLE", "dividend_yield_ttm = dv_ttm / 100"),
    f("pe_ttm_pct_5y", "DOUBLE", "pe_ttm_pct_5y = rolling_percentile_rank(pe_ttm,1250)"),
    f("pb_pct_5y", "DOUBLE", "pb_pct_5y = rolling_percentile_rank(pb,1250)"),
    f("ps_ttm_pct_5y", "DOUBLE", "ps_ttm_pct_5y = rolling_percentile_rank(ps_ttm,1250)"),
    f("total_mv_pct_5y", "DOUBLE", "total_mv_pct_5y = rolling_percentile_rank(total_mv,1250)"),
    f("pe_ttm_valid_flag", "BOOLEAN", "pe_ttm_valid_flag = pe_ttm > 0"),
    f("pb_valid_flag", "BOOLEAN", "pb_valid_flag = pb > 0"),
    f("ps_ttm_valid_flag", "BOOLEAN", "ps_ttm_valid_flag = ps_ttm > 0"),
    f("mv_valid_flag", "BOOLEAN", "mv_valid_flag = total_mv > 0 and circ_mv > 0"),
    f("valuation_missing_reason", "VARCHAR", "估值缺失原因：missing_daily_basic/missing_price/invalid_valuation/null"),
] + UPDATED


def pct_field(source: str, alias: str) -> dict:
    return f(f"{source}_pct_{alias}", "DOUBLE", f"{source}_pct_{alias} = rolling_percentile_rank({source},{PCT_WINDOWS[alias]})")


def chg_field(source: str, n: int) -> dict:
    return f(f"{source}_chg_{n}", "DOUBLE", f"{source}_chg_{n} = {source} / lag({source},{n}) - 1; positive current and lag only")


def ma_field(source: str, n: int) -> dict:
    return f(f"{source}_ma_{n}", "DOUBLE", f"{source}_ma_{n} = avg({source},{n})")


FULL_EXTRA_FIELDS = [
    f("earnings_yield", "DOUBLE", "earnings_yield = 1 / pe when pe > 0"),
    f("sales_yield", "DOUBLE", "sales_yield = 1 / ps when ps > 0"),
    f("dividend_yield", "DOUBLE", "dividend_yield = dv_ratio / 100"),
    f("log_pe_ttm", "DOUBLE", "log_pe_ttm = ln(pe_ttm) when pe_ttm > 0"),
    f("log_pb", "DOUBLE", "log_pb = ln(pb) when pb > 0"),
    f("log_ps_ttm", "DOUBLE", "log_ps_ttm = ln(ps_ttm) when ps_ttm > 0"),
    f("dv_valid_flag", "BOOLEAN", "dv_valid_flag = dv_ratio is not null or dv_ttm is not null"),
    *[pct_field(source, alias) for source in ["pe", "pe_ttm", "pb", "ps", "ps_ttm", "dv_ratio", "dv_ttm", "total_mv", "circ_mv", "free_float_mv"] for alias in PCT_WINDOWS if not (source, alias) in {("pe_ttm", "5y"), ("pb", "5y"), ("ps_ttm", "5y"), ("total_mv", "5y")}],
    *[chg_field(source, n) for source in ["pe_ttm", "pb", "ps_ttm", "total_mv", "circ_mv", "free_float_mv"] for n in PERIODS],
    *[ma_field(source, n) for source in ["pe_ttm", "pb", "ps_ttm", "total_mv", "circ_mv"] for n in MA_PERIODS],
    f("float_to_total_share_ratio", "DOUBLE", "float_to_total_share_ratio = float_share / total_share"),
    f("free_to_total_share_ratio", "DOUBLE", "free_to_total_share_ratio = free_share / total_share"),
    f("free_to_float_share_ratio", "DOUBLE", "free_to_float_share_ratio = free_share / float_share"),
    f("circ_mv_to_total_mv_ratio", "DOUBLE", "circ_mv_to_total_mv_ratio = circ_mv / total_mv"),
    f("free_float_mv_to_total_mv_ratio", "DOUBLE", "free_float_mv_to_total_mv_ratio = free_float_mv / total_mv"),
    f("amount_to_total_mv", "DOUBLE", "amount_to_total_mv = (derived_daily_spine.amount / 10) / total_mv"),
    f("amount_to_circ_mv", "DOUBLE", "amount_to_circ_mv = (derived_daily_spine.amount / 10) / circ_mv"),
    f("peg_ttm", "DOUBLE", "peg_ttm = pe_ttm / parent_net_profit_yoy_1y_calc_asof when growth > 0"),
    f("pb_to_roe", "DOUBLE", "pb_to_roe = pb / roe_asof when pb > 0 and roe_asof > 0"),
    f("pe_to_roe", "DOUBLE", "pe_to_roe = pe_ttm / roe_asof when pe_ttm > 0 and roe_asof > 0"),
    f("price_to_bps_asof", "DOUBLE", "price_to_bps_asof = close_raw / bps_asof when bps_asof > 0"),
    f("price_to_eps_asof", "DOUBLE", "price_to_eps_asof = close_raw / eps_asof when eps_asof > 0"),
    f("price_to_ocfps_asof", "DOUBLE", "price_to_ocfps_asof = close_raw / ocfps_asof when ocfps_asof > 0"),
    f("market_cap_to_parent_profit", "DOUBLE", "market_cap_to_parent_profit = total_mv * 10000 / parent_net_profit_single_quarter_value_asof"),
]

PCT_CACHE_FIELDS = PK + [
    pct_field(source, alias)
    for source in ["pe", "pe_ttm", "pb", "ps", "ps_ttm", "dv_ratio", "dv_ttm", "total_mv", "circ_mv", "free_float_mv"]
    for alias in PCT_WINDOWS
] + UPDATED


def upsert_table(schema: dict, table: dict) -> None:
    for index, existing in enumerate(schema["tables"]):
        if existing["name"] == table["name"]:
            schema["tables"][index] = table
            return
    schema["tables"].append(table)


def infer_price_basis(name: str) -> str:
    if name in {"amount_to_total_mv", "amount_to_circ_mv"}:
        return "mixed"
    if name.startswith("price_to_"):
        return "raw"
    return "not_price"


def infer_min_history(name: str) -> int:
    for alias, days in PCT_WINDOWS.items():
        if name.endswith(f"_{alias}"):
            return days
    for n in sorted(PERIODS + MA_PERIODS, reverse=True):
        if name.endswith(f"_{n}") or f"_{n}_" in name:
            return n
    return 1


def variable(field: dict) -> dict:
    name = field["name"]
    return {
        "name": name,
        "label_zh": field["description"].split("=")[0].strip(),
        "table": CORE_TABLE,
        "module": MODULE,
        "category": "valuation_size",
        "tier": "core",
        "dtype": field["dtype"],
        "unit": "none" if field["dtype"] in {"BOOLEAN", "VARCHAR", "DATE"} else "ratio_or_source_unit",
        "frequency": "daily",
        "grain": ["ts_code", "trade_date"],
        "source_type": "derived",
        "dependencies": ["stock_daily_basic", "derived_daily_spine"],
        "formula_ref": field["description"],
        "formula_zh": field["description"],
        "price_basis": infer_price_basis(name),
        "point_in_time": True,
        "min_history": infer_min_history(name),
        "read_window": max(20, infer_min_history(name) * 2 + 10),
        "write_window": 10,
        "missing_policy": "source_optional",
        "validation": {"constant_allowed": field["dtype"] in {"BOOLEAN", "VARCHAR", "INTEGER"}},
    }


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    old = next((item for item in schema["tables"] if item["name"] == CORE_TABLE), {})
    upsert_table(
        schema,
        {
            "name": CORE_TABLE,
            "phase": old.get("phase", "P3"),
            "description": "Phase 3 valuation and size core physical table",
            "primary_key": ["ts_code", "trade_date"],
            "fields": CORE_FIELDS,
        },
    )
    upsert_table(
        schema,
        {
            "name": FULL_VIEW,
            "phase": "P3",
            "description": "Phase 3 valuation and size full view",
            "table_type": "view",
            "primary_key": ["ts_code", "trade_date"],
            "fields": CORE_FIELDS[:-1] + FULL_EXTRA_FIELDS + UPDATED,
        },
    )
    upsert_table(
        schema,
        {
            "name": PCT_CACHE_TABLE,
            "phase": "P3",
            "description": "Phase 3 valuation rolling percentile physical cache used by derived_valuation_size_full_v",
            "primary_key": ["ts_code", "trade_date"],
            "fields": PCT_CACHE_FIELDS,
        },
    )
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for variables_path in (ROOT / "config" / "variables").glob("*.json"):
        payload = json.loads(variables_path.read_text(encoding="utf-8"))
        original_count = len(payload.get("variables", []))
        payload["variables"] = [
            item for item in payload.get("variables", []) if item.get("module") != MODULE
        ]
        if len(payload["variables"]) != original_count:
            variables_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = json.loads(DERIVED_VARIABLES_PATH.read_text(encoding="utf-8"))
    existing_names = {
        item.get("name")
        for variables_path in (ROOT / "config" / "variables").glob("*.json")
        for item in json.loads(variables_path.read_text(encoding="utf-8")).get("variables", [])
    }
    for field in CORE_FIELDS:
        if field["name"] in {"ts_code", "trade_date", "updated_at"}:
            continue
        if field["name"] in existing_names:
            continue
        registry["variables"].append(variable(field))
        existing_names.add(field["name"])
    DERIVED_VARIABLES_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({
        CORE_TABLE: len(CORE_FIELDS),
        FULL_VIEW: len(CORE_FIELDS[:-1] + FULL_EXTRA_FIELDS + UPDATED),
        PCT_CACHE_TABLE: len(PCT_CACHE_FIELDS),
    })


if __name__ == "__main__":
    main()
