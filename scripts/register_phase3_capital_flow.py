from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"

MODULE = "capital_flow"
CORE_TABLE = "derived_capital_flow"
NORTH_CACHE_TABLE = "derived_northbound_flow_cache"
EVENT_CACHE_TABLE = "derived_capital_flow_event_cache"
FULL_VIEW = "derived_capital_flow_full_v"

FULL_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
CORE_PERIODS = [5, 20, 60, 120]
NORTH_HOLD_PERIODS = [5, 20, 60, 120, 250]
ZSCORE_PERIODS = [20, 60, 120, 250]


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
    f("small_buy_amount", "DOUBLE", "小单买入额 = stock_moneyflow_daily.buy_sm_amount，单位万元"),
    f("small_sell_amount", "DOUBLE", "小单卖出额 = stock_moneyflow_daily.sell_sm_amount，单位万元"),
    f("small_net_amount", "DOUBLE", "小单净流入额 = buy_sm_amount - sell_sm_amount，单位万元"),
    f("medium_buy_amount", "DOUBLE", "中单买入额 = stock_moneyflow_daily.buy_md_amount，单位万元"),
    f("medium_sell_amount", "DOUBLE", "中单卖出额 = stock_moneyflow_daily.sell_md_amount，单位万元"),
    f("medium_net_amount", "DOUBLE", "中单净流入额 = buy_md_amount - sell_md_amount，单位万元"),
    f("large_buy_amount", "DOUBLE", "大单买入额 = stock_moneyflow_daily.buy_lg_amount，单位万元"),
    f("large_sell_amount", "DOUBLE", "大单卖出额 = stock_moneyflow_daily.sell_lg_amount，单位万元"),
    f("large_net_amount", "DOUBLE", "大单净流入额 = buy_lg_amount - sell_lg_amount，单位万元"),
    f("extra_large_buy_amount", "DOUBLE", "超大单买入额 = stock_moneyflow_daily.buy_elg_amount，单位万元"),
    f("extra_large_sell_amount", "DOUBLE", "超大单卖出额 = stock_moneyflow_daily.sell_elg_amount，单位万元"),
    f("extra_large_net_amount", "DOUBLE", "超大单净流入额 = buy_elg_amount - sell_elg_amount，单位万元"),
    f("main_net_amount", "DOUBLE", "主力净流入额 = large_net_amount + extra_large_net_amount，单位万元"),
    f("main_buy_amount", "DOUBLE", "主力买入额 = large_buy_amount + extra_large_buy_amount，单位万元"),
    f("main_sell_amount", "DOUBLE", "主力卖出额 = large_sell_amount + extra_large_sell_amount，单位万元"),
    f("retail_net_amount", "DOUBLE", "散户净流入额 = small_net_amount，单位万元"),
    f("net_mf_amount", "DOUBLE", "总净流入额 = stock_moneyflow_daily.net_mf_amount，单位万元"),
    f("net_mf_vol", "DOUBLE", "总净流入量 = stock_moneyflow_daily.net_mf_vol"),
    f("main_net_amount_rate", "DOUBLE", "主力净流入占成交额 = main_net_amount * 10 / derived_daily_spine.amount"),
    f("large_net_amount_rate", "DOUBLE", "大单净流入占成交额 = large_net_amount * 10 / derived_daily_spine.amount"),
    f("extra_large_net_amount_rate", "DOUBLE", "超大单净流入占成交额 = extra_large_net_amount * 10 / derived_daily_spine.amount"),
    f("small_net_amount_rate", "DOUBLE", "小单净流入占成交额 = small_net_amount * 10 / derived_daily_spine.amount"),
    *[f(f"main_flow_ma_{n}", "DOUBLE", f"{n}日主力净流入均值 = avg(main_net_amount,{n})，单位万元") for n in CORE_PERIODS],
    *[f(f"main_flow_sum_{n}", "DOUBLE", f"{n}日主力净流入累计 = sum(main_net_amount,{n})，单位万元") for n in CORE_PERIODS],
    f("main_flow_positive_days_20", "INTEGER", "20日主力净流入为正天数 = sum(main_net_amount > 0,20)"),
    f("main_flow_persist_ratio_20", "DOUBLE", "20日主力净流入持续比例 = main_flow_positive_days_20 / 20"),
    f("main_flow_to_total_mv_20", "DOUBLE", "20日主力净流入占总市值 = main_flow_sum_20 / derived_valuation_size.total_mv"),
    f("main_flow_to_circ_mv_20", "DOUBLE", "20日主力净流入占流通市值 = main_flow_sum_20 / derived_valuation_size.circ_mv"),
    f("margin_balance", "DOUBLE", "融资余额 = margin_detail.margin_balance，单位元"),
    f("short_balance", "DOUBLE", "融券余额 = margin_detail.short_balance，单位元"),
    f("margin_buy", "DOUBLE", "融资买入额 = margin_detail.margin_buy，单位元"),
    f("margin_repay", "DOUBLE", "融资偿还额 = margin_detail.margin_repay，单位元"),
    f("short_sell_volume", "DOUBLE", "融券卖出量 = margin_detail.short_sell_volume"),
    f("short_repay_volume", "DOUBLE", "融券偿还量 = margin_detail.short_repay_volume"),
    f("total_margin_short_balance", "DOUBLE", "两融总余额 = margin_detail.total_balance，单位元"),
    *[f(f"margin_balance_chg_{n}", "DOUBLE", f"{n}日融资余额变化率 = margin_balance / lag(margin_balance,{n}) - 1") for n in CORE_PERIODS],
    f("margin_buy_to_amount", "DOUBLE", "融资买入占成交额 = margin_buy / (derived_daily_spine.amount * 1000)"),
    f("margin_short_ratio", "DOUBLE", "融券余额/融资余额 = short_balance / margin_balance"),
    f("north_hold_shares", "DOUBLE", "北向持股数量 = northbound_holding.hold_shares"),
    f("north_hold_ratio", "DOUBLE", "北向持股比例 = sum(northbound_holding.hold_ratio)"),
    *[f(f"north_hold_shares_chg_{n}", "DOUBLE", f"{n}日北向持股数量变化率 = north_hold_shares / lag(north_hold_shares,{n}) - 1") for n in CORE_PERIODS],
    *[f(f"north_hold_ratio_chg_{n}", "DOUBLE", f"{n}日北向持股比例变化 = north_hold_ratio - lag(north_hold_ratio,{n})") for n in CORE_PERIODS],
    f("has_moneyflow", "BOOLEAN", "是否有个股资金流数据 = stock_moneyflow_daily 是否匹配"),
    f("has_margin", "BOOLEAN", "是否有两融数据 = margin_detail 是否匹配"),
    f("has_north_holding", "BOOLEAN", "是否有北向持股数据 = northbound_holding 是否匹配"),
    f("capital_flow_missing_reason", "VARCHAR", "资金流缺失原因 = missing_moneyflow/missing_price/no_margin_coverage/no_north_coverage/null"),
] + UPDATED


NORTH_CACHE_FIELDS = PK + [
    f("north_money", "DOUBLE", "市场级北向资金净流入 = northbound_daily.north_money"),
    f("hgt", "DOUBLE", "市场级沪股通资金流 = northbound_daily.hgt"),
    f("sgt", "DOUBLE", "市场级深股通资金流 = northbound_daily.sgt"),
    f("ggt_ss", "DOUBLE", "市场级港股通沪资金流 = northbound_daily.ggt_ss"),
    f("ggt_sz", "DOUBLE", "市场级港股通深资金流 = northbound_daily.ggt_sz"),
    f("south_money", "DOUBLE", "市场级南向资金净流入 = northbound_daily.south_money"),
    *[f(f"north_money_ma_{n}", "DOUBLE", f"{n}日市场级北向净流入均值 = avg(north_money,{n})") for n in FULL_PERIODS],
    *[f(f"north_money_sum_{n}", "DOUBLE", f"{n}日市场级北向净流入累计 = sum(north_money,{n})") for n in FULL_PERIODS],
    *[f(f"north_money_zscore_{n}", "DOUBLE", f"{n}日市场级北向净流入Z值 = (north_money - avg(north_money,{n})) / stddev(north_money,{n})") for n in ZSCORE_PERIODS],
    *[f(f"north_hold_shares_chg_{n}", "DOUBLE", f"{n}日北向持股数量变化率 = north_hold_shares / lag(north_hold_shares,{n}) - 1") for n in NORTH_HOLD_PERIODS],
    *[f(f"north_hold_ratio_chg_{n}", "DOUBLE", f"{n}日北向持股比例变化 = north_hold_ratio - lag(north_hold_ratio,{n})") for n in NORTH_HOLD_PERIODS],
] + UPDATED


EVENT_CACHE_FIELDS = PK + [
    f("top_list_flag", "BOOLEAN", "是否龙虎榜上榜 = top_list_daily 当日有记录"),
    f("top_list_net_amount", "DOUBLE", "龙虎榜净买入额 = top_list_daily.net_amount"),
    f("top_list_net_rate", "DOUBLE", "龙虎榜净买入率 = top_list_daily.net_rate"),
    f("top_list_amount_rate", "DOUBLE", "龙虎榜成交额占比 = top_list_daily.amount_rate"),
    f("top_list_reason", "VARCHAR", "龙虎榜上榜原因 = top_list_daily.reason"),
    f("top_inst_flag", "BOOLEAN", "是否有机构席位记录 = top_inst_detail 当日有记录"),
    f("top_inst_buy_amount", "DOUBLE", "机构席位买入额 = sum(top_inst_detail.buy)"),
    f("top_inst_sell_amount", "DOUBLE", "机构席位卖出额 = sum(top_inst_detail.sell)"),
    f("top_inst_net_buy", "DOUBLE", "机构席位净买入额 = sum(top_inst_detail.net_buy)"),
    f("top_inst_buy_sell_ratio", "DOUBLE", "机构席位买卖比 = top_inst_buy_amount / top_inst_sell_amount"),
    f("top_inst_count", "INTEGER", "机构席位记录数 = count(top_inst_detail)"),
    *[f(f"top_list_days_{n}", "INTEGER", f"{n}日龙虎榜上榜天数 = sum(top_list_flag,{n})") for n in FULL_PERIODS],
    *[f(f"top_inst_net_buy_sum_{n}", "DOUBLE", f"{n}日机构席位净买入累计 = sum(top_inst_net_buy,{n})") for n in FULL_PERIODS],
] + UPDATED


def full_extra_fields() -> list[dict]:
    fields: list[dict] = []
    core_names = {field["name"] for field in CORE_FIELDS}
    for n in FULL_PERIODS:
        for prefix, desc in [
            ("main_flow_ma", f"{n}日主力净流入均值 = avg(main_net_amount,{n})，单位万元"),
            ("main_flow_sum", f"{n}日主力净流入累计 = sum(main_net_amount,{n})，单位万元"),
            ("main_flow_positive_days", f"{n}日主力净流入为正天数 = sum(main_net_amount > 0,{n})"),
            ("main_flow_persist_ratio", f"{n}日主力净流入持续比例 = main_flow_positive_days_{n} / {n}"),
            ("main_flow_to_total_mv", f"{n}日主力净流入占总市值 = main_flow_sum_{n} / total_mv"),
            ("main_flow_to_circ_mv", f"{n}日主力净流入占流通市值 = main_flow_sum_{n} / circ_mv"),
        ]:
            name = f"{prefix}_{n}"
            if name not in core_names:
                fields.append(f(name, "DOUBLE" if "days" not in prefix else "INTEGER", desc))
    for source, label in [
        ("large_net_amount_rate", "大单净流入占成交额"),
        ("extra_large_net_amount_rate", "超大单净流入占成交额"),
        ("small_net_amount_rate", "小单净流入占成交额"),
        ("main_net_amount_rate", "主力净流入占成交额"),
    ]:
        fields.extend(f(f"{source}_ma_{n}", "DOUBLE", f"{n}日{label}均值 = avg({source},{n})") for n in FULL_PERIODS)
    fields.extend(
        [
            f("main_vs_retail_net_amount", "DOUBLE", "主力与散户净流入差额 = main_net_amount - retail_net_amount，单位万元"),
            f("main_vs_retail_net_amount_rate", "DOUBLE", "主力与散户净流入差额占成交额 = main_vs_retail_net_amount * 10 / amount"),
            f("main_flow_price_divergence_20", "BOOLEAN", "20日资金价格背离 = sign(main_flow_sum_20) != sign(ret_20_hfq)"),
            f("short_balance_to_margin_balance", "DOUBLE", "融券余额/融资余额 = short_balance / margin_balance"),
        ]
    )
    for n in FULL_PERIODS:
        for prefix, label in [
            ("margin_balance_chg", "融资余额变化率"),
            ("short_balance_chg", "融券余额变化率"),
            ("total_margin_short_balance_chg", "两融总余额变化率"),
            ("margin_buy_ma", "融资买入额均值"),
            ("margin_buy_to_amount_ma", "融资买入占成交额均值"),
        ]:
            name = f"{prefix}_{n}"
            if name not in core_names:
                fields.append(f(name, "DOUBLE", f"{n}日{label} = {prefix}({n})"))
    return fields


def unique_fields(fields: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for field in fields:
        name = field["name"]
        if name in seen:
            continue
        seen.add(name)
        result.append(field)
    return result


FULL_FIELDS = unique_fields(
    CORE_FIELDS[:-1] + full_extra_fields() + NORTH_CACHE_FIELDS[2:-1] + EVENT_CACHE_FIELDS[2:-1] + UPDATED
)


def upsert_table(schema: dict, table: dict) -> None:
    for index, existing in enumerate(schema["tables"]):
        if existing["name"] == table["name"]:
            schema["tables"][index] = table
            return
    schema["tables"].append(table)


def infer_min_history(name: str) -> int:
    for n in sorted(FULL_PERIODS + NORTH_HOLD_PERIODS, reverse=True):
        if name.endswith(f"_{n}") or f"_{n}_" in name:
            return n
    return 1


def infer_unit(name: str, dtype: str) -> str:
    if dtype in {"BOOLEAN", "VARCHAR", "DATE"}:
        return "none"
    if name.endswith("_amount") or name.endswith("_sum") or name.endswith("_ma") or "net_buy" in name:
        return "source_unit"
    if "ratio" in name or "rate" in name or "chg" in name or "zscore" in name:
        return "ratio"
    if name.endswith("_days") or name.endswith("_count"):
        return "count"
    return "source_unit"


def variable(field: dict, table: str = CORE_TABLE, tier: str = "core") -> dict:
    name = field["name"]
    return {
        "name": name,
        "label_zh": field["description"].split("=")[0].strip(),
        "table": table,
        "module": MODULE,
        "category": "capital_flow",
        "tier": tier,
        "dtype": field["dtype"],
        "unit": infer_unit(name, field["dtype"]),
        "frequency": "daily",
        "grain": ["ts_code", "trade_date"],
        "source_type": "derived",
        "dependencies": [
            "stock_moneyflow_daily",
            "derived_daily_spine",
            "margin_detail",
            "northbound_holding",
            "northbound_daily",
            "top_list_daily",
            "top_inst_detail",
        ],
        "formula_ref": field["description"],
        "formula_zh": field["description"],
        "price_basis": "not_price",
        "point_in_time": True,
        "min_history": infer_min_history(name),
        "read_window": max(20, infer_min_history(name) * 2 + 10),
        "write_window": 10,
        "missing_policy": "source_optional",
        "validation": {"constant_allowed": field["dtype"] in {"BOOLEAN", "VARCHAR", "INTEGER"}},
    }


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    tables = [
        (CORE_TABLE, "Phase 3 资金流与交易行为核心物理表", CORE_FIELDS, None),
        (NORTH_CACHE_TABLE, "Phase 3 北向资金市场背景与持仓变化缓存表", NORTH_CACHE_FIELDS, None),
        (EVENT_CACHE_TABLE, "Phase 3 龙虎榜与机构席位事件缓存表", EVENT_CACHE_FIELDS, None),
        (FULL_VIEW, "Phase 3 资金流与交易行为完整视图", FULL_FIELDS, "view"),
    ]
    for name, desc, fields, table_type in tables:
        payload = {
            "name": name,
            "phase": "P3",
            "description": desc,
            "primary_key": ["ts_code", "trade_date"],
            "fields": fields,
        }
        if table_type:
            payload["table_type"] = table_type
        upsert_table(schema, payload)
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for variables_path in (ROOT / "config" / "variables").glob("*.json"):
        payload = json.loads(variables_path.read_text(encoding="utf-8"))
        before = len(payload.get("variables", []))
        payload["variables"] = [item for item in payload.get("variables", []) if item.get("module") != MODULE]
        if len(payload["variables"]) != before:
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
        if field["name"] not in existing_names:
            registry["variables"].append(variable(field))
            existing_names.add(field["name"])
    DERIVED_VARIABLES_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: len(fields) for name, _, fields, _ in tables}, ensure_ascii=False))


if __name__ == "__main__":
    main()
