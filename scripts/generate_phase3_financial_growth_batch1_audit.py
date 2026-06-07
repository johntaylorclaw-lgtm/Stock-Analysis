from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_financial_growth_batch1_audit.md"


CHECK_FIELDS = [
    "current_report_end_date",
    "same_period_1y_end_date",
    "revenue_yoy_asof",
    "revenue_yoy_1y_calc_asof",
    "revenue_yoy_2y_calc_asof",
    "revenue_cagr_2y_asof",
    "parent_net_profit_yoy_1y_calc_asof",
    "ocf_yoy_1y_calc_asof",
    "total_assets_yoy_1y_calc_asof",
    "revenue_single_quarter_value_asof",
    "revenue_single_quarter_yoy_asof",
    "revenue_positive_growth_flag",
    "profit_positive_growth_flag",
]

SPECIAL_FIELDS = [
    "revenue_yoy_1y_calc_asof",
    "parent_net_profit_yoy_1y_calc_asof",
    "ocf_yoy_1y_calc_asof",
    "revenue_single_quarter_yoy_asof",
    "revenue_cagr_2y_asof",
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
        "# Phase 3 财务成长衍生第一批质量审计",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 表级覆盖",
        "",
        "| 表 | 行数 | 股票数 | 起始日期 | 结束日期 | 字段数 |",
        "|---|---:|---:|---|---|---:|",
    ]
    row = con.execute(
        """
        SELECT count(*), count(DISTINCT ts_code), min(trade_date), max(trade_date)
        FROM derived_financial_growth
        """
    ).fetchone()
    field_count = len(con.execute("PRAGMA table_info('derived_financial_growth')").fetchall())
    lines.append(
        f"| `derived_financial_growth` | {row[0]:,} | {row[1]:,} | {row[2]} | {row[3]} | {field_count} |"
    )

    lines.extend(
        [
            "",
            "## 关键字段覆盖",
            "| 字段 | 非空行数 | 非空率 | 正常值行数 | 特殊值行数 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    total = row[0]
    for field in CHECK_FIELDS:
        non_null = con.execute(f"SELECT count({field}) FROM derived_financial_growth").fetchone()[0]
        if field.endswith("_flag") or field.endswith("_end_date") or field.endswith("_value_asof"):
            normal_count = non_null
            special_count = 0
        else:
            normal_count = con.execute(
                f"SELECT count(*) FROM derived_financial_growth WHERE {field} IS NOT NULL AND {field} > -9000000"
            ).fetchone()[0]
            special_count = con.execute(
                f"SELECT count(*) FROM derived_financial_growth WHERE {field} IS NOT NULL AND {field} <= -9000000"
            ).fetchone()[0]
        lines.append(
            f"| `{field}` | {non_null:,} | {pct(non_null / total)} | {normal_count:,} | {special_count:,} |"
        )

    lines.extend(
        [
            "",
            "## 特殊值编码分布",
        ]
    )
    for field in SPECIAL_FIELDS:
        lines.extend(
            [
                "",
                f"### `{field}`",
                "",
                "| 特殊值 | 行数 | 含义 |",
                "|---:|---:|---|",
            ]
        )
        rows = con.execute(
            f"""
            SELECT {field}, count(*) AS row_count
            FROM derived_financial_growth
            WHERE {field} <= -9000000
            GROUP BY 1
            ORDER BY row_count DESC, {field}
            LIMIT 10
            """
        ).fetchall()
        for code, count in rows:
            lines.append(f"| {fmt(code)} | {count:,} | {decode_special(code)} |")

    lines.extend(
        [
            "",
            "## 极值抽查（正常值）",
            "| 字段 | min | p01 | median | p99 | max |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for field in SPECIAL_FIELDS:
        stats = con.execute(
            f"""
            SELECT
                min({field}),
                quantile_cont({field}, 0.01),
                median({field}),
                quantile_cont({field}, 0.99),
                max({field})
            FROM derived_financial_growth
            WHERE {field} > -9000000
            """
        ).fetchone()
        lines.append(f"| `{field}` | " + " | ".join(fmt(value) for value in stats) + " |")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


def decode_special(value: object) -> str:
    if value is None:
        return ""
    text = str(int(value))
    if not text.startswith("-9") or len(text) != 8:
        return ""
    bits = text[2:]
    labels = [
        "分子为0",
        "分子为空",
        "分子为负",
        "分母为0",
        "分母为空",
        "分母为负",
    ]
    active = [label for bit, label in zip(bits, labels, strict=True) if bit == "1"]
    return "；".join(active) if active else "特殊值但未命中状态位"


if __name__ == "__main__":
    main()
