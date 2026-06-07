from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"

MODULE = "corporate_action"
CORE_TABLE = "derived_corporate_action"
FULL_VIEW = "derived_corporate_action_full_v"
TIMELINE_VIEW = "corporate_action_event_timeline_v"


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
UPDATED = [f("updated_at", "TIMESTAMP", "本地更新时间 = CURRENT_TIMESTAMP", False)]

META_FIELDS = [
    f("corp_action_available_flag", "BOOLEAN", "公司行为数据可用标记 = 任一核心事件asof字段非空"),
    f("latest_corp_action_date", "DATE", "最近公司行为事件日期 = max(event_date <= trade_date)"),
    f("days_since_latest_corp_action", "INTEGER", "距最近公司行为事件天数 = trade_date - latest_corp_action_date"),
    f("corp_action_event_count_365d", "INTEGER", "近一年公司行为事件数 = count(event_date in [trade_date-365,trade_date])"),
]

DIVIDEND_FIELDS = [
    f("latest_dividend_ann_date", "DATE", "最近分红公告日 = asof(max(financial_dividend.ann_date <= trade_date))"),
    f("latest_dividend_end_date", "DATE", "最近分红所属报告期 = latest financial_dividend.end_date"),
    f("latest_dividend_ex_date", "DATE", "最近除权除息日 = latest financial_dividend.ex_date"),
    f("latest_dividend_record_date", "DATE", "最近股权登记日 = latest financial_dividend.record_date"),
    f("latest_dividend_pay_date", "DATE", "最近派息日 = latest financial_dividend.pay_date"),
    f("latest_dividend_proc", "VARCHAR", "最近分红实施进度 = financial_dividend.div_proc"),
    f("cash_dividend_per_share_latest", "DOUBLE", "最近每股现金分红 = financial_dividend.cash_div"),
    f("cash_dividend_after_tax_latest", "DOUBLE", "最近税后每股现金分红 = financial_dividend.cash_div_tax"),
    f("bonus_share_ratio_latest", "DOUBLE", "最近送股比例 = financial_dividend.stk_bo_rate"),
    f("transfer_share_ratio_latest", "DOUBLE", "最近转增比例 = financial_dividend.stk_co_rate"),
    f("stock_dividend_ratio_latest", "DOUBLE", "最近送转合计比例 = coalesce(stk_bo_rate,0)+coalesce(stk_co_rate,0)"),
    f("cash_dividend_ttm", "DOUBLE", "近一年每股现金分红合计 = sum(cash_div) over event_date 365d"),
    f("cash_dividend_after_tax_ttm", "DOUBLE", "近一年税后每股现金分红合计 = sum(cash_div_tax) over event_date 365d"),
    f("stock_dividend_ratio_ttm", "DOUBLE", "近一年送转比例合计 = sum(stk_bo_rate+stk_co_rate) over event_date 365d"),
    f("dividend_event_count_365d", "INTEGER", "近一年分红事件数 = count(dividend events in 365d)"),
    f("days_since_dividend_ann", "INTEGER", "距最近分红公告天数 = trade_date-latest_dividend_ann_date"),
    f("days_since_ex_dividend", "INTEGER", "距最近除权除息天数 = trade_date-latest_dividend_ex_date"),
    f("has_dividend_announced_not_executed", "BOOLEAN", "是否有已公告未除权分红 = exists(ann_date<=trade_date<ex_date)"),
    f("next_announced_ex_date", "DATE", "下一次已公告除权除息日 = min(ex_date where ann_date<=trade_date<ex_date)"),
    f("next_announced_cash_dividend", "DOUBLE", "下一次已公告每股现金分红 = cash_div at next_announced_ex_date"),
]

FORECAST_FIELDS = [
    f("has_forecast_asof", "BOOLEAN", "是否已有业绩预告 = exists(financial_forecast.ann_date <= trade_date)"),
    f("latest_forecast_ann_date", "DATE", "最近预告公告日 = latest financial_forecast.ann_date"),
    f("latest_forecast_end_date", "DATE", "最近预告报告期 = latest financial_forecast.end_date"),
    f("forecast_type_latest", "VARCHAR", "最近预告类型 = financial_forecast.forecast_type"),
    f("forecast_type_code_latest", "INTEGER", "最近预告类型编码 = enum(forecast_type_latest)"),
    f("forecast_p_change_min_latest", "DOUBLE", "预告净利变动下限 = financial_forecast.p_change_min"),
    f("forecast_p_change_max_latest", "DOUBLE", "预告净利变动上限 = financial_forecast.p_change_max"),
    f("forecast_p_change_mid_latest", "DOUBLE", "预告净利变动中位 = (p_change_min+p_change_max)/2"),
    f("forecast_net_profit_min_latest", "DOUBLE", "预告净利润下限 = financial_forecast.net_profit_min"),
    f("forecast_net_profit_max_latest", "DOUBLE", "预告净利润上限 = financial_forecast.net_profit_max"),
    f("forecast_net_profit_mid_latest", "DOUBLE", "预告净利润中位 = (net_profit_min+net_profit_max)/2"),
    f("forecast_range_width_latest", "DOUBLE", "预告净利润区间宽度 = net_profit_max-net_profit_min"),
    f("forecast_change_range_width_latest", "DOUBLE", "预告变动幅度区间宽度 = p_change_max-p_change_min"),
    f("days_since_forecast_ann", "INTEGER", "距最近预告公告天数 = trade_date-latest_forecast_ann_date"),
]

EXPRESS_FIELDS = [
    f("has_express_asof", "BOOLEAN", "是否已有业绩快报 = exists(financial_express.ann_date <= trade_date)"),
    f("latest_express_ann_date", "DATE", "最近快报公告日 = latest financial_express.ann_date"),
    f("latest_express_end_date", "DATE", "最近快报报告期 = latest financial_express.end_date"),
    f("express_revenue_latest", "DOUBLE", "最近快报营业收入 = financial_express.revenue"),
    f("express_operating_profit_latest", "DOUBLE", "最近快报营业利润 = financial_express.operating_profit"),
    f("express_total_profit_latest", "DOUBLE", "最近快报利润总额 = financial_express.total_profit"),
    f("express_net_profit_latest", "DOUBLE", "最近快报净利润 = financial_express.net_profit"),
    f("express_total_assets_latest", "DOUBLE", "最近快报总资产 = financial_express.total_assets"),
    f("express_equity_attr_parent_latest", "DOUBLE", "最近快报归母权益 = financial_express.equity_attr_parent"),
    f("express_diluted_eps_latest", "DOUBLE", "最近快报摊薄EPS = financial_express.diluted_eps"),
    f("express_diluted_roe_latest", "DOUBLE", "最近快报摊薄ROE = financial_express.diluted_roe"),
    f("express_yoy_net_profit_latest", "DOUBLE", "最近快报净利润同比 = financial_express.yoy_net_profit"),
    f("days_since_express_ann", "INTEGER", "距最近快报公告天数 = trade_date-latest_express_ann_date"),
]

AUDIT_FIELDS = [
    f("latest_audit_ann_date", "DATE", "最近审计公告日 = latest financial_audit_opinion.ann_date"),
    f("latest_audit_end_date", "DATE", "最近审计报告期 = latest financial_audit_opinion.end_date"),
    f("audit_opinion_latest", "VARCHAR", "最近审计意见 = financial_audit_opinion.audit_result"),
    f("audit_opinion_code_latest", "INTEGER", "最近审计意见编码 = enum(audit_opinion_latest)"),
    f("non_standard_audit_flag_latest", "BOOLEAN", "最近是否非标审计意见 = audit_opinion_code_latest in (2,3,4,5,99)"),
    f("audit_fees_latest", "DOUBLE", "最近审计费用 = financial_audit_opinion.audit_fees"),
    f("audit_agency_latest", "VARCHAR", "最近审计机构 = financial_audit_opinion.audit_agency"),
    f("days_since_audit_ann", "INTEGER", "距最近审计公告天数 = trade_date-latest_audit_ann_date"),
]

MAINBZ_FIELDS = [
    f("latest_mainbz_end_date", "DATE", "最近主营构成报告期 = asof(max(financial_main_business.end_date))"),
    f("mainbz_segment_count_latest", "INTEGER", "最近主营分部数量 = count(bz_item) by ts_code,end_date"),
    f("mainbz_revenue_total_latest", "DOUBLE", "最近主营分部收入合计 = sum(bz_sales)"),
    f("mainbz_profit_total_latest", "DOUBLE", "最近主营分部利润合计 = sum(bz_profit)"),
    f("mainbz_cost_total_latest", "DOUBLE", "最近主营分部成本合计 = sum(bz_cost)"),
    f("mainbz_top1_revenue_ratio_latest", "DOUBLE", "第一大业务收入占比 = max(bz_sales)/sum(bz_sales)"),
    f("mainbz_top3_revenue_ratio_latest", "DOUBLE", "前三大业务收入占比 = sum(top3 bz_sales)/sum(bz_sales)"),
    f("mainbz_top1_profit_ratio_latest", "DOUBLE", "第一大业务利润占比 = max(bz_profit)/sum(bz_profit)"),
    f("mainbz_gross_margin_latest", "DOUBLE", "主营分部毛利率 = (sum(bz_sales)-sum(bz_cost))/sum(bz_sales)"),
    f("days_since_mainbz_end_date", "INTEGER", "距主营构成报告期天数 = trade_date-latest_mainbz_end_date"),
]

REPURCHASE_FIELDS = [
    f("latest_repurchase_ann_date", "DATE", "最近回购公告日 = latest financial_repurchase.ann_date"),
    f("latest_repurchase_proc", "VARCHAR", "最近回购进度 = financial_repurchase.proc"),
    f("latest_repurchase_proc_code", "INTEGER", "最近回购进度编码 = enum(latest_repurchase_proc)"),
    f("latest_repurchase_volume", "DOUBLE", "最近回购数量 = financial_repurchase.volume"),
    f("latest_repurchase_amount", "DOUBLE", "最近回购金额 = financial_repurchase.amount"),
    f("latest_repurchase_high_limit", "DOUBLE", "最近回购价格上限 = financial_repurchase.high_limit"),
    f("latest_repurchase_low_limit", "DOUBLE", "最近回购价格下限 = financial_repurchase.low_limit"),
    f("repurchase_amount_365d", "DOUBLE", "近一年回购金额合计 = sum(amount) over 365d"),
    f("repurchase_volume_365d", "DOUBLE", "近一年回购数量合计 = sum(volume) over 365d"),
    f("repurchase_count_365d", "INTEGER", "近一年回购事件数 = count(repurchase events) over 365d"),
    f("days_since_repurchase_ann", "INTEGER", "距最近回购公告天数 = trade_date-latest_repurchase_ann_date"),
]

SHARE_FLOAT_FIELDS = [
    f("latest_share_float_ann_date", "DATE", "最近解禁公告日 = latest financial_share_float.ann_date"),
    f("latest_share_float_date", "DATE", "最近解禁日期 = max(float_date <= trade_date)"),
    f("latest_share_float_share", "DOUBLE", "最近解禁股数 = financial_share_float.float_share"),
    f("latest_share_float_ratio", "DOUBLE", "最近解禁比例 = financial_share_float.float_ratio"),
    f("share_float_event_count_365d", "INTEGER", "近一年解禁事件数 = count(float_date in 365d)"),
    f("share_float_share_365d", "DOUBLE", "近一年解禁股数合计 = sum(float_share) over 365d"),
    f("share_float_ratio_365d", "DOUBLE", "近一年解禁比例合计 = sum(float_ratio) over 365d"),
    f("days_since_share_float", "INTEGER", "距最近解禁天数 = trade_date-latest_share_float_date"),
    f("next_share_float_date_30d", "DATE", "未来30日最近已公告解禁日 = min(float_date) with ann_date<=trade_date<float_date<=trade_date+30"),
    f("next_share_float_share_30d", "DOUBLE", "未来30日已公告解禁股数 = sum(float_share) with ann_date<=trade_date<float_date<=trade_date+30"),
    f("next_share_float_ratio_30d", "DOUBLE", "未来30日已公告解禁比例 = sum(float_ratio) with ann_date<=trade_date<float_date<=trade_date+30"),
    f("next_share_float_share_90d", "DOUBLE", "未来90日已公告解禁股数 = sum(float_share) with ann_date<=trade_date<float_date<=trade_date+90"),
    f("next_share_float_ratio_90d", "DOUBLE", "未来90日已公告解禁比例 = sum(float_ratio) with ann_date<=trade_date<float_date<=trade_date+90"),
    f("total_share_asof", "DOUBLE", "当日总股本 = stock_daily_basic.total_share"),
    f("float_share_asof", "DOUBLE", "当日流通股本 = stock_daily_basic.float_share"),
    f("free_share_asof", "DOUBLE", "当日自由流通股本 = stock_daily_basic.free_share"),
    f("float_share_ratio_asof", "DOUBLE", "流通股本占总股本 = float_share_asof/total_share_asof"),
    f("free_share_ratio_asof", "DOUBLE", "自由流通股本占总股本 = free_share_asof/total_share_asof"),
    f("total_share_chg_20d", "DOUBLE", "总股本20日变化 = total_share_asof-lag(total_share_asof,20 trading days)"),
    f("float_share_chg_20d", "DOUBLE", "流通股本20日变化 = float_share_asof-lag(float_share_asof,20 trading days)"),
    f("free_share_chg_20d", "DOUBLE", "自由流通股本20日变化 = free_share_asof-lag(free_share_asof,20 trading days)"),
]

CORE_FIELDS = (
    PK
    + META_FIELDS
    + DIVIDEND_FIELDS
    + FORECAST_FIELDS
    + EXPRESS_FIELDS
    + AUDIT_FIELDS
    + MAINBZ_FIELDS
    + REPURCHASE_FIELDS
    + SHARE_FLOAT_FIELDS
    + UPDATED
)

FULL_EXTRA_FIELDS = [
    f("cash_dividend_3y_sum", "DOUBLE", "三年每股现金分红合计 = sum(cash_div) over 3y"),
    f("cash_dividend_5y_sum", "DOUBLE", "五年每股现金分红合计 = sum(cash_div) over 5y"),
    f("dividend_year_count_3y", "INTEGER", "三年有分红年份数 = count(distinct year(ex_date)) over 3y"),
    f("dividend_year_count_5y", "INTEGER", "五年有分红年份数 = count(distinct year(ex_date)) over 5y"),
    f("dividend_interval_days_latest", "INTEGER", "最近两次分红间隔 = latest_ex_date-previous_ex_date"),
    f("cash_dividend_ttm_to_close", "DOUBLE", "近一年现金分红/未复权收盘价 = cash_dividend_ttm/stock_daily.close"),
    f("cash_dividend_ttm_to_total_mv", "DOUBLE", "近一年现金分红估算/总市值 = cash_dividend_ttm*total_share/total_mv"),
    f("forecast_count_365d", "INTEGER", "近一年预告次数 = count(forecast ann_date in 365d)"),
    f("forecast_revision_count_same_end_date", "INTEGER", "同一报告期预告修正次数 = count(distinct ann_date) by ts_code,end_date"),
    f("forecast_latest_summary", "VARCHAR", "最近预告摘要 = financial_forecast.summary"),
    f("forecast_latest_change_reason", "VARCHAR", "最近预告原因 = financial_forecast.change_reason"),
    f("express_count_365d", "INTEGER", "近一年快报次数 = count(express ann_date in 365d)"),
    f("express_latest_performance_summary", "VARCHAR", "最近快报摘要 = financial_express.performance_summary"),
    f("audit_fees_change_1y", "DOUBLE", "审计费用一年变化 = audit_fees_latest-lag_1y_audit_fees"),
    f("audit_fees_change_rate_1y", "DOUBLE", "审计费用一年变化率 = audit_fees_change_1y/lag_1y_audit_fees"),
    f("audit_agency_changed_flag", "BOOLEAN", "审计机构是否变更 = audit_agency_latest != previous_audit_agency"),
    f("non_standard_audit_count_5y", "INTEGER", "五年非标审计次数 = sum(non_standard_audit_flag) over 5y"),
    f("mainbz_top1_item_latest", "VARCHAR", "第一大业务名称 = arg_max(bz_item,bz_sales)"),
    f("mainbz_top1_code_latest", "VARCHAR", "第一大业务代码 = arg_max(bz_code,bz_sales)"),
    f("mainbz_hhi_revenue_latest", "DOUBLE", "主营收入HHI = sum((bz_sales/sum_sales)^2)"),
    f("mainbz_hhi_profit_latest", "DOUBLE", "主营利润HHI = sum((bz_profit/sum_profit)^2)"),
    f("mainbz_segment_count_change_1y", "DOUBLE", "主营分部数一年变化 = current-lag_1y"),
    f("mainbz_top1_revenue_ratio_change_1y", "DOUBLE", "第一大业务收入占比一年变化 = current-lag_1y"),
    f("repurchase_amount_to_total_mv_365d", "DOUBLE", "近一年回购金额/总市值 = repurchase_amount_365d/total_mv"),
    f("repurchase_volume_to_total_share_365d", "DOUBLE", "近一年回购数量/总股本 = repurchase_volume_365d/total_share"),
    f("repurchase_amount_3y", "DOUBLE", "三年回购金额合计 = sum(amount) over 3y"),
    f("repurchase_count_3y", "INTEGER", "三年回购事件数 = count(events) over 3y"),
    f("next_share_float_share_180d", "DOUBLE", "未来180日已公告解禁股数 = sum(float_share) future 180d with ann_date<=trade_date"),
    f("next_share_float_ratio_180d", "DOUBLE", "未来180日已公告解禁比例 = sum(float_ratio) future 180d with ann_date<=trade_date"),
    f("share_float_share_3y", "DOUBLE", "过去三年解禁股数合计 = sum(float_share) over 3y"),
    f("share_float_ratio_3y", "DOUBLE", "过去三年解禁比例合计 = sum(float_ratio) over 3y"),
    f("total_share_chg_60d", "DOUBLE", "总股本60日变化 = total_share_asof-lag(total_share_asof,60)"),
    f("total_share_chg_120d", "DOUBLE", "总股本120日变化 = total_share_asof-lag(total_share_asof,120)"),
    f("total_share_chg_250d", "DOUBLE", "总股本250日变化 = total_share_asof-lag(total_share_asof,250)"),
    f("float_share_chg_60d", "DOUBLE", "流通股本60日变化 = float_share_asof-lag(float_share_asof,60)"),
    f("float_share_chg_120d", "DOUBLE", "流通股本120日变化 = float_share_asof-lag(float_share_asof,120)"),
    f("float_share_chg_250d", "DOUBLE", "流通股本250日变化 = float_share_asof-lag(float_share_asof,250)"),
    f("free_share_chg_60d", "DOUBLE", "自由流通股本60日变化 = free_share_asof-lag(free_share_asof,60)"),
    f("free_share_chg_120d", "DOUBLE", "自由流通股本120日变化 = free_share_asof-lag(free_share_asof,120)"),
    f("free_share_chg_250d", "DOUBLE", "自由流通股本250日变化 = free_share_asof-lag(free_share_asof,250)"),
]

TIMELINE_FIELDS = [
    f("ts_code", "VARCHAR", "股票代码", False),
    f("event_type", "VARCHAR", "事件类型", False),
    f("event_date", "DATE", "事件发生日"),
    f("effective_date", "DATE", "信息可得日"),
    f("end_date", "DATE", "报告期"),
    f("record_key", "VARCHAR", "原始记录键"),
    f("event_value_1", "DOUBLE", "事件数值1"),
    f("event_value_2", "DOUBLE", "事件数值2"),
    f("event_text", "VARCHAR", "事件文本"),
    f("source_table", "VARCHAR", "来源表"),
]


def upsert_table(schema: dict, table: dict) -> None:
    for index, existing in enumerate(schema["tables"]):
        if existing["name"] == table["name"]:
            schema["tables"][index] = table
            return
    schema["tables"].append(table)


def variable(field: dict, table: str, tier: str) -> dict:
    name = field["name"]
    dtype = field["dtype"]
    return {
        "name": name,
        "label_zh": field["description"].split("=")[0].strip(),
        "table": table,
        "module": MODULE,
        "category": MODULE,
        "tier": tier,
        "dtype": dtype,
        "unit": "none" if dtype in {"BOOLEAN", "VARCHAR", "DATE", "TIMESTAMP"} else "source_unit_or_ratio",
        "frequency": "daily" if table != TIMELINE_VIEW else "event",
        "grain": ["ts_code", "trade_date"] if table != TIMELINE_VIEW else ["ts_code", "event_type", "event_date", "record_key"],
        "source_type": "derived",
        "dependencies": [
            "derived_daily_spine",
            "financial_dividend",
            "financial_forecast",
            "financial_express",
            "financial_audit_opinion",
            "financial_main_business",
            "financial_repurchase",
            "financial_share_float",
            "stock_daily_basic",
        ],
        "formula_ref": field["description"],
        "formula_zh": field["description"],
        "price_basis": "raw" if "to_close" in name else "not_price",
        "point_in_time": True,
        "min_history": 1250 if name.endswith("_5y") else 750 if name.endswith("_3y") else 365 if "365d" in name else 1,
        "read_window": 1260,
        "write_window": 10,
        "missing_policy": "event_sparse" if dtype != "BOOLEAN" else "false_when_missing",
        "validation": {"constant_allowed": dtype in {"BOOLEAN", "VARCHAR", "INTEGER", "DATE"}},
    }


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    upsert_table(
        schema,
        {
            "name": CORE_TABLE,
            "phase": "P3",
            "description": "Phase 3 corporate action core physical table",
            "primary_key": ["ts_code", "trade_date"],
            "fields": CORE_FIELDS,
        },
    )
    upsert_table(
        schema,
        {
            "name": FULL_VIEW,
            "phase": "P3",
            "description": "Phase 3 corporate action full view",
            "table_type": "view",
            "primary_key": ["ts_code", "trade_date"],
            "fields": CORE_FIELDS[:-1] + FULL_EXTRA_FIELDS + UPDATED,
        },
    )
    upsert_table(
        schema,
        {
            "name": TIMELINE_VIEW,
            "phase": "P3",
            "description": "Corporate action unified event timeline view",
            "table_type": "view",
            "primary_key": ["ts_code", "event_type", "event_date", "record_key"],
            "fields": TIMELINE_FIELDS,
        },
    )
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = json.loads(DERIVED_VARIABLES_PATH.read_text(encoding="utf-8"))
    registry["variables"] = [
        item for item in registry.get("variables", []) if item.get("module") != MODULE
    ]
    for field in CORE_FIELDS:
        if field["name"] in {"ts_code", "trade_date", "updated_at"}:
            continue
        registry["variables"].append(variable(field, CORE_TABLE, "core"))
    core_names = {field["name"] for field in CORE_FIELDS}
    for field in FULL_EXTRA_FIELDS:
        if field["name"] not in core_names:
            registry["variables"].append(variable(field, FULL_VIEW, "extended"))
    for field in TIMELINE_FIELDS:
        if field["name"] != "ts_code":
            registry["variables"].append(variable(field, TIMELINE_VIEW, "extended"))
    DERIVED_VARIABLES_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({CORE_TABLE: len(CORE_FIELDS), FULL_VIEW: len(CORE_FIELDS) - 1 + len(FULL_EXTRA_FIELDS) + 1, TIMELINE_VIEW: len(TIMELINE_FIELDS)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
