from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .database import connect, refresh_source_api_status
from .paths import REPORTS_DIR
from .views import create_views


def run_quality_audit() -> list[Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        refresh_source_api_status(con)
        create_views(con)
        table_counts = con.execute(
            """
            SELECT table_name, estimated_size
            FROM duckdb_tables()
            WHERE schema_name = 'main'
            ORDER BY table_name
            """
        ).fetchdf()

        year_coverage = con.execute(
            """
            WITH years AS (
                SELECT year(cal_date) AS year, count(*) AS open_trade_days
                FROM trade_calendar
                WHERE exchange = 'SSE' AND is_open = true
                GROUP BY 1
            ),
            d AS (
                SELECT year(trade_date) AS year, count(*) AS daily_rows, count(DISTINCT trade_date) AS daily_trade_days
                FROM stock_daily
                GROUP BY 1
            ),
            b AS (
                SELECT year(trade_date) AS year, count(*) AS daily_basic_rows, count(DISTINCT trade_date) AS daily_basic_trade_days
                FROM stock_daily_basic
                GROUP BY 1
            ),
            l AS (
                SELECT year(trade_date) AS year, count(*) AS limit_rows, count(DISTINCT trade_date) AS limit_trade_days
                FROM stock_limit_price
                GROUP BY 1
            )
            SELECT
                y.year,
                y.open_trade_days,
                coalesce(d.daily_trade_days, 0) AS daily_trade_days,
                coalesce(b.daily_basic_trade_days, 0) AS daily_basic_trade_days,
                coalesce(l.limit_trade_days, 0) AS limit_trade_days,
                coalesce(d.daily_rows, 0) AS daily_rows,
                coalesce(b.daily_basic_rows, 0) AS daily_basic_rows,
                coalesce(l.limit_rows, 0) AS limit_rows,
                round(coalesce(d.daily_trade_days, 0) * 1.0 / nullif(y.open_trade_days, 0), 4) AS daily_day_coverage,
                round(coalesce(b.daily_basic_trade_days, 0) * 1.0 / nullif(y.open_trade_days, 0), 4) AS daily_basic_day_coverage,
                round(coalesce(l.limit_trade_days, 0) * 1.0 / nullif(y.open_trade_days, 0), 4) AS limit_day_coverage
            FROM years y
            LEFT JOIN d USING (year)
            LEFT JOIN b USING (year)
            LEFT JOIN l USING (year)
            ORDER BY y.year
            """
        ).fetchdf()

        null_checks = con.execute(
            """
            SELECT 'stock_daily.close_null' AS check_name, count(*) AS issue_count FROM stock_daily WHERE close IS NULL
            UNION ALL
            SELECT 'stock_daily.non_positive_close', count(*) FROM stock_daily WHERE close <= 0
            UNION ALL
            SELECT 'stock_adj_factor.null_factor', count(*) FROM stock_adj_factor WHERE adj_factor IS NULL
            UNION ALL
            SELECT 'stock_adj_factor.non_positive_factor', count(*) FROM stock_adj_factor WHERE adj_factor <= 0
            UNION ALL
            SELECT 'financial_income_raw.null_effective_date', count(*) FROM financial_income_raw WHERE coalesce(first_ann_date, ann_date) IS NULL
            UNION ALL
            SELECT 'financial_balance_raw.null_effective_date', count(*) FROM financial_balance_raw WHERE coalesce(first_ann_date, ann_date) IS NULL
            UNION ALL
            SELECT 'financial_cashflow_raw.null_effective_date', count(*) FROM financial_cashflow_raw WHERE coalesce(first_ann_date, ann_date) IS NULL
            UNION ALL
            SELECT 'financial_indicator_raw.null_ann_date', count(*) FROM financial_indicator_raw WHERE ann_date IS NULL
            """
        ).fetchdf()

        duplicate_checks = con.execute(
            """
            SELECT 'stock_daily.pk_duplicates' AS check_name, count(*) AS duplicate_groups
            FROM (
                SELECT ts_code, trade_date, count(*) AS c FROM stock_daily GROUP BY 1,2 HAVING c > 1
            )
            UNION ALL
            SELECT 'stock_daily_basic.pk_duplicates', count(*) FROM (
                SELECT ts_code, trade_date, count(*) AS c FROM stock_daily_basic GROUP BY 1,2 HAVING c > 1
            )
            UNION ALL
            SELECT 'stock_adj_factor.pk_duplicates', count(*) FROM (
                SELECT ts_code, trade_date, count(*) AS c FROM stock_adj_factor GROUP BY 1,2 HAVING c > 1
            )
            UNION ALL
            SELECT 'financial_income_raw.pk_duplicates', count(*) FROM (
                SELECT ts_code, end_date, comp_type, report_type, ann_date, count(*) AS c
                FROM financial_income_raw GROUP BY 1,2,3,4,5 HAVING c > 1
            )
            UNION ALL
            SELECT 'financial_indicator_raw.pk_duplicates', count(*) FROM (
                SELECT ts_code, end_date, ann_date, count(*) AS c
                FROM financial_indicator_raw GROUP BY 1,2,3 HAVING c > 1
            )
            """
        ).fetchdf()

        null_ratios = con.execute(
            """
            WITH checks AS (
                SELECT 'financial_income_raw.total_revenue' AS check_name, count(*) AS total_rows,
                    sum(CASE WHEN total_revenue IS NULL THEN 1 ELSE 0 END) AS null_rows, 0.05 AS warn_threshold
                FROM financial_income_raw
                UNION ALL
                SELECT 'financial_indicator_raw.roe', count(*),
                    sum(CASE WHEN roe IS NULL THEN 1 ELSE 0 END), 0.05
                FROM financial_indicator_raw
                UNION ALL
                SELECT 'financial_indicator_raw.gross_margin', count(*),
                    sum(CASE WHEN gross_margin IS NULL THEN 1 ELSE 0 END), 0.05
                FROM financial_indicator_raw
                UNION ALL
                SELECT 'stock_daily_basic.pe_ttm', count(*),
                    sum(CASE WHEN pe_ttm IS NULL THEN 1 ELSE 0 END), 0.10
                FROM stock_daily_basic
                UNION ALL
                SELECT 'stock_daily_basic.pb', count(*),
                    sum(CASE WHEN pb IS NULL THEN 1 ELSE 0 END), 0.10
                FROM stock_daily_basic
            )
            SELECT
                check_name,
                total_rows,
                null_rows,
                round(null_rows * 1.0 / nullif(total_rows, 0), 6) AS null_ratio,
                warn_threshold,
                null_rows * 1.0 / nullif(total_rows, 0) > warn_threshold AS is_warning
            FROM checks
            """
        ).fetchdf()

        view_counts = con.execute(
            """
            SELECT 'stock_price_adjusted' AS view_name, count(*) AS rows FROM stock_price_adjusted
            UNION ALL SELECT 'stock_base_daily', count(*) FROM stock_base_daily
            UNION ALL SELECT 'market_breadth_daily', count(*) FROM market_breadth_daily
            UNION ALL SELECT 'concept_daily', count(*) FROM concept_daily
            UNION ALL SELECT 'industry_daily', count(*) FROM industry_daily
            UNION ALL SELECT 'stock_base_daily_enriched', count(*) FROM stock_base_daily_enriched
            UNION ALL SELECT 'financial_income', count(*) FROM financial_income
            UNION ALL SELECT 'financial_balance', count(*) FROM financial_balance
            UNION ALL SELECT 'financial_cashflow', count(*) FROM financial_cashflow
            UNION ALL SELECT 'financial_indicator', count(*) FROM financial_indicator
            UNION ALL SELECT 'financial_event_forecast', count(*) FROM financial_event_forecast
            UNION ALL SELECT 'financial_event_audit', count(*) FROM financial_event_audit
            UNION ALL SELECT 'financial_event_mainbz', count(*) FROM financial_event_mainbz
            UNION ALL SELECT 'financial_event_holdernumber', count(*) FROM financial_event_holdernumber
            UNION ALL SELECT 'financial_event_top10_holders', count(*) FROM financial_event_top10_holders
            UNION ALL SELECT 'financial_event_pledge_detail', count(*) FROM financial_event_pledge_detail
            UNION ALL SELECT 'financial_event_repurchase', count(*) FROM financial_event_repurchase
            UNION ALL SELECT 'financial_event_share_float', count(*) FROM financial_event_share_float
            UNION ALL SELECT 'financial_dividend', count(*) FROM financial_dividend
            UNION ALL SELECT 'financial_pledge_stat', count(*) FROM financial_pledge_stat
            """
        ).fetchdf()

    paths = [
        _write_csv(table_counts, "quality_table_counts.csv"),
        _write_csv(year_coverage, "quality_year_coverage.csv"),
        _write_csv(null_checks, "quality_null_checks.csv"),
        _write_csv(null_ratios, "quality_null_ratios.csv"),
        _write_csv(duplicate_checks, "quality_duplicate_checks.csv"),
        _write_csv(view_counts, "quality_view_counts.csv"),
    ]
    paths.append(_write_markdown(table_counts, year_coverage, null_checks, null_ratios, duplicate_checks, view_counts))
    return paths


def _write_csv(df: pd.DataFrame, filename: str) -> Path:
    path = REPORTS_DIR / filename
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _write_markdown(
    table_counts: pd.DataFrame,
    year_coverage: pd.DataFrame,
    null_checks: pd.DataFrame,
    null_ratios: pd.DataFrame,
    duplicate_checks: pd.DataFrame,
    view_counts: pd.DataFrame,
) -> Path:
    path = REPORTS_DIR / "quality_audit_report.md"
    text = [
        "# Phase 2 Quality Audit Report",
        "",
        f"Generated at: {datetime.now(UTC).replace(tzinfo=None).isoformat(timespec='seconds')} UTC",
        "",
        "## Summary",
        "",
        f"- Tables inspected: {len(table_counts)}",
        f"- Years covered by trading calendar: {year_coverage['year'].min()} - {year_coverage['year'].max()}",
        f"- Quality checks with non-zero issues: {int((pd.concat([null_checks['issue_count'], duplicate_checks['duplicate_groups']]) > 0).sum())}",
        f"- Null-ratio warnings: {int(null_ratios['is_warning'].sum())}",
        "",
        "## Year Coverage",
        "",
        year_coverage.to_markdown(index=False),
        "",
        "## Null / Value Checks",
        "",
        null_checks.to_markdown(index=False),
        "",
        "## Null Ratio Checks",
        "",
        null_ratios.to_markdown(index=False),
        "",
        "## Duplicate Checks",
        "",
        duplicate_checks.to_markdown(index=False),
        "",
        "## View Counts",
        "",
        view_counts.to_markdown(index=False),
    ]
    path.write_text("\n".join(text), encoding="utf-8")
    return path
