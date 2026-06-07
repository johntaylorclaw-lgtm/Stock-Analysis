from __future__ import annotations

from datetime import datetime
from pathlib import Path

from stock_maintainance.database import connect


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "phase5_feature_view_coverage_audit.md"

MODULE_TABLES = [
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
    "derived_ownership_governance",
    "derived_composite_state",
]

FEATURE_VIEWS = [
    "stock_features_core",
    "stock_features_plus",
    "stock_features_full",
]

TECHNICAL_MODULES = {
    "derived_daily_spine",
    "derived_price_technical",
    "derived_volume_liquidity",
    "derived_return_momentum",
    "derived_volatility_risk",
    "derived_trading_constraint",
}

KEY_COLUMNS = {"ts_code", "trade_date", "updated_at"}


def columns(con, name: str) -> list[str]:
    return [row[1] for row in con.execute(f"PRAGMA table_info({name})").fetchall()]


def main() -> None:
    with connect() as con:
        module_columns = {name: columns(con, name) for name in MODULE_TABLES}
        view_columns = {name: columns(con, name) for name in FEATURE_VIEWS}

    module_payload = []
    for module, cols in module_columns.items():
        payload_cols = [col for col in cols if col not in KEY_COLUMNS]
        row = {
            "module": module,
            "module_payload_columns": len(payload_cols),
        }
        for view, vcols in view_columns.items():
            covered = sorted(set(payload_cols) & set(vcols))
            row[f"{view}_covered"] = len(covered)
            row[f"{view}_missing"] = len(set(payload_cols) - set(vcols))
            row[f"{view}_coverage"] = len(covered) / len(set(payload_cols)) if payload_cols else 1.0
        module_payload.append(row)

    technical_payload = sum(len([col for col in module_columns[name] if col not in KEY_COLUMNS]) for name in TECHNICAL_MODULES)
    phase3_payload = sum(len([col for col in cols if col not in KEY_COLUMNS]) for cols in module_columns.values())

    lines = [
        "# Phase 5 统一出口视图覆盖率审计",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 当前规模",
        "",
        "| 视图 | 当前列数 |",
        "|---|---:|",
    ]
    for view, cols in view_columns.items():
        lines.append(f"| `{view}` | {len(cols)} |")
    lines.extend(
        [
            "",
            "## 模块覆盖",
            "",
            "| 模块 | 模块有效字段 | core覆盖 | core缺口 | plus覆盖 | plus缺口 | full覆盖 | full缺口 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in module_payload:
        lines.append(
            f"| `{row['module']}` | {row['module_payload_columns']} | "
            f"{row['stock_features_core_covered']} | {row['stock_features_core_missing']} | "
            f"{row['stock_features_plus_covered']} | {row['stock_features_plus_missing']} | "
            f"{row['stock_features_full_covered']} | {row['stock_features_full_missing']} |"
        )
    full_missing = sum(row["stock_features_full_missing"] for row in module_payload)
    plus_missing = sum(row["stock_features_plus_missing"] for row in module_payload)
    core_missing = sum(row["stock_features_core_missing"] for row in module_payload)
    lines.extend(
        [
            "",
            "## 审计结论",
            "",
            f"1. Phase 3 股票级模块有效字段约 {phase3_payload} 个，`stock_features_full` 精确字段名缺口为 {full_missing} 个。",
            f"2. 交易行情与技术分析相关模块有效字段约 {technical_payload} 个，`stock_features_core` 当前缺口为 {core_missing} 个，定位为日常核心出口而非全量字段出口。",
            f"3. `stock_features_plus` 当前精确字段名缺口为 {plus_missing} 个，主要来自横截面全量字段；其定位为研究增强出口。",
            "4. `stock_features_full` 用于全量事实研究和审计；对重名字段会使用模块前缀，因此表格中的精确字段名覆盖口径可能低估带前缀字段的实际可用覆盖。",
            "",
            "## 当前边界",
            "",
            "| 视图 | 定位 | 当前处理 |",
            "|---|---|---|",
            "| `stock_features_core` | 日常高频稳定出口 | 扩充核心交易、估值、财务、资金、行业市场和截面字段 |",
            "| `stock_features_plus` | 研究增强出口 | 在 core 基础上纳入财务质量/成长、资金、行业概念、指数市场、公司行为、股权治理、综合事实状态全量字段 |",
            "| `stock_features_full` | 审计和全量研究出口 | 在 plus 基础上纳入横截面全量字段和基础 enriched 字段；对重复字段使用模块前缀 |",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
