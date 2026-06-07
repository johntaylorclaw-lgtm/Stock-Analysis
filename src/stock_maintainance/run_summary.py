from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .database import DB_PATH, connect
from .paths import REPORTS_DIR


SUMMARY_DIR = REPORTS_DIR / "summaries"
FEATURE_VIEWS = ["stock_features_core", "stock_features_plus", "stock_features_full"]


@dataclass(frozen=True)
class RunSummaryResult:
    mode: str
    report: dict[str, Any]
    markdown_path: Path

    @property
    def passed(self) -> bool:
        return self.report["summary"]["status"] == "pass"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_report(prefix: str) -> Path | None:
    candidates = sorted(REPORTS_DIR.glob(f"{prefix}*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _resolve_report(run_id: str | None, *, default_prefix: str) -> Path:
    if run_id:
        exact = REPORTS_DIR / f"{run_id}.json"
        if exact.exists():
            return exact
        matches = sorted(REPORTS_DIR.glob(f"{run_id}*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        if matches:
            return matches[0]
        raise ValueError(f"no report found for run_id: {run_id}")
    latest = _latest_report(default_prefix)
    if latest is None:
        raise ValueError(f"no report found with prefix: {default_prefix}")
    return latest


def _status_payload(as_of_date: str) -> dict[str, Any]:
    with connect(DB_PATH) as con:
        def one(sql: str, params: list[Any] | None = None) -> Any:
            return con.execute(sql, params or []).fetchone()[0]

        latest_trade_date = one(
            """
            SELECT max(CAST(cal_date AS DATE))
            FROM trade_calendar
            WHERE is_open = 1
              AND CAST(cal_date AS DATE) <= CAST(? AS DATE)
            """,
            [as_of_date],
        )
        anchor_data_date = one("SELECT max(CAST(trade_date AS DATE)) FROM derived_daily_spine")
        incremental_trade_day_count = one(
            """
            SELECT count(*)
            FROM trade_calendar
            WHERE is_open = 1
              AND CAST(cal_date AS DATE) > CAST(? AS DATE)
              AND CAST(cal_date AS DATE) <= CAST(? AS DATE)
            """,
            [anchor_data_date, latest_trade_date],
        )
        feature_view_field_counts = {}
        for view in FEATURE_VIEWS:
            feature_view_field_counts[view] = one(
                "SELECT count(*) FROM pragma_table_info(?)",
                [view],
            )
        return {
            "as_of_date": as_of_date,
            "latest_trade_date": str(latest_trade_date),
            "anchor_data_date": str(anchor_data_date),
            "incremental_trade_day_count": int(incremental_trade_day_count),
            "stock_basic_info_rows": int(one("SELECT count(*) FROM stock_basic_info")),
            "stock_active": int(one("SELECT count(*) FROM stock_basic_info WHERE list_status = 'L'")),
            "stock_delisted": int(one("SELECT count(*) FROM stock_basic_info WHERE list_status = 'D'")),
            "stock_daily_rows": int(one("SELECT count(*) FROM stock_daily")),
            "stock_daily_distinct": int(one("SELECT count(DISTINCT ts_code) FROM stock_daily")),
            "derived_spine_rows": int(one("SELECT count(*) FROM derived_daily_spine")),
            "derived_spine_distinct": int(one("SELECT count(DISTINCT ts_code) FROM derived_daily_spine")),
            "feature_view_field_counts": feature_view_field_counts,
        }


def _render_status(report: dict[str, Any]) -> str:
    rows = [
        ("证券主数据股票数", report["stock_basic_info_rows"]),
        ("当前上市股票数", report["stock_active"]),
        ("已退市股票数", report["stock_delisted"]),
        ("日行情覆盖股票数", report["stock_daily_distinct"]),
        ("日行情行数", report["stock_daily_rows"]),
        ("日频核心行数", report["derived_spine_rows"]),
        ("日频核心覆盖股票数", report["derived_spine_distinct"]),
        ("最新交易日", report["latest_trade_date"]),
        ("当前数据锚点", report["anchor_data_date"]),
        ("待增量交易日数", report["incremental_trade_day_count"]),
    ]
    lines = [
        "# 状态汇总报告",
        "",
        f"生成时间：{report['generated_at']}",
        f"截至日期：`{report['as_of_date']}`",
        f"结果：`{report['summary']['status']}`",
        "",
        "## 数据状态",
        "",
        "| 指标 | 值 |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {value} |" for name, value in rows)
    lines.extend(["", "## 统一出口列数", "", "| 视图 | 列数 |", "|---|---:|"])
    for view, count in report["feature_view_field_counts"].items():
        lines.append(f"| `{view}` | {count} |")
    lines.append("")
    return "\n".join(lines)


def _step_status(report: dict[str, Any], name: str) -> str:
    for step in report.get("steps", []):
        if step.get("name") == name:
            return str(step.get("status", ""))
    return ""


def _render_daily(report: dict[str, Any]) -> str:
    precheck = report["source_report"].get("precheck", {})
    postcheck = report["source_report"].get("postcheck") or {}
    lines = [
        "# 日报汇总",
        "",
        f"生成时间：{report['generated_at']}",
        f"来源报告：`{report['source_report_path']}`",
        f"截至日期：`{report['source_report'].get('as_of_date')}`",
        f"运行模式：`{'dry-run' if report['source_report'].get('dry_run') else 'execute'}`",
        f"结果：`{report['summary']['status']}`",
        "",
        "## 窗口",
        "",
        f"- 最新交易日：`{precheck.get('latest_trade_date')}`",
        f"- 当前锚点日期：`{precheck.get('anchor_data_date')}`",
        f"- 验证日期：{', '.join(precheck.get('validation_dates') or []) or '无'}",
        f"- 待增量日期：{', '.join(precheck.get('incremental_dates') or []) or '无'}",
        "",
        "## 步骤状态",
        "",
        "| 步骤 | 状态 |",
        "|---|---|",
    ]
    for name in [
        "sync-master",
        "validate-daily-precheck",
        "base-incremental",
        "feature-build",
        "create-views",
        "validate-daily-postcheck",
    ]:
        lines.append(f"| `{name}` | {_step_status(report['source_report'], name)} |")
    lines.extend(
        [
            "",
            "## 后验收",
            "",
            f"- postcheck 状态：`{postcheck.get('status', 'n/a')}`",
            f"- postcheck 报告：`{postcheck.get('markdown', '')}`",
            "",
        ]
    )
    return "\n".join(lines)


def _render_weekly(report: dict[str, Any]) -> str:
    source = report["source_report"]
    compare = source.get("compare_report") or {}
    cmp_summary = compare.get("summary", {})
    lines = [
        "# 周报汇总",
        "",
        f"生成时间：{report['generated_at']}",
        f"来源报告：`{report['source_report_path']}`",
        f"截至日期：`{source.get('as_of_date')}`",
        f"结果：`{report['summary']['status']}`",
        "",
        "## 窗口",
        "",
        f"- 参照窗口：`{source.get('reference_start_date')}` 至 `{source.get('reference_end_date')}`",
        f"- 请求比较窗口：`{source.get('requested_compare_start_date')}` 至 `{source.get('requested_compare_end_date')}`",
        f"- 快照共同窗口：`{source.get('snapshot_common_start_date')}` 至 `{source.get('snapshot_common_end_date')}`",
        f"- 实际比较窗口：`{source.get('compare_start_date')}` 至 `{source.get('compare_end_date')}`",
        "",
        "## 字段级对照",
        "",
        "| 指标 | 值 |",
        "|---|---:|",
        f"| 表数量 | {cmp_summary.get('table_count', source.get('summary', {}).get('table_count', ''))} |",
        f"| 通过表 | {cmp_summary.get('pass_table_count', '')} |",
        f"| 失败表 | {cmp_summary.get('fail_table_count', '')} |",
        f"| 键缺失/额外行 | {cmp_summary.get('missing_or_extra_key_rows', '')} |",
        f"| 差异字段数 | {cmp_summary.get('mismatch_column_count', '')} |",
        f"| 差异单元格数 | {cmp_summary.get('mismatch_cell_count', '')} |",
        "",
    ]
    fail_tables = cmp_summary.get("fail_tables") or []
    if fail_tables:
        lines.extend(["## 失败表", ""])
        lines.extend(f"- `{table}`" for table in fail_tables)
        lines.append("")
    return "\n".join(lines)


def _render_phase(report: dict[str, Any]) -> str:
    source = report.get("source_report", {})
    lines = [
        "# 阶段汇总",
        "",
        f"生成时间：{report['generated_at']}",
        f"阶段：`{report['phase']}`",
        f"结果：`{report['summary']['status']}`",
        "",
        "## 来源",
        "",
        f"- `{report.get('source_report_path', '')}`",
        "",
    ]
    if source:
        lines.extend(["## 摘要", ""])
        for key, value in source.get("summary", {}).items():
            lines.append(f"- `{key}`：{value}")
        lines.append("")
    return "\n".join(lines)


def summarize_run(
    *,
    mode: str,
    run_id: str | None = None,
    as_of_date: str | None = None,
    phase: str = "phase5",
    output_prefix: str | None = None,
) -> RunSummaryResult:
    generated_at = datetime.now().isoformat(timespec="seconds")
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    today = as_of_date or date.today().isoformat()

    if mode == "status":
        payload = _status_payload(today)
        status = "pass" if payload["incremental_trade_day_count"] == 0 else "warning"
        report = {"generated_at": generated_at, **payload, "summary": {"status": status}}
        name = output_prefix or f"status_summary_{today.replace('-', '')}"
        content = _render_status(report)
    elif mode == "daily":
        path = _resolve_report(run_id, default_prefix="phase5_daily_light_execute_")
        source = _read_json(path)
        status = source.get("summary", {}).get("status", "warning")
        report = {
            "generated_at": generated_at,
            "source_report_path": str(path),
            "source_report": source,
            "summary": {"status": status},
        }
        name = output_prefix or f"daily_summary_{path.stem}"
        content = _render_daily(report)
    elif mode == "weekly":
        path = _resolve_report(run_id, default_prefix="phase5_weekly_full_compare_")
        source = _read_json(path)
        status = source.get("summary", {}).get("status", "warning")
        report = {
            "generated_at": generated_at,
            "source_report_path": str(path),
            "source_report": source,
            "summary": {"status": status},
        }
        name = output_prefix or f"weekly_summary_{path.stem}"
        content = _render_weekly(report)
    elif mode == "phase":
        path = REPORTS_DIR / f"{phase}_final_acceptance_report.md"
        report = {
            "generated_at": generated_at,
            "phase": phase,
            "source_report_path": str(path),
            "source_report": {},
            "summary": {"status": "pass" if path.exists() else "blocked"},
        }
        name = output_prefix or f"phase_summary_{phase}"
        content = _render_phase(report)
    else:
        raise ValueError(f"unknown summary mode: {mode}")

    markdown_path = SUMMARY_DIR / f"{name}.md"
    markdown_path.write_text(content, encoding="utf-8")
    return RunSummaryResult(mode=mode, report=report, markdown_path=markdown_path)
