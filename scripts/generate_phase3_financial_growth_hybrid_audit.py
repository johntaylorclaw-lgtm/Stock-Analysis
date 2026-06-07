from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_financial_growth_hybrid_audit.md"


CORE_FIELDS = [
    "revenue_yoy_1y_calc_asof",
    "revenue_single_quarter_yoy_asof",
    "parent_net_profit_yoy_1y_calc_asof",
    "ocf_yoy_1y_calc_asof",
    "roe_yoy_diff_asof",
    "roe_yoy_growth_asof",
    "gross_margin_yoy_diff_asof",
    "debt_to_assets_yoy_diff_asof",
    "ocf_to_profit_yoy_growth_asof",
    "roe_yoy_improving_flag",
    "negative_profit_continued_flag",
]

VIEW_ONLY_FIELDS = [
    "operating_cost_yoy_1y_calc_asof",
    "cash_received_from_sales_single_quarter_yoy_asof",
    "report_lag_days_yoy_growth_asof",
    "assets_turn_yoy_growth_asof",
]


def pct(value: float) -> str:
    return f"{value:.2%}"


def table_summary(con: duckdb.DuckDBPyConnection, table_name: str) -> tuple:
    return con.execute(
        f"""
        SELECT count(*), count(DISTINCT ts_code), min(trade_date), max(trade_date)
        FROM {table_name}
        """
    ).fetchone()


def field_count(con: duckdb.DuckDBPyConnection, table_name: str) -> int:
    return len(con.execute(f"PRAGMA table_info('{table_name}')").fetchall())


def field_coverage(con: duckdb.DuckDBPyConnection, table_name: str, field: str, total: int) -> str:
    non_null = con.execute(f"SELECT count({field}) FROM {table_name}").fetchone()[0]
    if field.endswith("_flag"):
        normal = con.execute(f"SELECT count(*) FROM {table_name} WHERE {field}").fetchone()[0]
        special = 0
    elif "_diff_" in field:
        normal = non_null
        special = 0
    else:
        normal = con.execute(
            f"SELECT count(*) FROM {table_name} WHERE {field} IS NOT NULL AND {field} > -9000000"
        ).fetchone()[0]
        special = con.execute(
            f"SELECT count(*) FROM {table_name} WHERE {field} IS NOT NULL AND {field} <= -9000000"
        ).fetchone()[0]
    return f"| `{field}` | {non_null:,} | {pct(non_null / total)} | {normal:,} | {special:,} |"


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    core = table_summary(con, "derived_financial_growth")
    core_total = core[0]
    view_sample = con.execute(
        """
        SELECT count(*), count(DISTINCT ts_code), min(trade_date), max(trade_date)
        FROM derived_financial_growth_full_v
        WHERE trade_date BETWEEN DATE '2026-05-20' AND DATE '2026-05-26'
        """
    ).fetchone()

    lines = [
        "# Phase 3 财务成长二阶段混合结构审计",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 结构结论",
        "",
        "- `derived_financial_growth`：核心物理表，保留高频使用成长字段，承担日常增量加载。",
        "- `derived_financial_growth_full_v`：完整视图，覆盖二阶段 1196 列设计，按需查询，不重复占用宽表存储。",
        "- 本次重构保留全历史行粒度，降低物理表列数；DuckDB 文件是否立即释放磁盘空间取决于后续数据库压缩/重写。",
        "",
        "## 表级覆盖",
        "",
        "| 对象 | 类型 | 行数/样本行数 | 股票数 | 起始日期 | 结束日期 | 字段数 |",
        "|---|---|---:|---:|---|---|---:|",
        f"| `derived_financial_growth` | 物理表 | {core[0]:,} | {core[1]:,} | {core[2]} | {core[3]} | {field_count(con, 'derived_financial_growth')} |",
        f"| `derived_financial_growth_full_v` | 视图近期样本 | {view_sample[0]:,} | {view_sample[1]:,} | {view_sample[2]} | {view_sample[3]} | {field_count(con, 'derived_financial_growth_full_v')} |",
        "",
        "## 核心物理字段覆盖",
        "",
        "| 字段 | 非空行数 | 非空率 | 正常值/True 行数 | 特殊值行数 |",
        "|---|---:|---:|---:|---:|",
    ]
    for field in CORE_FIELDS:
        lines.append(field_coverage(con, "derived_financial_growth", field, core_total))

    lines.extend(
        [
            "",
            "## 完整视图字段抽检",
            "",
            "| 字段 | 近期样本非空行数 | 近期样本非空率 | 正常值行数 | 特殊值行数 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    view_total = view_sample[0]
    for field in VIEW_ONLY_FIELDS:
        lines.append(
            field_coverage(
                con,
                "(SELECT * FROM derived_financial_growth_full_v WHERE trade_date BETWEEN DATE '2026-05-20' AND DATE '2026-05-26')",
                field,
                view_total,
            )
        )

    lines.extend(
        [
            "",
            "## 年度行数",
            "",
            "| 年份 | 行数 | 有当前报告期行数 | ROE 同比差值非空行数 |",
            "|---:|---:|---:|---:|",
        ]
    )
    rows = con.execute(
        """
        SELECT
            year(trade_date) AS year,
            count(*) AS rows,
            count(current_report_end_date) AS report_rows,
            count(roe_yoy_diff_asof) AS roe_yoy_diff_rows
        FROM derived_financial_growth
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()
    for year, rows_count, report_rows, roe_rows in rows:
        lines.append(f"| {year} | {rows_count:,} | {report_rows:,} | {roe_rows:,} |")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
