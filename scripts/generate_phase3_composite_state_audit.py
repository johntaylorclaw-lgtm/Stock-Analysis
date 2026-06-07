from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_composite_state_audit.md"

ENUM_FIELDS = {
    "list_age_bucket": {"lt1y", "1to3y", "3to5y", "5to10y", "ge10y", "unknown"},
    "price_valid_state": {"valid_price", "trading_no_price", "no_price", "invalid_price"},
    "limit_lock_state": {"none", "limit_up", "limit_down", "one_price_limit", "unknown"},
    "ma_alignment_state": {"bull", "partial_bull", "mixed", "partial_bear", "bear", "unknown"},
    "trend_state": {"bull", "partial_bull", "mixed", "partial_bear", "bear"},
    "amount_activity_state": {"low", "mid", "high", "unknown"},
    "volatility_state": {"low", "mid", "high", "unknown"},
    "valuation_percentile_state": {"low", "mid", "high", "unknown"},
    "financial_staleness_state": {"fresh", "normal", "stale", "unknown"},
    "main_flow_persist_state": {"low", "mid", "high", "unknown"},
    "margin_balance_change_state": {"decrease", "flat", "increase", "unknown"},
    "sector_relative_return_state": {"lag", "mid", "lead", "unknown"},
    "market_context_state": {"down", "mixed", "up", "unknown"},
    "pledge_ratio_state": {"below10", "ge10", "ge30", "ge50", "unknown"},
}

KEY_FIELDS = [
    "composite_available_flag",
    "module_available_ratio",
    "state_condition_count",
    "trend_state",
    "financial_available_flag",
    "capital_flow_available_flag",
    "corporate_action_available_flag",
    "ownership_available_flag",
    "multi_domain_condition_count",
]


def scalar(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()[0]


def pct(n: int | float | None, d: int | float | None) -> str:
    if not d:
        return ""
    return f"{float(n or 0) / float(d):.4%}"


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(DB_PATH, read_only=True) as con:
        row_count, min_date, max_date, stock_count, trade_dates = con.execute(
            """
            SELECT count(*), min(trade_date), max(trade_date), count(DISTINCT ts_code), count(DISTINCT trade_date)
            FROM derived_composite_state
            """
        ).fetchone()
        latest_date = max_date
        core_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('derived_composite_state')")
        full_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('derived_composite_state_full_v')")
        condition_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('composite_state_condition_detail_v')")
        coverage_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('composite_state_module_coverage_v')")
        old_score_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('derived_composite_state') WHERE name LIKE '%score%'")
        duplicate_pk = scalar(
            con,
            """
            SELECT count(*)
            FROM (
                SELECT ts_code, trade_date, count(*) AS n
                FROM derived_composite_state
                GROUP BY ts_code, trade_date
                HAVING count(*) > 1
            )
            """,
        )
        coverage_rows = []
        for field in KEY_FIELDS:
            non_null = scalar(con, f'SELECT count(*) FROM derived_composite_state WHERE "{field}" IS NOT NULL')
            latest_non_null = scalar(
                con,
                f"""
                SELECT count(*)
                FROM derived_composite_state
                WHERE trade_date = DATE '{latest_date}' AND "{field}" IS NOT NULL
                """,
            )
            coverage_rows.append((field, non_null, pct(non_null, row_count), latest_non_null))
        enum_rows = []
        for field, allowed in ENUM_FIELDS.items():
            allowed_sql = ", ".join("'" + value + "'" for value in sorted(allowed))
            invalid = scalar(
                con,
                f"""
                SELECT count(*)
                FROM derived_composite_state
                WHERE "{field}" IS NOT NULL AND "{field}" NOT IN ({allowed_sql})
                """,
            )
            enum_rows.append((field, invalid))
        condition_mismatch_latest = scalar(
            con,
            f"""
            SELECT count(*)
            FROM derived_composite_state c
            LEFT JOIN (
                SELECT ts_code, trade_date, count(CASE WHEN condition_value THEN 1 END)::INTEGER AS true_count
                FROM composite_state_condition_detail_v
                WHERE trade_date = DATE '{latest_date}'
                GROUP BY ts_code, trade_date
            ) d ON c.ts_code = d.ts_code AND c.trade_date = d.trade_date
            WHERE c.trade_date = DATE '{latest_date}'
              AND c.state_condition_count != coalesce(d.true_count, 0)
            """,
        )
        module_coverage_latest = con.execute(
            f"""
            SELECT module_name, available_rows, expected_rows, available_ratio
            FROM composite_state_module_coverage_v
            WHERE trade_date = DATE '{latest_date}'
            ORDER BY module_name
            """
        ).fetchall()

    lines = [
        "# Phase 3 Composite State 审计报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 数据库：`{DB_PATH}`",
        "",
        "## 1. 表规模",
        "",
        "| 项目 | 结果 |",
        "|---|---:|",
        f"| 核心物理表列数 | {core_cols:,} |",
        f"| 完整视图列数 | {full_cols:,} |",
        f"| 条件明细视图列数 | {condition_cols:,} |",
        f"| 模块覆盖视图列数 | {coverage_cols:,} |",
        f"| 核心表行数 | {row_count:,} |",
        f"| 覆盖股票数 | {stock_count:,} |",
        f"| 覆盖交易日数 | {trade_dates:,} |",
        f"| 日期范围 | {min_date} 至 {max_date} |",
        "",
        "## 2. 核心字段覆盖率",
        "",
        "| 字段 | 非空行数 | 全历史覆盖率 | 最新交易日非空数 |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(f"| `{field}` | {non_null:,} | {coverage} | {latest_non_null:,} |" for field, non_null, coverage, latest_non_null in coverage_rows)
    lines.extend(
        [
            "",
            "## 3. 枚举和一致性检查",
            "",
            "| 检查项 | 结果 |",
            "|---|---:|",
            f"| 主键重复组数 | {duplicate_pk:,} |",
            f"| `score` 字段数量 | {old_score_cols:,} |",
            f"| 最新交易日条件明细 true 数与核心表不一致行数 | {condition_mismatch_latest:,} |",
        ]
    )
    lines.extend(f"| `{field}` 非法枚举行数 | {invalid:,} |" for field, invalid in enum_rows)
    lines.extend(
        [
            "",
            "## 4. 最新交易日模块覆盖率",
            "",
            "| 模块 | 可用行数 | 应覆盖行数 | 可用率 |",
            "|---|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| `{module}` | {available:,} | {expected:,} | {ratio:.4%} |"
        for module, available, expected, ratio in module_coverage_latest
    )
    lines.extend(
        [
            "",
            "## 5. 结论",
            "",
            "- `derived_composite_state` 已按事实状态汇总层口径落库。",
            "- 本模块不包含 `score` 字段，不生成选股分、买卖信号或未来收益标签。",
            "- 条件计数字段只统计明确布尔事实成立数量，解释入口为 `composite_state_condition_detail_v`。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
