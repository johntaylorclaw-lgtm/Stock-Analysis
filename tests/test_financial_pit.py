from __future__ import annotations

import duckdb
import pytest

from stock_maintainance.database import init_database
from stock_maintainance.features.context import FeatureBuildContext
from stock_maintainance.features.modules import build_financial_asof, build_financial_growth, build_financial_quality


def _ctx(con: duckdb.DuckDBPyConnection) -> FeatureBuildContext:
    return FeatureBuildContext(
        con=con,
        module="financial_test",
        read_start_date="2026-04-01",
        write_start_date="2026-04-10",
        write_end_date="2026-04-25",
    )


@pytest.fixture()
def con() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    init_database(connection)
    try:
        yield connection
    finally:
        connection.close()


def _insert_asof(con: duckdb.DuckDBPyConnection, ts_code: str, trade_date: str, end_date: str) -> None:
    con.execute(
        """
        INSERT INTO derived_financial_asof (
            ts_code, trade_date, latest_report_end_date, latest_financial_effective_date,
            latest_financial_ann_date, report_age_days, report_lag_days, report_year,
            report_quarter, statement_available_count, has_forecast_asof, has_express_asof
        )
        VALUES (?, ?, ?, ?, ?, 1, 1, 2025, 4, 4, false, false)
        """,
        [ts_code, trade_date, end_date, trade_date, trade_date],
    )


def _insert_report_set(
    con: duckdb.DuckDBPyConnection,
    ts_code: str,
    end_date: str,
    ann_date: str,
    revenue: float | None,
    parent_net_profit: float | None,
    roe: float,
    or_yoy: float,
) -> None:
    con.execute(
        """
        INSERT INTO financial_indicator_raw (
            ts_code, ann_date, end_date, roe, or_yoy, profit_dedt,
            debt_to_assets, assets_to_eqt, current_ratio, gross_margin, effective_date, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, 50, 2, 1.5, 40, ?, '{}')
        """,
        [ts_code, ann_date, end_date, roe, or_yoy, parent_net_profit, ann_date],
    )
    con.execute(
        """
        INSERT INTO financial_income_raw (
            ts_code, ann_date, first_ann_date, end_date, report_type, comp_type,
            total_revenue, revenue, operating_cost, total_cogs, operating_profit,
            total_profit, net_profit, net_profit_attr_parent, ebit, ebitda,
            business_tax_surcharge, income_tax, effective_date, payload_json
        )
        VALUES (?, ?, ?, ?, '1', '1', ?, ?, 60, 60, ?, ?, ?, ?, ?, ?, 1, 5, ?, '{}')
        """,
        [
            ts_code,
            ann_date,
            ann_date,
            end_date,
            revenue,
            revenue,
            parent_net_profit,
            parent_net_profit,
            parent_net_profit,
            parent_net_profit,
            parent_net_profit,
            parent_net_profit,
            ann_date,
        ],
    )
    con.execute(
        """
        INSERT INTO financial_balance_raw (
            ts_code, ann_date, first_ann_date, end_date, report_type, comp_type,
            cash_and_equivalents, current_assets, fixed_assets, total_assets,
            current_liabilities, total_liabilities, total_equity, equity_attr_parent,
            effective_date, payload_json
        )
        VALUES (?, ?, ?, ?, '1', '1', 30, 80, 50, 200, 50, 100, 100, 100, ?, '{}')
        """,
        [ts_code, ann_date, ann_date, end_date, ann_date],
    )
    con.execute(
        """
        INSERT INTO financial_cashflow_raw (
            ts_code, ann_date, first_ann_date, end_date, report_type, comp_type,
            cash_received_from_sales, cash_paid_for_goods, cf_from_operating,
            cash_paid_for_capex, free_cashflow, net_increase_in_cash,
            cash_at_beginning, cash_at_end, effective_date, payload_json
        )
        VALUES (?, ?, ?, ?, '1', '1', 90, 50, 20, 5, 15, 10, 20, 30, ?, '{}')
        """,
        [ts_code, ann_date, ann_date, end_date, ann_date],
    )


def test_financial_quality_uses_trade_date_point_in_time_version(con: duckdb.DuckDBPyConnection) -> None:
    _insert_asof(con, "000001.SZ", "2026-04-10", "2025-12-31")
    _insert_asof(con, "000001.SZ", "2026-04-25", "2025-12-31")
    _insert_report_set(con, "000001.SZ", "2025-12-31", "2026-04-01", 100, 10, 10, 11)
    _insert_report_set(con, "000001.SZ", "2025-12-31", "2026-04-20", 100, 20, 20, 22)

    build_financial_quality(_ctx(con))

    rows = con.execute(
        """
        SELECT trade_date, roe_asof, round(dupont_roe_calc_asof, 6), round(roe_calc_gap_asof, 6)
        FROM derived_financial_quality
        WHERE ts_code = '000001.SZ'
        ORDER BY trade_date
        """
    ).fetchall()

    assert [(str(row[0]), row[1], row[2], row[3]) for row in rows] == [
        ("2026-04-10", 10.0, 0.1, 0.0),
        ("2026-04-25", 20.0, 0.2, 0.0),
    ]


def test_financial_asof_maps_next_disclosure_schedule(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS financial_forecast (
            ts_code VARCHAR,
            ann_date DATE,
            end_date DATE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS financial_express (
            ts_code VARCHAR,
            ann_date DATE,
            end_date DATE
        )
        """
    )
    con.execute(
        """
        INSERT INTO stock_daily (ts_code, trade_date, close)
        VALUES ('000001.SZ', '2026-04-10', 10.0)
        """
    )
    con.execute(
        """
        INSERT INTO financial_indicator_raw (
            ts_code, ann_date, end_date, roe, effective_date, payload_json
        )
        VALUES ('000001.SZ', '2026-03-30', '2025-12-31', 10, '2026-03-30', '{}')
        """
    )
    con.execute(
        """
        INSERT INTO financial_disclosure_schedule (
            ts_code, ann_date, end_date, record_key, pre_date, actual_date, modify_date
        )
        VALUES ('000001.SZ', '2026-04-01', '2026-03-31', 'r1', '2026-04-20', NULL, NULL)
        """
    )

    build_financial_asof(_ctx(con))

    row = con.execute(
        """
        SELECT next_disclosure_pre_date, days_to_next_disclosure
        FROM derived_financial_asof
        WHERE ts_code = '000001.SZ' AND trade_date = '2026-04-10'
        """
    ).fetchone()

    assert str(row[0]) == "2026-04-20"
    assert row[1] == 10


def test_financial_growth_uses_trade_date_pit_and_excludes_sentinel_direction(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_asof(con, "000002.SZ", "2025-04-25", "2024-12-31")
    _insert_asof(con, "000002.SZ", "2026-04-10", "2025-12-31")
    _insert_asof(con, "000002.SZ", "2026-04-25", "2025-12-31")
    _insert_report_set(con, "000002.SZ", "2024-12-31", "2025-04-01", 100, 100, 10, 10)
    _insert_report_set(con, "000002.SZ", "2025-12-31", "2026-04-01", 0, 80, 10, 11)
    _insert_report_set(con, "000002.SZ", "2025-12-31", "2026-04-20", 200, 120, 20, 22)

    build_financial_growth(_ctx(con))

    rows = con.execute(
        """
        SELECT
            trade_date,
            revenue_yoy_asof,
            revenue_yoy_1y_calc_asof,
            parent_net_profit_yoy_1y_calc_asof,
            revenue_profit_same_direction_flag
        FROM derived_financial_growth
        WHERE ts_code = '000002.SZ'
        ORDER BY trade_date
        """
    ).fetchall()

    assert str(rows[0][0]) == "2026-04-10"
    assert rows[0][1] == 11.0
    assert rows[0][2] < -9_000_000
    assert rows[0][3] == pytest.approx(-0.2)
    assert rows[0][4] is False
    assert str(rows[1][0]) == "2026-04-25"
    assert rows[1][1] == 22.0


def test_financial_growth_qoq_and_single_quarter_require_adjacent_report(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_asof(con, "000003.SZ", "2025-10-31", "2025-09-30")
    _insert_report_set(con, "000003.SZ", "2025-03-31", "2025-04-20", 100, 10, 10, 10)
    _insert_report_set(con, "000003.SZ", "2025-09-30", "2025-10-20", 300, 30, 10, 30)

    build_financial_growth(
        FeatureBuildContext(
            con=con,
            module="financial_test",
            read_start_date="2025-10-01",
            write_start_date="2025-10-31",
            write_end_date="2025-10-31",
        )
    )

    row = con.execute(
        """
        SELECT revenue_qoq_report_asof, revenue_single_quarter_value_asof
        FROM derived_financial_growth
        WHERE ts_code = '000003.SZ' AND trade_date = DATE '2025-10-31'
        """
    ).fetchone()

    assert row == (None, None)


def test_financial_asof_statement_flags_coalesce_to_false() -> None:
    from pathlib import Path

    source = Path("src/stock_maintainance/features/modules.py").read_text(encoding="utf-8")

    assert "coalesce(income_report_end_date = latest_report_end_date, false) AS has_income_statement" in source
    assert "coalesce(balance_report_end_date = latest_report_end_date, false) AS has_balance_sheet" in source
    assert "coalesce(cashflow_report_end_date = latest_report_end_date, false) AS has_cashflow_statement" in source
    assert "coalesce(indicator_report_end_date = latest_report_end_date, false) AS has_indicator_statement" in source
