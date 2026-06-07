from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"

MODULE = "ownership_governance"
CORE_TABLE = "derived_ownership_governance"
FULL_VIEW = "derived_ownership_governance_full_v"
TIMELINE_VIEW = "ownership_governance_event_timeline_v"
CONCENTRATION_VIEW = "ownership_holder_concentration_v"


def f(name: str, dtype: str, desc: str, nullable: bool = True) -> dict:
    payload = {"name": name, "dtype": dtype, "nullable": nullable, "description": desc, "source_api": "local_derived"}
    if name == "updated_at":
        payload["nullable"] = False
        payload["default"] = "CURRENT_TIMESTAMP"
    return payload


PK = [f("ts_code", "VARCHAR", "股票代码", False), f("trade_date", "DATE", "交易日期", False)]
UPDATED = [f("updated_at", "TIMESTAMP", "本地更新时间 = CURRENT_TIMESTAMP", False)]

META_FIELDS = [
    f("ownership_available_flag", "BOOLEAN", "持有人治理数据可用标记 = 任一核心来源字段非空"),
    f("latest_ownership_event_date", "DATE", "最近持有人治理事件日期 = max(event_date <= trade_date)"),
    f("days_since_latest_ownership_event", "INTEGER", "距最近持有人治理事件天数 = trade_date-latest_ownership_event_date"),
    f("ownership_event_count_365d", "INTEGER", "近一年持有人治理事件数 = count(event_date in 365d)"),
]

PLEDGE_FIELDS = [
    f("latest_pledge_end_date", "DATE", "最新质押统计日期 = asof(max(financial_pledge_stat.end_date <= trade_date))"),
    f("pledge_count_asof", "INTEGER", "最新质押笔数 = financial_pledge_stat.pledge_count"),
    f("pledge_unreleased_share_asof", "DOUBLE", "最新未解押质押股数 = financial_pledge_stat.unrest_pledge"),
    f("pledge_released_share_asof", "DOUBLE", "最新已解押质押股数 = financial_pledge_stat.rest_pledge"),
    f("pledge_total_share_base_asof", "DOUBLE", "质押统计总股本 = financial_pledge_stat.total_share"),
    f("pledge_ratio_asof", "DOUBLE", "最新质押比例 = financial_pledge_stat.pledge_ratio; source percent/rate口径"),
    f("pledge_ratio_chg_1report", "DOUBLE", "质押比例较上一统计期变化 = current-previous pledge report"),
    f("pledge_ratio_chg_4report", "DOUBLE", "质押比例较四个统计期前变化 = current-lag4 pledge report"),
    f("pledge_count_chg_1report", "DOUBLE", "质押笔数较上一统计期变化 = current-previous pledge report"),
    f("pledge_share_to_total_share_asof", "DOUBLE", "未解押质押股数/总股本 = pledge_unreleased_share_asof/stock_daily_basic.total_share"),
    f("pledge_stat_staleness_days", "INTEGER", "质押统计滞后天数 = trade_date-latest_pledge_end_date"),
    f("pledge_ratio_ge_10_flag", "BOOLEAN", "质押比例不低于10事实标记 = pledge_ratio_asof >= 10"),
    f("pledge_ratio_ge_30_flag", "BOOLEAN", "质押比例不低于30事实标记 = pledge_ratio_asof >= 30"),
    f("pledge_ratio_ge_50_flag", "BOOLEAN", "质押比例不低于50事实标记 = pledge_ratio_asof >= 50"),
    f("pledge_data_available_flag", "BOOLEAN", "质押统计可用标记 = latest_pledge_end_date is not null"),
]

HOLDER_FIELDS = [
    f("latest_holder_ann_date", "DATE", "最新股东户数公告日 = asof(max(financial_holder_number.ann_date <= trade_date))"),
    f("latest_holder_end_date", "DATE", "最新股东户数报告期 = financial_holder_number.end_date"),
    f("holder_num_asof", "BIGINT", "最新股东户数 = financial_holder_number.holder_num"),
    f("holder_num_chg_1report", "DOUBLE", "股东户数较上一期变化 = current-previous holder report"),
    f("holder_num_chg_rate_1report", "DOUBLE", "股东户数较上一期变化率 = holder_num_chg_1report/previous_holder_num"),
    f("holder_num_chg_4report", "DOUBLE", "股东户数较四期前变化 = current-lag4 holder report"),
    f("holder_num_chg_rate_4report", "DOUBLE", "股东户数较四期前变化率 = holder_num_chg_4report/lag4_holder_num"),
    f("shares_per_holder_asof", "DOUBLE", "户均持股数 = stock_daily_basic.total_share/holder_num_asof"),
    f("free_shares_per_holder_asof", "DOUBLE", "户均自由流通股数 = stock_daily_basic.free_share/holder_num_asof"),
    f("holder_num_to_total_share", "DOUBLE", "股东户数/总股本 = holder_num_asof/stock_daily_basic.total_share"),
    f("holder_num_to_free_share", "DOUBLE", "股东户数/自由流通股本 = holder_num_asof/stock_daily_basic.free_share"),
    f("holder_num_staleness_days", "INTEGER", "股东户数数据滞后天数 = trade_date-latest_holder_ann_date"),
    f("holder_data_available_flag", "BOOLEAN", "股东户数可用标记 = latest_holder_ann_date is not null"),
]

TOP10_FIELDS = [
    f("latest_top10_holder_ann_date", "DATE", "最新十大股东公告日 = asof(max(ann_date <= trade_date))"),
    f("latest_top10_holder_end_date", "DATE", "最新十大股东报告期 = financial_top10_holders.end_date"),
    f("top10_holder_count_latest", "INTEGER", "十大股东明细数 = count(holder_name)"),
    f("top1_holder_ratio_latest", "DOUBLE", "第一大股东持股比例 = max(hold_ratio)"),
    f("top3_holder_ratio_latest", "DOUBLE", "前三大股东持股比例 = sum(top3 hold_ratio)"),
    f("top5_holder_ratio_latest", "DOUBLE", "前五大股东持股比例 = sum(top5 hold_ratio)"),
    f("top10_holder_ratio_latest", "DOUBLE", "十大股东持股比例 = sum(hold_ratio)"),
    f("top10_holder_hhi_latest", "DOUBLE", "十大股东持股HHI = sum((hold_ratio/100)^2)"),
    f("top10_holder_ratio_chg_1report", "DOUBLE", "十大股东比例较上一期变化 = current-previous"),
    f("top1_holder_ratio_chg_1report", "DOUBLE", "第一大股东比例较上一期变化 = current-previous"),
    f("top10_holder_staleness_days", "INTEGER", "十大股东数据滞后天数 = trade_date-latest_top10_holder_ann_date"),
    f("latest_top10_float_ann_date", "DATE", "最新十大流通股东公告日 = asof(max(ann_date <= trade_date))"),
    f("latest_top10_float_end_date", "DATE", "最新十大流通股东报告期 = financial_top10_float_holders.end_date"),
    f("top10_float_holder_count_latest", "INTEGER", "十大流通股东明细数 = count(holder_name)"),
    f("top1_float_holder_ratio_latest", "DOUBLE", "第一大流通股东持股比例 = max(hold_float_ratio)"),
    f("top3_float_holder_ratio_latest", "DOUBLE", "前三大流通股东持股比例 = sum(top3 hold_float_ratio)"),
    f("top5_float_holder_ratio_latest", "DOUBLE", "前五大流通股东持股比例 = sum(top5 hold_float_ratio)"),
    f("top10_float_holder_ratio_latest", "DOUBLE", "十大流通股东持股比例 = sum(hold_float_ratio)"),
    f("top10_float_holder_hhi_latest", "DOUBLE", "十大流通股东HHI = sum((hold_float_ratio/100)^2)"),
    f("top10_float_holder_ratio_chg_1report", "DOUBLE", "十大流通股东比例较上一期变化 = current-previous"),
    f("top1_float_holder_ratio_chg_1report", "DOUBLE", "第一大流通股东比例较上一期变化 = current-previous"),
    f("top10_float_staleness_days", "INTEGER", "十大流通股东数据滞后天数 = trade_date-latest_top10_float_ann_date"),
]

COMBO_FIELDS = [
    f("ownership_concentration_ratio_latest", "DOUBLE", "综合股权集中度 = coalesce(top10_holder_ratio_latest, top10_float_holder_ratio_latest)"),
    f("ownership_concentration_chg_1report", "DOUBLE", "综合集中度较上一期变化 = current-previous"),
    f("float_concentration_premium_latest", "DOUBLE", "流通集中度相对总股东集中度差 = top10_float_holder_ratio_latest-top10_holder_ratio_latest"),
    f("pledge_to_concentration_ratio", "DOUBLE", "质押比例/集中度 = pledge_ratio_asof/top10_holder_ratio_latest"),
    f("ownership_data_completeness_count", "INTEGER", "持有人治理核心字段可用数 = non_null核心字段计数"),
    f("ownership_data_completeness_ratio", "DOUBLE", "持有人治理核心字段可用率 = count/核心字段数"),
]

CORE_FIELDS = PK + META_FIELDS + PLEDGE_FIELDS + HOLDER_FIELDS + TOP10_FIELDS + COMBO_FIELDS + UPDATED

FULL_EXTRA_FIELDS = [
    *[f(f"pledge_ratio_chg_{n}d", "DOUBLE", f"质押比例{n}日变化 = pledge_ratio_asof-lag(pledge_ratio_asof,{n})") for n in [20, 60, 120, 250]],
    *[f(f"pledge_count_chg_{n}d", "DOUBLE", f"质押笔数{n}日变化 = pledge_count_asof-lag(pledge_count_asof,{n})") for n in [20, 60, 120, 250]],
    *[f(f"holder_num_chg_{n}d", "DOUBLE", f"股东户数{n}日变化 = holder_num_asof-lag(holder_num_asof,{n})") for n in [20, 60, 120, 250]],
    *[f(f"holder_num_chg_rate_{n}d", "DOUBLE", f"股东户数{n}日变化率 = chg/lag") for n in [20, 60, 120, 250]],
    f("top1_holder_name_latest", "VARCHAR", "第一大股东名称 = arg_max(holder_name,hold_ratio)"),
    f("top1_holder_type_latest", "VARCHAR", "第一大股东类型 = arg_max(holder_type,hold_ratio)"),
    f("top10_institution_holder_ratio_latest", "DOUBLE", "十大股东中机构持股比例 = sum(hold_ratio where holder_type normalized institution)"),
    f("top10_individual_holder_ratio_latest", "DOUBLE", "十大股东中个人持股比例 = sum(hold_ratio where holder_type normalized individual)"),
    f("top10_holder_change_sum_latest", "DOUBLE", "十大股东持股变动合计 = sum(hold_change)"),
    f("top10_holder_positive_change_count", "INTEGER", "十大股东增持人数 = count(hold_change>0)"),
    f("top10_holder_negative_change_count", "INTEGER", "十大股东减持人数 = count(hold_change<0)"),
    f("top10_holder_name_churn_1report", "INTEGER", "十大股东名单较上一报告期是否变动 = same set 0 else 1"),
    f("top1_float_holder_name_latest", "VARCHAR", "第一大流通股东名称 = arg_max(holder_name,hold_float_ratio)"),
    f("top1_float_holder_type_latest", "VARCHAR", "第一大流通股东类型 = arg_max(holder_type,hold_float_ratio)"),
    f("top10_float_institution_ratio_latest", "DOUBLE", "十大流通股东机构持股比例 = sum(hold_float_ratio where institution)"),
    f("top10_float_individual_ratio_latest", "DOUBLE", "十大流通股东个人持股比例 = sum(hold_float_ratio where individual)"),
    f("top10_float_holder_change_sum_latest", "DOUBLE", "十大流通股东持股变动合计 = sum(hold_change)"),
    f("top10_float_holder_positive_change_count", "INTEGER", "十大流通股东增持人数 = count(hold_change>0)"),
    f("top10_float_holder_negative_change_count", "INTEGER", "十大流通股东减持人数 = count(hold_change<0)"),
    f("top10_float_holder_name_churn_1report", "INTEGER", "十大流通股东名单较上一报告期是否变动 = same set 0 else 1"),
    f("pledge_detail_active_count_asof", "INTEGER", "asof有效质押明细数 = active pledge detail count"),
    f("pledge_detail_active_amount_asof", "DOUBLE", "asof有效质押明细股数 = sum(active pledge_amount)"),
    f("pledge_release_count_365d", "INTEGER", "近一年解押事件数 = count(release events in 365d)"),
]

TIMELINE_FIELDS = [
    f("ts_code", "VARCHAR", "股票代码", False),
    f("event_type", "VARCHAR", "事件类型", False),
    f("event_date", "DATE", "事件日期"),
    f("effective_date", "DATE", "信息可得日"),
    f("end_date", "DATE", "报告期或截止日"),
    f("record_key", "VARCHAR", "原始记录键"),
    f("holder_name", "VARCHAR", "持有人名称"),
    f("holder_type", "VARCHAR", "持有人类型"),
    f("event_value_1", "DOUBLE", "事件数值1"),
    f("event_value_2", "DOUBLE", "事件数值2"),
    f("event_text", "VARCHAR", "事件文本"),
    f("source_table", "VARCHAR", "来源表"),
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
        "unit": "none" if dtype in {"BOOLEAN", "VARCHAR", "DATE", "TIMESTAMP"} else "source_unit_or_ratio",
        "frequency": "daily" if table != TIMELINE_VIEW else "event",
        "grain": ["ts_code", "trade_date"] if table != TIMELINE_VIEW else ["ts_code", "event_type", "event_date", "record_key"],
        "source_type": "derived",
        "dependencies": ["derived_daily_spine", "financial_pledge_stat", "financial_pledge_detail", "financial_holder_number", "financial_top10_holders", "financial_top10_float_holders", "stock_daily_basic"],
        "formula_ref": field["description"],
        "formula_zh": field["description"],
        "price_basis": "not_price",
        "point_in_time": True,
        "min_history": 250 if field["name"].endswith("_250d") else 1,
        "read_window": 1260,
        "write_window": 10,
        "missing_policy": "event_sparse" if dtype != "BOOLEAN" else "false_when_missing",
        "validation": {"constant_allowed": dtype in {"BOOLEAN", "VARCHAR", "INTEGER", "DATE"}},
    }


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    upsert_table(schema, {"name": CORE_TABLE, "phase": "P3", "description": "Phase 3 ownership and governance core physical table", "primary_key": ["ts_code", "trade_date"], "fields": CORE_FIELDS})
    upsert_table(schema, {"name": FULL_VIEW, "phase": "P3", "description": "Phase 3 ownership and governance full view", "table_type": "view", "primary_key": ["ts_code", "trade_date"], "fields": CORE_FIELDS[:-1] + FULL_EXTRA_FIELDS + UPDATED})
    upsert_table(schema, {"name": TIMELINE_VIEW, "phase": "P3", "description": "Ownership governance unified event timeline view", "table_type": "view", "primary_key": ["ts_code", "event_type", "event_date", "record_key"], "fields": TIMELINE_FIELDS})
    upsert_table(schema, {"name": CONCENTRATION_VIEW, "phase": "P3", "description": "Low-frequency holder concentration view", "table_type": "view", "primary_key": ["ts_code", "end_date", "holder_scope"], "fields": [
        f("ts_code", "VARCHAR", "股票代码", False), f("end_date", "DATE", "报告期", False), f("ann_date", "DATE", "公告日"), f("holder_scope", "VARCHAR", "股东范围：top10/top10_float", False),
        f("holder_count", "INTEGER", "明细数量"), f("top1_ratio", "DOUBLE", "第一大持有人比例"), f("top3_ratio", "DOUBLE", "前三大比例"), f("top5_ratio", "DOUBLE", "前五大比例"), f("top10_ratio", "DOUBLE", "前十大比例"), f("hhi", "DOUBLE", "持有人HHI")
    ]})
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = json.loads(DERIVED_VARIABLES_PATH.read_text(encoding="utf-8"))
    registry["variables"] = [item for item in registry.get("variables", []) if item.get("module") != MODULE]
    for field in CORE_FIELDS:
        if field["name"] not in {"ts_code", "trade_date", "updated_at"}:
            registry["variables"].append(variable(field, CORE_TABLE, "core"))
    for field in FULL_EXTRA_FIELDS:
        registry["variables"].append(variable(field, FULL_VIEW, "extended"))
    for field in TIMELINE_FIELDS:
        if field["name"] != "ts_code":
            registry["variables"].append(variable(field, TIMELINE_VIEW, "extended"))
    DERIVED_VARIABLES_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({CORE_TABLE: len(CORE_FIELDS), FULL_VIEW: len(CORE_FIELDS) - 1 + len(FULL_EXTRA_FIELDS) + 1, TIMELINE_VIEW: len(TIMELINE_FIELDS)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
