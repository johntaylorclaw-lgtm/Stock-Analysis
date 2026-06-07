from __future__ import annotations

from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"

FULL_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
CORE_PERIODS = [5, 20, 60, 120]
NON_CORE_PERIODS = [n for n in FULL_PERIODS if n not in CORE_PERIODS]

CORE_FIELDS = [
    "ts_code", "trade_date",
    "small_buy_amount", "small_sell_amount", "small_net_amount",
    "medium_buy_amount", "medium_sell_amount", "medium_net_amount",
    "large_buy_amount", "large_sell_amount", "large_net_amount",
    "extra_large_buy_amount", "extra_large_sell_amount", "extra_large_net_amount",
    "main_net_amount", "main_buy_amount", "main_sell_amount", "retail_net_amount",
    "net_mf_amount", "net_mf_vol",
    "main_net_amount_rate", "large_net_amount_rate", "extra_large_net_amount_rate", "small_net_amount_rate",
    "main_flow_ma_5", "main_flow_ma_20", "main_flow_ma_60", "main_flow_ma_120",
    "main_flow_sum_5", "main_flow_sum_20", "main_flow_sum_60", "main_flow_sum_120",
    "main_flow_positive_days_20", "main_flow_persist_ratio_20",
    "main_flow_to_total_mv_20", "main_flow_to_circ_mv_20",
    "margin_balance", "short_balance", "margin_buy", "margin_repay",
    "short_sell_volume", "short_repay_volume", "total_margin_short_balance",
    "margin_balance_chg_5", "margin_balance_chg_20", "margin_balance_chg_60", "margin_balance_chg_120",
    "margin_buy_to_amount", "margin_short_ratio",
    "north_hold_shares", "north_hold_ratio",
    "north_hold_shares_chg_5", "north_hold_shares_chg_20", "north_hold_shares_chg_60", "north_hold_shares_chg_120",
    "north_hold_ratio_chg_5", "north_hold_ratio_chg_20", "north_hold_ratio_chg_60", "north_hold_ratio_chg_120",
    "has_moneyflow", "has_margin", "has_north_holding",
    "capital_flow_missing_reason",
]

NORTH_MARKET_FIELDS = [
    "north_money", "hgt", "sgt", "ggt_ss", "ggt_sz", "south_money",
    *[f"north_money_ma_{n}" for n in FULL_PERIODS],
    *[f"north_money_sum_{n}" for n in FULL_PERIODS],
    *[f"north_money_zscore_{n}" for n in [20, 60, 120, 250]],
    "north_hold_shares_chg_250", "north_hold_ratio_chg_250",
]

EVENT_FIELDS = [
    "top_list_flag", "top_list_net_amount", "top_list_net_rate", "top_list_amount_rate", "top_list_reason",
    "top_inst_flag", "top_inst_buy_amount", "top_inst_sell_amount", "top_inst_net_buy",
    "top_inst_buy_sell_ratio", "top_inst_count",
    *[f"top_list_days_{n}" for n in FULL_PERIODS],
    *[f"top_inst_net_buy_sum_{n}" for n in FULL_PERIODS],
]


def win(n: int) -> str:
    return f"PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW"


def avg_raw(source: str, n: int) -> str:
    return f"avg({source}) OVER ({win(n)})"


def sum_raw(source: str, n: int) -> str:
    return f"sum({source}) OVER ({win(n)})"


def count_raw(source: str, n: int) -> str:
    return f"count({source}) OVER ({win(n)})"


def lag_raw(source: str, n: int) -> str:
    return f"lag({source}, {n}) OVER (PARTITION BY ts_code ORDER BY trade_date)"


def create_sql() -> str:
    window_items: list[str] = []
    select_items: list[str] = [f"w.{field} AS {field}" for field in CORE_FIELDS]

    for n in NON_CORE_PERIODS:
        window_items.extend(
            [
                f"{avg_raw('main_net_amount', n)} AS main_flow_ma_{n}_raw",
                f"{sum_raw('main_net_amount', n)} AS main_flow_sum_{n}_raw",
                f"{count_raw('main_net_amount', n)} AS main_obs_{n}",
            ]
        )
        select_items.extend(
            [
                f"CASE WHEN main_obs_{n} >= {n} THEN main_flow_ma_{n}_raw ELSE NULL END AS main_flow_ma_{n}",
                f"CASE WHEN main_obs_{n} >= {n} THEN main_flow_sum_{n}_raw ELSE NULL END AS main_flow_sum_{n}",
            ]
        )

    for n in FULL_PERIODS:
        if n == 20:
            continue
        window_items.extend(
            [
                f"sum(CASE WHEN main_net_amount > 0 THEN 1 ELSE 0 END) OVER ({win(n)}) AS main_flow_positive_days_{n}_raw",
                f"{count_raw('main_net_amount', n)} AS main_positive_obs_{n}",
            ]
        )
        select_items.extend(
            [
                f"CASE WHEN main_positive_obs_{n} >= {n} THEN CAST(main_flow_positive_days_{n}_raw AS INTEGER) ELSE NULL END AS main_flow_positive_days_{n}",
                f"CASE WHEN main_positive_obs_{n} >= {n} THEN main_flow_positive_days_{n}_raw / {float(n)} ELSE NULL END AS main_flow_persist_ratio_{n}",
            ]
        )

    for n in FULL_PERIODS:
        if n == 20:
            continue
        if n in CORE_PERIODS:
            sum_expr = f"main_flow_sum_{n}"
            obs_expr = f"{n}"
        else:
            sum_expr = f"main_flow_sum_{n}_raw"
            obs_expr = f"main_obs_{n}"
        select_items.extend(
            [
                f"CASE WHEN total_mv > 0 AND {obs_expr} >= {n} THEN {sum_expr} / total_mv ELSE NULL END AS main_flow_to_total_mv_{n}",
                f"CASE WHEN circ_mv > 0 AND {obs_expr} >= {n} THEN {sum_expr} / circ_mv ELSE NULL END AS main_flow_to_circ_mv_{n}",
            ]
        )

    for source in ["large_net_amount_rate", "extra_large_net_amount_rate", "small_net_amount_rate", "main_net_amount_rate"]:
        for n in FULL_PERIODS:
            window_items.append(f"{avg_raw(source, n)} AS {source}_ma_{n}_raw")
            window_items.append(f"{count_raw(source, n)} AS {source}_obs_{n}")
            select_items.append(
                f"CASE WHEN {source}_obs_{n} >= {n} THEN {source}_ma_{n}_raw ELSE NULL END AS {source}_ma_{n}"
            )

    select_items.extend(
        [
            "main_net_amount - retail_net_amount AS main_vs_retail_net_amount",
            "CASE WHEN amount > 0 THEN (main_net_amount - retail_net_amount) * 10.0 / amount ELSE NULL END AS main_vs_retail_net_amount_rate",
            "CASE WHEN main_flow_sum_20 IS NULL OR ret_20_hfq IS NULL OR main_flow_sum_20 = 0 OR ret_20_hfq = 0 THEN NULL ELSE sign(main_flow_sum_20) != sign(ret_20_hfq) END AS main_flow_price_divergence_20",
            "CASE WHEN margin_balance > 0 THEN short_balance / margin_balance ELSE NULL END AS short_balance_to_margin_balance",
        ]
    )

    for source in ["margin_balance", "short_balance", "total_margin_short_balance"]:
        for n in FULL_PERIODS:
            name = f"{source}_chg_{n}"
            if source == "margin_balance" and n in CORE_PERIODS:
                continue
            lag_expr = lag_raw(source, n)
            select_items.append(
                f"CASE WHEN {source} > 0 AND {lag_expr} > 0 THEN {source} / {lag_expr} - 1 ELSE NULL END AS {name}"
            )

    for source in ["margin_buy", "margin_buy_to_amount"]:
        for n in FULL_PERIODS:
            window_items.append(f"{avg_raw(source, n)} AS {source}_ma_{n}_raw")
            window_items.append(f"{count_raw(source, n)} AS {source}_obs_{n}")
            select_items.append(
                f"CASE WHEN {source}_obs_{n} >= {n} THEN {source}_ma_{n}_raw ELSE NULL END AS {source}_ma_{n}"
            )

    select_items.extend([f"n.{field} AS {field}" for field in NORTH_MARKET_FIELDS])
    select_items.extend([f"e.{field} AS {field}" for field in EVENT_FIELDS])
    select_items.append("w.updated_at AS updated_at")

    return f"""
    CREATE OR REPLACE VIEW derived_capital_flow_full_v AS
    WITH b AS (
        SELECT
            c.*,
            ds.amount,
            v.total_mv,
            v.circ_mv,
            r.ret_20_hfq
        FROM derived_capital_flow c
        LEFT JOIN derived_daily_spine ds USING (ts_code, trade_date)
        LEFT JOIN derived_valuation_size v USING (ts_code, trade_date)
        LEFT JOIN derived_return_momentum r USING (ts_code, trade_date)
    ),
    w AS (
        SELECT
            *,
            {", ".join(window_items)}
        FROM b
    )
    SELECT
        {", ".join(select_items)}
    FROM w
    LEFT JOIN derived_northbound_flow_cache n USING (ts_code, trade_date)
    LEFT JOIN derived_capital_flow_event_cache e USING (ts_code, trade_date)
    """


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    con.execute(create_sql())
    columns = len(con.execute("PRAGMA table_info('derived_capital_flow_full_v')").fetchall())
    print({"view": "derived_capital_flow_full_v", "columns": columns})


if __name__ == "__main__":
    main()
