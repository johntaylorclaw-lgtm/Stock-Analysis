from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
REPORT_PATH = ROOT / "reports" / "phase3_index_market_core_run.json"

CORE_PERIODS = [5, 20, 60, 120]
INDEX_CODES = {
    "hs300": "000300.SH",
    "zz500": "000905.SH",
    "zz1000": "000852.SH",
    "sse50": "000016.SH",
    "star50": "000688.SH",
    "chinext": "399006.SZ",
}


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


def fields(table: str) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for item in schema["tables"]:
        if item["name"] == table:
            return [field["name"] for field in item["fields"]]
    raise KeyError(table)


def sql(
    columns: list[str],
    start: str | None = None,
    end: str | None = None,
    read_start: str | None = None,
) -> str:
    select: dict[str, str] = {
        "ts_code": "ds.ts_code",
        "trade_date": "ds.trade_date",
        "index_member_count": "im.index_member_count",
        "primary_index_code": "im.primary_index_code",
        "primary_index_name": "im.primary_index_name",
        "has_index_weight": "im.has_index_weight",
        "market_stock_count": "mb.stock_count",
        "market_up_ratio": "mb.market_up_ratio",
        "market_down_ratio": "mb.market_down_ratio",
        "market_limit_up_count": "mb.limit_up_count",
        "market_limit_down_count": "mb.limit_down_count",
        "market_limit_up_ratio": "mb.market_limit_up_ratio",
        "market_limit_down_ratio": "mb.market_limit_down_ratio",
        "market_amount": "mb.market_amount",
        "has_market_breadth": "mb.trade_date IS NOT NULL",
        "index_context_missing_reason": "CASE WHEN mb.trade_date IS NULL THEN 'missing_market_breadth' WHEN NOT coalesce(im.has_index_weight,false) THEN 'no_index_membership' ELSE NULL END",
        "updated_at": "CURRENT_TIMESTAMP",
    }
    for p in INDEX_CODES:
        select[f"is_{p}_member"] = f"im.is_{p}_member"
        select[f"{p}_weight"] = f"im.{p}_weight"
    for n in CORE_PERIODS:
        for p in INDEX_CODES:
            select[f"{p}_ret_{n}"] = f"idx.{p}_ret_{n}"
        primary_case = "CASE " + " ".join(
            f"WHEN im.primary_index_code = '{code}' THEN idx.{p}_ret_{n}" for p, code in INDEX_CODES.items()
        ) + " ELSE NULL END"
        select[f"primary_index_ret_{n}"] = primary_case
        select[f"stock_excess_hs300_{n}"] = f"r.ret_{n}_hfq - idx.hs300_ret_{n}"
        select[f"stock_excess_zz500_{n}"] = f"r.ret_{n}_hfq - idx.zz500_ret_{n}"
        select[f"stock_excess_zz1000_{n}"] = f"r.ret_{n}_hfq - idx.zz1000_ret_{n}"
        select[f"stock_excess_primary_index_{n}"] = f"r.ret_{n}_hfq - ({primary_case})"
        select[f"market_amount_ma_{n}"] = f"mb.market_amount_ma_{n}"
        select[f"market_amount_chg_{n}"] = f"mb.market_amount_chg_{n}"
        select[f"market_up_ratio_ma_{n}"] = f"mb.market_up_ratio_ma_{n}"
        select[f"market_breadth_chg_{n}"] = f"mb.market_breadth_chg_{n}"
        select[f"large_vs_small_ret_{n}"] = f"idx.hs300_ret_{n} - idx.zz1000_ret_{n}"
        select[f"mid_vs_large_ret_{n}"] = f"idx.zz500_ret_{n} - idx.hs300_ret_{n}"
        select[f"growth_vs_broad_ret_{n}"] = f"idx.chinext_ret_{n} - idx.hs300_ret_{n}"
        select[f"star_vs_broad_ret_{n}"] = f"idx.star50_ret_{n} - idx.hs300_ret_{n}"
    select_sql = ",\n        ".join(f"{select[col]} AS {q(col)}" for col in columns)
    col_sql = ", ".join(q(col) for col in columns)
    idx_select = ["trade_date"]
    for p, code in INDEX_CODES.items():
        for n in CORE_PERIODS:
            idx_select.append(f"max(CASE WHEN index_code = '{code}' THEN index_ret_{n} END) AS {p}_ret_{n}")
    market_roll = []
    for n in CORE_PERIODS:
        market_roll.extend(
            [
                f"avg(amount_total) OVER w{n} AS market_amount_ma_{n}",
                f"avg(up_count::DOUBLE / nullif(stock_count,0)) OVER w{n} AS market_up_ratio_ma_{n}",
                f"up_count::DOUBLE / nullif(stock_count,0) - lag(up_count::DOUBLE / nullif(stock_count,0), {n}) OVER ord AS market_breadth_chg_{n}",
            ]
        )
    market_final = [
        "trade_date", "stock_count", "market_up_ratio", "market_down_ratio", "limit_up_count",
        "limit_down_count", "market_limit_up_ratio", "market_limit_down_ratio", "market_amount",
    ]
    for n in CORE_PERIODS:
        market_final.extend(
            [
                f"market_amount_ma_{n}",
                f"CASE WHEN lag(market_amount_ma_{n}, {n}) OVER (ORDER BY trade_date) > 0 THEN market_amount_ma_{n} / lag(market_amount_ma_{n}, {n}) OVER (ORDER BY trade_date) - 1 ELSE NULL END AS market_amount_chg_{n}",
                f"market_up_ratio_ma_{n}",
                f"market_breadth_chg_{n}",
            ]
        )
    windows = ", ".join([f"w{n} AS (ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)" for n in CORE_PERIODS] + ["ord AS (ORDER BY trade_date)"])
    idx_where = ""
    market_where = ""
    final_where = ""
    if start and end and read_start:
        idx_where = f"WHERE trade_date BETWEEN {date_literal(read_start)} AND {date_literal(end)}"
        market_where = f"WHERE trade_date BETWEEN {date_literal(read_start)} AND {date_literal(end)}"
        final_where = f"WHERE ds.trade_date BETWEEN {date_literal(start)} AND {date_literal(end)}"
    return f"""
    INSERT INTO derived_index_market_context ({col_sql})
    WITH idx AS (
        SELECT {", ".join(idx_select)}
        FROM derived_index_daily_cache
        {idx_where}
        GROUP BY trade_date
    ),
    market_base AS (
        SELECT
            trade_date,
            stock_count,
            up_count,
            down_count,
            limit_up_count,
            limit_down_count,
            amount_total,
            up_count::DOUBLE / nullif(stock_count,0) AS market_up_ratio,
            down_count::DOUBLE / nullif(stock_count,0) AS market_down_ratio,
            limit_up_count::DOUBLE / nullif(stock_count,0) AS market_limit_up_ratio,
            limit_down_count::DOUBLE / nullif(stock_count,0) AS market_limit_down_ratio
        FROM market_breadth_daily
        {market_where}
    ),
    mb_raw AS (
        SELECT
            trade_date,
            stock_count,
            market_up_ratio,
            market_down_ratio,
            limit_up_count,
            limit_down_count,
            market_limit_up_ratio,
            market_limit_down_ratio,
            amount_total AS market_amount,
            {", ".join(market_roll)}
        FROM market_base
        WINDOW {windows}
    ),
    mb AS (
        SELECT {", ".join(market_final)}
        FROM mb_raw
    )
    SELECT
        {select_sql}
    FROM derived_daily_spine ds
    LEFT JOIN derived_index_membership_cache im USING (ts_code, trade_date)
    LEFT JOIN derived_return_momentum r USING (ts_code, trade_date)
    LEFT JOIN idx ON ds.trade_date = idx.trade_date
    LEFT JOIN mb ON ds.trade_date = mb.trade_date
    {final_where}
    """


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 3 index market context.")
    parser.add_argument("--start-date", help="Write-window start date, YYYY-MM-DD. Omit for full rebuild.")
    parser.add_argument("--end-date", help="Write-window end date, YYYY-MM-DD. Omit for full rebuild.")
    parser.add_argument("--context-days", type=int, default=260, help="Trading-day read context for rolling market fields.")
    args = parser.parse_args()
    if bool(args.start_date) != bool(args.end_date):
        raise SystemExit("--start-date and --end-date must be provided together")

    started_at = datetime.now().isoformat(timespec="seconds")
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    columns = fields("derived_index_market_context")
    start = args.start_date
    end = args.end_date
    read_start = resolve_read_start(con, start, args.context_days) if start and end else None
    con.execute("BEGIN TRANSACTION")
    try:
        if start and end:
            con.execute("DELETE FROM derived_index_market_context WHERE trade_date BETWEEN ? AND ?", [start, end])
        else:
            con.execute("DELETE FROM derived_index_market_context")
        con.execute(sql(columns, start, end, read_start))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    if start and end:
        rows = con.execute(
            "SELECT count(*) FROM derived_index_market_context WHERE trade_date BETWEEN ? AND ?",
            [start, end],
        ).fetchone()[0]
    else:
        rows = con.execute("SELECT count(*) FROM derived_index_market_context").fetchone()[0]
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "window" if start and end else "full",
        "start_date": start,
        "end_date": end,
        "read_start_date": read_start,
        "context_days": args.context_days,
        "rows": int(rows),
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
