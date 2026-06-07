from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_financial_growth_full_audit.md"


FIELDS = [
    "revenue_yoy_1y_calc_asof",
    "revenue_single_quarter_yoy_asof",
    "parent_net_profit_yoy_1y_calc_asof",
    "ocf_yoy_1y_calc_asof",
    "roe_yoy_diff_asof",
    "roe_yoy_growth_asof",
    "gross_margin_yoy_diff_asof",
    "debt_to_assets_yoy_diff_asof",
    "ocf_to_profit_yoy_growth_asof",
    "report_lag_days_yoy_growth_asof",
    "roe_yoy_improving_flag",
    "negative_profit_continued_flag",
]


def pct(value: float) -> str:
    return f"{value:.2%}"


def fmt(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if abs(value) >= 9_000_000 and value.is_integer():
            return str(int(value))
        return f"{value:.6g}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    lines = [
        "# Phase 3 财务成长衍生完整落库审计",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 表级覆盖",
        "",
        "| 表 | 行数 | 股票数 | 起始日期 | 结束日期 | 字段数 |",
        "|---|---:|---:|---|---|---:|",
    ]
    table_row = con.execute(
        """
        SELECT count(*), count(DISTINCT ts_code), min(trade_date), max(trade_date)
        FROM derived_financial_growth
        """
    ).fetchone()
    field_count = len(con.execute("PRAGMA table_info('derived_financial_growth')").fetchall())
    lines.append(
        f"| `derived_financial_growth` | {table_row[0]:,} | {table_row[1]:,} | {table_row[2]} | {table_row[3]} | {field_count} |"
    )

    lines.extend(
        [
            "",
            "## 关键字段覆盖",
            "| 字段 | 非空行数 | 非空率 | 正常值/True 行数 | 特殊值行数 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    total = table_row[0]
    for field in FIELDS:
        non_null = con.execute(f"SELECT count({field}) FROM derived_financial_growth").fetchone()[0]
        if field.endswith("_flag"):
            normal = con.execute(f"SELECT count(*) FROM derived_financial_growth WHERE {field}").fetchone()[0]
            special = 0
        elif "_diff_" in field:
            normal = non_null
            special = 0
        else:
            normal = con.execute(
                f"SELECT count(*) FROM derived_financial_growth WHERE {field} IS NOT NULL AND {field} > -9000000"
            ).fetchone()[0]
            special = con.execute(
                f"SELECT count(*) FROM derived_financial_growth WHERE {field} IS NOT NULL AND {field} <= -9000000"
            ).fetchone()[0]
        lines.append(f"| `{field}` | {non_null:,} | {pct(non_null / total)} | {normal:,} | {special:,} |")

    lines.extend(
        [
            "",
            "## 年度行数",
            "| 年份 | 行数 | 有当前报告期行数 | ROE同比差值非空行数 |",
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

    lines.extend(
        [
            "",
            "## 特殊值示例分布",
            "| 字段 | 特殊值 | 行数 |",
            "|---|---:|---:|",
        ]
    )
    for field in ["roe_yoy_growth_asof", "ocf_to_profit_yoy_growth_asof"]:
        rows = con.execute(
            f"""
            SELECT {field}, count(*)
            FROM derived_financial_growth
            WHERE {field} <= -9000000
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 8
            """
        ).fetchall()
        for code, count in rows:
            lines.append(f"| `{field}` | {fmt(code)} | {count:,} |")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
