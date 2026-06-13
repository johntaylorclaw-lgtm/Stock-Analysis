from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_capital_flow_cache_run.json"

FULL_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
CORE_PERIODS = [5, 20, 60, 120]
NORTH_HOLD_PERIODS = [5, 20, 60, 120, 250]
ZSCORE_PERIODS = [20, 60, 120, 250]


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def date_literal(value: str) -> str:
    return "DATE '" + value.replace("'", "''") + "'"


def resolve_read_start(con: duckdb.DuckDBPyConnection, start: str, context_days: int) -> str:
    row = con.execute(
        """
        SELECT min(cal_date)
        FROM (
            SELECT cal_date
            FROM trade_calendar
            WHERE is_open AND cal_date <= CAST(? AS DATE)
            ORDER BY cal_date DESC
            LIMIT ?
        )
        """,
        [start, context_days + 1],
    ).fetchone()
    return str(row[0] or start)


def delete_table_window(con: duckdb.DuckDBPyConnection, table: str, start: str | None, end: str | None) -> None:
    if start and end:
        con.execute(f"DELETE FROM {q(table)} WHERE trade_date BETWEEN ? AND ?", [start, end])
    else:
        con.execute(f"DELETE FROM {q(table)}")


def table_count(con: duckdb.DuckDBPyConnection, table: str, start: str | None, end: str | None) -> int:
    if start and end:
        return int(
            con.execute(
                f"SELECT count(*) FROM {q(table)} WHERE trade_date BETWEEN ? AND ?",
                [start, end],
            ).fetchone()[0]
        )
    return int(con.execute(f"SELECT count(*) FROM {q(table)}").fetchone()[0])


def north_cache_sql(start: str | None = None, end: str | None = None, read_start: str | None = None) -> str:
    market_select = [
        "trade_date",
        "north_money",
        "hgt",
        "sgt",
        "ggt_ss",
        "ggt_sz",
        "south_money",
    ]
    for n in FULL_PERIODS:
        market_select.append(
            f"avg(north_money) OVER (ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW) AS north_money_ma_{n}"
        )
    for n in FULL_PERIODS:
        market_select.append(
            f"sum(north_money) OVER (ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW) AS north_money_sum_{n}"
        )
    for n in ZSCORE_PERIODS:
        avg_expr = f"avg(north_money) OVER (ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)"
        std_expr = f"stddev_samp(north_money) OVER (ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)"
        count_expr = f"count(north_money) OVER (ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)"
        market_select.append(
            f"CASE WHEN {count_expr} >= {n} AND {std_expr} > 0 THEN (north_money - {avg_expr}) / {std_expr} ELSE NULL END AS north_money_zscore_{n}"
        )
    final_select = [
        "c.ts_code",
        "c.trade_date",
        "m.north_money",
        "m.hgt",
        "m.sgt",
        "m.ggt_ss",
        "m.ggt_sz",
        "m.south_money",
        *[f"m.north_money_ma_{n}" for n in FULL_PERIODS],
        *[f"m.north_money_sum_{n}" for n in FULL_PERIODS],
        *[f"m.north_money_zscore_{n}" for n in ZSCORE_PERIODS],
    ]
    for n in NORTH_HOLD_PERIODS:
        if n in CORE_PERIODS:
            final_select.append(f"c.north_hold_shares_chg_{n}")
        else:
            lag_expr = f"lag(c.north_hold_shares, {n}) OVER (PARTITION BY c.ts_code ORDER BY c.trade_date)"
            final_select.append(
                f"CASE WHEN c.north_hold_shares > 0 AND {lag_expr} > 0 THEN c.north_hold_shares / {lag_expr} - 1 ELSE NULL END AS north_hold_shares_chg_{n}"
            )
    for n in NORTH_HOLD_PERIODS:
        if n in CORE_PERIODS:
            final_select.append(f"c.north_hold_ratio_chg_{n}")
        else:
            lag_expr = f"lag(c.north_hold_ratio, {n}) OVER (PARTITION BY c.ts_code ORDER BY c.trade_date)"
            final_select.append(
                f"CASE WHEN c.north_hold_ratio IS NOT NULL AND {lag_expr} IS NOT NULL THEN c.north_hold_ratio - {lag_expr} ELSE NULL END AS north_hold_ratio_chg_{n}"
            )
    final_select.append("CURRENT_TIMESTAMP AS updated_at")
    market_where = ""
    capital_where = ""
    final_where = ""
    if start and end and read_start:
        market_where = f"WHERE trade_date BETWEEN {date_literal(read_start)} AND {date_literal(end)}"
        capital_where = f"WHERE trade_date BETWEEN {date_literal(read_start)} AND {date_literal(end)}"
        final_where = f"WHERE trade_date BETWEEN {date_literal(start)} AND {date_literal(end)}"
    return f"""
    INSERT INTO derived_northbound_flow_cache
    WITH market AS (
        SELECT
            {", ".join(market_select)}
        FROM northbound_daily
        {market_where}
    ),
    joined AS (
        SELECT
            {", ".join(final_select)}
        FROM (
            SELECT *
            FROM derived_capital_flow
            {capital_where}
        ) c
        LEFT JOIN market m
            ON c.trade_date = m.trade_date
    )
    SELECT
        *
    FROM joined
    {final_where}
    """


def event_cache_sql(start: str | None = None, end: str | None = None, read_start: str | None = None) -> str:
    rolling_select = []
    for n in FULL_PERIODS:
        rolling_select.append(
            f"CASE WHEN event_obs_{n} >= {n} THEN CAST(top_list_days_{n}_raw AS INTEGER) ELSE NULL END AS top_list_days_{n}"
        )
    for n in FULL_PERIODS:
        rolling_select.append(
            f"CASE WHEN event_obs_{n} >= {n} THEN top_inst_net_buy_sum_{n}_raw ELSE NULL END AS top_inst_net_buy_sum_{n}"
        )
    rolling_raw = []
    for n in FULL_PERIODS:
        rolling_raw.extend(
            [
                f"sum(CASE WHEN top_list_flag THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW) AS top_list_days_{n}_raw",
                f"sum(top_inst_net_buy) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW) AS top_inst_net_buy_sum_{n}_raw",
                f"count(*) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW) AS event_obs_{n}",
            ]
        )
    base_where = ""
    final_where = ""
    if start and end and read_start:
        base_where = f"WHERE c.trade_date BETWEEN {date_literal(read_start)} AND {date_literal(end)}"
        final_where = f"WHERE trade_date BETWEEN {date_literal(start)} AND {date_literal(end)}"
    return f"""
    INSERT INTO derived_capital_flow_event_cache
    WITH top_list AS (
        SELECT
            ts_code,
            trade_date,
            TRUE AS top_list_flag,
            sum(net_amount) AS top_list_net_amount,
            avg(net_rate) AS top_list_net_rate,
            avg(amount_rate) AS top_list_amount_rate,
            string_agg(DISTINCT reason, '; ' ORDER BY reason) AS top_list_reason
        FROM top_list_daily
        GROUP BY ts_code, trade_date
    ),
    top_inst AS (
        SELECT
            ts_code,
            trade_date,
            TRUE AS top_inst_flag,
            sum(buy) AS top_inst_buy_amount,
            sum(sell) AS top_inst_sell_amount,
            sum(net_buy) AS top_inst_net_buy,
            count(*) AS top_inst_count
        FROM top_inst_detail
        GROUP BY ts_code, trade_date
    ),
    base AS (
        SELECT
            c.ts_code,
            c.trade_date,
            coalesce(tl.top_list_flag, FALSE) AS top_list_flag,
            tl.top_list_net_amount,
            tl.top_list_net_rate,
            tl.top_list_amount_rate,
            tl.top_list_reason,
            coalesce(ti.top_inst_flag, FALSE) AS top_inst_flag,
            coalesce(ti.top_inst_buy_amount, 0) AS top_inst_buy_amount,
            coalesce(ti.top_inst_sell_amount, 0) AS top_inst_sell_amount,
            coalesce(ti.top_inst_net_buy, 0) AS top_inst_net_buy,
            CASE WHEN ti.top_inst_sell_amount > 0 THEN ti.top_inst_buy_amount / ti.top_inst_sell_amount ELSE NULL END AS top_inst_buy_sell_ratio,
            coalesce(ti.top_inst_count, 0)::INTEGER AS top_inst_count
        FROM derived_capital_flow c
        LEFT JOIN top_list tl USING (ts_code, trade_date)
        LEFT JOIN top_inst ti USING (ts_code, trade_date)
        {base_where}
    ),
    rolling AS (
        SELECT
            *,
            {", ".join(rolling_raw)}
        FROM base
    )
    SELECT
        ts_code,
        trade_date,
        top_list_flag,
        top_list_net_amount,
        top_list_net_rate,
        top_list_amount_rate,
        top_list_reason,
        top_inst_flag,
        top_inst_buy_amount,
        top_inst_sell_amount,
        top_inst_net_buy,
        top_inst_buy_sell_ratio,
        top_inst_count,
        {", ".join(rolling_select)},
        CURRENT_TIMESTAMP AS updated_at
    FROM rolling
    {final_where}
    """


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 3 capital-flow cache tables.")
    parser.add_argument("--start-date", help="Write-window start date, YYYY-MM-DD. Omit for full rebuild.")
    parser.add_argument("--end-date", help="Write-window end date, YYYY-MM-DD. Omit for full rebuild.")
    parser.add_argument("--context-days", type=int, default=260, help="Trading-day read context for rolling cache refresh.")
    args = parser.parse_args()
    if bool(args.start_date) != bool(args.end_date):
        raise SystemExit("--start-date and --end-date must be provided together")

    started_at = datetime.now().isoformat(timespec="seconds")
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    start = args.start_date
    end = args.end_date
    read_start = resolve_read_start(con, start, args.context_days) if start and end else None
    jobs = [
        ("derived_northbound_flow_cache", north_cache_sql(start, end, read_start)),
        ("derived_capital_flow_event_cache", event_cache_sql(start, end, read_start)),
    ]
    summary = {}
    for table, sql in jobs:
        con.execute("BEGIN TRANSACTION")
        try:
            delete_table_window(con, table, start, end)
            con.execute(sql)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        summary[table] = table_count(con, table, start, end)
        print(json.dumps({"table": table, "rows": summary[table]}, ensure_ascii=False))
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "window" if start and end else "full",
        "start_date": start,
        "end_date": end,
        "read_start_date": read_start,
        "context_days": args.context_days,
        "summary": summary,
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
