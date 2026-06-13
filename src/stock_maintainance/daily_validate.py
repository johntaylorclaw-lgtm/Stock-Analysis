from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from .config import load_pipeline
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

NEW_STOCK_COVERAGE_TABLES = {
    "stock_daily",
    "stock_daily_basic",
    "stock_adj_factor",
    "stock_limit_price",
    "stock_moneyflow_daily",
}

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

DEFAULT_EXPECTED_DELAY_TABLES = {
    "margin_detail",
    "northbound_holding",
}

ROW_COUNT_MONITOR_TABLES = {
    "stock_daily",
    "stock_daily_basic",
    "stock_adj_factor",
    "stock_limit_price",
    "stock_moneyflow_daily",
    "margin_detail",
    "northbound_daily",
    "northbound_holding",
    "index_daily",
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
    "derived_ownership_governance",
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
        SELECT DISTINCT CAST(cal_date AS DATE) AS trade_date
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


def _table_max_date_on_or_before(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    date_col: str,
    cutoff_date: str,
) -> str | None:
    row = con.execute(
        f"""
        SELECT max(CAST({quote_ident(date_col)} AS DATE))
        FROM {quote_ident(table_name)}
        WHERE CAST({quote_ident(date_col)} AS DATE) <= CAST(? AS DATE)
        """,
        [cutoff_date],
    ).fetchone()
    return _as_date(row[0]) if row else None


def _table_lag_dates(con: duckdb.DuckDBPyConnection, max_date: str | None, latest_trade: str) -> list[str]:
    if max_date is None:
        return []
    return _trade_dates(
        con,
        "CAST(cal_date AS DATE) > CAST(? AS DATE) AND CAST(cal_date AS DATE) <= CAST(? AS DATE)",
        [max_date, latest_trade],
    )


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


def _historical_row_count_stats(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    date_col: str,
    trade_date: str,
    lookback_days: int,
) -> dict[str, Any] | None:
    rows = con.execute(
        f"""
        WITH prior_dates AS (
            SELECT CAST({quote_ident(date_col)} AS DATE) AS target_date, count(*) AS row_count
            FROM {quote_ident(table_name)}
            WHERE CAST({quote_ident(date_col)} AS DATE) < CAST(? AS DATE)
            GROUP BY 1
            ORDER BY 1 DESC
            LIMIT ?
        )
        SELECT count(*) AS day_count, avg(row_count) AS avg_rows, min(row_count) AS min_rows, max(row_count) AS max_rows
        FROM prior_dates
        """,
        [trade_date, lookback_days],
    ).fetchone()
    if not rows or int(rows[0] or 0) == 0:
        return None
    return {
        "lookback_day_count": int(rows[0]),
        "avg_rows": float(rows[1] or 0),
        "min_rows": int(rows[2] or 0),
        "max_rows": int(rows[3] or 0),
    }


def _expected_delay_tables() -> set[str]:
    try:
        phases = load_pipeline().get("daily_policy", {}).get("api_release_phases", {})
    except Exception:  # noqa: BLE001 - validation must still work in isolated test fixtures.
        return set(DEFAULT_EXPECTED_DELAY_TABLES)
    next_day_apis = set(phases.get("next_day", {}).get("apis", []))
    table_by_api = {
        "margin_detail": "margin_detail",
        "hk_hold": "northbound_holding",
    }
    return {table_by_api[api] for api in next_day_apis if api in table_by_api} or set(DEFAULT_EXPECTED_DELAY_TABLES)


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


def _new_stock_coverage_issues(
    con: duckdb.DuckDBPyConnection,
    table_names: list[str],
    cutoff_date: str,
    latest_trade: str,
    sample_limit: int = 20,
) -> list[dict[str, Any]]:
    if not _table_exists(con, "stock_basic_info"):
        return []
    stock_columns = set(_columns(con, "stock_basic_info"))
    if not {"ts_code", "list_date"}.issubset(stock_columns):
        return []
    listed_filter = (
        "CAST(b.list_date AS DATE) < CAST(? AS DATE) "
        "AND NOT regexp_matches(b.ts_code, '^(900[0-9]{3}\\.SH|20[0-9]{4}\\.SZ)$')"
    )
    params: list[Any] = [cutoff_date, latest_trade, sample_limit]
    if "delist_date" in stock_columns:
        listed_filter += " AND (b.delist_date IS NULL OR CAST(b.delist_date AS DATE) >= CAST(? AS DATE))"
        params.insert(2, latest_trade)
    if "list_status" in stock_columns:
        listed_filter += " AND coalesce(b.list_status, 'L') IN ('L', 'D')"
    issues: list[dict[str, Any]] = []
    for table in table_names:
        if table not in NEW_STOCK_COVERAGE_TABLES or not _table_exists(con, table):
            continue
        columns = set(_columns(con, table))
        if not {"ts_code", "trade_date"}.issubset(columns):
            continue
        query_params = params.copy()
        rows = con.execute(
            f"""
            WITH listed AS (
                SELECT b.ts_code, CAST(b.list_date AS DATE) AS list_date
                FROM stock_basic_info b
                WHERE {listed_filter}
            ),
            covered AS (
                SELECT DISTINCT t.ts_code
                FROM {quote_ident(table)} t
                JOIN listed b ON t.ts_code = b.ts_code
                WHERE CAST(t.trade_date AS DATE) >= b.list_date
                  AND CAST(t.trade_date AS DATE) <= CAST(? AS DATE)
            ),
            missing AS (
                SELECT l.ts_code, l.list_date
                FROM listed l
                LEFT JOIN covered c USING (ts_code)
                WHERE c.ts_code IS NULL
            )
            SELECT count(*) OVER () AS missing_count, ts_code, list_date
            FROM missing
            ORDER BY list_date, ts_code
            LIMIT ?
            """,
            query_params,
        ).fetchall()
        if not rows:
            continue
        issues.append(
            {
                "table": table,
                "missing_stock_count": int(rows[0][0]),
                "sample": [
                    {"ts_code": row[1], "list_date": _as_date(row[2])}
                    for row in rows
                ],
            }
        )
    return issues


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
        f"- 有隐藏滞后的表：{summary['table_lag_issue_count']}",
        f"- 新股覆盖问题：{summary['new_stock_coverage_issue_count']}",
        f"- 有重复键的表：{summary['duplicate_issue_table_count']}",
        f"- 股票级衍生行数低于 spine 的表：{summary['stock_level_row_count_issue_table_count']}",
        f"- 预期 T+1 延迟表：{summary['expected_delay_table_count']}",
        f"- 行数波动预警表：{summary['row_count_warning_table_count']}",
        "",
        "## 表级结果",
        "",
        "| 表 | 分组 | 最大日期 | 目标日期缺口 | 隐藏滞后 | 预期延迟 | 行数预警 | 重复键 | 空 ts_code | 最新/目标行数 | 结果 |",
        "|---|---|---|---:|---:|---|---|---:|---:|---:|---|",
    ]
    for item in report["tables"]:
        latest_rows = item.get("latest_target_rows")
        lines.append(
            f"| `{item['table']}` | {item.get('group', '')} | {item.get('max_date') or ''} | "
            f"{len(item.get('missing_target_dates', []))} | {len(item.get('hidden_lag_dates', []))} | "
            f"{'是' if item.get('expected_delay_missing') or item.get('expected_delay_lag') else '否'} | "
            f"{'是' if item.get('row_count_warning') else '否'} | {item.get('duplicate_key_count', '')} | "
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
            if item.get("expected_delay_missing"):
                lines.append("- 缺口归类：预期 T+1 数据源延迟，不阻塞当日晚间日批")
            if item.get("hidden_lag_dates"):
                lines.append(f"- 最大日期落后且不在锚点补数窗口内：{', '.join(item['hidden_lag_dates'])}")
            if item.get("expected_delay_lag"):
                lines.append("- 滞后归类：预期 T+1 数据源延迟，不阻塞当日晚间日批")
            if item.get("row_count_warning"):
                lines.append(f"- 行数波动：{item['row_count_warning']}")
            if item.get("duplicate_key_count"):
                lines.append(f"- 重复键数量：{item['duplicate_key_count']}")
            if item.get("stock_level_row_count_issue"):
                lines.append(f"- 股票级行数低于 spine：{item['stock_level_row_count_issue']}")
    if report.get("new_stock_coverage_issues"):
        lines.extend(["", "## 新股覆盖检查", ""])
        for issue in report["new_stock_coverage_issues"]:
            sample = ", ".join(f"{item['ts_code']}({item['list_date']})" for item in issue["sample"])
            lines.append(
                f"- `{issue['table']}`：{issue['missing_stock_count']} 只主数据已上市股票没有上市日起至最新交易日的覆盖记录；样例：{sample}"
            )
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
    row_count_warning_threshold: float = 0.8,
    row_count_lookback_days: int = 5,
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
                anchor_date = _table_max_date_on_or_before(con, anchor_table, anchor_date_col, latest_trade)
        empty_anchor = anchor_date is None
        if anchor_date is None:
            anchor_date = latest_trade

        incremental_dates = _trade_dates(
            con,
            "CAST(cal_date AS DATE) > CAST(? AS DATE) AND CAST(cal_date AS DATE) <= CAST(? AS DATE)",
            [anchor_date, latest_trade],
        )
        if validation_days <= 0:
            validation_dates = []
        else:
            validation_dates = _trade_dates(
                con,
                "CAST(cal_date AS DATE) <= CAST(? AS DATE)",
                [anchor_date],
            )[-validation_days:]
        target_dates = [*validation_dates, *incremental_dates]

        spine_counts: dict[str, int] = {}
        if _table_exists(con, "derived_daily_spine"):
            for day in target_dates:
                spine_counts[day] = _row_count_for_date(con, "derived_daily_spine", "trade_date", day)

        expected_delay_tables = _expected_delay_tables()
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
            lag_dates = _table_lag_dates(con, max_date, latest_trade) if group != "base_periodic" else []
            expected_delay_missing = bool(
                table in expected_delay_tables
                and missing_target_dates
                and set(missing_target_dates).issubset({latest_trade})
            )
            expected_delay_lag = bool(
                table in expected_delay_tables
                and lag_dates
                and set(lag_dates).issubset({latest_trade})
            )
            hidden_lag_dates = []
            if lag_dates and not expected_delay_lag:
                target_date_set = set(target_dates)
                hidden_lag_dates = [day for day in lag_dates if day not in target_date_set]
            duplicate_key_count = 0 if group == "feature_view" else _duplicate_key_count(con, table, columns, date_col, expected_dates)
            null_ts_code_count = 0 if group == "feature_view" else _null_ts_code_count(con, table, columns, date_col, expected_dates)
            latest_target_rows = rows_by_date.get(target_dates[-1]) if target_dates else None
            row_count_warning = None
            if (
                table in ROW_COUNT_MONITOR_TABLES
                and latest_target_rows is not None
                and latest_target_rows > 0
                and target_dates
            ):
                stats = _historical_row_count_stats(con, table, date_col, target_dates[-1], row_count_lookback_days)
                if stats and stats["avg_rows"] > 0 and latest_target_rows < stats["avg_rows"] * row_count_warning_threshold:
                    row_count_warning = (
                        f"{target_dates[-1]} rows={latest_target_rows}, "
                        f"prior_{stats['lookback_day_count']}_day_avg={stats['avg_rows']:.1f}, "
                        f"threshold={row_count_warning_threshold:.2f}"
                    )
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
            blocking_missing_dates = [] if expected_delay_missing else missing_target_dates
            if blocking_missing_dates or (duplicate_key_count or 0) > 0 or stock_level_issue:
                status = "fail"
            elif row_count_warning or expected_delay_missing or expected_delay_lag or hidden_lag_dates:
                status = "warning"
            table_reports.append(
                {
                    "table": table,
                    "group": group,
                    "date_column": date_col,
                    "max_date": max_date,
                    "rows_by_target_date": rows_by_date,
                    "lag_dates_to_latest": lag_dates,
                    "hidden_lag_dates": hidden_lag_dates,
                    "latest_target_rows": latest_target_rows,
                    "missing_target_dates": missing_target_dates,
                    "expected_delay_missing": expected_delay_missing,
                    "expected_delay_lag": expected_delay_lag,
                    "duplicate_key_count": duplicate_key_count,
                    "null_ts_code_count": null_ts_code_count,
                    "row_count_warning": row_count_warning,
                    "stock_level_row_count_issue": stock_level_issue,
                    "status": status,
                }
            )

        new_stock_cutoff = incremental_dates[0] if incremental_dates else latest_trade
        new_stock_coverage_issues = _new_stock_coverage_issues(
            con,
            table_names,
            new_stock_cutoff,
            latest_trade,
        )
    requires_confirmation = len(incremental_dates) > max_auto_trade_days
    missing_tables = [item for item in table_reports if item.get("error") == "missing_table"]
    coverage_issues = [item for item in table_reports if item.get("missing_target_dates") and not item.get("expected_delay_missing")]
    table_lag_issues = [item for item in table_reports if item.get("hidden_lag_dates")]
    duplicate_issues = [item for item in table_reports if item.get("duplicate_key_count")]
    row_count_issues = [item for item in table_reports if item.get("stock_level_row_count_issue")]
    expected_delay_issues = [item for item in table_reports if item.get("expected_delay_missing") or item.get("expected_delay_lag")]
    row_count_warnings = [item for item in table_reports if item.get("row_count_warning")]
    no_target_data = not any(item.get("max_date") for item in table_reports)
    blocked_empty_anchor = empty_anchor and no_target_data
    if blocked_empty_anchor:
        status = "blocked"
    elif requires_confirmation:
        status = "blocked"
    elif missing_tables or coverage_issues or duplicate_issues or row_count_issues or table_lag_issues or new_stock_coverage_issues:
        status = "warning"
    elif expected_delay_issues or row_count_warnings:
        status = "pass"
    else:
        status = "pass"
    summary = {
        "status": status,
        "requires_confirmation": requires_confirmation,
        "empty_anchor": empty_anchor,
        "blocked_empty_anchor": blocked_empty_anchor,
        "incremental_trade_day_count": len(incremental_dates),
        "table_count": len(table_reports),
        "missing_table_count": len(missing_tables),
        "coverage_issue_table_count": len(coverage_issues),
        "table_lag_issue_count": len(table_lag_issues),
        "new_stock_coverage_issue_count": len(new_stock_coverage_issues),
        "duplicate_issue_table_count": len(duplicate_issues),
        "stock_level_row_count_issue_table_count": len(row_count_issues),
        "expected_delay_table_count": len(expected_delay_issues),
        "row_count_warning_table_count": len(row_count_warnings),
        "problem_tables": [item["table"] for item in table_reports if item["status"] != "pass"],
    }
    if blocked_empty_anchor:
        summary["blocked_reason"] = "no stock_daily or derived_daily_spine anchor data found; run base initialization before daily validation"
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
        "new_stock_coverage_issues": new_stock_coverage_issues,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(_render_markdown(report), encoding="utf-8")
    return DailyValidationResult(report=report, json_path=output_json, markdown_path=output_md)
