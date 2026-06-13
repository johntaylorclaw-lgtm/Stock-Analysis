from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .database import DB_PATH, connect
from .incremental_compare import DEFAULT_COMPARE_TABLES, compare_incremental_window
from .paths import REPORTS_DIR
from .schema import quote_ident


@dataclass(frozen=True)
class WeeklyFullResult:
    report: dict[str, Any]
    json_path: Path
    markdown_path: Path

    @property
    def passed(self) -> bool:
        return self.report["summary"]["status"] == "pass"


def _table_exists(con, table_name: str) -> bool:
    return bool(
        con.execute(
            "SELECT count(1) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()[0]
    )


def _open_dates(con, end_date: str, days: int) -> list[str]:
    rows = con.execute(
        """
        SELECT DISTINCT CAST(cal_date AS DATE)
        FROM trade_calendar
        WHERE is_open = 1
          AND CAST(cal_date AS DATE) <= CAST(? AS DATE)
        ORDER BY CAST(cal_date AS DATE) DESC
        LIMIT ?
        """,
        [end_date, days],
    ).fetchall()
    return [row[0].isoformat() for row in reversed(rows)]


def _latest_trade_date(con, as_of_date: str) -> str:
    row = con.execute(
        """
        SELECT max(CAST(cal_date AS DATE))
        FROM trade_calendar
        WHERE is_open = 1
          AND CAST(cal_date AS DATE) <= CAST(? AS DATE)
        """,
        [as_of_date],
    ).fetchone()
    if not row or row[0] is None:
        raise ValueError(f"no open trade date found on or before {as_of_date}")
    return row[0].isoformat()


def _snapshot_missing(con, tables: list[str], snapshot_prefix: str) -> list[str]:
    missing = []
    for table in tables:
        if not _table_exists(con, f"{snapshot_prefix}{table}"):
            missing.append(table)
    return missing


def _snapshot_common_bounds(con, tables: list[str], snapshot_prefix: str) -> tuple[str | None, str | None]:
    min_dates = []
    max_dates = []
    for table in tables:
        snapshot = f"{snapshot_prefix}{table}"
        if not _table_exists(con, snapshot):
            continue
        cols = [row[1] for row in con.execute(f"PRAGMA table_info({quote_ident(snapshot)})").fetchall()]
        if "trade_date" not in cols:
            continue
        row = con.execute(
            f"SELECT min(CAST(trade_date AS DATE)), max(CAST(trade_date AS DATE)) FROM {quote_ident(snapshot)}"
        ).fetchone()
        if row and row[0] is not None and row[1] is not None:
            min_dates.append(row[0].isoformat())
            max_dates.append(row[1].isoformat())
    if not min_dates or not max_dates:
        return None, None
    return max(min_dates), min(max_dates)


def _create_snapshot_from_current(
    *,
    tables: list[str],
    start_date: str,
    end_date: str,
    snapshot_prefix: str,
    db_path: Path,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    with connect(db_path) as con:
        for table in tables:
            snapshot = f"{snapshot_prefix}{table}"
            con.execute(f"DROP TABLE IF EXISTS {quote_ident(snapshot)}")
            con.execute(
                f"""
                CREATE TABLE {quote_ident(snapshot)} AS
                SELECT *
                FROM {quote_ident(table)}
                WHERE trade_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
                """,
                [start_date, end_date],
            )
            counts[table] = int(con.execute(f"SELECT count(1) FROM {quote_ident(snapshot)}").fetchone()[0])
    return counts


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Weekly-Full 验证报告",
        "",
        f"生成时间：{report['generated_at']}",
        f"截至日期：`{report['as_of_date']}`",
        f"最新交易日：`{report['latest_trade_date']}`",
        f"参照窗口：`{report['reference_start_date']}` 至 `{report['reference_end_date']}`",
        f"请求比较窗口：`{report['requested_compare_start_date']}` 至 `{report['requested_compare_end_date']}`",
        f"快照共同窗口：`{report['snapshot_common_start_date']}` 至 `{report['snapshot_common_end_date']}`",
        f"比较窗口：`{report['compare_start_date']}` 至 `{report['compare_end_date']}`",
        f"结果：`{summary['status']}`",
        "",
        "## 汇总",
        "",
        f"- 表数量：{summary['table_count']}",
        f"- 快照前缀：`{report['snapshot_prefix']}`",
        f"- 缺失快照表：{len(report['missing_snapshot_tables'])}",
        f"- dry-run：{'是' if report['dry_run'] else '否'}",
    ]
    if report.get("compare_report"):
        cmp_summary = report["compare_report"]["summary"]
        lines.extend(
            [
                "",
                "## 字段级对照",
                "",
                f"- 通过表：{cmp_summary['pass_table_count']}",
                f"- 失败表：{cmp_summary['fail_table_count']}",
                f"- 键缺失/额外行：{cmp_summary['missing_or_extra_key_rows']}",
                f"- 差异字段数：{cmp_summary['mismatch_column_count']}",
                f"- 差异单元格数：{cmp_summary['mismatch_cell_count']}",
            ]
        )
    if report["missing_snapshot_tables"]:
        lines.extend(["", "## 缺失快照表", ""])
        for table in report["missing_snapshot_tables"]:
            lines.append(f"- `{table}`")
    if summary.get("blocked_reason"):
        lines.extend(["", "## 阻塞原因", "", summary["blocked_reason"]])
    lines.append("")
    return "\n".join(lines)


def _write_report(report: dict[str, Any], output_prefix: str) -> WeeklyFullResult:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"{output_prefix}.json"
    md_path = REPORTS_DIR / f"{output_prefix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return WeeklyFullResult(report=report, json_path=json_path, markdown_path=md_path)


def run_weekly_full(
    *,
    as_of_date: str | None = None,
    reference_days: int = 40,
    compare_days: int = 10,
    tables: list[str] | None = None,
    snapshot_prefix: str = "audit_tmp_phase4_full_",
    output_prefix: str = "weekly_full_run",
    dry_run: bool = False,
    create_snapshot_from_current: bool = False,
    auto_create_missing_snapshot: bool = False,
    db_path: Path = DB_PATH,
) -> WeeklyFullResult:
    as_of = as_of_date or date.today().isoformat()
    table_names = tables or DEFAULT_COMPARE_TABLES
    with connect(db_path) as con:
        latest = _latest_trade_date(con, as_of)
        reference_dates = _open_dates(con, latest, reference_days)
        compare_dates = _open_dates(con, latest, compare_days)
        if not reference_dates or not compare_dates:
            raise ValueError("trade calendar has no dates for weekly-full windows")
        missing = _snapshot_missing(con, table_names, snapshot_prefix)
        snapshot_min, snapshot_max = _snapshot_common_bounds(con, table_names, snapshot_prefix)

    snapshot_counts = None
    should_create_snapshot = create_snapshot_from_current or (auto_create_missing_snapshot and bool(missing))
    if should_create_snapshot and not dry_run:
        snapshot_counts = _create_snapshot_from_current(
            tables=table_names,
            start_date=compare_dates[0],
            end_date=compare_dates[-1],
            snapshot_prefix=snapshot_prefix,
            db_path=db_path,
        )
        with connect(db_path) as con:
            missing = _snapshot_missing(con, table_names, snapshot_prefix)
            snapshot_min, snapshot_max = _snapshot_common_bounds(con, table_names, snapshot_prefix)

    requested_compare_start = compare_dates[0]
    requested_compare_end = compare_dates[-1]
    effective_compare_start = requested_compare_start
    effective_compare_end = requested_compare_end
    if snapshot_min and snapshot_max:
        effective_compare_start = max(requested_compare_start, snapshot_min)
        effective_compare_end = min(requested_compare_end, snapshot_max)

    compare_result = None
    blocked_reason = ""
    if dry_run:
        status = "pass"
    elif should_create_snapshot:
        status = "snapshot_created"
        blocked_reason = "snapshot refreshed from current data; rerun weekly-full without --create-snapshot-from-current to perform an independent comparison"
    elif missing:
        status = "blocked"
        blocked_reason = "full-reference snapshot tables are missing; create or refresh snapshots before compare"
    elif effective_compare_start > effective_compare_end:
        status = "blocked"
        blocked_reason = "requested compare window has no overlap with snapshot common date bounds"
    else:
        compare_result = compare_incremental_window(
            start_date=effective_compare_start,
            end_date=effective_compare_end,
            tables=table_names,
            snapshot_prefix=snapshot_prefix,
            output_prefix=f"{output_prefix}_compare",
            db_path=db_path,
        )
        status = "pass" if compare_result.passed else "fail"

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "latest_trade_date": latest,
        "reference_start_date": reference_dates[0],
        "reference_end_date": reference_dates[-1],
        "requested_compare_start_date": requested_compare_start,
        "requested_compare_end_date": requested_compare_end,
        "compare_start_date": effective_compare_start,
        "compare_end_date": effective_compare_end,
        "snapshot_common_start_date": snapshot_min,
        "snapshot_common_end_date": snapshot_max,
        "reference_days": reference_days,
        "compare_days": compare_days,
        "snapshot_prefix": snapshot_prefix,
        "dry_run": dry_run,
        "create_snapshot_from_current": create_snapshot_from_current,
        "auto_create_missing_snapshot": auto_create_missing_snapshot,
        "snapshot_counts": snapshot_counts,
        "missing_snapshot_tables": missing,
        "compare_report": compare_result.report if compare_result else None,
        "summary": {
            "status": status,
            "table_count": len(table_names),
            "blocked_reason": blocked_reason,
        },
    }
    return _write_report(report, output_prefix)
