from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import load_schema_registry, load_variable_registry
from .docs import check_docs
from .features.planner import build_feature_plan
from .paths import REPORTS_DIR
from .validate import validate_schema_registry, validate_variable_registry, validate_variable_schema_alignment


SCRIPT_CLASSIFICATION_PATH = REPORTS_DIR / "phase4_phase3_script_classification.csv"
MODULE_WINDOW_SPEC_PATH = REPORTS_DIR / "phase4_module_window_spec.csv"
LAST_BUILD_RUN_PATH = REPORTS_DIR / "phase4_last_build_features_run.json"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _module_spec_rows(plan_dict: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in plan_dict["module_plans"]:
        rows.append(
            {
                "module": item["module"],
                "variables": item["variables"],
                "tables": ";".join(item["tables"]),
                "read_start_date": item["read_start_date"],
                "write_start_date": item["write_start_date"],
                "write_end_date": item["write_end_date"],
                "read_window": item["read_window"],
                "write_window": item["write_window"],
                "max_min_history": item["max_min_history"],
                "dependencies": ";".join(item["dependencies"]),
            }
        )
    return rows


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 4 增量性能审计报告",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 1. 总览",
        "",
        f"- 写入窗口：`{report['feature_plan']['write_start_date']}` 至 `{report['feature_plan']['write_end_date']}`",
        f"- 模块数量：{len(report['feature_plan']['module_plans'])}",
        f"- 配置校验：{report['validation']['status']}",
        f"- 文档同步：{report['docs']['status']}",
        "",
        "## 2. 模块窗口",
        "",
        "| 模块 | 变量数 | 读取窗口 | 写入窗口 | 表 |",
        "|---|---:|---:|---:|---|",
    ]
    for item in report["feature_plan"]["module_plans"]:
        tables = ", ".join(item["tables"])
        lines.append(
            f"| `{item['module']}` | {item['variables']} | {item['read_window']} | "
            f"{item['write_window']} | {tables} |"
        )

    lines.extend(["", "## 3. Phase 3 脚本分类", "", "| 分类 | 数量 |", "|---|---:|"])
    for category, count in sorted(report["script_classification"]["counts"].items()):
        lines.append(f"| `{category}` | {count} |")

    lines.extend(["", "## 4. 最近构建耗时"])
    last_run = report["last_build_run"]
    if last_run:
        lines.extend(
            [
                "",
                f"- 最近运行时间：{last_run.get('started_at')} 至 {last_run.get('finished_at')}",
                f"- 总耗时：{last_run.get('elapsed_seconds')} 秒",
                "",
                "| 类型 | 名称 | 阶段 | 状态 | 行数 | 耗时秒 |",
                "|---|---|---|---|---:|---:|",
            ]
        )
        for item in last_run.get("results", []):
            lines.append(
                f"| module | `{item.get('module')}` | core | {item.get('status')} | "
                f"{item.get('rows_written', 0)} | {item.get('elapsed_seconds')} |"
            )
        for item in last_run.get("cache_results", []):
            lines.append(
                f"| cache | `{item.get('name')}` | {item.get('phase')} | {item.get('status')} | "
                f"{item.get('rows_written', 0)} | {item.get('elapsed_seconds')} |"
            )
    else:
        lines.append("")
        lines.append("尚无 `phase4_last_build_features_run.json`，需要完成一次非 dry-run 的 `build-features` 后生成。")

    lines.extend(["", "## 5. 风险与遗留"])
    if report["validation"]["errors"]:
        lines.extend(["", "配置问题："])
        lines.extend(f"- {item}" for item in report["validation"]["errors"])
    if report["docs"]["diffs"]:
        lines.extend(["", "文档漂移："])
        lines.extend(f"- {item}" for item in report["docs"]["diffs"])
    if report["script_classification"]["missing"]:
        lines.extend(["", "缺失脚本分类报告："])
        lines.extend(f"- {item}" for item in report["script_classification"]["missing"])
    if (
        not report["validation"]["errors"]
        and not report["docs"]["diffs"]
        and not report["script_classification"]["missing"]
    ):
        lines.append("")
        lines.append("当前未发现配置、文档或脚本分类层面的阻断问题。")

    lines.extend(
        [
            "",
            "## 6. 建议",
            "",
            "1. 将 `phase4-audit` 纳入日批前后固定检查。",
            "2. 分析 `return_momentum`、`price_technical` 等仍保留 750 天上下文的技术模块，评估状态缓存或按股票批处理。",
            "3. 对完整日批组合做分组验收，确认 Phase 4 剩余瓶颈和可验收标准。",
            "",
        ]
    )
    return "\n".join(lines)


def run_phase4_audit(*, end_date: str | None = None, output_prefix: str = "phase4_audit_report") -> dict[str, Path]:
    schema = load_schema_registry()
    variables = load_variable_registry()
    validation_errors: list[str] = []
    validation_errors.extend(validate_schema_registry(schema))
    validation_errors.extend(validate_variable_registry(variables))
    validation_errors.extend(validate_variable_schema_alignment(variables, schema))
    docs_diffs = check_docs()

    plan = build_feature_plan(variables, end_date=end_date)
    plan_dict = plan.to_dict()
    module_rows = _module_spec_rows(plan_dict)
    _write_csv(
        MODULE_WINDOW_SPEC_PATH,
        module_rows,
        [
            "module",
            "variables",
            "tables",
            "read_start_date",
            "write_start_date",
            "write_end_date",
            "read_window",
            "write_window",
            "max_min_history",
            "dependencies",
        ],
    )

    script_rows = _read_csv(SCRIPT_CLASSIFICATION_PATH)
    classification_counts = Counter(row.get("classification") or row.get("category") or "" for row in script_rows)
    classification_counts.pop("", None)
    last_build_run = (
        json.loads(LAST_BUILD_RUN_PATH.read_text(encoding="utf-8"))
        if LAST_BUILD_RUN_PATH.exists()
        else None
    )

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "feature_plan": plan_dict,
        "validation": {
            "status": "passed" if not validation_errors else "failed",
            "errors": validation_errors,
        },
        "docs": {
            "status": "up_to_date" if not docs_diffs else "drifted",
            "diffs": docs_diffs,
        },
        "script_classification": {
            "path": str(SCRIPT_CLASSIFICATION_PATH),
            "rows": len(script_rows),
            "counts": dict(sorted(classification_counts.items())),
            "missing": [] if SCRIPT_CLASSIFICATION_PATH.exists() else [str(SCRIPT_CLASSIFICATION_PATH)],
        },
        "last_build_run": last_build_run,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"{output_prefix}.json"
    md_path = REPORTS_DIR / f"{output_prefix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
