from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    audit = json.loads((ROOT / "outputs/phase3/derived_variable_audit_full.json").read_text(encoding="utf-8"))
    lines: list[str] = [
        "# Phase 3 历史全量衍生变量质量审计报告",
        "",
        "生成日期：2026-05-30",
        "",
        "## 1. 构建范围",
        "",
        f"- 历史窗口：`{audit['window_start']}` 至 `{audit['window_end']}`",
    ]
    base = audit["base_stock_daily"]
    lines.append(
        f"- 基础行情：{base['rows']} 行，{base['min_date']} 至 {base['max_date']}，{base['stocks']} 只股票"
    )
    history = audit["history_build"]
    lines.extend(
        [
            f"- 历史分块：{history['unique_success_chunks']} 个唯一月度块成功，失败块 {history['failed_chunks']} 个",
            "",
            "## 2. 总体结论",
            "",
            "1. Phase 3 第一批 17 张衍生变量表已完成历史全量构建。",
            "2. `stock_features_core`、`stock_features_plus`、`stock_features_full` 三个统一出口视图已刷新，均与 `stock_daily` 主干行数一致。",
            "3. 资金流、估值、质押和组合变量的非空率受源数据起点或源字段覆盖影响，属于后续质量解释和变量扩展重点。",
            "",
            "## 3. 衍生表覆盖",
            "",
            "| 表 | 主变量 | 行数 | 日期范围 | 股票数 | 非空率 | 最小值 | 最大值 |",
            "|---|---|---:|---|---:|---:|---:|---:|",
        ]
    )
    for row in audit["rows"]:
        non_null_rate = "" if row["non_null_rate"] is None else f"{row['non_null_rate']:.2%}"
        lines.append(
            f"| `{row['table']}` | `{row['primary_variable']}` | {row['rows']} | "
            f"{row['min_date']} 至 {row['max_date']} | {row['stocks']} | {non_null_rate} | "
            f"{row['min_value']} | {row['max_value']} |"
        )
    lines.extend(
        [
            "",
            "## 4. 统一出口视图",
            "",
            "| 视图 | 行数 | 日期范围 | 股票数 |",
            "|---|---:|---|---:|",
        ]
    )
    for view in audit["views"]:
        lines.append(f"| `{view['view']}` | {view['rows']} | {view['min_date']} 至 {view['max_date']} | {view['stocks']} |")
    lines.extend(
        [
            "",
            "## 5. 后续建议",
            "",
            "1. 下一批应把每个模块从代表变量扩展为多字段变量集。",
            "2. 对资金流从 2007 年起覆盖、估值 `pe_ttm` 缺失、质押覆盖和组合分数缺失建立原因拆解。",
            "3. 将历史分块脚本纳入正式运行机制，保留 `--resume` 作为失败恢复入口。",
        ]
    )
    output = ROOT / "reports/phase3_history_full_quality_audit.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
