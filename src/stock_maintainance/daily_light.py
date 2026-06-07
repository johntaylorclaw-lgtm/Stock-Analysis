from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .daily_validate import DailyValidationResult, validate_daily
from .features.build import build_features
from .ingest import (
    default_index_codes,
    sync_adj_factor_range,
    sync_daily_range,
    sync_financial_events_batch,
    sync_financial_incremental_range,
    sync_index_daily_range,
    sync_index_weight_range,
    sync_market_behavior_range,
    sync_stock_basic,
    sync_stock_company,
    sync_stock_status_history,
    sync_trade_calendar,
    sync_index_basic,
)
from .paths import REPORTS_DIR
from .views import create_views


@dataclass(frozen=True)
class DailyLightResult:
    report: dict[str, Any]
    json_path: Path
    markdown_path: Path

    @property
    def passed(self) -> bool:
        return self.report["summary"]["status"] == "pass"


def _compact_date(value: str) -> str:
    return value.replace("-", "")


def _month(value: str) -> str:
    return value.replace("-", "")[:6]


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Daily-Light 运行报告",
        "",
        f"生成时间：{report['generated_at']}",
        f"截至日期：`{report['as_of_date']}`",
        f"运行模式：`{'dry-run' if report['dry_run'] else 'execute'}`",
        f"结果：`{summary['status']}`",
        "",
        "## 窗口",
        "",
        f"- 最新交易日：`{report['precheck']['latest_trade_date']}`",
        f"- 当前锚点日期：`{report['precheck']['anchor_data_date']}`",
        f"- 验证日期：{', '.join(report['precheck']['validation_dates']) or '无'}",
        f"- 待增量日期：{', '.join(report['precheck']['incremental_dates']) or '无'}",
        f"- 待增量交易日数：{len(report['precheck']['incremental_dates'])}",
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
        lines.extend(["", "## 阻塞原因", "", summary["blocked_reason"], ""])
    return "\n".join(lines).rstrip() + "\n"


def _write_report(report: dict[str, Any], output_prefix: str) -> DailyLightResult:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"{output_prefix}.json"
    md_path = REPORTS_DIR / f"{output_prefix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return DailyLightResult(report=report, json_path=json_path, markdown_path=md_path)


def _precheck_payload(result: DailyValidationResult) -> dict[str, Any]:
    return {
        "json": str(result.json_path),
        "markdown": str(result.markdown_path),
        "status": result.report["summary"]["status"],
        "latest_trade_date": result.report["latest_trade_date"],
        "anchor_data_date": result.report["anchor_data_date"],
        "validation_dates": result.report["validation_dates"],
        "incremental_dates": result.report["incremental_dates"],
        "requires_confirmation": result.report["summary"]["requires_confirmation"],
    }


def run_daily_light(
    *,
    as_of_date: str | None = None,
    max_auto_trade_days: int = 10,
    validation_days: int = 1,
    dry_run: bool = False,
    allow_confirmed_history: bool = False,
    include_financial: bool = False,
    include_index_weight: bool = False,
    output_prefix: str = "daily_light_run",
) -> DailyLightResult:
    started = time.perf_counter()
    run_at = datetime.now().isoformat(timespec="seconds")
    as_of = as_of_date or date.today().isoformat()
    steps: list[dict[str, Any]] = []

    def add_step(name: str, status: str, detail: Any = None) -> None:
        steps.append({"name": name, "status": status, "detail": detail})

    if dry_run:
        add_step("sync-master", "planned", "refresh stock_basic/company/status/trade_calendar/index_basic before daily data")
    else:
        master: dict[str, Any] = {}
        master.update(sync_stock_basic())
        master.update(sync_stock_company())
        master.update(sync_stock_status_history())
        master.update(sync_trade_calendar(start_date="20060101", end_date=_compact_date(as_of)))
        master.update(sync_index_basic())
        add_step("sync-master", "done", master)

    precheck = validate_daily(
        as_of_date=as_of,
        max_auto_trade_days=max_auto_trade_days,
        validation_days=validation_days,
        output_prefix=f"{output_prefix}_precheck",
    )
    precheck_payload = _precheck_payload(precheck)
    add_step("validate-daily-precheck", precheck_payload["status"], precheck_payload)

    incremental_dates = precheck.report["incremental_dates"]
    validation_dates = precheck.report["validation_dates"]
    requires_confirmation = precheck.report["summary"]["requires_confirmation"]
    if requires_confirmation and not allow_confirmed_history:
        report = {
            "generated_at": run_at,
            "as_of_date": as_of,
            "dry_run": dry_run,
            "precheck": precheck_payload,
            "steps": steps,
            "summary": {
                "status": "blocked",
                "blocked_reason": f"incremental window exceeds {max_auto_trade_days} trade days; rerun with --allow-confirmed-history after review",
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            },
        }
        return _write_report(report, output_prefix)

    if not incremental_dates:
        add_step("base-incremental", "skipped", "no missing trade dates")
        add_step("feature-build", "skipped", "no missing trade dates")
    else:
        start_iso = incremental_dates[0]
        end_iso = incremental_dates[-1]
        start_compact = _compact_date(start_iso)
        end_compact = _compact_date(end_iso)
        if dry_run:
            add_step(
                "base-incremental",
                "planned",
                {
                    "start_date": start_compact,
                    "end_date": end_compact,
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
            base["daily"] = sync_daily_range(start_compact, end_compact)
            base["adj_factor"] = sync_adj_factor_range(start_compact, end_compact)
            base["market_behavior"] = sync_market_behavior_range(start_compact, end_compact)
            base["index_daily"] = sync_index_daily_range(start_compact, end_compact)
            add_step("base-incremental", "done", base)
            if include_index_weight:
                index_weight = sync_index_weight_range(_month(start_iso), _month(end_iso), index_codes=default_index_codes())
                add_step("index-weight", "done", index_weight)
            if include_financial:
                financial = sync_financial_incremental_range(start_compact, end_compact, all_stocks=True)
                events = sync_financial_events_batch(start_date=start_compact, end_date=end_compact)
                add_step("financial-incremental", "done", {"financial": financial, "events": events})

        build_start = validation_dates[0] if validation_dates else start_iso
        if dry_run:
            feature_result = build_features(start_date=build_start, end_date=end_iso, dry_run=True)
        else:
            feature_result = build_features(
                start_date=build_start,
                end_date=end_iso,
                allow_confirmed_history=allow_confirmed_history,
            )
        add_step(
            "feature-build",
            "planned" if dry_run else "done",
            {
                "start_date": build_start,
                "end_date": end_iso,
                "elapsed_seconds": feature_result.get("elapsed_seconds"),
                "module_count": len(feature_result.get("results", [])),
            },
        )

    if dry_run:
        add_step("create-views", "planned", "refresh stock_features_core/plus/full and analytical views")
        postcheck_payload = None
        add_step("validate-daily-postcheck", "planned", "run after execution")
    else:
        create_views()
        add_step("create-views", "done", "created analytical views")
        postcheck = validate_daily(
            as_of_date=as_of,
            max_auto_trade_days=max_auto_trade_days,
            validation_days=validation_days,
            output_prefix=f"{output_prefix}_postcheck",
        )
        postcheck_payload = _precheck_payload(postcheck)
        add_step("validate-daily-postcheck", postcheck_payload["status"], postcheck_payload)

    status = "pass"
    if any(step["status"] in {"warning", "blocked", "fail"} for step in steps):
        status = "warning"
    report = {
        "generated_at": run_at,
        "as_of_date": as_of,
        "dry_run": dry_run,
        "precheck": precheck_payload,
        "postcheck": postcheck_payload,
        "steps": steps,
        "summary": {
            "status": status,
            "incremental_trade_day_count": len(incremental_dates),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        },
    }
    return _write_report(report, output_prefix)
