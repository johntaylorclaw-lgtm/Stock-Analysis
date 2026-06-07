from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"


CORE_AMOUNT_METRICS = {
    "revenue",
    "total_revenue",
    "parent_net_profit",
    "net_profit",
    "deducted_profit",
    "ocf",
    "free_cashflow",
    "total_assets",
    "equity_attr_parent",
    "interestdebt",
    "netdebt",
    "rd_expense",
}

CORE_SINGLE_QUARTER_METRICS = {
    "revenue",
    "total_revenue",
    "parent_net_profit",
    "net_profit",
    "deducted_profit",
    "ocf",
    "free_cashflow",
    "rd_expense",
}

CORE_QUALITY_BASE_FIELDS = {
    "roe",
    "gross_margin",
    "netprofit_margin",
    "debt_to_assets",
    "ocf_to_profit",
    "goodwill_to_assets",
    "accounts_receivable_to_revenue",
    "inventory_to_revenue",
    "expense_to_revenue",
    "dupont_roe_calc",
}

CORE_STATUS_FIELDS = {
    "revenue_positive_growth_flag",
    "profit_positive_growth_flag",
    "deducted_profit_positive_growth_flag",
    "ocf_positive_growth_flag",
    "revenue_profit_same_direction_flag",
    "profit_ocf_same_direction_flag",
    "roe_yoy_improving_flag",
    "gross_margin_yoy_improving_flag",
    "debt_to_assets_yoy_increasing_flag",
    "ocf_to_profit_yoy_improving_flag",
    "negative_profit_continued_flag",
    "negative_ocf_continued_flag",
    "high_goodwill_continued_flag",
    "high_leverage_continued_flag",
}


def is_core_growth_field(name: str, category: str) -> bool:
    if category in {"report_sequence", "tushare_growth"}:
        return True
    if category == "growth_state":
        return name in CORE_STATUS_FIELDS
    if category == "amount_growth":
        metric = _metric_from_suffix(
            name,
            (
                "_qoq_report_asof",
                "_change_2report_asof",
                "_change_4report_asof",
                "_change_8report_asof",
                "_yoy_1y_calc_asof",
                "_yoy_2y_calc_asof",
                "_yoy_3y_calc_asof",
                "_cagr_2y_asof",
                "_cagr_3y_asof",
            ),
        )
        return metric in CORE_AMOUNT_METRICS
    if category == "single_quarter_growth":
        metric = _metric_from_suffix(
            name,
            (
                "_single_quarter_value_asof",
                "_single_quarter_yoy_asof",
                "_single_quarter_qoq_asof",
            ),
        )
        return metric in CORE_SINGLE_QUARTER_METRICS
    if category == "quality_change":
        base = _metric_from_suffix(
            name,
            (
                "_diff_1report_asof",
                "_diff_4report_asof",
                "_diff_8report_asof",
                "_yoy_diff_asof",
                "_growth_1report_asof",
                "_growth_4report_asof",
                "_growth_8report_asof",
                "_yoy_growth_asof",
            ),
        )
        return base in CORE_QUALITY_BASE_FIELDS
    return False


def _metric_from_suffix(name: str, suffixes: tuple[str, ...]) -> str:
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name
