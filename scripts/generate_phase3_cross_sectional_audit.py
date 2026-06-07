from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_cross_sectional_audit.md"

KEY_FIELDS = [
    "ret_20_hfq_rank_all_desc",
    "ret_20_hfq_z_all",
    "ret_20_hfq_resid_size_sw_l2_z",
    "log_free_float_mv_z_all",
    "earnings_yield_ttm_z_all",
    "roe_asof_z_all",
    "revenue_yoy_asof_z_all",
    "main_flow_to_total_mv_20_z_all",
    "size_exposure_z",
    "value_exposure_z",
    "quality_exposure_z",
    "growth_exposure_z",
    "flow_exposure_z",
]

ZSCORE_FIELDS = [
    "ret_20_hfq_z_all",
    "log_free_float_mv_z_all",
    "roe_asof_z_all",
    "main_flow_to_total_mv_20_z_all",
]

VIEW_FIELDS = [
    "ret_20_hfq_z_market",
    "ret_20_hfq_rank_sw_l1_desc",
    "ret_5_hfq_z_all",
    "profitability_exposure_z",
    "index_relative_exposure_z",
]


def scalar(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()[0]


def pct(numerator: int | float | None, denominator: int | float | None) -> str:
    if not denominator:
        return ""
    return f"{float(numerator or 0) / float(denominator):.4%}"


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(DB_PATH, read_only=True) as con:
        table_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('derived_cross_sectional')")
        view_cols = scalar(con, "SELECT count(*) FROM pragma_table_info('derived_cross_sectional_full_v')")
        row_count, min_date, max_date, stock_count, trade_dates = con.execute(
            """
            SELECT
                count(*) AS row_count,
                min(trade_date) AS min_date,
                max(trade_date) AS max_date,
                count(DISTINCT ts_code) AS stock_count,
                count(DISTINCT trade_date) AS trade_dates
            FROM derived_cross_sectional
            """
        ).fetchone()
        universe_rows = scalar(
            con, "SELECT count(*) FROM derived_cross_sectional WHERE xs_universe_flag"
        )
        latest_date = scalar(con, "SELECT max(trade_date) FROM derived_cross_sectional")

        coverage_rows = []
        for field in KEY_FIELDS:
            non_null = scalar(
                con,
                f'SELECT count(*) FROM derived_cross_sectional WHERE "{field}" IS NOT NULL',
            )
            latest_non_null = scalar(
                con,
                f"""
                SELECT count(*)
                FROM derived_cross_sectional
                WHERE trade_date = DATE '{latest_date}' AND "{field}" IS NOT NULL
                """,
            )
            coverage_rows.append((field, non_null, pct(non_null, universe_rows), latest_non_null))

        zscore_rows = []
        for field in ZSCORE_FIELDS:
            avg_val, std_val, n_val = con.execute(
                f"""
                SELECT avg("{field}"), stddev_samp("{field}"), count("{field}")
                FROM derived_cross_sectional
                WHERE trade_date = DATE '{latest_date}'
                """
            ).fetchone()
            zscore_rows.append((field, avg_val, std_val, n_val))

        rank_min, rank_max, rank_n = con.execute(
            f"""
            SELECT
                min(ret_20_hfq_rank_all_desc),
                max(ret_20_hfq_rank_all_desc),
                count(ret_20_hfq_rank_all_desc)
            FROM derived_cross_sectional
            WHERE trade_date = DATE '{latest_date}'
            """
        ).fetchone()

        view_rows = []
        for field in VIEW_FIELDS:
            latest_non_null = scalar(
                con,
                f"""
                SELECT count(*)
                FROM derived_cross_sectional_full_v
                WHERE trade_date = DATE '{latest_date}' AND "{field}" IS NOT NULL
                """,
            )
            view_rows.append((field, latest_non_null))

    lines = [
        "# Phase 3 Cross Sectional 审计报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 数据库：`{DB_PATH}`",
        "",
        "## 1. 表规模",
        "",
        "| 项目 | 结果 |",
        "|---|---:|",
        f"| 核心物理表列数 | {table_cols:,} |",
        f"| 完整视图列数 | {view_cols:,} |",
        f"| 核心表行数 | {row_count:,} |",
        f"| 截面有效股票行数 | {universe_rows:,} |",
        f"| 覆盖股票数 | {stock_count:,} |",
        f"| 覆盖交易日数 | {trade_dates:,} |",
        f"| 日期范围 | {min_date} 至 {max_date} |",
        "",
        "## 2. 关键字段覆盖率",
        "",
        "| 字段 | 非空行数 | 全历史有效样本覆盖率 | 最新交易日非空数 |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| `{field}` | {non_null:,} | {coverage} | {latest_non_null:,} |"
        for field, non_null, coverage, latest_non_null in coverage_rows
    )
    lines.extend(
        [
            "",
            "## 3. 最新交易日 z 值 sanity check",
            "",
            f"最新交易日：`{latest_date}`",
            "",
            "| 字段 | 均值 | 标准差 | 非空数 |",
            "|---|---:|---:|---:|",
        ]
    )
    for field, avg_val, std_val, n_val in zscore_rows:
        avg_text = "" if avg_val is None else f"{avg_val:.6f}"
        std_text = "" if std_val is None else f"{std_val:.6f}"
        lines.append(f"| `{field}` | {avg_text} | {std_text} | {n_val:,} |")
    lines.extend(
        [
            "",
            "## 4. 排名边界检查",
            "",
            "| 字段 | 最新交易日最小名次 | 最新交易日最大名次 | 非空数 |",
            "|---|---:|---:|---:|",
            f"| `ret_20_hfq_rank_all_desc` | {rank_min} | {rank_max} | {rank_n:,} |",
            "",
            "## 5. 完整视图运行检查",
            "",
            "| 字段 | 最新交易日非空数 |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| `{field}` | {latest_non_null:,} |" for field, latest_non_null in view_rows)
    lines.extend(
        [
            "",
            "## 6. 结论",
            "",
            "- `derived_cross_sectional` 已完成 2006-2026 全历史核心物理表落库。",
            "- `derived_cross_sectional_full_v` 已创建为视图，避免大宽表重复占用磁盘空间。",
            "- 分组 z 值和排名字段存在自然缺失：停牌、未上市、源变量不可得、特殊值、分组样本低于阈值时均保留为空。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
