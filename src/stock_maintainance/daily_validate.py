from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from .database import DB_PATH, connect
from .incremental_compare import DEFAULT_COMPARE_TABLES
from .paths import REPORTS_DIR
from .schema import quote_ident


DAILY_BASE_TABLES = [
    "stock_daily",
    "stock_daily_basic",
    "stock_adj_factor",
    "stock_limit_price",
    "stock_moneyflow_daily",
    "margin_detail",
    "northbound_daily",
    "northbound_holding",
    "top_list_daily",
    "top_inst_detail",
    "index_daily",
]

PERIODIC_BASE_TABLES = [
    "index_weight",
]

FEATURE_VIEWS = [
    "stock_features_core",
    "stock_features_plus",
    "stock_features_full",
]

EVENT_OR_DETAIL_TABLES = {
    "top_list_daily",
    "top_inst_detail",
}

STOCK_LEVEL_DERIVED_TABLES = {
    "derived_daily_spine",
    "derived_price_technical",
    "derived_volume_liquidity",
    "derived_return_momentum",
    "derived_volatility_risk",
    "derived_trading_constraint",
    "derived_valuation_size",
    "derived_financial_asof",
    "derived_financial_quality",
    "derived_financial_growth",
    "derived_capital_flow",
    "derived_sector_concept_context",
    "derived_index_market_context",
    "derived_cross_sectional",
    "derived_corporate_action",
    "derived_composite_state",
}


@dataclass(frozen=True)
class DailyValidationResult:
    report: dict[str, Any]
    json_path: Path
    markdown_path: Path

    @property
    def passed(self) -> bool:
        return self.report["summary"]["status"] == "pass"


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT count(*)
            FROM information_schema.tables
            WHERE table_name = ?
            """,
            [table_name],
        ).fetchone()[0]
    )


def _columns(con: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
    return [str(row[1]) for row in con.execute(f"PRAGMA table_info({quote_ident(table_name)})").fetchall()]


def _date_column(columns: list[str]) -> str | None:
    if "trade_date" in columns:
        return "trade_date"
    if "cal_date" in columns:
        return "cal_date"
    return None


def _as_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _trade_dates(con: duckdb.DuckDBPyConnection, where_sql: str, params: list[Any]) -> list[str]:
    rows = con.execute(
        f"""
        SELECT CAST(cal_date AS DATE) AS trade_date
        FROM trade_calendar
        WHERE is_open = 1 AND {where_sql}
        ORDER BY CAST(cal_date AS DATE)
        """,
        params,
    ).fetchall()
    return [_as_date(row[0]) or "" for row in rows]


def _latest_trade_date(con: duckdb.DuckDBPyConnection, as_of_date: str) -> str | None:
    row = con.execute(
        """
        SELECT max(CAST(cal_date AS DATE))
        FROM trade_calendar
        WHERE is_open = 1 AND CAST(cal_date AS DATE) <= CAST(? AS DATE)
        """,
        [as_of_date],
    ).fetchone()
    return _as_date(row[0]) if row else None


def _table_max_date(con: duckdb.DuckDBPyConnection, table_name: str, date_col: str) -> str | None:
    row = con.execute(
        f"SELECT max(CAST({quote_ident(date_col)} AS DATE)) FROM {quote_ident(table_name)}"
    ).fetchone()
    return _as_date(row[0]) if row else None


def _row_count_for_date(con: duckdb.DuckDBPyConnection, table_name: str, date_col: str, trade_date: str) -> int:
    return int(
        con.execute(
            f"""
            SELECT count(*)
            FROM {quote_ident(table_name)}
            WHERE CAST({quote_ident(date_col)} AS DATE) = CAST(? AS DATE)
            """,
            [trade_date],
        ).fetchone()[0]
    )


def _key_row_count_for_date(con: duckdb.DuckDBPyConnection, table_name: str, date_col: str, trade_date: str) -> int:
    return int(
        con.execute(
            f"""
            SELECT count(*)
            FROM (
                SELECT ts_code, {quote_ident(date_col)}
                FROM {quote_ident(table_name)}
                WHERE CAST({quote_ident(date_col)} AS DATE) = CAST(? AS DATE)
            )
            """,
            [trade_date],
        ).fetchone()[0]
    )


def _duplicate_key_count(con: duckdb.DuckDBPyConnection, table_name: str, columns: list[str], date_col: str, dates: list[str]) -> int | None:
    if not dates or table_name in EVENT_OR_DETAIL_TABLES:
        return None
    if {"ts_code", date_col}.issubset(columns):
        keys = ["ts_code", date_col]
    elif {"industry_level", "industry_code", date_col}.issubset(columns):
        keys = ["industry_level", "industry_code", date_col]
    elif {"concept_id", date_col}.issubset(columns):
        keys = ["concept_id", date_col]
    elif {"index_code", date_col}.issubset(columns):
        keys = ["index_code", date_col]
    elif date_col in columns:
        keys = [date_col]
    else:
        return None
    key_sql = ", ".join(quote_ident(col) for col in keys)
    return int(
        con.execute(
            f"""
            SELECT count(*)
            FROM (
                SELECT {key_sql}, count(*) AS row_count
                FROM {quote_ident(table_name)}
                WHERE CAST({quote_ident(date_col)} AS DATE) IN (
                    SELECT CAST(value AS DATE) FROM unnest(?::VARCHAR[]) AS t(value)
                )
                GROUP BY {key_sql}
                HAVING count(*) > 1
            )
            """,
            [dates],
        ).fetchone()[0]
    )


def _null_ts_code_count(con: duckdb.DuckDBPyConnection, table_name: str, columns: list[str], date_col: str, dates: list[str]) -> int | None:
    if not dates or "ts_code" not in columns:
        return None
    return int(
        con.execute(
            f"""
            SELECT count(*)
            FROM {quote_ident(table_name)}
            WHERE CAST({quote_ident(date_col)} AS DATE) IN (
                SELECT CAST(value AS DATE) FROM unnest(?::VARCHAR[]) AS t(value)
            )
            AND ts_code IS NULL
            """,
            [dates],
        ).fetchone()[0]
    )


def _table_group(table_name: str) -> str:
    if table_name in DAILY_BASE_TABLES:
        return "base_daily"
    if table_name in PERIODIC_BASE_TABLES:
        return "base_periodic"
    if table_name in FEATURE_VIEWS:
        return "feature_view"
    return "derived"


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Daily-Light 验证报告",
        "",
        f"生成时间：{report['generated_at']}",
        f"截至日期：`{report['as_of_date']}`",
        f"最新交易日：`{report['latest_trade_date']}`",
        f"当前锚点日期：`{report['anchor_data_date']}`",
        f"结果：`{summary['status']}`",
        "",
        "## 窗口判断",
        "",
        f"- 自动补数上限：{report['max_auto_trade_days']} 个交易日",
        f"- 校验日期：{', '.join(report['validation_dates']) or '无'}",
        f"- 待增量日期：{', '.join(report['incremental_dates']) or '无'}",
        f"- 待增量交易日数：{summary['incremental_trade_day_count']}",
        f"- 是否需要显式确认：{'是' if summary['requires_confirmation'] else '否'}",
        "",
        "## 汇总",
        "",
        f"- 表数量：{summary['table_count']}",
        f"- 缺失表：{summary['missing_table_count']}",
        f"- 有目标日期缺口的表：{summary['coverage_issue_table_count']}",
        f"- 有重复键的表：{summary['duplicate_issue_table_count']}",
        f"- 股票级衍生行数低于 spine 的表：{summary['stock_level_row_count_issue_table_count']}",
        "",
        "## 表级结果",
        "",
        "| 表 | 分组 | 最大日期 | 目标日期缺口 | 重复键 | 空 ts_code | 最新/目标行数 | 结果 |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for item in report["tables"]:
        latest_rows = item.get("latest_target_rows")
        lines.append(
            f"| `{item['table']}` | {item.get('group', '')} | {item.get('max_date') or ''} | "
            f"{len(item.get('missing_target_dates', []))} | {item.get('duplicate_key_count', '')} | "
            f"{item.get('null_ts_code_count', '')} | {latest_rows if latest_rows is not None else ''} | {item['status']} |"
        )
    problem_tables = [item for item in report["tables"] if item["status"] != "pass"]
    if problem_tables:
        lines.extend(["", "## 问题明细", ""])
        for item in problem_tables:
            lines.append(f"### {item['table']}")
            if item.get("error"):
                lines.append(f"- 错误：{item['error']}")
            if item.get("missing_target_dates"):
                lines.append(f"- 目标日期无数据：{', '.join(item['missing_target_dates'])}")
            if item.get("duplicate_key_count"):
                lines.append(f"- 重复键数量：{item['duplicate_key_count']}")
            if item.get("stock_level_row_count_issue"):
                lines.append(f"- 股票级行数低于 spine：{item['stock_level_row_count_issue']}")
    lines.append("")
    return "\n".join(lines)


def validate_daily(
    *,
    as_of_date: str | None = None,
    max_auto_trade_days: int = 10,
    validation_days: int = 1,
    tables: list[str] | None = None,
    output_prefix: str = "validate_daily_report",
    db_path: Path = DB_PATH,
) -> DailyValidationResult:
    as_of = as_of_date or date.today().isoformat()
    table_names = tables or [*DAILY_BASE_TABLES, *PERIODIC_BASE_TABLES, *DEFAULT_COMPARE_TABLES, *FEATURE_VIEWS]
    output_json = REPORTS_DIR / f"{output_prefix}.json"
    output_md = REPORTS_DIR / f"{output_prefix}.md"

    with connect(db_path) as con:
        if not _table_exists(con, "trade_calendar"):
            raise ValueError("trade_calendar is required for daily validation")
        latest_trade = _latest_trade_date(con, as_of)
        if latest_trade is None:
            raise ValueError(f"no open trade date found on or before {as_of}")

        anchor_table = "derived_daily_spine" if _table_exists(con, "derived_daily_spine") else "stock_daily"
        anchor_date = None
        if _table_exists(con, anchor_table):
            anchor_cols = _columns(con, anchor_table)
            anchor_date_col = _date_column(anchor_cols)
            if anchor_date_col:
                anchor_date = _table_max_date(con, anchor_table, anchor_date_col)
        if anchor_date is None:
            anchor_date = latest_trade

        incremental_dates = _trade_dates(
            con,
            "CAST(cal_date AS DATE) > CAST(? AS DATE) AND CAST(cal_date AS DATE) <= CAST(? AS DATE)",
            [anchor_date, latest_trade],
        )
        validation_dates = _trade_dates(
            con,
            "CAST(cal_date AS DATE) <= CAST(? AS DATE)",
            [anchor_date],
        )[-max(validation_days, 0) :]
        target_dates = [*validation_dates, *incremental_dates]

        spine_counts: dict[str, int] = {}
        if _table_exists(con, "derived_daily_spine"):
            for day in target_dates:
                spine_counts[day] = _row_count_for_date(con, "derived_daily_spine", "trade_date", day)

        table_reports: list[dict[str, Any]] = []
        for table in table_names:
            if not _table_exists(con, table):
                table_reports.append({"table": table, "group": _table_group(table), "status": "fail", "error": "missing_table"})
                continue
            columns = _columns(con, table)
            date_col = _date_column(columns)
            if date_col is None:
                table_reports.append({"table": table, "group": _table_group(table), "status": "pass", "max_date": None})
                continue
            max_date = _table_max_date(con, table, date_col)
            group = _table_group(table)
            expected_dates = target_dates if group != "base_periodic" else validation_dates
            if group == "feature_view" and "ts_code" in columns:
                rows_by_date = {day: _key_row_count_for_date(con, table, date_col, day) for day in expected_dates}
            else:
                rows_by_date = {day: _row_count_for_date(con, table, date_col, day) for day in expected_dates}
            missing_target_dates = [day for day, count in rows_by_date.items() if count == 0 and group != "base_periodic"]
            duplicate_key_count = 0 if group == "feature_view" else _duplicate_key_count(con, table, columns, date_col, expected_dates)
            null_ts_code_count = 0 if group == "feature_view" else _null_ts_code_count(con, table, columns, date_col, expected_dates)
            latest_target_rows = rows_by_date.get(target_dates[-1]) if target_dates else None
            stock_level_issue = None
            if table in STOCK_LEVEL_DERIVED_TABLES and table != "derived_daily_spine":
                bad_days = []
                for day, spine_count in spine_counts.items():
                    row_count = rows_by_date.get(day)
                    if row_count is not None and spine_count and row_count < spine_count:
                        bad_days.append(f"{day}: {row_count}/{spine_count}")
                if bad_days:
                    stock_level_issue = "; ".join(bad_days)
            status = "pass"
            if missing_target_dates or (duplicate_key_count or 0) > 0 or stock_level_issue:
                status = "fail"
            table_reports.append(
                {
                    "table": table,
                    "group": group,
                    "date_column": date_col,
                    "max_date": max_date,
                    "rows_by_target_date": rows_by_date,
                    "latest_target_rows": latest_target_rows,
                    "missing_target_dates": missing_target_dates,
                    "duplicate_key_count": duplicate_key_count,
                    "null_ts_code_count": null_ts_code_count,
                    "stock_level_row_count_issue": stock_level_issue,
                    "status": status,
                }
            )

    requires_confirmation = len(incremental_dates) > max_auto_trade_days
    missing_tables = [item for item in table_reports if item.get("error") == "missing_table"]
    coverage_issues = [item for item in table_reports if item.get("missing_target_dates")]
    duplicate_issues = [item for item in table_reports if item.get("duplicate_key_count")]
    row_count_issues = [item for item in table_reports if item.get("stock_level_row_count_issue")]
    if requires_confirmation:
        status = "blocked"
    elif missing_tables or coverage_issues or duplicate_issues or row_count_issues:
        status = "warning"
    else:
        status = "pass"
    summary = {
        "status": status,
        "requires_confirmation": requires_confirmation,
        "incremental_trade_day_count": len(incremental_dates),
        "table_count": len(table_reports),
        "missing_table_count": len(missing_tables),
        "coverage_issue_table_count": len(coverage_issues),
        "duplicate_issue_table_count": len(duplicate_issues),
        "stock_level_row_count_issue_table_count": len(row_count_issues),
        "problem_tables": [item["table"] for item in table_reports if item["status"] != "pass"],
    }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "latest_trade_date": latest_trade,
        "anchor_data_date": anchor_date,
        "max_auto_trade_days": max_auto_trade_days,
        "validation_days": validation_days,
        "validation_dates": validation_dates,
        "incremental_dates": incremental_dates,
        "summary": summary,
        "tables": table_reports,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(_render_markdown(report), encoding="utf-8")
    return DailyValidationResult(report=report, json_path=output_json, markdown_path=output_md)
