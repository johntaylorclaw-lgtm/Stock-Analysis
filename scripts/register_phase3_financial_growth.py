from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"


META_FIELDS = [
    ("ts_code", "股票代码", "VARCHAR", "主键"),
    ("trade_date", "交易日期", "DATE", "主键"),
    ("current_report_end_date", "当前可得报告期", "DATE", "derived_financial_asof.latest_report_end_date"),
    ("prev_report_end_date", "上一报告期", "DATE", "lag(current_report_end_date, 1)"),
    ("lag_2report_end_date", "前2个报告期", "DATE", "lag(current_report_end_date, 2)"),
    ("lag_4report_end_date", "前4个报告期", "DATE", "lag(current_report_end_date, 4)"),
    ("lag_8report_end_date", "前8个报告期", "DATE", "lag(current_report_end_date, 8)"),
    ("same_period_1y_end_date", "去年同期报告期", "DATE", "same quarter previous year"),
    ("same_period_2y_end_date", "两年前同期报告期", "DATE", "same quarter two years ago"),
    ("same_period_3y_end_date", "三年前同期报告期", "DATE", "same quarter three years ago"),
]

TUSHARE_GROWTH_FIELDS = [
    ("revenue_yoy_asof", "营业收入同比", "financial_indicator_raw.or_yoy"),
    ("total_revenue_yoy_asof", "营业总收入同比", "financial_indicator_raw.tr_yoy"),
    ("netprofit_yoy_asof", "净利润同比", "financial_indicator_raw.netprofit_yoy"),
    ("deducted_netprofit_yoy_asof", "扣非净利润同比", "financial_indicator_raw.dt_netprofit_yoy"),
    ("ocf_yoy_asof", "经营现金流同比", "financial_indicator_raw.ocf_yoy"),
    ("eps_yoy_asof", "EPS同比", "financial_indicator_raw.basic_eps_yoy"),
    ("dt_eps_yoy_asof", "扣非EPS同比", "financial_indicator_raw.dt_eps_yoy"),
    ("cfps_yoy_asof", "每股现金流同比", "financial_indicator_raw.cfps_yoy"),
    ("roe_yoy_asof", "ROE同比", "financial_indicator_raw.roe_yoy"),
    ("bps_yoy_asof", "每股净资产同比", "financial_indicator_raw.bps_yoy"),
    ("assets_yoy_asof", "总资产同比", "financial_indicator_raw.assets_yoy"),
    ("equity_yoy_asof", "所有者权益同比", "financial_indicator_raw.eqt_yoy"),
    ("q_revenue_yoy_asof", "Tushare单季收入同比", "financial_indicator_raw.q_sales_yoy"),
    ("q_revenue_qoq_asof", "Tushare单季收入环比", "financial_indicator_raw.q_sales_qoq"),
    ("q_operating_profit_yoy_asof", "Tushare单季营业利润同比", "financial_indicator_raw.q_op_yoy"),
    ("q_operating_profit_qoq_asof", "Tushare单季营业利润环比", "financial_indicator_raw.q_op_qoq"),
    ("q_netprofit_yoy_asof", "Tushare单季净利润同比", "financial_indicator_raw.q_netprofit_yoy"),
    ("q_netprofit_qoq_asof", "Tushare单季净利润环比", "financial_indicator_raw.q_netprofit_qoq"),
]

AMOUNT_METRICS = [
    ("revenue", "营业收入", "financial_income_raw.revenue", True),
    ("total_revenue", "营业总收入", "financial_income_raw.total_revenue", True),
    ("operating_cost", "营业成本", "financial_income_raw.operating_cost", True),
    ("total_cogs", "营业总成本", "financial_income_raw.total_cogs", True),
    ("operating_profit", "营业利润", "financial_income_raw.operating_profit", True),
    ("total_profit", "利润总额", "financial_income_raw.total_profit", True),
    ("net_profit", "净利润", "financial_income_raw.net_profit", True),
    ("parent_net_profit", "归母净利润", "financial_income_raw.net_profit_attr_parent", True),
    ("deducted_profit", "扣非净利润", "financial_indicator_raw.profit_dedt", True),
    ("ebit", "EBIT", "financial_income_raw.ebit", True),
    ("ebitda", "EBITDA", "financial_income_raw.ebitda", True),
    ("ocf", "经营现金流净额", "financial_cashflow_raw.cf_from_operating", True),
    ("icf", "投资现金流净额", "financial_cashflow_raw.cf_from_investing", True),
    ("fcf", "筹资现金流净额", "financial_cashflow_raw.cf_from_financing", True),
    ("free_cashflow", "自由现金流", "financial_cashflow_raw.free_cashflow", True),
    ("cash_received_from_sales", "销售商品提供劳务收到现金", "financial_cashflow_raw.cash_received_from_sales", True),
    ("cash_paid_for_goods", "购买商品接受劳务支付现金", "financial_cashflow_raw.cash_paid_for_goods", True),
    ("cash_paid_for_capex", "购建固定资产等支付现金", "financial_cashflow_raw.cash_paid_for_capex", True),
    ("total_assets", "总资产", "financial_balance_raw.total_assets", False),
    ("current_assets", "流动资产", "financial_balance_raw.current_assets", False),
    ("noncurrent_assets", "非流动资产", "financial_balance_raw.total_noncurrent_assets", False),
    ("total_liabilities", "总负债", "financial_balance_raw.total_liabilities", False),
    ("current_liabilities", "流动负债", "financial_balance_raw.current_liabilities", False),
    ("total_equity", "所有者权益", "financial_balance_raw.total_equity", False),
    ("equity_attr_parent", "归母权益", "financial_balance_raw.equity_attr_parent", False),
    ("interestdebt", "有息负债", "financial_indicator_raw.interestdebt", False),
    ("netdebt", "净债务", "financial_indicator_raw.netdebt", False),
    ("rd_expense", "研发费用", "financial_income_raw.rd_expense", True),
    ("selling_expense", "销售费用", "financial_income_raw.selling_expense", True),
    ("admin_expense", "管理费用", "financial_income_raw.admin_expense", True),
    ("finance_expense", "财务费用", "financial_income_raw.finance_expense", True),
]

AMOUNT_SUFFIXES = [
    ("qoq_report_asof", "上一报告期变化率", "safe_growth(current, prev_report)"),
    ("change_2report_asof", "近2报告期变化率", "safe_growth(current, lag_2report)"),
    ("change_4report_asof", "近4报告期变化率", "safe_growth(current, lag_4report)"),
    ("change_8report_asof", "近8报告期变化率", "safe_growth(current, lag_8report)"),
    ("yoy_1y_calc_asof", "1年同比计算值", "safe_growth(current, same_period_1y)"),
    ("yoy_2y_calc_asof", "2年累计同比", "safe_growth(current, same_period_2y)"),
    ("yoy_3y_calc_asof", "3年累计同比", "safe_growth(current, same_period_3y)"),
    ("cagr_2y_asof", "2年复合增速", "safe_cagr(current, same_period_2y, 2)"),
    ("cagr_3y_asof", "3年复合增速", "safe_cagr(current, same_period_3y, 3)"),
]

SINGLE_QUARTER_SUFFIXES = [
    ("single_quarter_value_asof", "倒推单季值", "cumulative quarter deduction"),
    ("single_quarter_yoy_asof", "倒推单季同比", "safe_growth(current_single_quarter, prior_year_single_quarter)"),
    ("single_quarter_qoq_asof", "倒推单季环比", "safe_growth(current_single_quarter, previous_quarter_single_quarter)"),
]

QUALITY_DIFF_SUFFIXES = [
    ("diff_1report_asof", "上一报告期差值", "current - prev_report"),
    ("diff_4report_asof", "近4报告期差值", "current - lag_4report"),
    ("diff_8report_asof", "近8报告期差值", "current - lag_8report"),
    ("yoy_diff_asof", "同比差值", "current - same_period_1y"),
    ("growth_1report_asof", "上一报告期变化率", "safe_growth(current, prev_report)"),
    ("growth_4report_asof", "近4报告期变化率", "safe_growth(current, lag_4report)"),
    ("growth_8report_asof", "近8报告期变化率", "safe_growth(current, lag_8report)"),
    ("yoy_growth_asof", "同比变化率", "safe_growth(current, same_period_1y)"),
]

STATUS_FIELDS = [
    ("revenue_positive_growth_flag", "收入正增长标记", "revenue_yoy_1y_calc_asof > 0"),
    ("profit_positive_growth_flag", "归母净利润正增长标记", "parent_net_profit_yoy_1y_calc_asof > 0"),
    ("deducted_profit_positive_growth_flag", "扣非净利润正增长标记", "deducted_profit_yoy_1y_calc_asof > 0"),
    ("ocf_positive_growth_flag", "经营现金流正增长标记", "ocf_yoy_1y_calc_asof > 0"),
    ("revenue_profit_same_direction_flag", "收入利润同向标记", "revenue and parent net profit growth have same sign"),
    ("profit_ocf_same_direction_flag", "利润现金流同向标记", "parent net profit and ocf growth have same sign"),
    ("roe_yoy_improving_flag", "ROE同比改善标记", "roe_yoy_diff_asof > 0"),
    ("gross_margin_yoy_improving_flag", "毛利率同比改善标记", "gross_margin_yoy_diff_asof > 0"),
    ("debt_to_assets_yoy_increasing_flag", "资产负债率同比上升标记", "debt_to_assets_yoy_diff_asof > 0"),
    ("ocf_to_profit_yoy_improving_flag", "经营现金流/净利润同比改善标记", "ocf_to_profit_yoy_diff_asof > 0"),
    ("negative_profit_continued_flag", "净利润连续为负标记", "current and previous negative_net_profit_flag"),
    ("negative_ocf_continued_flag", "经营现金流连续为负标记", "current and previous negative_ocf_flag"),
    ("high_goodwill_continued_flag", "高商誉状态延续标记", "current and previous high_goodwill_flag"),
    ("high_leverage_continued_flag", "高杠杆状态延续标记", "current and previous high_leverage_flag"),
]


def field(name: str, dtype: str, description: str, nullable: bool = True) -> dict:
    payload = {
        "name": name,
        "dtype": dtype,
        "nullable": nullable,
        "description": description,
        "source_api": "local_derived",
    }
    if name == "updated_at":
        payload["default"] = "CURRENT_TIMESTAMP"
    return payload


def variable(name: str, label: str, dtype: str, formula: str, category: str) -> dict:
    return {
        "name": name,
        "label_zh": label,
        "table": "derived_financial_growth",
        "module": "financial_growth",
        "category": category,
        "tier": "core",
        "dtype": dtype,
        "unit": "none" if dtype in {"DATE", "BOOLEAN"} else "ratio_or_source_unit",
        "frequency": "daily",
        "grain": ["ts_code", "trade_date"],
        "source_type": "derived",
        "dependencies": [
            "derived_financial_asof",
            "derived_financial_quality",
            "financial_indicator_raw",
            "financial_income_raw",
            "financial_balance_raw",
            "financial_cashflow_raw",
        ],
        "formula_ref": formula,
        "formula_zh": formula,
        "price_basis": "financial_asof",
        "point_in_time": True,
        "effective_date_rule": "first_non_null(first_ann_date, ann_date)",
        "min_history": 1,
        "read_window": 1300,
        "write_window": 10,
        "missing_policy": "ratio_special_code_-9ABCDEF" if "safe_" in formula else "financial_not_disclosed",
        "validation": {"constant_allowed": True},
    }


def build_growth_definitions() -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    for name, label, dtype, formula in META_FIELDS:
        rows.append((name, label, dtype, formula, "report_sequence"))
    for name, label, formula in TUSHARE_GROWTH_FIELDS:
        rows.append((name, label, "DOUBLE", f"asof({formula})", "tushare_growth"))
    for metric, label, source, _flow in AMOUNT_METRICS:
        for suffix, suffix_label, formula in AMOUNT_SUFFIXES:
            name = f"{metric}_{suffix}"
            rows.append((name, f"{label}{suffix_label}", "DOUBLE", f"{name} = {formula}; source={source}", "amount_growth"))
        if _flow:
            for suffix, suffix_label, formula in SINGLE_QUARTER_SUFFIXES:
                name = f"{metric}_{suffix}"
                rows.append((name, f"{label}{suffix_label}", "DOUBLE", f"{name} = {formula}; source={source}", "single_quarter_growth"))
    quality_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    quality_table = next(table for table in quality_schema["tables"] if table["name"] == "derived_financial_quality")
    for quality_field in quality_table["fields"]:
        qname = quality_field["name"]
        if qname in {"ts_code", "trade_date", "updated_at"}:
            continue
        if quality_field["dtype"] not in {"DOUBLE", "INTEGER", "BIGINT"}:
            continue
        base = qname.removesuffix("_asof")
        label = quality_field.get("description", qname)
        for suffix, suffix_label, formula in QUALITY_DIFF_SUFFIXES:
            name = f"{base}_{suffix}"
            rows.append((name, f"{label}{suffix_label}", "DOUBLE", f"{name} = {formula}; source=derived_financial_quality.{qname}", "quality_change"))
    for name, label, formula in STATUS_FIELDS:
        rows.append((name, label, "BOOLEAN", formula, "growth_state"))
    return rows


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    definitions = build_growth_definitions()
    growth_fields = [
        field("ts_code", "VARCHAR", "Stock code", False),
        field("trade_date", "DATE", "Trade date", False),
    ]
    for name, _label, dtype, formula, _category in definitions:
        if name in {"ts_code", "trade_date"}:
            continue
        growth_fields.append(field(name, dtype, formula, True))
    growth_fields.append(field("updated_at", "TIMESTAMP", "Local update timestamp", False))
    for table in schema["tables"]:
        if table["name"] == "derived_financial_growth":
            table["description"] = (
                "Phase 3 financial growth derived variables, fully registered and batch materialized"
            )
            table["fields"] = growth_fields
            break
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = json.loads(DERIVED_VARIABLES_PATH.read_text(encoding="utf-8"))
    registry["variables"] = [
        variable_item
        for variable_item in registry["variables"]
        if variable_item.get("table") != "derived_financial_growth"
    ]
    registry["variables"].extend(
        variable(name, label, dtype, formula, category)
        for name, label, dtype, formula, category in definitions
        if name not in {"ts_code", "trade_date"}
    )
    DERIVED_VARIABLES_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"registered derived_financial_growth fields: {len(growth_fields)}")
    print(f"registered derived_financial_growth variables: {len(definitions) - 2}")


if __name__ == "__main__":
    main()
