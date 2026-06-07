from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_financial_stage1_quality_audit.md"


def pct(value: float) -> str:
    return f"{value:.2%}"


def fmt_num(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    lines: list[str] = [
        "# Phase 3 财务衍生第一阶段质量审计",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 表级覆盖",
        "",
        "| 表 | 行数 | 股票数 | 起始日期 | 结束日期 | 字段数 |",
        "|---|---:|---:|---|---|---:|",
    ]

    for table in ["derived_financial_asof", "derived_financial_quality"]:
        row = con.execute(
            f"""
            SELECT
                count(*) AS row_count,
                count(DISTINCT ts_code) AS stock_count,
                min(trade_date),
                max(trade_date)
            FROM {table}
            """
        ).fetchone()
        field_count = len(con.execute(f"PRAGMA table_info('{table}')").fetchall())
        lines.append(
            f"| `{table}` | {row[0]:,} | {row[1]:,} | {row[2]} | {row[3]} | {field_count} |"
        )

    point_in_time_violations = con.execute(
        """
        SELECT count(*)
        FROM derived_financial_asof
        WHERE latest_financial_effective_date IS NOT NULL
          AND latest_financial_effective_date > trade_date
        """
    ).fetchone()[0]
    report_regressions = con.execute(
        """
        WITH ordered AS (
            SELECT
                ts_code,
                trade_date,
                latest_report_end_date,
                lag(latest_report_end_date) OVER (
                    PARTITION BY ts_code ORDER BY trade_date
                ) AS previous_report_end_date
            FROM derived_financial_asof
        )
        SELECT count(*)
        FROM ordered
        WHERE latest_report_end_date IS NOT NULL
          AND previous_report_end_date IS NOT NULL
          AND latest_report_end_date < previous_report_end_date
        """
    ).fetchone()[0]
    lines.extend(
        [
            "",
            "## 点时安全",
            f"- `latest_financial_effective_date <= trade_date` 违反行数：{point_in_time_violations:,}",
            f"- 报告期随交易日倒退行数：{report_regressions:,}",
            "",
            "## 关键字段非空率",
            "| 表 | 字段 | 非空行数 | 非空率 |",
            "|---|---|---:|---:|",
        ]
    )

    check_fields = {
        "derived_financial_asof": [
            "latest_report_end_date",
            "latest_financial_effective_date",
            "report_age_days",
            "statement_available_count",
            "has_income_statement",
            "has_balance_sheet",
            "has_cashflow_statement",
            "has_indicator_statement",
            "has_forecast_asof",
            "has_express_asof",
        ],
        "derived_financial_quality": [
            "roe_asof",
            "roa_asof",
            "gross_margin_asof",
            "netprofit_margin_asof",
            "ocf_to_profit_asof",
            "ocf_to_revenue_asof",
            "cash_to_assets_asof",
            "debt_to_assets_asof",
            "current_ratio_asof",
            "accounts_receivable_to_revenue_asof",
            "goodwill_to_assets_asof",
            "expense_to_revenue_asof",
            "dupont_roe_calc_asof",
            "liability_equity_balance_gap_asof",
            "cashflow_cash_balance_gap_asof",
        ],
    }
    for table, fields in check_fields.items():
        total = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for field in fields:
            non_null = con.execute(f"SELECT count({field}) FROM {table}").fetchone()[0]
            lines.append(f"| `{table}` | `{field}` | {non_null:,} | {pct(non_null / total)} |")

    lines.extend(
        [
            "",
            "## 年度覆盖率",
            "| 年份 | 行数 | 有财报行数 | 覆盖率 |",
            "|---:|---:|---:|---:|",
        ]
    )
    year_rows = con.execute(
        """
        SELECT
            year(trade_date) AS report_year,
            count(*) AS row_count,
            count(latest_report_end_date) AS financial_rows,
            count(latest_report_end_date)::DOUBLE / count(*) AS coverage
        FROM derived_financial_asof
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()
    for year, row_count, financial_rows, coverage in year_rows:
        lines.append(f"| {year} | {row_count:,} | {financial_rows:,} | {pct(coverage)} |")

    lines.extend(
        [
            "",
            "## 极值抽查",
            "| 字段 | min | p01 | median | p99 | max |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for field in [
        "roe_asof",
        "roa_asof",
        "gross_margin_asof",
        "debt_to_assets_asof",
        "ocf_to_profit_asof",
        "goodwill_to_assets_asof",
        "liability_equity_balance_gap_ratio_asof",
        "cashflow_cash_balance_gap_ratio_asof",
    ]:
        row = con.execute(
            f"""
            SELECT
                min({field}),
                quantile_cont({field}, 0.01),
                median({field}),
                quantile_cont({field}, 0.99),
                max({field})
            FROM derived_financial_quality
            WHERE {field} IS NOT NULL
            """
        ).fetchone()
        lines.append(f"| `{field}` | " + " | ".join(fmt_num(value) for value in row) + " |")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
