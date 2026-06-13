from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from stock_maintainance.database import init_database
from stock_maintainance.features.context import FeatureBuildContext
from stock_maintainance.features.modules import (
    build_price_technical,
    build_volume_liquidity,
    build_volatility_risk,
)


def _ctx(con: duckdb.DuckDBPyConnection, start: str, end: str) -> FeatureBuildContext:
    return FeatureBuildContext(
        con=con,
        module="technical_test",
        read_start_date=start,
        write_start_date=start,
        write_end_date=end,
    )


@pytest.fixture()
def con() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    init_database(connection)
    try:
        yield connection
    finally:
        connection.close()


def _insert_spine_rows(con: duckdb.DuckDBPyConnection, closes: list[float]) -> None:
    start = date(2026, 1, 1)
    previous = None
    for idx, close in enumerate(closes):
        trade_date = start + timedelta(days=idx)
        ret = None if previous is None else close / previous - 1
        log_ret = None if previous is None else __import__("math").log(close / previous)
        con.execute(
            """
            INSERT INTO derived_daily_spine (
                ts_code, trade_date, close_hfq, high_hfq, low_hfq,
                volume, amount, ret_1_hfq, log_ret_1_hfq
            )
            VALUES ('000001.SZ', ?, ?, ?, ?, 100, 1000, ?, ?)
            """,
            [trade_date.isoformat(), close, close, close, ret, log_ret],
        )
        con.execute(
            """
            INSERT INTO stock_daily_basic (ts_code, trade_date, turnover_rate, turnover_rate_free)
            VALUES ('000001.SZ', ?, 1.0, 1.0)
            """,
            [trade_date.isoformat()],
        )
        previous = close


def test_price_and_volume_ratios_require_full_observation_windows(con: duckdb.DuckDBPyConnection) -> None:
    closes = [float(i) for i in range(1, 26)]
    _insert_spine_rows(con, closes)

    build_price_technical(_ctx(con, "2026-01-01", "2026-01-25"))
    build_volume_liquidity(_ctx(con, "2026-01-01", "2026-01-25"))

    early_price = con.execute(
        """
        SELECT ma_20_hfq, close_to_ma_20_hfq, price_position_20_hfq
        FROM derived_price_technical
        WHERE ts_code = '000001.SZ' AND trade_date = DATE '2026-01-05'
        """
    ).fetchone()
    mature_price = con.execute(
        """
        SELECT ma_20_hfq, close_to_ma_20_hfq, price_position_20_hfq
        FROM derived_price_technical
        WHERE ts_code = '000001.SZ' AND trade_date = DATE '2026-01-20'
        """
    ).fetchone()
    early_volume = con.execute(
        """
        SELECT volume_ma_20, volume_ratio_20, amount_ratio_20
        FROM derived_volume_liquidity
        WHERE ts_code = '000001.SZ' AND trade_date = DATE '2026-01-05'
        """
    ).fetchone()

    assert early_price == (None, None, None)
    assert mature_price[0] is not None
    assert mature_price[1] is not None
    assert mature_price[2] is not None
    assert early_volume == (None, None, None)


def test_max_drawdown_uses_only_current_window_pairs(con: duckdb.DuckDBPyConnection) -> None:
    closes = [90.0] * 40
    closes[1] = 100.0
    closes[20] = 50.0
    _insert_spine_rows(con, closes)

    build_volatility_risk(_ctx(con, "2026-01-01", "2026-02-09"))

    row = con.execute(
        """
        SELECT max_drawdown_20_hfq
        FROM derived_volatility_risk
        WHERE ts_code = '000001.SZ' AND trade_date = DATE '2026-02-09'
        """
    ).fetchone()

    assert row[0] == pytest.approx(0.0)


def test_trading_technical_full_view_uses_core_aligned_risk_formulas() -> None:
    sql_source = Path("scripts/create_phase3_trading_technical_full_views.py").read_text(encoding="utf-8")

    assert "FROM b AS trough" in sql_source
    assert "FROM b AS peak" in sql_source
    assert "close_hfq / nullif({max_expr('close_hfq'" not in sql_source
    assert "CASE WHEN log_ret_1_hfq < 0 THEN log_ret_1_hfq ELSE 0 END" not in sql_source
    assert "count(CASE WHEN log_ret_1_hfq < 0 THEN log_ret_1_hfq END)" in sql_source


def test_daily_spine_gap_open_is_absolute_not_overnight_duplicate() -> None:
    source = (Path("src") / "stock_maintainance" / "features" / "modules.py").read_text(encoding="utf-8")

    assert "END AS overnight_ret_hfq" in source
    assert "THEN abs(open_hfq / lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) - 1)" in source
    assert "END AS gap_open_hfq" in source


def test_volatility_core_uses_window_specific_observation_guards() -> None:
    source = (Path("src") / "stock_maintainance" / "features" / "modules.py").read_text(encoding="utf-8")

    assert "obs_ret_20 >= 20 THEN hv_20" in source
    assert "obs_ret_60 >= 60 THEN hv_60" in source
    assert "obs_ret_120 >= 120 THEN hv_120" in source
    assert "obs_hilo_20 >= 20 THEN parkinson_vol_20" in source
    assert "obs_tr_14 >= 14 THEN atr_14_hfq" in source
    assert "obs_120 >= 20" not in source


def test_trading_constraint_rollups_require_flag_observations() -> None:
    source = (Path("src") / "stock_maintainance" / "features" / "modules.py").read_text(encoding="utf-8")

    assert "count(limit_up_flag) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)" in source
    assert "CASE WHEN limit_flag_obs_5 >= 5 THEN CAST(limit_up_days_5 AS INTEGER) ELSE NULL END" in source
    assert "CASE WHEN limit_flag_obs_20 >= 20 THEN CAST(limit_up_days_20 AS INTEGER) ELSE NULL END" in source
    assert "CASE WHEN touch_limit_flag_obs_20 >= 20 THEN CAST(touch_limit_up_days_20 AS INTEGER) ELSE NULL END" in source
