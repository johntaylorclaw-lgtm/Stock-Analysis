from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_corporate_action_audit.md"

KEY_FIELDS = [
    "cash_dividend_ttm",
    "has_forecast_asof",
    "has_express_asof",
    "audit_opinion_code_latest",
    "mainbz_top1_revenue_ratio_latest",
    "repurchase_amount_365d",
    "share_float_share_365d",
    "next_share_float_share_30d",
    "next_share_float_share_90d",
    "float_share_ratio_asof",
    "total_share_chg_20d",
]

SOURCE_OBJECTS = [
    "financial_dividend",
    "financial_forecast",
    "financial_express",
    "financial_audit_opinion",
    "financial_main_business",
    "financial_repurchase",
    "financial_share_float",
    "derived_corporate_action",
    "derived_corporate_action_full_v",
    "corporate_action_event_timeline_v",
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
            FROM derived_corporate_action
            """
        ).fetchone()
        core_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('derived_corporate_action')")
        full_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('derived_corporate_action_full_v')")
        timeline_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('corporate_action_event_timeline_v')")
        latest_date = max_date

        source_rows = []
        for obj in SOURCE_OBJECTS:
            try:
                count_value = scalar(con, f"SELECT count(*) FROM {obj}")
                source_rows.append((obj, count_value))
            except Exception:
                source_rows.append((obj, None))

        coverage_rows = []
        for field in KEY_FIELDS:
            non_null = scalar(con, f'SELECT count(*) FROM derived_corporate_action WHERE "{field}" IS NOT NULL')
            latest_non_null = scalar(
                con,
                f"""
                SELECT count(*)
                FROM derived_corporate_action
                WHERE trade_date = DATE '{latest_date}' AND "{field}" IS NOT NULL
                """,
            )
            coverage_rows.append((field, non_null, pct(non_null, row_count), latest_non_null))

        future_violation = scalar(
            con,
            """
            SELECT count(*)
            FROM derived_corporate_action c
            WHERE c.next_share_float_share_90d IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM financial_share_float sf
                  WHERE sf.ts_code = c.ts_code
                    AND sf.ann_date <= c.trade_date
                    AND sf.float_date > c.trade_date
                    AND sf.float_date <= c.trade_date + INTERVAL 90 DAY
              )
            """,
        )

        latest_full = con.execute(
            f"""
            SELECT
                count(cash_dividend_5y_sum),
                count(forecast_count_365d),
                count(mainbz_hhi_revenue_latest),
                count(next_share_float_share_180d)
            FROM derived_corporate_action_full_v
            WHERE trade_date = DATE '{latest_date}'
            """
        ).fetchone()

    lines = [
        "# Phase 3 Corporate Action 审计报告",
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
        f"| 事件时间线视图列数 | {timeline_cols:,} |",
        f"| 核心表行数 | {row_count:,} |",
        f"| 覆盖股票数 | {stock_count:,} |",
        f"| 覆盖交易日数 | {trade_dates:,} |",
        f"| 日期范围 | {min_date} 至 {max_date} |",
        "",
        "## 2. 来源对象行数",
        "",
        "| 对象 | 行数 |",
        "|---|---:|",
    ]
    lines.extend(f"| `{obj}` | {'' if count_value is None else f'{count_value:,}'} |" for obj, count_value in source_rows)
    lines.extend(
        [
            "",
            "## 3. 核心字段覆盖率",
            "",
            "| 字段 | 非空行数 | 全历史覆盖率 | 最新交易日非空数 |",
            "|---|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| `{field}` | {non_null:,} | {coverage} | {latest_non_null:,} |"
        for field, non_null, coverage, latest_non_null in coverage_rows
    )
    lines.extend(
        [
            "",
            "## 4. Point-in-time 检查",
            "",
            "| 检查项 | 结果 |",
            "|---|---:|",
            f"| 未来90日解禁窗口无已公告事件支撑行数 | {future_violation:,} |",
            "",
            "## 5. 完整视图运行检查",
            "",
            "| 字段 | 最新交易日非空数 |",
            "|---|---:|",
            f"| `cash_dividend_5y_sum` | {latest_full[0]:,} |",
            f"| `forecast_count_365d` | {latest_full[1]:,} |",
            f"| `mainbz_hhi_revenue_latest` | {latest_full[2]:,} |",
            f"| `next_share_float_share_180d` | {latest_full[3]:,} |",
            "",
            "## 6. 结论",
            "",
            "- `derived_corporate_action` 已按公司行为事实口径落库。",
            "- 分红现金字段保留 Tushare 原始每股口径，不做复权。",
            "- 未来解禁窗口仅统计 `ann_date <= trade_date < float_date` 的已公告事件。",
            "- 质押、股东户数、十大股东未进入本模块，后续由 `ownership_governance` 维护。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
