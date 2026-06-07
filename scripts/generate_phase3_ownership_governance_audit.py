from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_ownership_governance_audit.md"

KEY_FIELDS = [
    "pledge_ratio_asof",
    "pledge_ratio_ge_10_flag",
    "pledge_ratio_ge_30_flag",
    "pledge_ratio_ge_50_flag",
    "holder_num_asof",
    "holder_num_to_total_share",
    "holder_num_to_free_share",
    "top10_holder_ratio_latest",
    "top10_float_holder_ratio_latest",
    "ownership_concentration_ratio_latest",
    "ownership_data_completeness_ratio",
]

SOURCE_OBJECTS = [
    "financial_pledge_stat",
    "financial_pledge_detail",
    "financial_holder_number",
    "financial_top10_holders",
    "financial_top10_float_holders",
    "derived_ownership_governance",
    "derived_ownership_governance_full_v",
    "ownership_holder_concentration_v",
    "ownership_governance_event_timeline_v",
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
            FROM derived_ownership_governance
            """
        ).fetchone()
        latest_date = max_date
        core_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('derived_ownership_governance')")
        full_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('derived_ownership_governance_full_v')")
        concentration_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('ownership_holder_concentration_v')")
        timeline_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('ownership_governance_event_timeline_v')")

        source_rows = []
        for obj in SOURCE_OBJECTS:
            try:
                count_value = scalar(con, f"SELECT count(*) FROM {obj}")
                source_rows.append((obj, count_value))
            except Exception:
                source_rows.append((obj, None))

        coverage_rows = []
        for field in KEY_FIELDS:
            non_null = scalar(con, f'SELECT count(*) FROM derived_ownership_governance WHERE "{field}" IS NOT NULL')
            latest_non_null = scalar(
                con,
                f"""
                SELECT count(*)
                FROM derived_ownership_governance
                WHERE trade_date = DATE '{latest_date}' AND "{field}" IS NOT NULL
                """,
            )
            coverage_rows.append((field, non_null, pct(non_null, row_count), latest_non_null))

        duplicate_pk = scalar(
            con,
            """
            SELECT count(*)
            FROM (
                SELECT ts_code, trade_date, count(*) AS n
                FROM derived_ownership_governance
                GROUP BY ts_code, trade_date
                HAVING count(*) > 1
            )
            """,
        )
        holder_pit_violation = scalar(
            con,
            """
            SELECT count(*)
            FROM derived_ownership_governance c
            WHERE c.latest_holder_ann_date IS NOT NULL
              AND c.latest_holder_ann_date > c.trade_date
            """,
        )
        top10_pit_violation = scalar(
            con,
            """
            SELECT count(*)
            FROM derived_ownership_governance c
            WHERE (c.latest_top10_holder_ann_date IS NOT NULL AND c.latest_top10_holder_ann_date > c.trade_date)
               OR (c.latest_top10_float_ann_date IS NOT NULL AND c.latest_top10_float_ann_date > c.trade_date)
            """,
        )
        pledge_pit_violation = scalar(
            con,
            """
            SELECT count(*)
            FROM derived_ownership_governance c
            WHERE c.latest_pledge_end_date IS NOT NULL
              AND c.latest_pledge_end_date > c.trade_date
            """,
        )
        pledge_threshold_violation = scalar(
            con,
            """
            SELECT count(*)
            FROM derived_ownership_governance
            WHERE (pledge_ratio_ge_50_flag AND NOT pledge_ratio_ge_30_flag)
               OR (pledge_ratio_ge_30_flag AND NOT pledge_ratio_ge_10_flag)
            """,
        )
        churn_value_violation = scalar(
            con,
            """
            SELECT count(*)
            FROM derived_ownership_governance_full_v
            WHERE coalesce(top10_holder_name_churn_1report, 0) NOT IN (0, 1)
               OR coalesce(top10_float_holder_name_churn_1report, 0) NOT IN (0, 1)
            """,
        )
        latest_full = con.execute(
            f"""
            SELECT
                count(top1_holder_name_latest),
                count(top10_institution_holder_ratio_latest),
                count(top1_float_holder_name_latest),
                count(pledge_detail_active_count_asof)
            FROM derived_ownership_governance_full_v
            WHERE trade_date = DATE '{latest_date}'
            """
        ).fetchone()

    lines = [
        "# Phase 3 Ownership Governance 审计报告",
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
        f"| 持有人集中度视图列数 | {concentration_cols:,} |",
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
            "## 4. Point-in-time 与唯一性检查",
            "",
            "| 检查项 | 结果 |",
            "|---|---:|",
            f"| 主键重复组数 | {duplicate_pk:,} |",
            f"| 股东户数公告日晚于交易日行数 | {holder_pit_violation:,} |",
            f"| 十大股东公告日晚于交易日行数 | {top10_pit_violation:,} |",
            f"| 质押统计有效日晚于交易日行数 | {pledge_pit_violation:,} |",
            f"| 质押阈值三档非单调行数 | {pledge_threshold_violation:,} |",
            f"| 名单变动字段非0/1行数 | {churn_value_violation:,} |",
            "",
            "## 5. 完整视图运行检查",
            "",
            "| 字段 | 最新交易日非空数 |",
            "|---|---:|",
            f"| `top1_holder_name_latest` | {latest_full[0]:,} |",
            f"| `top10_institution_holder_ratio_latest` | {latest_full[1]:,} |",
            f"| `top1_float_holder_name_latest` | {latest_full[2]:,} |",
            f"| `pledge_detail_active_count_asof` | {latest_full[3]:,} |",
            "",
            "## 6. 结论",
            "",
            "- `derived_ownership_governance` 已按 ownership/governance 第一阶段边界落库：质押、股东户数、十大股东、十大流通股东。",
            "- 质押统计使用 `pledge_stat.end_date` 作为 as-of 有效日；股东户数和十大股东使用公告日进行 point-in-time 广播。",
            "- 高质押阈值采用 10/30/50 三档事实标识，不引入评价分。",
            "- Tushare 百分比/比例字段在核心表中保留来源口径；HHI 内部按百分数除以 100 后计算。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
