from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase4_valuation_percentile_cache_run.json"
WINDOWS = {"1y": 250, "3y": 750, "5y": 1250, "10y": 2500}
SOURCES = ["pe", "pe_ttm", "pb", "ps", "ps_ttm", "dv_ratio", "dv_ttm", "total_mv", "circ_mv", "free_float_mv"]
DAILY_CORE_WINDOWS = {"5y": 1250}
DAILY_CORE_SOURCES = ["pe_ttm", "pb", "ps_ttm", "total_mv"]


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


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


def load_valuation_frame(
    con: duckdb.DuckDBPyConnection,
    start: str | None,
    end: str | None,
    sources: list[str],
):
    where = "WHERE trade_date BETWEEN ? AND ?" if start and end else ""
    params = [start, end] if start and end else []
    return con.execute(
        f"""
        SELECT
            ts_code,
            trade_date,
            {", ".join(sources)}
        FROM derived_valuation_size
        {where}
        ORDER BY ts_code, trade_date
        """,
        params,
    ).fetchdf()


def table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT count(1)
            FROM information_schema.tables
            WHERE table_name = ?
            """,
            [table_name],
        ).fetchone()[0]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build valuation rolling percentile cache.")
    parser.add_argument("--start-date", help="Write-window start date, YYYY-MM-DD. Omit for full rebuild.")
    parser.add_argument("--end-date", help="Write-window end date, YYYY-MM-DD. Omit for full rebuild.")
    parser.add_argument("--profile", choices=["daily-core", "full"], default="full", help="daily-core computes the four 5y compatibility fields; full computes all cache fields.")
    parser.add_argument("--context-days", type=int, help="Trading-day read context for rolling percentiles. Defaults to profile max window.")
    args = parser.parse_args()
    if bool(args.start_date) != bool(args.end_date):
        raise SystemExit("--start-date and --end-date must be provided together")

    started_at = datetime.now().isoformat(timespec="seconds")
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    start = args.start_date
    end = args.end_date
    active_sources = DAILY_CORE_SOURCES if args.profile == "daily-core" else SOURCES
    active_windows = DAILY_CORE_WINDOWS if args.profile == "daily-core" else WINDOWS
    context_days = args.context_days or max(active_windows.values())
    read_start = resolve_read_start(con, start, context_days) if start and end else None
    df = (
        load_valuation_frame(con, read_start, end, active_sources)
        if read_start and end
        else load_valuation_frame(con, None, None, active_sources)
    )
    print(
        {
            "stage": "loaded",
            "rows": len(df),
            "sources": len(active_sources),
            "profile": args.profile,
            "read_start": read_start,
            "end": end,
        }
    )
    pct_columns: list[str] = []
    grouped = df.groupby("ts_code", sort=False)
    for source in active_sources:
        for alias, window in active_windows.items():
            target = f"{source}_pct_{alias}"
            df[target] = grouped[source].transform(
                lambda s, w=window: s.rolling(w, min_periods=1).rank(pct=True)
            )
            pct_columns.append(target)
            print({"stage": "computed", "field": target})
    if start and end:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        write_mask = (df["trade_date"] >= start_ts) & (df["trade_date"] <= end_ts)
        cache_df = df.loc[write_mask, ["ts_code", "trade_date", *pct_columns]].copy()
    else:
        cache_df = df[["ts_code", "trade_date", *pct_columns]].copy()
    con.register("valuation_percentile_cache_df", cache_df)
    con.execute("BEGIN TRANSACTION")
    try:
        if start and end:
            columns = ["ts_code", "trade_date", *pct_columns]
            if args.profile == "daily-core":
                if not table_exists(con, "derived_valuation_percentile_cache"):
                    raise SystemExit("daily-core requires existing derived_valuation_percentile_cache; run --profile full first.")
                set_sql = ", ".join(f"{q(col)} = p.{q(col)}" for col in pct_columns)
                con.execute(
                    f"""
                    UPDATE derived_valuation_percentile_cache AS c
                    SET {set_sql}, updated_at = CURRENT_TIMESTAMP
                    FROM valuation_percentile_cache_df AS p
                    WHERE c.ts_code = p.ts_code
                      AND c.trade_date = p.trade_date
                    """
                )
                con.execute(
                    f"""
                    INSERT INTO derived_valuation_percentile_cache ({", ".join(q(col) for col in columns)}, updated_at)
                    SELECT {", ".join("p." + q(col) for col in columns)}, CURRENT_TIMESTAMP AS updated_at
                    FROM valuation_percentile_cache_df AS p
                    LEFT JOIN derived_valuation_percentile_cache AS c
                      ON p.ts_code = c.ts_code
                     AND p.trade_date = c.trade_date
                    WHERE c.ts_code IS NULL
                    """
                )
            else:
                con.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS derived_valuation_percentile_cache AS
                    SELECT *, CURRENT_TIMESTAMP AS updated_at
                    FROM valuation_percentile_cache_df
                    WHERE false
                    """
                )
                con.execute(
                    "DELETE FROM derived_valuation_percentile_cache WHERE trade_date BETWEEN ? AND ?",
                    [start, end],
                )
                con.execute(
                    f"""
                    INSERT INTO derived_valuation_percentile_cache ({", ".join(q(col) for col in columns)}, updated_at)
                    SELECT {", ".join(q(col) for col in columns)}, CURRENT_TIMESTAMP AS updated_at
                    FROM valuation_percentile_cache_df
                    """
                )
        else:
            if args.profile != "full":
                raise SystemExit("Full-table rebuild requires --profile full; use --start-date/--end-date for daily-core.")
            con.execute("DROP TABLE IF EXISTS derived_valuation_percentile_cache")
            con.execute(
                """
                CREATE TABLE derived_valuation_percentile_cache AS
                SELECT *, CURRENT_TIMESTAMP AS updated_at
                FROM valuation_percentile_cache_df
                """
            )
        update_where = "AND v.trade_date BETWEEN ? AND ?" if start and end else ""
        params = [start, end] if start and end else []
        con.execute(
            f"""
            UPDATE derived_valuation_size AS v
            SET
                pe_ttm_pct_5y = c.pe_ttm_pct_5y,
                pb_pct_5y = c.pb_pct_5y,
                ps_ttm_pct_5y = c.ps_ttm_pct_5y,
                total_mv_pct_5y = c.total_mv_pct_5y
            FROM derived_valuation_percentile_cache AS c
            WHERE v.ts_code = c.ts_code
              AND v.trade_date = c.trade_date
              {update_where}
            """,
            params,
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    summary = con.execute(
        f"""
        SELECT
            count(*) AS rows,
            count(pe_ttm_pct_5y) AS pe_ttm_pct_5y_non_null,
            count(pb_pct_5y) AS pb_pct_5y_non_null,
            count(ps_ttm_pct_5y) AS ps_ttm_pct_5y_non_null,
            count(total_mv_pct_5y) AS total_mv_pct_5y_non_null
        FROM derived_valuation_percentile_cache
        {"WHERE trade_date BETWEEN ? AND ?" if start and end else ""}
        """,
        [start, end] if start and end else [],
    ).fetchone()
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "window" if start and end else "full",
        "start_date": start,
        "end_date": end,
        "read_start_date": read_start,
        "context_days": context_days,
        "profile": args.profile,
        "computed_fields": pct_columns,
        "summary": {
            "rows": int(summary[0]),
            "pe_ttm_pct_5y_non_null": int(summary[1]),
            "pb_pct_5y_non_null": int(summary[2]),
            "ps_ttm_pct_5y_non_null": int(summary[3]),
            "total_mv_pct_5y_non_null": int(summary[4]),
        },
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
