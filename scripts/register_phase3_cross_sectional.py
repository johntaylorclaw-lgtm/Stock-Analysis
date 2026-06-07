from __future__ import annotations

import json
from pathlib import Path

from phase3_cross_sectional_config import (
    EXPOSURES,
    MIN_GROUP_RANK_N,
    MIN_GROUP_ZSCORE_N,
    PHYSICAL_VARIABLES,
    RESIDUAL_VARIABLES,
    VIEW_EXTRA_VARIABLES,
    WINSOR_LOWER,
    WINSOR_UPPER,
    physical_field_names,
    view_extra_field_names,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"


def f(name: str, dtype: str, desc: str, nullable: bool = True) -> dict:
    payload = {"name": name, "dtype": dtype, "nullable": nullable, "description": desc, "source_api": "local_derived"}
    if name == "updated_at":
        payload["nullable"] = False
        payload["default"] = "CURRENT_TIMESTAMP"
    return payload


def upsert_table(schema: dict, table: dict) -> None:
    for idx, existing in enumerate(schema["tables"]):
        if existing["name"] == table["name"]:
            schema["tables"][idx] = table
            return
    schema["tables"].append(table)


def physical_fields() -> list[dict]:
    fields = [
        f("ts_code", "VARCHAR", "股票代码", False),
        f("trade_date", "DATE", "交易日期", False),
        f("xs_universe_flag", "BOOLEAN", "是否进入截面样本 = is_listed_asof AND has_price AND price_valid_flag"),
        f("xs_market", "VARCHAR", "截面市场分组 = derived_daily_spine.market"),
        f("xs_exchange", "VARCHAR", "截面交易所分组 = derived_daily_spine.exchange"),
        f("xs_sw_l1_code", "VARCHAR", "截面申万一级行业 = derived_sector_concept_context.sw_l1_code"),
        f("xs_sw_l2_code", "VARCHAR", "截面申万二级行业 = derived_sector_concept_context.sw_l2_code"),
        f("xs_sample_all_count", "INTEGER", "全市场截面样本数 = count(valid universe) over trade_date"),
        f("xs_sample_market_count", "INTEGER", "市场分组样本数 = count(valid universe) over trade_date, market"),
        f("xs_sample_sw_l1_count", "INTEGER", "申万一级样本数 = count(valid universe) over trade_date, sw_l1_code"),
        f("xs_sample_sw_l2_count", "INTEGER", "申万二级样本数 = count(valid universe) over trade_date, sw_l2_code"),
        f("xs_core_available_count", "INTEGER", "核心截面变量可用数 = count(non_null_core_values)"),
        f("xs_core_available_ratio", "DOUBLE", f"核心截面变量可用率 = xs_core_available_count / {len(PHYSICAL_VARIABLES)}"),
        f("xs_missing_fields", "VARCHAR", "缺失核心字段列表 = string_join(missing field names,';')"),
        f("xs_winsor_lower_pct", "DOUBLE", f"缩尾下分位 = {WINSOR_LOWER}"),
        f("xs_winsor_upper_pct", "DOUBLE", f"缩尾上分位 = {WINSOR_UPPER}"),
        f("xs_min_group_zscore_n", "INTEGER", f"z-score最小分组样本数 = {MIN_GROUP_ZSCORE_N}"),
        f("xs_min_group_rank_n", "INTEGER", f"排名最小分组样本数 = {MIN_GROUP_RANK_N}"),
    ]
    for var in PHYSICAL_VARIABLES:
        label = var.label_zh
        fields.extend(
            [
                f(f"{var.name}_rank_all_desc", "INTEGER", f"{label}全市场降序排名 = rank({var.source_table}.{var.source_field} DESC) over trade_date"),
                f(f"{var.name}_pct_all_desc", "DOUBLE", f"{label}全市场降序分位 = (n-rank)/(n-1)"),
                f(f"{var.name}_z_all", "DOUBLE", f"{label}全市场z值 = z(winsor({var.source_table}.{var.source_field},1%,99%))"),
                f(f"{var.name}_rank_market_desc", "INTEGER", f"{label}市场分组降序排名 = rank({var.source_field} DESC) over trade_date,xs_market"),
                f(f"{var.name}_pct_market_desc", "DOUBLE", f"{label}市场分组降序分位 = (n-rank)/(n-1)"),
                f(f"{var.name}_rank_sw_l2_desc", "INTEGER", f"{label}申万二级降序排名 = rank({var.source_field} DESC) over trade_date,xs_sw_l2_code"),
                f(f"{var.name}_pct_sw_l2_desc", "DOUBLE", f"{label}申万二级降序分位 = (n-rank)/(n-1)"),
            ]
        )
    for name in RESIDUAL_VARIABLES:
        label = next(var.label_zh for var in PHYSICAL_VARIABLES if var.name == name)
        fields.append(
            f(
                f"{name}_resid_size_sw_l2_z",
                "DOUBLE",
                f"{label}规模行业中性残差z值 = z(resid({name}_z_all ~ log_free_float_mv_z_all + sw_l2_dummy))",
            )
        )
    for name, (label, components) in EXPOSURES.items():
        formula = "avg_z(" + ", ".join(("-" if sign < 0 else "") + comp + "_z_all" for comp, sign in components) + ")"
        fields.append(f(name, "DOUBLE", f"{label} = {formula}"))
    fields.append(f("updated_at", "TIMESTAMP", "本地更新时间", False))
    return fields


def view_fields() -> list[dict]:
    fields = list(physical_fields())
    existing = {field["name"] for field in fields}
    for var in PHYSICAL_VARIABLES + VIEW_EXTRA_VARIABLES:
        for name in view_extra_field_names(var.name):
            if name in existing:
                continue
            fields.append(f(name, "DOUBLE", f"{var.label_zh}完整视图扩展截面字段 = {name}"))
            existing.add(name)
    for var in VIEW_EXTRA_VARIABLES:
        for name in physical_field_names(var.name):
            if name in existing:
                continue
            dtype = "INTEGER" if "_rank_" in name else "DOUBLE"
            fields.append(f(name, dtype, f"{var.label_zh}完整视图扩展截面字段 = {name}"))
            existing.add(name)
    for name, desc in [
        ("profitability_exposure_z", "盈利能力暴露z值 = avg_z(roe,roa,roic,gross_margin,netprofit_margin)"),
        ("cashflow_quality_exposure_z", "现金流质量暴露z值 = avg_z(ocf_to_profit,ocf_to_revenue,free_cashflow_to_revenue,-accrual_ratio)"),
        ("leverage_exposure_z", "杠杆暴露z值 = avg_z(debt_to_assets,interestdebt_to_assets,netdebt_to_assets,liabilities_to_equity)"),
        ("concept_heat_exposure_z", "概念热度暴露z值 = avg_z(concept_hot_count_20,concept_avg_ret_20,concept_narrow_count)"),
        ("index_relative_exposure_z", "指数相对强弱暴露z值 = avg_z(stock_excess_hs300_20,stock_excess_zz500_20,stock_excess_zz1000_20)"),
    ]:
        if name not in existing:
            fields.append(f(name, "DOUBLE", desc))
            existing.add(name)
    return fields


def variable(field: dict, table: str, table_type: str = "physical") -> dict:
    return {
        "name": field["name"],
        "label_zh": field["description"].split("=")[0].strip(),
        "table": table,
        "module": "cross_sectional",
        "category": "cross_sectional",
        "tier": "core" if table_type == "physical" else "extended",
        "dtype": field["dtype"],
        "unit": "rank" if "_rank_" in field["name"] else "ratio_or_zscore",
        "frequency": "daily",
        "grain": ["ts_code", "trade_date"],
        "source_type": "derived",
        "dependencies": [
            "derived_daily_spine",
            "derived_return_momentum",
            "derived_volume_liquidity",
            "derived_volatility_risk",
            "derived_valuation_size",
            "derived_financial_quality",
            "derived_financial_growth",
            "derived_capital_flow",
            "derived_sector_concept_context",
            "derived_index_market_context",
        ],
        "formula_ref": field["description"],
        "formula_zh": field["description"],
        "price_basis": "mixed",
        "point_in_time": True,
        "min_history": 1,
        "read_window": 520,
        "write_window": 10,
        "missing_policy": "source_optional",
        "validation": {"constant_allowed": field["dtype"] in {"VARCHAR", "BOOLEAN", "INTEGER"}},
    }


def main() -> None:
    physical = physical_fields()
    full = view_fields()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    upsert_table(
        schema,
        {
            "name": "derived_cross_sectional",
            "phase": "P3",
            "description": "Phase 3 截面变换核心物理表",
            "primary_key": ["ts_code", "trade_date"],
            "fields": physical,
        },
    )
    upsert_table(
        schema,
        {
            "name": "derived_cross_sectional_full_v",
            "phase": "P3",
            "description": "Phase 3 截面变换完整视图",
            "table_type": "view",
            "primary_key": ["ts_code", "trade_date"],
            "fields": full,
        },
    )
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = json.loads(DERIVED_VARIABLES_PATH.read_text(encoding="utf-8"))
    registry["variables"] = [
        item for item in registry.get("variables", [])
        if item.get("module") != "cross_sectional"
    ]
    for field in physical:
        if field["name"] in {"ts_code", "trade_date", "updated_at"}:
            continue
        registry["variables"].append(variable(field, "derived_cross_sectional", "physical"))
    for field in full:
        if field["name"] in {item["name"] for item in physical} or field["name"] in {"ts_code", "trade_date", "updated_at"}:
            continue
        registry["variables"].append(variable(field, "derived_cross_sectional_full_v", "view"))
    DERIVED_VARIABLES_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"derived_cross_sectional": len(physical), "derived_cross_sectional_full_v": len(full)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
