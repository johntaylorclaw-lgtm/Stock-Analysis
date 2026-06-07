from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("STOCK_DB_PATH", ROOT / "data" / "duckdb" / "stock_data.duckdb"))
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
REPORT_PATH = ROOT / "reports" / "phase3_concept_stock_context_cache_run.json"

FULL_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
DAILY_CORE_PERIODS = [20]
STATIC_COLUMNS = ["concept_count", "concept_ids_all", "concept_names_all", "concept_broad_count", "concept_narrow_count"]


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def delete_table_window(con: duckdb.DuckDBPyConnection, table: str, start: str | None, end: str | None) -> None:
    if start and end:
        con.execute(f"DELETE FROM {q(table)} WHERE trade_date BETWEEN ? AND ?", [start, end])
    else:
        con.execute(f"DELETE FROM {q(table)}")


def count_table_window(con: duckdb.DuckDBPyConnection, table: str, start: str | None, end: str | None) -> int:
    if start and end:
        return int(
            con.execute(
                f"SELECT count(*) FROM {q(table)} WHERE trade_date BETWEEN ? AND ?",
                [start, end],
            ).fetchone()[0]
        )
    return int(con.execute(f"SELECT count(*) FROM {q(table)}").fetchone()[0])


def table_fields(table: str) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for item in schema["tables"]:
        if item["name"] == table:
            return [field["name"] for field in item["fields"]]
    raise KeyError(table)


def period_columns(n: int) -> list[str]:
    return [
        f"concept_ids_top_{n}",
        f"concept_names_top_{n}",
        f"concept_lagging_ids_{n}",
        f"concept_lagging_names_{n}",
        f"concept_active_ids_{n}",
        f"concept_active_names_{n}",
        f"concept_narrow_leading_ids_{n}",
        f"concept_narrow_leading_names_{n}",
        f"concept_best_id_{n}",
        f"concept_best_name_{n}",
        f"concept_best_ret_{n}",
        f"concept_worst_id_{n}",
        f"concept_worst_name_{n}",
        f"concept_worst_ret_{n}",
        f"concept_avg_ret_{n}",
        f"concept_median_ret_{n}",
        f"concept_max_ret_{n}",
        f"concept_min_ret_{n}",
        f"concept_ret_spread_{n}",
        f"concept_positive_count_{n}",
        f"concept_negative_count_{n}",
        f"concept_avg_amount_{n}",
        f"concept_main_flow_sum_{n}",
        f"concept_hot_count_{n}",
    ]


def static_temp_sql(start_date: str, end_date: str) -> str:
    return f"""
    CREATE OR REPLACE TEMP TABLE concept_static AS
    WITH latest_flags AS (
        SELECT concept_id, concept_broad_flag, concept_narrow_flag
        FROM (
            SELECT
                concept_id,
                concept_broad_flag,
                concept_narrow_flag,
                row_number() OVER (PARTITION BY concept_id ORDER BY trade_date DESC) AS rn
            FROM derived_concept_daily_cache
            WHERE trade_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
        )
        WHERE rn = 1
    )
    SELECT
        cm.ts_code,
        count(DISTINCT cm.concept_id)::INTEGER AS concept_count,
        string_agg(DISTINCT cm.concept_id, ';' ORDER BY cm.concept_id) AS concept_ids_all,
        string_agg(DISTINCT cm.concept_name, ';' ORDER BY cm.concept_name) AS concept_names_all,
        sum(CASE WHEN lf.concept_broad_flag THEN 1 ELSE 0 END)::INTEGER AS concept_broad_count,
        sum(CASE WHEN lf.concept_narrow_flag THEN 1 ELSE 0 END)::INTEGER AS concept_narrow_count
    FROM concept_member cm
    LEFT JOIN latest_flags lf ON cm.concept_id = lf.concept_id
    GROUP BY cm.ts_code
    """


def period_temp_sql(n: int, start_date: str, end_date: str) -> str:
    return f"""
    CREATE OR REPLACE TEMP TABLE concept_period_{n} AS
    SELECT
        cm.ts_code,
        cc.trade_date,
        array_to_string(arg_max(cm.concept_id, cc.concept_ret_{n}, 5), ';') AS concept_ids_top_{n},
        array_to_string(arg_max(coalesce(cm.concept_name, cc.concept_name), cc.concept_ret_{n}, 5), ';') AS concept_names_top_{n},
        array_to_string(arg_min(cm.concept_id, cc.concept_ret_{n}, 5), ';') AS concept_lagging_ids_{n},
        array_to_string(arg_min(coalesce(cm.concept_name, cc.concept_name), cc.concept_ret_{n}, 5), ';') AS concept_lagging_names_{n},
        array_to_string(arg_max(cm.concept_id, cc.concept_amount_pct_all_{n}, 5), ';') AS concept_active_ids_{n},
        array_to_string(arg_max(coalesce(cm.concept_name, cc.concept_name), cc.concept_amount_pct_all_{n}, 5), ';') AS concept_active_names_{n},
        array_to_string(arg_max(cm.concept_id, CASE WHEN cc.concept_narrow_flag THEN cc.concept_ret_{n} ELSE NULL END, 5), ';') AS concept_narrow_leading_ids_{n},
        array_to_string(arg_max(coalesce(cm.concept_name, cc.concept_name), CASE WHEN cc.concept_narrow_flag THEN cc.concept_ret_{n} ELSE NULL END, 5), ';') AS concept_narrow_leading_names_{n},
        arg_max(cm.concept_id, cc.concept_ret_{n}) AS concept_best_id_{n},
        arg_max(coalesce(cm.concept_name, cc.concept_name), cc.concept_ret_{n}) AS concept_best_name_{n},
        max(cc.concept_ret_{n}) AS concept_best_ret_{n},
        arg_min(cm.concept_id, cc.concept_ret_{n}) AS concept_worst_id_{n},
        arg_min(coalesce(cm.concept_name, cc.concept_name), cc.concept_ret_{n}) AS concept_worst_name_{n},
        min(cc.concept_ret_{n}) AS concept_worst_ret_{n},
        avg(cc.concept_ret_{n}) AS concept_avg_ret_{n},
        median(cc.concept_ret_{n}) AS concept_median_ret_{n},
        max(cc.concept_ret_{n}) AS concept_max_ret_{n},
        min(cc.concept_ret_{n}) AS concept_min_ret_{n},
        max(cc.concept_ret_{n}) - min(cc.concept_ret_{n}) AS concept_ret_spread_{n},
        sum(CASE WHEN cc.concept_ret_{n} > 0 THEN 1 ELSE 0 END)::INTEGER AS concept_positive_count_{n},
        sum(CASE WHEN cc.concept_ret_{n} < 0 THEN 1 ELSE 0 END)::INTEGER AS concept_negative_count_{n},
        avg(cc.concept_amount_ma_{n}) AS concept_avg_amount_{n},
        avg(cc.concept_main_flow_sum_{n}) AS concept_main_flow_sum_{n},
        sum(CASE WHEN cc.concept_hot_flag_{n} THEN 1 ELSE 0 END)::INTEGER AS concept_hot_count_{n}
    FROM concept_member cm
    JOIN derived_concept_daily_cache cc ON cm.concept_id = cc.concept_id
    WHERE cc.trade_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
    GROUP BY cm.ts_code, cc.trade_date
    """


def combined_period_temp_sql(start_date: str, end_date: str, periods: list[int] | None = None) -> str:
    active_periods = periods or FULL_PERIODS
    select_items = ["ts_code", "trade_date"]
    base_items = [
        "cm.ts_code",
        "cc.trade_date",
        "cm.concept_id",
        "coalesce(cm.concept_name, cc.concept_name) AS concept_name",
    ]
    rank_items = []
    for n in active_periods:
        base_items.extend(
            [
                f"cc.concept_ret_{n} AS concept_ret_{n}",
                f"cc.concept_amount_pct_all_{n} AS concept_amount_pct_all_{n}",
                f"cc.concept_amount_ma_{n} AS concept_amount_ma_{n}",
                f"cc.concept_main_flow_sum_{n} AS concept_main_flow_sum_{n}",
                f"cc.concept_hot_flag_{n} AS concept_hot_flag_{n}",
                f"CASE WHEN cc.concept_narrow_flag THEN cc.concept_ret_{n} ELSE NULL END AS concept_narrow_ret_{n}",
            ]
        )
        rank_items.extend(
            [
                f"row_number() OVER (PARTITION BY ts_code, trade_date ORDER BY concept_ret_{n} DESC NULLS LAST, concept_id) AS rn_top_{n}",
                f"row_number() OVER (PARTITION BY ts_code, trade_date ORDER BY concept_ret_{n} ASC NULLS LAST, concept_id) AS rn_lagging_{n}",
                f"row_number() OVER (PARTITION BY ts_code, trade_date ORDER BY concept_amount_pct_all_{n} DESC NULLS LAST, concept_id) AS rn_active_{n}",
                f"row_number() OVER (PARTITION BY ts_code, trade_date ORDER BY concept_narrow_ret_{n} DESC NULLS LAST, concept_id) AS rn_narrow_{n}",
            ]
        )
        select_items.extend(
            [
                f"string_agg(concept_id, ';' ORDER BY rn_top_{n}) FILTER (WHERE rn_top_{n} <= 5 AND concept_ret_{n} IS NOT NULL) AS concept_ids_top_{n}",
                f"string_agg(concept_name, ';' ORDER BY rn_top_{n}) FILTER (WHERE rn_top_{n} <= 5 AND concept_ret_{n} IS NOT NULL) AS concept_names_top_{n}",
                f"string_agg(concept_id, ';' ORDER BY rn_lagging_{n}) FILTER (WHERE rn_lagging_{n} <= 5 AND concept_ret_{n} IS NOT NULL) AS concept_lagging_ids_{n}",
                f"string_agg(concept_name, ';' ORDER BY rn_lagging_{n}) FILTER (WHERE rn_lagging_{n} <= 5 AND concept_ret_{n} IS NOT NULL) AS concept_lagging_names_{n}",
                f"string_agg(concept_id, ';' ORDER BY rn_active_{n}) FILTER (WHERE rn_active_{n} <= 5 AND concept_amount_pct_all_{n} IS NOT NULL) AS concept_active_ids_{n}",
                f"string_agg(concept_name, ';' ORDER BY rn_active_{n}) FILTER (WHERE rn_active_{n} <= 5 AND concept_amount_pct_all_{n} IS NOT NULL) AS concept_active_names_{n}",
                f"string_agg(concept_id, ';' ORDER BY rn_narrow_{n}) FILTER (WHERE rn_narrow_{n} <= 5 AND concept_narrow_ret_{n} IS NOT NULL) AS concept_narrow_leading_ids_{n}",
                f"string_agg(concept_name, ';' ORDER BY rn_narrow_{n}) FILTER (WHERE rn_narrow_{n} <= 5 AND concept_narrow_ret_{n} IS NOT NULL) AS concept_narrow_leading_names_{n}",
                f"max(concept_id) FILTER (WHERE rn_top_{n} = 1 AND concept_ret_{n} IS NOT NULL) AS concept_best_id_{n}",
                f"max(concept_name) FILTER (WHERE rn_top_{n} = 1 AND concept_ret_{n} IS NOT NULL) AS concept_best_name_{n}",
                f"max(concept_ret_{n}) AS concept_best_ret_{n}",
                f"max(concept_id) FILTER (WHERE rn_lagging_{n} = 1 AND concept_ret_{n} IS NOT NULL) AS concept_worst_id_{n}",
                f"max(concept_name) FILTER (WHERE rn_lagging_{n} = 1 AND concept_ret_{n} IS NOT NULL) AS concept_worst_name_{n}",
                f"min(concept_ret_{n}) AS concept_worst_ret_{n}",
                f"avg(concept_ret_{n}) AS concept_avg_ret_{n}",
                f"median(concept_ret_{n}) AS concept_median_ret_{n}",
                f"max(concept_ret_{n}) AS concept_max_ret_{n}",
                f"min(concept_ret_{n}) AS concept_min_ret_{n}",
                f"max(concept_ret_{n}) - min(concept_ret_{n}) AS concept_ret_spread_{n}",
                f"sum(CASE WHEN concept_ret_{n} > 0 THEN 1 ELSE 0 END)::INTEGER AS concept_positive_count_{n}",
                f"sum(CASE WHEN concept_ret_{n} < 0 THEN 1 ELSE 0 END)::INTEGER AS concept_negative_count_{n}",
                f"avg(concept_amount_ma_{n}) AS concept_avg_amount_{n}",
                f"avg(concept_main_flow_sum_{n}) AS concept_main_flow_sum_{n}",
                f"sum(CASE WHEN concept_hot_flag_{n} THEN 1 ELSE 0 END)::INTEGER AS concept_hot_count_{n}",
            ]
        )
    return f"""
    CREATE OR REPLACE TEMP TABLE concept_period_all AS
    WITH base AS (
        SELECT
            {", ".join(base_items)}
        FROM concept_member cm
        JOIN derived_concept_daily_cache cc ON cm.concept_id = cc.concept_id
        WHERE cc.trade_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
    ),
    ranked AS (
        SELECT
            *,
            {", ".join(rank_items)}
        FROM base
    )
    SELECT
        {", ".join(select_items)}
    FROM ranked
    GROUP BY ts_code, trade_date
    """


def insert_year_sql(start_date: str, end_date: str, columns: list[str]) -> str:
    select = {col: "NULL" for col in columns}
    select["ts_code"] = "ds.ts_code"
    select["trade_date"] = "ds.trade_date"
    for col in ["concept_count", "concept_ids_all", "concept_names_all", "concept_broad_count", "concept_narrow_count"]:
        select[col] = f"s.{q(col)}"
    for n in FULL_PERIODS:
        for col in period_columns(n):
            select[col] = f"p{n}.{q(col)}"
    select["updated_at"] = "CURRENT_TIMESTAMP"
    col_sql = ", ".join(q(col) for col in columns)
    select_sql = ",\n        ".join(f"{select[col]} AS {q(col)}" for col in columns)
    joins = "\n    ".join(
        f"LEFT JOIN concept_period_{n} p{n} ON ds.ts_code = p{n}.ts_code AND ds.trade_date = p{n}.trade_date"
        for n in FULL_PERIODS
    )
    return f"""
    INSERT INTO derived_concept_stock_context_cache ({col_sql})
    SELECT
        {select_sql}
    FROM derived_daily_spine ds
    LEFT JOIN concept_static s ON ds.ts_code = s.ts_code
    {joins}
    WHERE ds.trade_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
    """


def select_combined_sql(start_date: str, end_date: str, columns: list[str]) -> str:
    select = {col: "NULL" for col in columns}
    select["ts_code"] = "ds.ts_code"
    select["trade_date"] = "ds.trade_date"
    for col in STATIC_COLUMNS:
        select[col] = f"s.{q(col)}"
    for n in FULL_PERIODS:
        for col in period_columns(n):
            if col in select:
                select[col] = f"p.{q(col)}"
    select["updated_at"] = "CURRENT_TIMESTAMP"
    select_sql = ",\n        ".join(f"{select[col]} AS {q(col)}" for col in columns)
    return f"""
    SELECT
        {select_sql}
    FROM derived_daily_spine ds
    LEFT JOIN concept_static s ON ds.ts_code = s.ts_code
    LEFT JOIN concept_period_all p ON ds.ts_code = p.ts_code AND ds.trade_date = p.trade_date
    WHERE ds.trade_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
    """


def insert_combined_sql(start_date: str, end_date: str, columns: list[str]) -> str:
    col_sql = ", ".join(q(col) for col in columns)
    return f"""
    INSERT INTO derived_concept_stock_context_cache ({col_sql})
    {select_combined_sql(start_date, end_date, columns)}
    """


def daily_core_columns() -> list[str]:
    return ["ts_code", "trade_date", *STATIC_COLUMNS, *period_columns(20), "updated_at"]


def core_delta_temp_sql(start_date: str, end_date: str) -> str:
    return f"""
    CREATE OR REPLACE TEMP TABLE concept_stock_context_core_delta AS
    {select_combined_sql(start_date, end_date, daily_core_columns())}
    """


def update_daily_core_sql(columns: list[str]) -> str:
    value_columns = [col for col in columns if col not in {"ts_code", "trade_date"}]
    set_sql = ", ".join(f"{q(col)} = d.{q(col)}" for col in value_columns)
    changed_sql = " OR ".join(f"c.{q(col)} IS DISTINCT FROM d.{q(col)}" for col in value_columns)
    return f"""
    UPDATE derived_concept_stock_context_cache AS c
    SET {set_sql}
    FROM concept_stock_context_core_delta AS d
    WHERE c.ts_code = d.ts_code
      AND c.trade_date = d.trade_date
      AND ({changed_sql})
    """


def insert_missing_daily_core_sql(columns: list[str]) -> str:
    col_sql = ", ".join(q(col) for col in columns)
    select_sql = ", ".join("d." + q(col) for col in columns)
    return f"""
    INSERT INTO derived_concept_stock_context_cache ({col_sql})
    SELECT {select_sql}
    FROM concept_stock_context_core_delta AS d
    LEFT JOIN derived_concept_stock_context_cache AS c
      ON d.ts_code = c.ts_code
     AND d.trade_date = c.trade_date
    WHERE c.ts_code IS NULL
    """


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2006)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--start-date", help="Write-window start date, YYYY-MM-DD. Omit for year/full rebuild.")
    parser.add_argument("--end-date", help="Write-window end date, YYYY-MM-DD. Omit for year/full rebuild.")
    parser.add_argument("--profile", choices=["daily-core", "full"], default="full")
    parser.add_argument("--no-delete", action="store_true")
    args = parser.parse_args()
    if bool(args.start_date) != bool(args.end_date):
        raise SystemExit("--start-date and --end-date must be provided together")

    started_at = datetime.now().isoformat(timespec="seconds")
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    columns = table_fields("derived_concept_stock_context_cache")
    table_name = "derived_concept_stock_context_cache"
    if args.start_date and args.end_date:
        start = args.start_date
        end = args.end_date
        con.execute(static_temp_sql(start, end))
        if args.profile == "daily-core":
            con.execute(combined_period_temp_sql(start, end, DAILY_CORE_PERIODS))
            con.execute(core_delta_temp_sql(start, end))
            core_columns = daily_core_columns()
            con.execute("BEGIN TRANSACTION")
            try:
                con.execute(update_daily_core_sql(core_columns))
                con.execute(insert_missing_daily_core_sql(core_columns))
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
        else:
            con.execute(combined_period_temp_sql(start, end))
            con.execute("BEGIN TRANSACTION")
            try:
                delete_table_window(con, table_name, start, end)
                con.execute(insert_combined_sql(start, end, columns))
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
        rows = count_table_window(con, table_name, start, end)
        payload = {
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "window",
            "profile": args.profile,
            "start_date": start,
            "end_date": end,
            "summary": {table_name: rows},
        }
        REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return

    if not args.no_delete:
        delete_table_window(con, table_name, None, None)

    summary = []
    for year in range(args.start_year, args.end_year + 1):
        start = f"{year}-01-01"
        end = "2026-05-26" if year == 2026 else f"{year}-12-31"
        con.execute(
            f"DELETE FROM {q(table_name)} WHERE trade_date BETWEEN ? AND ?",
            [start, end],
        )
        con.execute(static_temp_sql(start, end))
        con.execute(combined_period_temp_sql(start, end))
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(insert_combined_sql(start, end, columns))
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        rows = con.execute(
            f"SELECT count(*) FROM {q(table_name)} WHERE trade_date BETWEEN ? AND ?",
            [start, end],
        ).fetchone()[0]
        item = {"year": year, "rows": int(rows)}
        summary.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
        if year == 2026:
            break

    total = count_table_window(con, table_name, None, None)
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "full",
        "rows": int(total),
        "batches": summary,
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
