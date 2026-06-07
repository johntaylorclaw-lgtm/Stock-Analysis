from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"

FULL_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
CORE_PERIODS = [5, 20, 60, 120]
RANK_PERIODS = [20, 60]
INDEX_PREFIXES = ["hs300", "zz500", "zz1000", "sse50", "star50", "chinext"]


def f(name: str, dtype: str, desc: str, nullable: bool = True) -> dict:
    payload = {"name": name, "dtype": dtype, "nullable": nullable, "description": desc, "source_api": "local_derived"}
    if name == "updated_at":
        payload["nullable"] = False
        payload["default"] = "CURRENT_TIMESTAMP"
    return payload


PK_STOCK = [f("ts_code", "VARCHAR", "股票代码", False), f("trade_date", "DATE", "交易日期", False)]
UPDATED = [f("updated_at", "TIMESTAMP", "本地更新时间", False)]


def upsert_table(schema: dict, table: dict) -> None:
    for idx, existing in enumerate(schema["tables"]):
        if existing["name"] == table["name"]:
            schema["tables"][idx] = table
            return
    schema["tables"].append(table)


ENHANCED_MEMBER_FIELDS = [
    f("ts_code", "VARCHAR", "股票代码", False),
    f("stock_name", "VARCHAR", "股票名称"),
    f("sw_l1_code", "VARCHAR", "申万一级行业代码"),
    f("sw_l1_name", "VARCHAR", "申万一级行业名称"),
    f("sw_l2_code", "VARCHAR", "申万二级行业代码", False),
    f("sw_l2_name", "VARCHAR", "申万二级行业名称"),
    f("sw_l3_code", "VARCHAR", "申万三级行业代码"),
    f("sw_l3_name", "VARCHAR", "申万三级行业名称"),
    f("in_date", "DATE", "行业成分纳入日期", False),
    f("out_date", "DATE", "行业成分剔除日期"),
    f("is_new", "VARCHAR", "是否最新成分"),
] + UPDATED


SECTOR_CACHE_FIELDS = [
    f("industry_level", "VARCHAR", "行业层级：L1/L2", False),
    f("industry_code", "VARCHAR", "行业代码", False),
    f("trade_date", "DATE", "交易日期", False),
    f("industry_name", "VARCHAR", "行业名称"),
    f("industry_stock_count", "INTEGER", "行业股票数量"),
    f("industry_total_mv", "DOUBLE", "行业总市值 = sum(total_mv)"),
]
for n in FULL_PERIODS:
    SECTOR_CACHE_FIELDS.extend(
        [
            f(f"industry_ret_{n}", "DOUBLE", f"{n}日行业等权收益 = avg(ret_{n}_hfq)"),
            f(f"industry_ret_rank_all_{n}", "INTEGER", f"{n}日行业收益全行业排名 = rank(industry_ret_{n})"),
            f(f"industry_ret_pct_all_{n}", "DOUBLE", f"{n}日行业收益全行业分位 = percent_rank(industry_ret_{n})"),
            f(f"industry_amount_ma_{n}", "DOUBLE", f"{n}日行业成交额均值 = avg(sum(amount),{n})"),
            f(f"industry_amount_pct_all_{n}", "DOUBLE", f"{n}日行业成交额全行业分位 = percent_rank(industry_amount_ma_{n})"),
            f(f"industry_turnover_ma_{n}", "DOUBLE", f"{n}日行业换手均值 = avg(turnover_rate_ma_20,{n})"),
            f(f"industry_up_ratio_{n}", "DOUBLE", f"{n}日行业上涨比例均值 = avg(up_ratio,{n})"),
            f(f"industry_limit_up_count_{n}", "INTEGER", f"{n}日行业涨停数量累计 = sum(limit_up_count,{n})"),
            f(f"industry_main_flow_sum_{n}", "DOUBLE", f"{n}日行业主力净流入累计 = sum(main_net_amount,{n})"),
            f(f"industry_main_flow_to_mv_{n}", "DOUBLE", f"{n}日行业主力净流入占行业市值 = industry_main_flow_sum_{n} / industry_total_mv"),
        ]
    )
SECTOR_CACHE_FIELDS += UPDATED


CONCEPT_CACHE_FIELDS = [
    f("concept_id", "VARCHAR", "概念ID", False),
    f("trade_date", "DATE", "交易日期", False),
    f("concept_name", "VARCHAR", "概念名称"),
    f("concept_stock_count", "INTEGER", "概念成分股票数量"),
    f("concept_member_share", "DOUBLE", "概念成分数占全市场比例 = concept_stock_count / market_stock_count"),
    f("concept_broad_flag", "BOOLEAN", "是否宽泛概念 = concept_member_share > 0.10"),
    f("concept_narrow_flag", "BOOLEAN", "是否窄口径概念 = concept_stock_count >= 5 AND concept_member_share <= 0.10"),
]
for n in FULL_PERIODS:
    CONCEPT_CACHE_FIELDS.extend(
        [
            f(f"concept_ret_{n}", "DOUBLE", f"{n}日概念等权收益 = avg(ret_{n}_hfq)"),
            f(f"concept_ret_rank_all_{n}", "INTEGER", f"{n}日概念收益全概念排名 = rank(concept_ret_{n})"),
            f(f"concept_ret_pct_all_{n}", "DOUBLE", f"{n}日概念收益全概念分位 = percent_rank(concept_ret_{n})"),
            f(f"concept_amount_ma_{n}", "DOUBLE", f"{n}日概念成交额均值 = avg(sum(amount),{n})"),
            f(f"concept_amount_pct_all_{n}", "DOUBLE", f"{n}日概念成交额全概念分位 = percent_rank(concept_amount_ma_{n})"),
            f(f"concept_up_ratio_{n}", "DOUBLE", f"{n}日概念上涨比例均值 = avg(up_ratio,{n})"),
            f(f"concept_limit_up_count_{n}", "INTEGER", f"{n}日概念涨停数量累计 = sum(limit_up_count,{n})"),
            f(f"concept_main_flow_sum_{n}", "DOUBLE", f"{n}日概念主力净流入累计 = sum(main_net_amount,{n})"),
            f(f"concept_hot_flag_{n}", "BOOLEAN", f"{n}日概念是否高热 = concept_ret_pct_all_{n} >= 0.8 OR concept_amount_pct_all_{n} >= 0.8"),
        ]
    )
CONCEPT_CACHE_FIELDS += UPDATED


CONCEPT_STOCK_CONTEXT_FIELDS = PK_STOCK + [
    f("concept_count", "INTEGER", "所属概念数量 = count_distinct(concept_member.concept_id)"),
    f("concept_ids_all", "VARCHAR", "全部所属概念ID列表 = string_agg(concept_member.concept_id,';')"),
    f("concept_names_all", "VARCHAR", "全部所属概念名称列表 = string_agg(concept_member.concept_name,';')"),
    f("concept_broad_count", "INTEGER", "宽泛概念数量 = sum(derived_concept_daily_cache.concept_broad_flag)"),
    f("concept_narrow_count", "INTEGER", "窄口径概念数量 = sum(derived_concept_daily_cache.concept_narrow_flag)"),
]
for n in FULL_PERIODS:
    CONCEPT_STOCK_CONTEXT_FIELDS.extend(
        [
            f(f"concept_ids_top_{n}", "VARCHAR", f"{n}日领涨概念ID列表 = array_to_string(arg_max(concept_member.concept_id, derived_concept_daily_cache.concept_ret_{n}, 5), ';')"),
            f(f"concept_names_top_{n}", "VARCHAR", f"{n}日领涨概念名称列表 = array_to_string(arg_max(concept_name, concept_ret_{n}, 5), ';')"),
            f(f"concept_lagging_ids_{n}", "VARCHAR", f"{n}日领跌概念ID列表 = array_to_string(arg_min(concept_member.concept_id, concept_ret_{n}, 5), ';')"),
            f(f"concept_lagging_names_{n}", "VARCHAR", f"{n}日领跌概念名称列表 = array_to_string(arg_min(concept_name, concept_ret_{n}, 5), ';')"),
            f(f"concept_active_ids_{n}", "VARCHAR", f"{n}日活跃概念ID列表 = array_to_string(arg_max(concept_member.concept_id, concept_amount_pct_all_{n}, 5), ';')"),
            f(f"concept_active_names_{n}", "VARCHAR", f"{n}日活跃概念名称列表 = array_to_string(arg_max(concept_name, concept_amount_pct_all_{n}, 5), ';')"),
            f(f"concept_narrow_leading_ids_{n}", "VARCHAR", f"{n}日窄口径领涨概念ID列表 = array_to_string(arg_max(concept_id, CASE WHEN concept_narrow_flag THEN concept_ret_{n} END, 5), ';')"),
            f(f"concept_narrow_leading_names_{n}", "VARCHAR", f"{n}日窄口径领涨概念名称列表 = array_to_string(arg_max(concept_name, CASE WHEN concept_narrow_flag THEN concept_ret_{n} END, 5), ';')"),
            f(f"concept_best_id_{n}", "VARCHAR", f"{n}日领涨概念ID = arg_max(concept_id, concept_ret_{n})"),
            f(f"concept_best_name_{n}", "VARCHAR", f"{n}日领涨概念名称 = arg_max(concept_name, concept_ret_{n})"),
            f(f"concept_best_ret_{n}", "DOUBLE", f"{n}日领涨概念收益 = max(concept_ret_{n})"),
            f(f"concept_worst_id_{n}", "VARCHAR", f"{n}日领跌概念ID = arg_min(concept_id, concept_ret_{n})"),
            f(f"concept_worst_name_{n}", "VARCHAR", f"{n}日领跌概念名称 = arg_min(concept_name, concept_ret_{n})"),
            f(f"concept_worst_ret_{n}", "DOUBLE", f"{n}日领跌概念收益 = min(concept_ret_{n})"),
            f(f"concept_avg_ret_{n}", "DOUBLE", f"所属概念{n}日平均收益 = avg(concept_ret_{n})"),
            f(f"concept_median_ret_{n}", "DOUBLE", f"所属概念{n}日中位收益 = median(concept_ret_{n})"),
            f(f"concept_max_ret_{n}", "DOUBLE", f"所属概念{n}日最大收益 = max(concept_ret_{n})"),
            f(f"concept_min_ret_{n}", "DOUBLE", f"所属概念{n}日最小收益 = min(concept_ret_{n})"),
            f(f"concept_ret_spread_{n}", "DOUBLE", f"所属概念{n}日收益跨度 = max(concept_ret_{n}) - min(concept_ret_{n})"),
            f(f"concept_positive_count_{n}", "INTEGER", f"{n}日正收益概念数量 = count(concept_ret_{n} > 0)"),
            f(f"concept_negative_count_{n}", "INTEGER", f"{n}日负收益概念数量 = count(concept_ret_{n} < 0)"),
            f(f"concept_avg_amount_{n}", "DOUBLE", f"所属概念{n}日平均成交额 = avg(concept_amount_ma_{n})"),
            f(f"concept_main_flow_sum_{n}", "DOUBLE", f"所属概念{n}日主力净流入均值 = avg(concept_main_flow_sum_{n})"),
            f(f"concept_hot_count_{n}", "INTEGER", f"{n}日高热概念数量 = count(concept_hot_flag_{n})"),
        ]
    )
CONCEPT_STOCK_CONTEXT_FIELDS += UPDATED


SECTOR_CORE_FIELDS = PK_STOCK + [
    f("sw_l1_code", "VARCHAR", "申万一级行业代码"),
    f("sw_l1_name", "VARCHAR", "申万一级行业名称"),
    f("sw_l2_code", "VARCHAR", "申万二级行业代码"),
    f("sw_l2_name", "VARCHAR", "申万二级行业名称"),
    f("has_sw_industry", "BOOLEAN", "是否有申万行业归属"),
    f("industry_member_days", "INTEGER", "行业归属持续天数 = trade_date - in_date"),
    f("industry_member_is_current", "BOOLEAN", "是否当前行业成员"),
]
for n in CORE_PERIODS:
    for level in ["sw_l1", "sw_l2"]:
        SECTOR_CORE_FIELDS.extend(
            [
                f(f"{level}_ret_{n}", "DOUBLE", f"{n}日{level}行业等权收益"),
                f(f"stock_excess_{level}_{n}", "DOUBLE", f"个股相对{level}行业{n}日超额收益 = ret_{n}_hfq - {level}_ret_{n}"),
                f(f"{level}_ret_rank_all_{n}", "INTEGER", f"{n}日{level}行业收益排名"),
                f(f"{level}_ret_pct_all_{n}", "DOUBLE", f"{n}日{level}行业收益分位"),
                f(f"{level}_amount_ma_{n}", "DOUBLE", f"{n}日{level}行业成交额均值"),
                f(f"{level}_main_flow_sum_{n}", "DOUBLE", f"{n}日{level}行业主力净流入累计"),
            ]
        )
for n in RANK_PERIODS:
    SECTOR_CORE_FIELDS.extend(
        [
            f(f"stock_ret_rank_industry_{n}", "INTEGER", f"个股{n}日收益行业内排名"),
            f(f"stock_ret_pct_industry_{n}", "DOUBLE", f"个股{n}日收益行业内分位"),
            f(f"stock_amount_rank_industry_{n}", "INTEGER", f"个股{n}日成交额行业内排名"),
            f(f"stock_turnover_rank_industry_{n}", "INTEGER", f"个股{n}日换手行业内排名"),
            f(f"stock_main_flow_rank_industry_{n}", "INTEGER", f"个股{n}日主力净流入行业内排名"),
        ]
    )
SECTOR_CORE_FIELDS.extend(
    [
        f("stock_mv_rank_industry", "INTEGER", "个股总市值行业内排名"),
        f("stock_mv_pct_industry", "DOUBLE", "个股总市值行业内分位"),
        f("stock_pe_ttm_pct_industry", "DOUBLE", "个股PE_TTM行业内分位"),
        f("stock_pb_pct_industry", "DOUBLE", "个股PB行业内分位"),
        f("stock_ps_ttm_pct_industry", "DOUBLE", "个股PS_TTM行业内分位"),
        f("concept_count", "INTEGER", "概念数量"),
        f("concept_ids_all", "VARCHAR", "全部概念ID列表"),
        f("concept_names_all", "VARCHAR", "全部概念名称列表"),
        f("concept_broad_count", "INTEGER", "宽泛概念数量"),
        f("concept_narrow_count", "INTEGER", "窄口径概念数量"),
    ]
)
for name, dtype, desc in [
    ("concept_ids_top_20", "VARCHAR", "20日领涨概念ID列表"),
    ("concept_names_top_20", "VARCHAR", "20日领涨概念名称列表"),
    ("concept_lagging_ids_20", "VARCHAR", "20日领跌概念ID列表"),
    ("concept_lagging_names_20", "VARCHAR", "20日领跌概念名称列表"),
    ("concept_active_ids_20", "VARCHAR", "20日活跃概念ID列表"),
    ("concept_active_names_20", "VARCHAR", "20日活跃概念名称列表"),
    ("concept_narrow_leading_ids_20", "VARCHAR", "20日窄口径领涨概念ID列表"),
    ("concept_narrow_leading_names_20", "VARCHAR", "20日窄口径领涨概念名称列表"),
    ("concept_best_id_20", "VARCHAR", "20日领涨概念ID"),
    ("concept_best_name_20", "VARCHAR", "20日领涨概念名称"),
    ("concept_best_ret_20", "DOUBLE", "20日领涨概念收益"),
    ("concept_worst_id_20", "VARCHAR", "20日领跌概念ID"),
    ("concept_worst_name_20", "VARCHAR", "20日领跌概念名称"),
    ("concept_worst_ret_20", "DOUBLE", "20日领跌概念收益"),
    ("concept_avg_ret_20", "DOUBLE", "所属概念20日平均收益"),
    ("concept_median_ret_20", "DOUBLE", "所属概念20日中位收益"),
    ("concept_max_ret_20", "DOUBLE", "所属概念20日最大收益"),
    ("concept_min_ret_20", "DOUBLE", "所属概念20日最小收益"),
    ("concept_ret_spread_20", "DOUBLE", "所属概念20日收益跨度"),
    ("concept_positive_count_20", "INTEGER", "20日正收益概念数量"),
    ("concept_negative_count_20", "INTEGER", "20日负收益概念数量"),
    ("concept_avg_amount_20", "DOUBLE", "所属概念20日平均成交额"),
    ("concept_main_flow_sum_20", "DOUBLE", "所属概念20日主力净流入均值"),
    ("concept_hot_count_20", "INTEGER", "20日高热概念数量"),
]:
    SECTOR_CORE_FIELDS.append(f(name, dtype, desc))
SECTOR_CORE_FIELDS += [f("has_concept", "BOOLEAN", "是否有概念归属"), f("sector_context_missing_reason", "VARCHAR", "行业概念缺失原因")] + UPDATED


INDEX_DAILY_CACHE_FIELDS = [
    f("index_code", "VARCHAR", "指数代码", False),
    f("trade_date", "DATE", "交易日期", False),
    f("index_name", "VARCHAR", "指数名称"),
    f("index_close", "DOUBLE", "指数收盘价"),
]
for n in FULL_PERIODS:
    INDEX_DAILY_CACHE_FIELDS.append(f(f"index_ret_{n}", "DOUBLE", f"{n}日指数收益 = close / lag(close,{n}) - 1"))
for n in [5, 20, 60, 120, 250]:
    INDEX_DAILY_CACHE_FIELDS.extend(
        [
            f(f"index_vol_{n}", "DOUBLE", f"{n}日指数年化波动 = stddev(log_ret_1,{n}) * sqrt(242)"),
            f(f"index_amount_ma_{n}", "DOUBLE", f"{n}日指数成交额均值"),
            f(f"index_amount_chg_{n}", "DOUBLE", f"{n}日指数成交额变化率"),
        ]
    )
INDEX_DAILY_CACHE_FIELDS += UPDATED


INDEX_MEMBERSHIP_FIELDS = PK_STOCK.copy()
for p in INDEX_PREFIXES:
    INDEX_MEMBERSHIP_FIELDS.extend([f(f"is_{p}_member", "BOOLEAN", f"是否{p}成分"), f(f"{p}_weight", "DOUBLE", f"{p}指数权重")])
INDEX_MEMBERSHIP_FIELDS += [
    f("index_member_count", "INTEGER", "所属核心指数数量"),
    f("primary_index_code", "VARCHAR", "主要指数代码"),
    f("primary_index_name", "VARCHAR", "主要指数名称"),
    f("has_index_weight", "BOOLEAN", "是否有核心指数权重"),
] + UPDATED


INDEX_CORE_FIELDS = PK_STOCK.copy() + INDEX_MEMBERSHIP_FIELDS[2:-1]
for n in CORE_PERIODS:
    for p in INDEX_PREFIXES:
        INDEX_CORE_FIELDS.append(f(f"{p}_ret_{n}", "DOUBLE", f"{p}指数{n}日收益"))
    INDEX_CORE_FIELDS.append(f(f"primary_index_ret_{n}", "DOUBLE", f"主指数{n}日收益"))
    for p in ["hs300", "zz500", "zz1000"]:
        INDEX_CORE_FIELDS.append(f(f"stock_excess_{p}_{n}", "DOUBLE", f"个股相对{p}{n}日超额收益"))
    INDEX_CORE_FIELDS.append(f(f"stock_excess_primary_index_{n}", "DOUBLE", f"个股相对主指数{n}日超额收益"))
INDEX_CORE_FIELDS.extend(
    [
        f("market_stock_count", "INTEGER", "全市场股票数量"),
        f("market_up_ratio", "DOUBLE", "全市场上涨比例"),
        f("market_down_ratio", "DOUBLE", "全市场下跌比例"),
        f("market_limit_up_count", "INTEGER", "全市场涨停数量"),
        f("market_limit_down_count", "INTEGER", "全市场跌停数量"),
        f("market_limit_up_ratio", "DOUBLE", "全市场涨停比例"),
        f("market_limit_down_ratio", "DOUBLE", "全市场跌停比例"),
        f("market_amount", "DOUBLE", "全市场成交额"),
    ]
)
for n in CORE_PERIODS:
    INDEX_CORE_FIELDS.extend(
        [
            f(f"market_amount_ma_{n}", "DOUBLE", f"{n}日全市场成交额均值"),
            f(f"market_amount_chg_{n}", "DOUBLE", f"{n}日全市场成交额变化率"),
            f(f"market_up_ratio_ma_{n}", "DOUBLE", f"{n}日全市场上涨比例均值"),
            f(f"market_breadth_chg_{n}", "DOUBLE", f"{n}日市场宽度变化"),
            f(f"large_vs_small_ret_{n}", "DOUBLE", f"{n}日大盘相对小盘收益差"),
            f(f"mid_vs_large_ret_{n}", "DOUBLE", f"{n}日中盘相对大盘收益差"),
            f(f"growth_vs_broad_ret_{n}", "DOUBLE", f"{n}日创业板相对宽基收益差"),
            f(f"star_vs_broad_ret_{n}", "DOUBLE", f"{n}日科创50相对宽基收益差"),
        ]
    )
INDEX_CORE_FIELDS += [f("has_market_breadth", "BOOLEAN", "是否有市场宽度数据"), f("index_context_missing_reason", "VARCHAR", "指数市场上下文缺失原因")] + UPDATED


def variable(field: dict, table: str, module: str) -> dict:
    name = field["name"]
    return {
        "name": name,
        "label_zh": field["description"].split("=")[0].strip(),
        "table": table,
        "module": module,
        "category": module,
        "tier": "core",
        "dtype": field["dtype"],
        "unit": "none" if field["dtype"] in {"VARCHAR", "BOOLEAN", "DATE"} else "ratio_or_source_unit",
        "frequency": "daily",
        "grain": ["ts_code", "trade_date"],
        "source_type": "derived",
        "dependencies": ["derived_daily_spine", "sw_industry_member", "concept_member", "index_daily", "index_weight"],
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
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    tables = [
        ("derived_sw_industry_member_enhanced", "Phase 3 申万行业一二三级增强成员历史", ["sw_l2_code", "ts_code", "in_date"], ENHANCED_MEMBER_FIELDS, None),
        ("derived_sector_daily_cache", "Phase 3 行业日频上下文缓存", ["industry_level", "industry_code", "trade_date"], SECTOR_CACHE_FIELDS, None),
        ("derived_concept_daily_cache", "Phase 3 概念日频上下文缓存", ["concept_id", "trade_date"], CONCEPT_CACHE_FIELDS, None),
        ("derived_concept_stock_context_cache", "Phase 3 个股概念多周期列表缓存", ["ts_code", "trade_date"], CONCEPT_STOCK_CONTEXT_FIELDS, None),
        ("derived_sector_concept_context", "Phase 3 行业概念上下文核心表", ["ts_code", "trade_date"], SECTOR_CORE_FIELDS, None),
        ("derived_sector_concept_context_full_v", "Phase 3 行业概念上下文完整视图", ["ts_code", "trade_date"], SECTOR_CORE_FIELDS, "view"),
        ("derived_index_daily_cache", "Phase 3 指数日频缓存", ["index_code", "trade_date"], INDEX_DAILY_CACHE_FIELDS, None),
        ("derived_index_membership_cache", "Phase 3 指数成分权重缓存", ["ts_code", "trade_date"], INDEX_MEMBERSHIP_FIELDS, None),
        ("derived_index_market_context", "Phase 3 指数市场上下文核心表", ["ts_code", "trade_date"], INDEX_CORE_FIELDS, None),
        ("derived_index_market_context_full_v", "Phase 3 指数市场上下文完整视图", ["ts_code", "trade_date"], INDEX_CORE_FIELDS, "view"),
    ]
    for name, desc, pk, fields, table_type in tables:
        payload = {"name": name, "phase": "P3", "description": desc, "primary_key": pk, "fields": fields}
        if table_type:
            payload["table_type"] = table_type
        upsert_table(schema, payload)
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for variables_path in (ROOT / "config" / "variables").glob("*.json"):
        payload = json.loads(variables_path.read_text(encoding="utf-8"))
        before = len(payload.get("variables", []))
        payload["variables"] = [
            item for item in payload.get("variables", [])
            if item.get("module") not in {"sector_concept_context", "index_market_context"}
        ]
        if len(payload["variables"]) != before:
            variables_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = json.loads(DERIVED_VARIABLES_PATH.read_text(encoding="utf-8"))
    existing = {item.get("name") for item in registry.get("variables", [])}
    for table, module, fields in [
        ("derived_sector_concept_context", "sector_concept_context", SECTOR_CORE_FIELDS),
        ("derived_index_market_context", "index_market_context", INDEX_CORE_FIELDS),
    ]:
        for field in fields:
            if field["name"] in {"ts_code", "trade_date", "updated_at"} or field["name"] in existing:
                continue
            registry["variables"].append(variable(field, table, module))
            existing.add(field["name"])
    DERIVED_VARIABLES_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: len(fields) for name, _, _, fields, _ in tables}, ensure_ascii=False))


if __name__ == "__main__":
    main()
