from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"

MODULE = "composite_state"
CORE_TABLE = "derived_composite_state"
FULL_VIEW = "derived_composite_state_full_v"
CONDITION_VIEW = "composite_state_condition_detail_v"
COVERAGE_VIEW = "composite_state_module_coverage_v"


def f(name: str, dtype: str, desc: str, nullable: bool = True) -> dict:
    payload = {"name": name, "dtype": dtype, "nullable": nullable, "description": desc, "source_api": "local_derived"}
    if name == "updated_at":
        payload["nullable"] = False
        payload["default"] = "CURRENT_TIMESTAMP"
    return payload


PK = [f("ts_code", "VARCHAR", "股票代码", False), f("trade_date", "DATE", "交易日期", False)]
UPDATED = [f("updated_at", "TIMESTAMP", "本地更新时间 = CURRENT_TIMESTAMP", False)]

META_FIELDS = [
    f("composite_available_flag", "BOOLEAN", "综合状态可用标记 = 任一核心上游模块可用"),
    f("module_available_count", "INTEGER", "上游模块可用数量 = core module available flags true count"),
    f("module_available_ratio", "DOUBLE", "上游模块可用率 = module_available_count / module_count"),
    f("missing_module_names", "VARCHAR", "缺失模块名称列表 = missing core modules joined by semicolon"),
    f("state_condition_count", "INTEGER", "核心状态条件满足数量 = true condition count"),
    f("state_condition_available_count", "INTEGER", "核心状态条件可判断数量 = non-null condition count"),
    f("state_condition_available_ratio", "DOUBLE", "核心状态条件可判断率 = available condition count / total condition count"),
    f("latest_low_freq_event_date", "DATE", "最近低频事件日期 = greatest(financial/corporate/ownership event dates)"),
    f("days_since_latest_low_freq_event", "INTEGER", "距最近低频事件天数 = trade_date - latest_low_freq_event_date"),
]

IDENTITY_FIELDS = [
    f("is_listed_asof", "BOOLEAN", "当日是否上市 = derived_daily_spine.is_listed_asof"),
    f("list_status_asof", "VARCHAR", "当日上市状态 = derived_daily_spine.list_status_asof"),
    f("market_board_state", "VARCHAR", "市场板块状态 = exchange + ':' + market"),
    f("list_age_bucket", "VARCHAR", "上市年限分层 = <1y/1-3y/3-5y/5-10y/ge10y/unknown"),
    f("tradable_state", "VARCHAR", "交易可达状态 = derived_trading_constraint.tradable_state"),
    f("price_valid_state", "VARCHAR", "价格有效状态 = valid_price/trading_no_price/no_price/invalid_price"),
    f("limit_lock_state", "VARCHAR", "涨跌停锁定状态 = none/limit_up/limit_down/one_price_limit/unknown"),
    f("recent_suspend_state", "VARCHAR", "近期停牌状态 = none/recent/mild/frequent/unknown"),
]

TREND_FIELDS = [
    f("price_above_ma20_flag", "BOOLEAN", "收盘价高于20日均线 = close_hfq > ma_20_hfq"),
    f("price_above_ma60_flag", "BOOLEAN", "收盘价高于60日均线 = close_hfq > ma_60_hfq"),
    f("ma20_above_ma60_flag", "BOOLEAN", "20日均线高于60日均线 = ma_20_hfq > ma_60_hfq"),
    f("ma60_above_ma120_flag", "BOOLEAN", "60日均线高于120日均线 = ma_60_hfq > ma_120_hfq"),
    f("ma_alignment_state", "VARCHAR", "均线排列状态 = bull/partial_bull/mixed/partial_bear/bear/unknown"),
    f("ret_20_positive_flag", "BOOLEAN", "20日收益为正 = ret_20_hfq > 0"),
    f("ret_60_positive_flag", "BOOLEAN", "60日收益为正 = ret_60_hfq > 0"),
    f("ret_250_positive_flag", "BOOLEAN", "250日收益为正 = ret_250_hfq > 0"),
    f("momentum_spread_positive_flag", "BOOLEAN", "中期动量差为正 = momentum_60_20_hfq > 0"),
    f("trend_condition_count", "INTEGER", "趋势条件满足数 = trend flags true count"),
    f("trend_state", "VARCHAR", "趋势枚举状态 = bull/partial_bull/mixed/partial_bear/bear/unknown"),
]

LIQUIDITY_RISK_FIELDS = [
    f("liquidity_available_flag", "BOOLEAN", "流动性状态可判断 = amount/turnover/amihud fields available"),
    f("amount_activity_state", "VARCHAR", "成交额活跃度状态 = low/mid/high/unknown from amount_ma_20_pct_all_desc"),
    f("turnover_activity_state", "VARCHAR", "换手活跃度状态 = low/mid/high/unknown from turnover_rate_ma_20_pct_all_desc"),
    f("liquidity_cost_state", "VARCHAR", "流动性成本状态 = low/mid/high/unknown from amihud_20_pct_all_desc"),
    f("volatility_state", "VARCHAR", "波动状态 = low/mid/high/unknown from hv_60_pct_all_desc"),
    f("drawdown_state", "VARCHAR", "回撤状态 = low/mid/high/unknown from max_drawdown_60_hfq_pct_all_desc"),
    f("liquidity_condition_count", "INTEGER", "流动性条件满足数 = liquidity flags true count"),
    f("risk_condition_count", "INTEGER", "风险状态条件数 = risk flags true count"),
]

VALUATION_FIELDS = [
    f("size_bucket_all", "VARCHAR", "全市场规模分层 = low/mid/high/unknown from log_total_mv_pct_all_desc"),
    f("size_bucket_sw_l2", "VARCHAR", "申万二级内规模分层 = low/mid/high/unknown from log_total_mv_pct_sw_l2_desc"),
    f("pe_valid_flag", "BOOLEAN", "PE可解释标记 = derived_valuation_size.pe_ttm_valid_flag"),
    f("pb_valid_flag", "BOOLEAN", "PB可解释标记 = derived_valuation_size.pb_valid_flag"),
    f("valuation_percentile_state", "VARCHAR", "历史估值位置状态 = low/mid/high/unknown from pe/pb/ps historical percentile"),
    f("value_exposure_state", "VARCHAR", "价值暴露状态 = low/mid/high/unknown from value_exposure_z"),
    f("size_exposure_state", "VARCHAR", "规模暴露状态 = low/mid/high/unknown from size_exposure_z"),
    f("valuation_condition_count", "INTEGER", "估值状态条件数 = valuation flags true count"),
]

FINANCIAL_FIELDS = [
    f("financial_available_flag", "BOOLEAN", "财务状态可用标记 = latest_report_end_date is not null"),
    f("financial_statement_complete_flag", "BOOLEAN", "当前报告期三表及指标完整 = has_complete_statement_set_asof"),
    f("financial_staleness_state", "VARCHAR", "财务数据滞后状态 = fresh/normal/stale/unknown by report age"),
    f("profitability_positive_flag", "BOOLEAN", "盈利能力为正 = roe_asof > 0 or roa_asof > 0"),
    f("cashflow_profit_match_flag", "BOOLEAN", "经营现金流与利润同向 = ocf_to_profit_asof > 0"),
    f("leverage_state", "VARCHAR", "资产负债状态 = low/mid/high/unknown from debt_to_assets_asof_pct_all_desc"),
    f("growth_revenue_positive_flag", "BOOLEAN", "收入同比为正 = revenue_yoy_asof > 0"),
    f("growth_profit_positive_flag", "BOOLEAN", "净利润同比为正 = netprofit_yoy_asof > 0"),
    f("quality_exposure_state", "VARCHAR", "财务质量暴露状态 = low/mid/high/unknown from quality_exposure_z"),
    f("growth_exposure_state", "VARCHAR", "成长暴露状态 = low/mid/high/unknown from growth_exposure_z"),
    f("financial_condition_count", "INTEGER", "财务条件满足数 = financial flags true count"),
]

FLOW_FIELDS = [
    f("capital_flow_available_flag", "BOOLEAN", "资金流状态可用标记 = has_moneyflow or has_margin or has_north_holding"),
    f("main_flow_20_positive_flag", "BOOLEAN", "20日主力净流入为正 = main_flow_sum_20 > 0"),
    f("main_flow_persist_state", "VARCHAR", "主力净流入持续状态 = low/mid/high/unknown from main_flow_persist_ratio_20"),
    f("margin_balance_change_state", "VARCHAR", "融资余额变化状态 = decrease/flat/increase/unknown"),
    f("north_holding_change_state", "VARCHAR", "北向持股变化状态 = decrease/flat/increase/unknown"),
    f("top_list_recent_flag", "BOOLEAN", "近期龙虎榜事件标记 = top_list_count_20 > 0 when available"),
    f("flow_exposure_state", "VARCHAR", "资金流暴露状态 = low/mid/high/unknown from flow_exposure_z"),
    f("capital_flow_condition_count", "INTEGER", "资金流条件满足数 = capital flow flags true count"),
]

SECTOR_MARKET_FIELDS = [
    f("sector_context_available_flag", "BOOLEAN", "行业上下文可用标记 = sw_l1_code is not null"),
    f("sw_l1_code", "VARCHAR", "申万一级行业代码 = derived_sector_concept_context.sw_l1_code"),
    f("sw_l2_code", "VARCHAR", "申万二级行业代码 = derived_sector_concept_context.sw_l2_code"),
    f("sector_relative_return_state", "VARCHAR", "行业内相对收益状态 = lag/mid/lead/unknown from stock_excess_sw_l2_20"),
    f("concept_membership_state", "VARCHAR", "概念归属状态 = none/single/multiple/unknown"),
    f("concept_heat_state", "VARCHAR", "概念热度状态 = low/mid/high/unknown from concept_hot_count_20"),
    f("index_membership_state", "VARCHAR", "主要指数成员状态 = major/broad/none/unknown"),
    f("market_context_state", "VARCHAR", "市场环境状态 = down/mixed/up/unknown from market_up_ratio"),
    f("sector_market_condition_count", "INTEGER", "板块市场条件数 = sector/market flags true count"),
]

EVENT_FIELDS = [
    f("corporate_action_available_flag", "BOOLEAN", "公司行为状态可用标记 = derived_corporate_action.corp_action_available_flag"),
    f("dividend_recent_state", "VARCHAR", "近期分红状态 = none/recent/active/unknown"),
    f("forecast_recent_state", "VARCHAR", "业绩预告状态 = none/available/unknown"),
    f("audit_opinion_state", "VARCHAR", "审计意见状态 = standard/non_standard/unknown"),
    f("repurchase_recent_flag", "BOOLEAN", "近期回购事件标记 = repurchase_amount_365d > 0"),
    f("unlock_future_state", "VARCHAR", "未来解禁状态 = none/within30d/within90d/unknown for announced events"),
    f("ownership_available_flag", "BOOLEAN", "持有人治理状态可用标记 = derived_ownership_governance.ownership_available_flag"),
    f("pledge_ratio_state", "VARCHAR", "质押比例状态 = below10/ge10/ge30/ge50/unknown"),
    f("holder_number_change_state", "VARCHAR", "股东户数变化状态 = decrease/flat/increase/unknown"),
    f("holder_concentration_state", "VARCHAR", "股权集中度状态 = low/mid/high/unknown"),
    f("event_condition_count", "INTEGER", "事件治理条件数 = event and ownership flags true count"),
]

EXPOSURE_FIELDS = [
    f("exposure_available_count", "INTEGER", "横截面暴露可用数量 = non-null exposure z count"),
    f("value_quality_pair_state", "VARCHAR", "价值与质量暴露共现状态 = value_state + '_' + quality_state"),
    f("momentum_flow_pair_state", "VARCHAR", "动量与资金流暴露共现状态 = momentum_state + '_' + flow_state"),
    f("growth_quality_pair_state", "VARCHAR", "成长与质量暴露共现状态 = growth_state + '_' + quality_state"),
    f("risk_liquidity_pair_state", "VARCHAR", "波动与流动性暴露共现状态 = volatility_state + '_' + liquidity_state"),
    f("multi_domain_condition_count", "INTEGER", "多域条件满足数 = trend/liquidity/financial/flow/sector/event condition counts sum"),
]

CORE_FIELDS = (
    PK
    + META_FIELDS
    + IDENTITY_FIELDS
    + TREND_FIELDS
    + LIQUIDITY_RISK_FIELDS
    + VALUATION_FIELDS
    + FINANCIAL_FIELDS
    + FLOW_FIELDS
    + SECTOR_MARKET_FIELDS
    + EVENT_FIELDS
    + EXPOSURE_FIELDS
    + UPDATED
)

FULL_EXTRA_FIELDS = [
    f("close_hfq", "DOUBLE", "解释字段：derived_daily_spine.close_hfq"),
    f("ma_20_hfq", "DOUBLE", "解释字段：derived_price_technical.ma_20_hfq"),
    f("ma_60_hfq", "DOUBLE", "解释字段：derived_price_technical.ma_60_hfq"),
    f("ma_120_hfq", "DOUBLE", "解释字段：derived_price_technical.ma_120_hfq"),
    f("ret_20_hfq", "DOUBLE", "解释字段：derived_return_momentum.ret_20_hfq"),
    f("ret_60_hfq", "DOUBLE", "解释字段：derived_return_momentum.ret_60_hfq"),
    f("ret_250_hfq", "DOUBLE", "解释字段：derived_return_momentum.ret_250_hfq"),
    f("amount_ma_20_pct_all_desc", "DOUBLE", "解释字段：derived_cross_sectional.amount_ma_20_pct_all_desc"),
    f("hv_60_pct_all_desc", "DOUBLE", "解释字段：derived_cross_sectional.hv_60_pct_all_desc"),
    f("log_total_mv_pct_all_desc", "DOUBLE", "解释字段：derived_cross_sectional.log_total_mv_pct_all_desc"),
    f("value_exposure_z", "DOUBLE", "解释字段：derived_cross_sectional.value_exposure_z"),
    f("quality_exposure_z", "DOUBLE", "解释字段：derived_cross_sectional.quality_exposure_z"),
    f("momentum_exposure_z", "DOUBLE", "解释字段：derived_cross_sectional.momentum_exposure_z"),
    f("flow_exposure_z", "DOUBLE", "解释字段：derived_cross_sectional.flow_exposure_z"),
    f("growth_exposure_z", "DOUBLE", "解释字段：derived_cross_sectional.growth_exposure_z"),
    f("volatility_exposure_z", "DOUBLE", "解释字段：derived_cross_sectional.volatility_exposure_z"),
    f("liquidity_exposure_z", "DOUBLE", "解释字段：derived_cross_sectional.liquidity_exposure_z"),
    f("latest_report_end_date", "DATE", "解释字段：derived_financial_asof.latest_report_end_date"),
    f("latest_corp_action_date", "DATE", "解释字段：derived_corporate_action.latest_corp_action_date"),
    f("latest_ownership_event_date", "DATE", "解释字段：derived_ownership_governance.latest_ownership_event_date"),
    f("concept_names_all", "VARCHAR", "解释字段：derived_sector_concept_context.concept_names_all"),
    f("primary_index_name", "VARCHAR", "解释字段：derived_index_market_context.primary_index_name"),
    f("condition_names_true", "VARCHAR", "成立条件名称列表 = condition detail true condition names joined by semicolon"),
]

CONDITION_FIELDS = [
    f("ts_code", "VARCHAR", "股票代码", False),
    f("trade_date", "DATE", "交易日期", False),
    f("condition_group", "VARCHAR", "条件组", False),
    f("condition_name", "VARCHAR", "条件名称", False),
    f("condition_value", "BOOLEAN", "条件是否成立"),
    f("condition_available_flag", "BOOLEAN", "条件是否可判断"),
    f("source_table", "VARCHAR", "来源表"),
    f("source_fields", "VARCHAR", "来源字段"),
    f("formula_text", "VARCHAR", "公式文本"),
    f("updated_at", "TIMESTAMP", "本地更新时间 = CURRENT_TIMESTAMP", False),
]

COVERAGE_FIELDS = [
    f("trade_date", "DATE", "交易日期", False),
    f("module_name", "VARCHAR", "模块名称", False),
    f("expected_rows", "BIGINT", "应覆盖行数"),
    f("available_rows", "BIGINT", "可用行数"),
    f("available_ratio", "DOUBLE", "可用率 = available_rows / expected_rows"),
    f("key_non_null_ratio", "DOUBLE", "关键字段非空率"),
    f("latest_source_update_at", "TIMESTAMP", "来源最新更新时间"),
    f("quality_note", "VARCHAR", "质量备注"),
]


def upsert_table(schema: dict, table: dict) -> None:
    for idx, existing in enumerate(schema["tables"]):
        if existing["name"] == table["name"]:
            schema["tables"][idx] = table
            return
    schema["tables"].append(table)


def variable(field: dict, table: str, tier: str) -> dict:
    dtype = field["dtype"]
    return {
        "name": field["name"],
        "label_zh": field["description"].split("=")[0].strip(),
        "table": table,
        "module": MODULE,
        "category": MODULE,
        "tier": tier,
        "dtype": dtype,
        "unit": "none" if dtype in {"BOOLEAN", "VARCHAR", "DATE", "TIMESTAMP"} else "source_unit_or_count",
        "frequency": "daily",
        "grain": ["ts_code", "trade_date"] if table not in {COVERAGE_VIEW} else ["trade_date", "module_name"],
        "source_type": "derived",
        "dependencies": [
            "derived_daily_spine",
            "derived_price_technical",
            "derived_volume_liquidity",
            "derived_return_momentum",
            "derived_volatility_risk",
            "derived_trading_constraint",
            "derived_valuation_size",
            "derived_financial_asof",
            "derived_financial_quality",
            "derived_financial_growth",
            "derived_capital_flow",
            "derived_sector_concept_context",
            "derived_index_market_context",
            "derived_cross_sectional",
            "derived_corporate_action",
            "derived_ownership_governance",
        ],
        "formula_ref": field["description"],
        "formula_zh": field["description"],
        "price_basis": "mixed_documented",
        "point_in_time": True,
        "min_history": 1,
        "read_window": 250,
        "write_window": 10,
        "missing_policy": "unknown_enum_or_null",
        "validation": {"constant_allowed": dtype in {"BOOLEAN", "VARCHAR", "INTEGER", "DATE"}},
    }


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    upsert_table(
        schema,
        {
            "name": CORE_TABLE,
            "phase": "P3",
            "description": "Phase 3 composite factual state core physical table; no score fields",
            "primary_key": ["ts_code", "trade_date"],
            "fields": CORE_FIELDS,
        },
    )
    upsert_table(
        schema,
        {
            "name": FULL_VIEW,
            "phase": "P3",
            "description": "Phase 3 composite factual state full explanatory view",
            "table_type": "view",
            "primary_key": ["ts_code", "trade_date"],
            "fields": CORE_FIELDS[:-1] + FULL_EXTRA_FIELDS + UPDATED,
        },
    )
    upsert_table(
        schema,
        {
            "name": CONDITION_VIEW,
            "phase": "P3",
            "description": "Composite state condition detail long view",
            "table_type": "view",
            "primary_key": ["ts_code", "trade_date", "condition_name"],
            "fields": CONDITION_FIELDS,
        },
    )
    upsert_table(
        schema,
        {
            "name": COVERAGE_VIEW,
            "phase": "P3",
            "description": "Composite state upstream module coverage view",
            "table_type": "view",
            "primary_key": ["trade_date", "module_name"],
            "fields": COVERAGE_FIELDS,
        },
    )
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = json.loads(DERIVED_VARIABLES_PATH.read_text(encoding="utf-8"))
    registry["variables"] = [
        item
        for item in registry.get("variables", [])
        if item.get("module") != MODULE and item.get("table") not in {CORE_TABLE, FULL_VIEW, CONDITION_VIEW, COVERAGE_VIEW}
    ]
    for field in CORE_FIELDS:
        if field["name"] not in {"ts_code", "trade_date", "updated_at"}:
            registry["variables"].append(variable(field, CORE_TABLE, "core"))
    for field in FULL_EXTRA_FIELDS:
        registry["variables"].append(variable(field, FULL_VIEW, "extended"))
    for field in CONDITION_FIELDS:
        if field["name"] not in {"ts_code", "trade_date"}:
            registry["variables"].append(variable(field, CONDITION_VIEW, "extended"))
    for field in COVERAGE_FIELDS:
        registry["variables"].append(variable(field, COVERAGE_VIEW, "extended"))
    DERIVED_VARIABLES_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({CORE_TABLE: len(CORE_FIELDS), FULL_VIEW: len(CORE_FIELDS) - 1 + len(FULL_EXTRA_FIELDS) + 1, CONDITION_VIEW: len(CONDITION_FIELDS), COVERAGE_VIEW: len(COVERAGE_FIELDS)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
