from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
LOG_PATH = ROOT / "reports" / "phase3_financial_growth_quality_batch_run.jsonl"


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def special_code(num: str, den: str) -> str:
    return (
        "CAST(('-9' || "
        f"CASE WHEN {num} = 0 THEN '1' ELSE '0' END || "
        f"CASE WHEN {num} IS NULL THEN '1' ELSE '0' END || "
        f"CASE WHEN {num} < 0 THEN '1' ELSE '0' END || "
        f"CASE WHEN {den} = 0 THEN '1' ELSE '0' END || "
        f"CASE WHEN {den} IS NULL THEN '1' ELSE '0' END || "
        f"CASE WHEN {den} < 0 THEN '1' ELSE '0' END) AS DOUBLE)"
    )


def safe_growth(num: str, den: str) -> str:
    return (
        f"CASE WHEN {num} > 0 AND {den} > 0 "
        f"THEN {num} / {den} - 1 ELSE {special_code(num, den)} END"
    )


def quality_numeric_fields() -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    table = next(item for item in schema["tables"] if item["name"] == "derived_financial_quality")
    growth_table = next(item for item in schema["tables"] if item["name"] == "derived_financial_growth")
    growth_columns = {field["name"] for field in growth_table["fields"]}
    fields = []
    for field in table["fields"]:
        name = field["name"]
        if name in {"ts_code", "trade_date", "updated_at"}:
            continue
        if field["dtype"] in {"DOUBLE", "INTEGER", "BIGINT"}:
            base = name.removesuffix("_asof")
            expected_columns = {
                f"{base}_diff_1report_asof",
                f"{base}_diff_4report_asof",
                f"{base}_diff_8report_asof",
                f"{base}_yoy_diff_asof",
                f"{base}_growth_1report_asof",
                f"{base}_growth_4report_asof",
                f"{base}_growth_8report_asof",
                f"{base}_yoy_growth_asof",
            }
            if expected_columns.issubset(growth_columns):
                fields.append(name)
    return fields


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_update_sql(fields: list[str]) -> str:
    select_items = ["g.ts_code", "g.trade_date"]
    assignments = []
    for field in fields:
        base = field.removesuffix("_asof")
        expressions = {
            f"{base}_diff_1report_asof": f"qcur.{field} - qprev.{field}",
            f"{base}_diff_4report_asof": f"qcur.{field} - qlag4.{field}",
            f"{base}_diff_8report_asof": f"qcur.{field} - qlag8.{field}",
            f"{base}_yoy_diff_asof": f"qcur.{field} - qsame1.{field}",
            f"{base}_growth_1report_asof": safe_growth(f"qcur.{field}", f"qprev.{field}"),
            f"{base}_growth_4report_asof": safe_growth(f"qcur.{field}", f"qlag4.{field}"),
            f"{base}_growth_8report_asof": safe_growth(f"qcur.{field}", f"qlag8.{field}"),
            f"{base}_yoy_growth_asof": safe_growth(f"qcur.{field}", f"qsame1.{field}"),
        }
        for column, expression in expressions.items():
            select_items.append(f"{expression} AS {quote_ident(column)}")
            assignments.append(f"{quote_ident(column)} = s.{quote_ident(column)}")
    select_sql = ",\n                ".join(select_items)
    assignment_sql = ",\n            ".join(assignments)
    return f"""
        UPDATE derived_financial_growth AS target
        SET
            {assignment_sql}
        FROM (
            SELECT
                {select_sql}
            FROM derived_financial_growth g
            LEFT JOIN tmp_report_quality qcur
                ON g.ts_code = qcur.ts_code
               AND g.current_report_end_date = qcur.report_end_date
            LEFT JOIN tmp_report_quality qprev
                ON g.ts_code = qprev.ts_code
               AND g.prev_report_end_date = qprev.report_end_date
            LEFT JOIN tmp_report_quality qlag4
                ON g.ts_code = qlag4.ts_code
               AND g.lag_4report_end_date = qlag4.report_end_date
            LEFT JOIN tmp_report_quality qlag8
                ON g.ts_code = qlag8.ts_code
               AND g.lag_8report_end_date = qlag8.report_end_date
            LEFT JOIN tmp_report_quality qsame1
                ON g.ts_code = qsame1.ts_code
               AND g.same_period_1y_end_date = qsame1.report_end_date
            WHERE g.trade_date BETWEEN ? AND ?
        ) s
        WHERE target.ts_code = s.ts_code
          AND target.trade_date = s.trade_date
    """


def update_status_flags(con: duckdb.DuckDBPyConnection, start_date: str, end_date: str) -> None:
    con.execute(
        """
        UPDATE derived_financial_growth AS g
        SET
            roe_yoy_improving_flag = s.roe_yoy_improving_flag,
            gross_margin_yoy_improving_flag = s.gross_margin_yoy_improving_flag,
            debt_to_assets_yoy_increasing_flag = s.debt_to_assets_yoy_increasing_flag,
            ocf_to_profit_yoy_improving_flag = s.ocf_to_profit_yoy_improving_flag,
            negative_profit_continued_flag = s.negative_profit_continued_flag,
            negative_ocf_continued_flag = s.negative_ocf_continued_flag,
            high_goodwill_continued_flag = s.high_goodwill_continued_flag,
            high_leverage_continued_flag = s.high_leverage_continued_flag
        FROM (
            SELECT
                g.ts_code,
                g.trade_date,
                g.roe_yoy_diff_asof > 0 AS roe_yoy_improving_flag,
                g.gross_margin_yoy_diff_asof > 0 AS gross_margin_yoy_improving_flag,
                g.debt_to_assets_yoy_diff_asof > 0 AS debt_to_assets_yoy_increasing_flag,
                g.ocf_to_profit_yoy_diff_asof > 0 AS ocf_to_profit_yoy_improving_flag,
                coalesce(cur.negative_net_profit_flag, false)
                    AND coalesce(prev.negative_net_profit_flag, false) AS negative_profit_continued_flag,
                coalesce(cur.negative_ocf_flag, false)
                    AND coalesce(prev.negative_ocf_flag, false) AS negative_ocf_continued_flag,
                coalesce(cur.high_goodwill_flag, false)
                    AND coalesce(prev.high_goodwill_flag, false) AS high_goodwill_continued_flag,
                coalesce(cur.high_leverage_flag, false)
                    AND coalesce(prev.high_leverage_flag, false) AS high_leverage_continued_flag
            FROM derived_financial_growth g
            LEFT JOIN tmp_report_quality cur
                ON g.ts_code = cur.ts_code
               AND g.current_report_end_date = cur.report_end_date
            LEFT JOIN tmp_report_quality prev
                ON g.ts_code = prev.ts_code
               AND g.prev_report_end_date = prev.report_end_date
            WHERE g.trade_date BETWEEN ? AND ?
        ) s
        WHERE g.ts_code = s.ts_code
          AND g.trade_date = s.trade_date
        """,
        [start_date, end_date],
    )


def main() -> None:
    fields = quality_numeric_fields()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE tmp_report_quality AS
        SELECT
            a.ts_code,
            a.latest_report_end_date AS report_end_date,
            q.*
        FROM derived_financial_asof a
        JOIN derived_financial_quality q
          ON a.ts_code = q.ts_code
         AND a.trade_date = q.trade_date
        WHERE a.latest_report_end_date IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY a.ts_code, a.latest_report_end_date
            ORDER BY a.trade_date DESC
        ) = 1
        """
    )
    chunks = chunked(fields, 10)
    start_year = int(os.environ.get("START_YEAR", "2006"))
    log_mode = "a" if start_year > 2006 else "w"
    with LOG_PATH.open(log_mode, encoding="utf-8") as handle:
        for year in range(start_year, 2027):
            start_date = f"{year}-01-01"
            end_date = "2026-05-26" if year == 2026 else f"{year}-12-31"
            for chunk_index, chunk in enumerate(chunks, start=1):
                started_at = datetime.now().isoformat(timespec="seconds")
                con.execute(build_update_sql(chunk), [start_date, end_date])
                payload = {
                    "year": year,
                    "chunk": chunk_index,
                    "chunk_count": len(chunks),
                    "field_count": len(chunk),
                    "start_date": start_date,
                    "end_date": end_date,
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
                handle.flush()
                print(json.dumps(payload, ensure_ascii=False))
            update_status_flags(con, start_date, end_date)


if __name__ == "__main__":
    main()
