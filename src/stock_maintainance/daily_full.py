from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from .database import connect
from .daily_light import _compact_date, _latest_open_trade_date, _month, _precheck_payload
from .daily_validate import validate_daily
from .features.build import build_features
from .ingest import (
    default_index_codes,
    sync_adj_factor_range,
    sync_daily_range,
    sync_financial_events_batch,
    sync_financial_incremental_range,
    sync_index_basic,
    sync_index_daily_range,
    sync_index_weight_range,
    sync_market_behavior_range,
    sync_stock_basic,
    sync_stock_company,
    sync_stock_status_history,
    sync_trade_calendar,
)
from .paths import REPORTS_DIR
from .views import create_views
from .weekly_full import run_weekly_full


@dataclass(frozen=True)
class DailyFullResult:
    report: dict[str, Any]
    json_path: Path
    markdown_path: Path

    @property
    def passed(self) -> bool:
        return self.report["summary"]["status"] == "pass"


def _open_trade_dates(end_date: str, days: int) -> list[str]:
    with connect() as con:
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


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Daily-Full 运行报告",
        "",
        f"生成时间：{report['generated_at']}",
        f"截至日期：`{report['as_of_date']}`",
        f"运行模式：`{'dry-run' if report['dry_run'] else 'execute'}`",
        f"结果：`{summary['status']}`",
        "",
        "## 全量窗口",
        "",
        f"- 重拉交易日：{', '.join(report['target_dates']) or '无'}",
        f"- 重拉交易日数：{len(report['target_dates'])}",
        "",
        "## 步骤",
        "",
        "| 步骤 | 状态 | 说明 |",
        "|---|---|---|",
    ]
    for step in report["steps"]:
        detail = step.get("detail")
        detail_text = json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else str(detail or "")
        lines.append(f"| `{step['name']}` | {step['status']} | {detail_text} |")
    if summary.get("blocked_reason"):
        lines.extend(["", "## 阻塞原因", "", summary["blocked_reason"]])
    lines.append("")
    return "\n".join(lines)


def _write_report(report: dict[str, Any], output_prefix: str) -> DailyFullResult:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"{output_prefix}.json"
    md_path = REPORTS_DIR / f"{output_prefix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return DailyFullResult(report=report, json_path=json_path, markdown_path=md_path)


def _failure_result(
    *,
    run_at: str,
    as_of: str,
    dry_run: bool,
    target_dates: list[str],
    precheck_payload: dict[str, Any] | None,
    postcheck_payload: dict[str, Any] | None,
    steps: list[dict[str, Any]],
    output_prefix: str,
    exc: Exception,
) -> DailyFullResult:
    report = {
        "generated_at": run_at,
        "as_of_date": as_of,
        "dry_run": dry_run,
        "target_dates": target_dates,
        "precheck": precheck_payload,
        "postcheck": postcheck_payload,
        "steps": steps,
        "summary": {
            "status": "fail",
            "blocked_reason": str(exc),
            "target_trade_day_count": len(target_dates),
        },
    }
    return _write_report(report, output_prefix)


def run_daily_full(
    *,
    as_of_date: str | None = None,
    reload_trade_days: int = 1,
    validation_days: int = 1,
    dry_run: bool = False,
    include_financial: bool = False,
    include_index_weight: bool = False,
    refresh_weekly_snapshot: bool = False,
    weekly_reference_days: int = 40,
    weekly_compare_days: int = 10,
    output_prefix: str = "daily_full_run",
) -> DailyFullResult:
    started = time.perf_counter()
    run_at = datetime.now().isoformat(timespec="seconds")
    requested_as_of = as_of_date or date.today().isoformat()
    as_of = requested_as_of
    steps: list[dict[str, Any]] = []
    target_dates: list[str] = []
    precheck_payload: dict[str, Any] | None = None
    postcheck_payload: dict[str, Any] | None = None

    def add_step(name: str, status: str, detail: Any = None) -> None:
        steps.append({"name": name, "status": status, "detail": detail})

    if reload_trade_days < 1:
        raise ValueError("reload_trade_days must be >= 1")

    if dry_run:
        add_step("sync-master", "planned", "refresh stock_basic/company/status/trade_calendar/index_basic before full daily reload")
    else:
        master: dict[str, Any] = {}
        master.update(sync_stock_basic())
        master.update(sync_stock_company())
        master.update(sync_stock_status_history())
        master.update(sync_trade_calendar(start_date="20060101", end_date=_compact_date(requested_as_of)))
        master.update(sync_index_basic())
        add_step("sync-master", "done", master)

    if as_of_date is None:
        latest_open = _latest_open_trade_date(requested_as_of)
        if latest_open:
            as_of = latest_open
            add_step("resolve-as-of-date", "done", {"requested_as_of_date": requested_as_of, "resolved_as_of_date": as_of})
        else:
            add_step("resolve-as-of-date", "warning", {"requested_as_of_date": requested_as_of, "message": "no open trade date found; using requested date"})

    try:
        target_dates = _open_trade_dates(as_of, reload_trade_days)
    except duckdb.CatalogException:
        target_dates = [as_of]
    if not target_dates:
        target_dates = [as_of]
    add_step("resolve-target-window", "done", {"reload_trade_days": reload_trade_days, "target_dates": target_dates})

    precheck = validate_daily(
        as_of_date=as_of,
        max_auto_trade_days=max(reload_trade_days, 10),
        validation_days=max(validation_days, 1),
        output_prefix=f"{output_prefix}_precheck",
    )
    precheck_payload = _precheck_payload(precheck)
    add_step("validate-daily-precheck", precheck_payload["status"], precheck_payload)

    start_iso = target_dates[0]
    end_iso = target_dates[-1]
    start_compact = _compact_date(start_iso)
    end_compact = _compact_date(end_iso)

    if dry_run:
        add_step(
            "base-full-reload",
            "planned",
            {
                "start_date": start_compact,
                "end_date": end_compact,
                "resume": False,
                "force_market_behavior": True,
                "apis": [
                    "daily",
                    "daily_basic",
                    "stk_limit",
                    "adj_factor",
                    "moneyflow",
                    "margin_detail",
                    "moneyflow_hsgt",
                    "hk_hold",
                    "top_list",
                    "top_inst",
                    "index_daily",
                ],
            },
        )
        if include_index_weight:
            add_step("index-weight", "planned", {"start_month": _month(start_iso), "end_month": _month(end_iso), "index_codes": default_index_codes()})
        if include_financial:
            add_step("financial-incremental", "planned", {"ann_date_window": [start_compact, end_compact], "all_stocks": True})
    else:
        base: dict[str, Any] = {}
        try:
            base["daily"] = sync_daily_range(start_compact, end_compact, resume=False)
            base["adj_factor"] = sync_adj_factor_range(start_compact, end_compact)
            base["market_behavior"] = sync_market_behavior_range(start_compact, end_compact, force=True)
            base["index_daily"] = sync_index_daily_range(start_compact, end_compact)
        except Exception as exc:
            add_step("base-full-reload", "fail", {"error": str(exc), "partial": base})
            return _failure_result(
                run_at=run_at,
                as_of=as_of,
                dry_run=dry_run,
                target_dates=target_dates,
                precheck_payload=precheck_payload,
                postcheck_payload=postcheck_payload,
                steps=steps,
                output_prefix=output_prefix,
                exc=exc,
            )
        base_status = "warning" if base.get("market_behavior", {}).get("optional_failures") else "done"
        add_step("base-full-reload", base_status, base)
        if include_index_weight:
            index_weight = sync_index_weight_range(_month(start_iso), _month(end_iso), index_codes=default_index_codes(), resume=False)
            add_step("index-weight", "done", index_weight)
        if include_financial:
            try:
                financial = sync_financial_incremental_range(start_compact, end_compact, all_stocks=True, resume=False)
                events = sync_financial_events_batch(start_date=start_compact, end_date=end_compact, resume=False)
            except Exception as exc:
                add_step("financial-incremental", "fail", {"error": str(exc)})
                return _failure_result(
                    run_at=run_at,
                    as_of=as_of,
                    dry_run=dry_run,
                    target_dates=target_dates,
                    precheck_payload=precheck_payload,
                    postcheck_payload=postcheck_payload,
                    steps=steps,
                    output_prefix=output_prefix,
                    exc=exc,
                )
            add_step("financial-incremental", "done", {"financial": financial, "events": events})

    if dry_run:
        add_step(
            "feature-build",
            "planned",
            {
                "start_date": start_iso,
                "end_date": end_iso,
                "mode": "daily",
                "note": "daily-full dry-run keeps feature planning lightweight; execute mode rebuilds all feature modules for the target window",
            },
        )
    else:
        try:
            feature_result = build_features(start_date=start_iso, end_date=end_iso, allow_confirmed_history=True)
        except Exception as exc:
            add_step("feature-build", "fail", {"start_date": start_iso, "end_date": end_iso, "error": str(exc)})
            return _failure_result(
                run_at=run_at,
                as_of=as_of,
                dry_run=dry_run,
                target_dates=target_dates,
                precheck_payload=precheck_payload,
                postcheck_payload=postcheck_payload,
                steps=steps,
                output_prefix=output_prefix,
                exc=exc,
            )
        add_step(
            "feature-build",
            "done",
            {
                "start_date": start_iso,
                "end_date": end_iso,
                "elapsed_seconds": feature_result.get("elapsed_seconds"),
                "module_count": len(feature_result.get("results", [])),
            },
        )

    if dry_run:
        add_step("create-views", "planned", "refresh stock_features_core/plus/full and analytical views")
        add_step("validate-daily-postcheck", "planned", "run after execution")
        if refresh_weekly_snapshot:
            add_step("refresh-weekly-snapshot", "planned", {"reference_days": weekly_reference_days, "compare_days": weekly_compare_days})
    else:
        try:
            create_views()
        except Exception as exc:
            add_step("create-views", "fail", {"error": str(exc)})
            return _failure_result(
                run_at=run_at,
                as_of=as_of,
                dry_run=dry_run,
                target_dates=target_dates,
                precheck_payload=precheck_payload,
                postcheck_payload=postcheck_payload,
                steps=steps,
                output_prefix=output_prefix,
                exc=exc,
            )
        add_step("create-views", "done", "created analytical views")
        postcheck = validate_daily(
            as_of_date=as_of,
            max_auto_trade_days=max(reload_trade_days, 10),
            validation_days=max(validation_days, 1),
            output_prefix=f"{output_prefix}_postcheck",
        )
        postcheck_payload = _precheck_payload(postcheck)
        add_step("validate-daily-postcheck", postcheck_payload["status"], postcheck_payload)
        if refresh_weekly_snapshot:
            weekly = run_weekly_full(
                as_of_date=as_of,
                reference_days=weekly_reference_days,
                compare_days=weekly_compare_days,
                output_prefix=f"{output_prefix}_weekly_snapshot",
                create_snapshot_from_current=True,
            )
            add_step(
                "refresh-weekly-snapshot",
                weekly.report["summary"]["status"],
                {"json": str(weekly.json_path), "markdown": str(weekly.markdown_path), **weekly.report["summary"]},
            )

    status = "pass"
    for step in steps:
        if step["status"] == "fail":
            status = "fail"
            break
        if step["status"] in {"warning", "blocked"}:
            if (
                step["name"] == "validate-daily-precheck"
                and not dry_run
                and postcheck_payload
                and postcheck_payload.get("status") == "pass"
            ):
                continue
            status = "warning"
    report = {
        "generated_at": run_at,
        "as_of_date": as_of,
        "dry_run": dry_run,
        "target_dates": target_dates,
        "precheck": precheck_payload,
        "postcheck": postcheck_payload,
        "steps": steps,
        "summary": {
            "status": status,
            "target_trade_day_count": len(target_dates),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        },
    }
    return _write_report(report, output_prefix)
