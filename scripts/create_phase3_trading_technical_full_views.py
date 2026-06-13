from __future__ import annotations

from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"

PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
RETURN_PERIODS = [1, 2, 3, 5, 10, 20, 30, 60, 120, 250]
SHORT_REVERSAL_PERIODS = [2, 3, 5, 10]
PATH_PERIODS = [5, 10, 20, 30, 60, 120]
VOL_PERIODS = [5, 10, 20, 30, 60, 120, 250]
ATR_PERIODS = [5, 10, 14, 20, 30, 60]
LIMIT_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120]


def win(alias: str, n: int) -> str:
    return f"{alias}.ts_code ORDER BY {alias}.trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW"


def avg_expr(expr: str, n: int, alias: str = "ds") -> str:
    return f"avg({expr}) OVER (PARTITION BY {win(alias, n)})"


def std_expr(expr: str, n: int, alias: str = "ds") -> str:
    return f"stddev_samp({expr}) OVER (PARTITION BY {win(alias, n)})"


def min_expr(expr: str, n: int, alias: str = "ds") -> str:
    return f"min({expr}) OVER (PARTITION BY {win(alias, n)})"


def max_expr(expr: str, n: int, alias: str = "ds") -> str:
    return f"max({expr}) OVER (PARTITION BY {win(alias, n)})"


def sum_bool_expr(expr: str, n: int, alias: str = "ds") -> str:
    return f"sum(CASE WHEN {expr} THEN 1 ELSE 0 END) OVER (PARTITION BY {win(alias, n)})::INTEGER"


def pct_change_expr(n: int) -> str:
    return (
        "CASE WHEN ds.close_hfq > 0 "
        f"AND lag(ds.close_hfq, {n}) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0 "
        f"THEN ds.close_hfq / lag(ds.close_hfq, {n}) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) - 1 "
        "ELSE NULL END"
    )


def rsi_expr(n: int) -> str:
    gain = avg_expr("CASE WHEN ds.ret_1_hfq > 0 THEN ds.ret_1_hfq ELSE 0 END", n)
    loss = avg_expr("CASE WHEN ds.ret_1_hfq < 0 THEN -ds.ret_1_hfq ELSE 0 END", n)
    return (
        f"CASE WHEN {loss} > 0 THEN 100 - 100 / (1 + {gain} / NULLIF({loss}, 0)) "
        f"WHEN {gain} > 0 THEN 100 ELSE NULL END"
    )


def daily_spine_view() -> str:
    return """
    CREATE OR REPLACE VIEW derived_daily_spine_full_v AS
    SELECT
        ds.*,
        open_raw * adj_factor / nullif(latest_adj_factor_asof, 0) AS open_qfq,
        high_raw * adj_factor / nullif(latest_adj_factor_asof, 0) AS high_qfq,
        low_raw * adj_factor / nullif(latest_adj_factor_asof, 0) AS low_qfq,
        close_raw * adj_factor / nullif(latest_adj_factor_asof, 0) AS close_qfq,
        pre_close_raw * adj_factor / nullif(latest_adj_factor_asof, 0) AS pre_close_qfq,
        close_raw - open_raw AS body_raw,
        high_raw - greatest(open_raw, close_raw) AS upper_shadow_raw,
        least(open_raw, close_raw) - low_raw AS lower_shadow_raw,
        abs(close_raw - open_raw) / nullif(high_raw - low_raw, 0) AS body_ratio_raw,
        greatest(
            high_hfq - low_hfq,
            abs(high_hfq - lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date)),
            abs(low_hfq - lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date))
        ) AS true_range_hfq,
        volume IS NULL OR volume = 0 AS suspended_flag,
        (
            open_raw BETWEEN up_limit - 0.005 AND up_limit + 0.005
            AND high_raw BETWEEN up_limit - 0.005 AND up_limit + 0.005
            AND low_raw BETWEEN up_limit - 0.005 AND up_limit + 0.005
            AND close_raw BETWEEN up_limit - 0.005 AND up_limit + 0.005
        )
        OR (
            open_raw BETWEEN down_limit - 0.005 AND down_limit + 0.005
            AND high_raw BETWEEN down_limit - 0.005 AND down_limit + 0.005
            AND low_raw BETWEEN down_limit - 0.005 AND down_limit + 0.005
            AND close_raw BETWEEN down_limit - 0.005 AND down_limit + 0.005
        ) AS one_price_limit_flag,
        NOT price_valid_flag AS ohlc_relation_error_flag
    FROM derived_daily_spine ds
    """


def price_technical_view() -> str:
    ma_extra = [2, 3, 30]
    ma_cte = [f"{avg_expr('ds.close_hfq', n)} AS ma_{n}_hfq" for n in ma_extra + [6, 9, 12, 24, 26]]
    std_cte = [f"{std_expr('ds.close_hfq', n)} AS close_std_{n}" for n in [20, 30, 60]]
    high_low_cte = [
        item
        for n in [5, 9, 10, 20, 30, 60, 120, 250]
        for item in (
            f"{min_expr('ds.low_hfq', n)} AS low_{n}",
            f"{max_expr('ds.high_hfq', n)} AS high_{n}",
        )
    ]
    base_fields = [
        "ds.ts_code",
        "ds.trade_date",
        "ds.close_hfq",
        "ds.ret_1_hfq",
        "pt.ma_5_hfq",
        "pt.ma_10_hfq",
        "pt.ma_20_hfq",
        "pt.ma_60_hfq",
        "pt.ma_120_hfq",
        "pt.ma_250_hfq",
        "pt.close_to_ma_20_hfq",
        "pt.close_to_ma_60_hfq",
        "pt.ma_20_slope_20_hfq",
        "pt.ma_60_slope_60_hfq",
        "pt.rsi_14",
        "pt.price_position_20_hfq",
        "pt.price_position_60_hfq",
        "pt.updated_at",
        *ma_cte,
        *std_cte,
        *high_low_cte,
    ]
    slopes = [
        f"CASE WHEN ma_{n}_hfq > 0 AND lag(ma_{n}_hfq, {n}) OVER (PARTITION BY ts_code ORDER BY trade_date) > 0 "
        f"THEN ma_{n}_hfq / lag(ma_{n}_hfq, {n}) OVER (PARTITION BY ts_code ORDER BY trade_date) - 1 ELSE NULL END AS ma_{n}_slope_{n}_hfq"
        for n in [2, 3, 5, 10, 30, 120]
    ]
    close_to = [
        f"CASE WHEN ma_{n}_hfq > 0 THEN close_hfq / ma_{n}_hfq - 1 ELSE NULL END AS close_to_ma_{n}_hfq"
        for n in [2, 3, 5, 10, 30, 120, 250]
    ]
    positions = [
        f"CASE WHEN high_{n} > low_{n} THEN (close_hfq - low_{n}) / (high_{n} - low_{n}) ELSE NULL END AS price_position_{n}_hfq"
        for n in [5, 10, 30, 120, 250]
    ]
    bias = [
        f"CASE WHEN ma_{n}_hfq > 0 THEN close_hfq / ma_{n}_hfq - 1 ELSE NULL END AS bias_{n}_hfq"
        for n in [3, 5, 6, 10, 12, 20, 24, 30, 60]
    ]
    boll = [item for n in [20, 30, 60] for item in boll_for(n)]
    select_fields = [
        "ts_code",
        "trade_date",
        "ma_2_hfq",
        "ma_3_hfq",
        "ma_5_hfq",
        "ma_10_hfq",
        "ma_20_hfq",
        "ma_30_hfq",
        "ma_60_hfq",
        "ma_120_hfq",
        "ma_250_hfq",
        "close_to_ma_20_hfq",
        "close_to_ma_60_hfq",
        *close_to,
        "ma_20_slope_20_hfq",
        "ma_60_slope_60_hfq",
        *slopes,
        "ma_5_hfq > ma_20_hfq AND ma_20_hfq > ma_60_hfq AS ma_bullish_5_20_60_flag",
        "ma_10_hfq > ma_30_hfq AND ma_30_hfq > ma_120_hfq AS ma_bullish_10_30_120_flag",
        "ma_5_hfq < ma_20_hfq AND ma_20_hfq < ma_60_hfq AS ma_bearish_5_20_60_flag",
        "ma_10_hfq < ma_30_hfq AND ma_30_hfq < ma_120_hfq AS ma_bearish_10_30_120_flag",
        f"{rsi_expr(6)} AS rsi_6",
        f"{rsi_expr(9)} AS rsi_9",
        "rsi_14",
        f"{rsi_expr(24)} AS rsi_24",
        *bias,
        "price_position_20_hfq",
        "price_position_60_hfq",
        *positions,
        *boll,
        "macd_dif_12_26_hfq",
        "macd_dea_9_hfq",
        "macd_dif_12_26_hfq - macd_dea_9_hfq AS macd_hist_12_26_9_hfq",
        "kdj_k_9_3_3_hfq",
        "avg(kdj_k_9_3_3_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS kdj_d_9_3_3_hfq",
        "3 * kdj_k_9_3_3_hfq - 2 * avg(kdj_k_9_3_3_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS kdj_j_9_3_3_hfq",
        "updated_at",
    ]
    return f"""
    CREATE OR REPLACE VIEW derived_price_technical_full_v AS
    WITH base AS (
        SELECT
            {",\n            ".join(base_fields)}
        FROM derived_daily_spine ds
        LEFT JOIN derived_price_technical pt USING (ts_code, trade_date)
    ),
    calc AS (
        SELECT
            *,
            ma_12_hfq - ma_26_hfq AS macd_dif_12_26_hfq,
            CASE WHEN high_9 > low_9 THEN (close_hfq - low_9) / (high_9 - low_9) * 100 ELSE NULL END AS rsv_9
        FROM base
    ),
    calc2 AS (
        SELECT
            *,
            avg(macd_dif_12_26_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 8 PRECEDING AND CURRENT ROW) AS macd_dea_9_hfq,
            avg(rsv_9) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS kdj_k_9_3_3_hfq
        FROM calc
    )
    SELECT
        {",\n        ".join(select_fields)}
    FROM calc2 ds
    """


def boll_for(n: int) -> list[str]:
    return [
        f"ma_{n}_hfq AS boll_mid_{n}_hfq",
        f"ma_{n}_hfq + 2 * close_std_{n} AS boll_upper_{n}_hfq",
        f"ma_{n}_hfq - 2 * close_std_{n} AS boll_lower_{n}_hfq",
        f"4 * close_std_{n} / nullif(ma_{n}_hfq, 0) AS boll_width_{n}_hfq",
        f"(close_hfq - (ma_{n}_hfq - 2 * close_std_{n})) / nullif(4 * close_std_{n}, 0) AS boll_pct_b_{n}_hfq",
    ]


def return_momentum_view() -> str:
    ret_extras = [n for n in RETURN_PERIODS if n not in {2, 5, 10, 20, 60, 120, 250}]
    fields = [
        "rm.ts_code",
        "rm.trade_date",
        "rm.ret_2_hfq",
        "rm.ret_5_hfq",
        "rm.ret_10_hfq",
        "rm.ret_20_hfq",
        "rm.ret_60_hfq",
        "rm.ret_120_hfq",
        "rm.ret_250_hfq",
        "rm.log_ret_sum_20_hfq",
        "rm.momentum_20_5_hfq",
        "rm.momentum_60_20_hfq",
        "rm.reversal_5_hfq",
        "rm.up_days_20",
        "rm.down_days_20",
        *[f"{pct_change_expr(n)} AS ret_{n}_hfq" for n in ret_extras],
        *[
            f"sum(ds.log_ret_1_hfq) OVER (PARTITION BY {win('ds', n)}) AS log_ret_sum_{n}_hfq"
            for n in PERIODS
            if n != 20
        ],
        "CASE WHEN lag(ds.close_hfq, 10) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0 AND lag(ds.close_hfq, 30) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0 THEN lag(ds.close_hfq, 10) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) / lag(ds.close_hfq, 30) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) - 1 ELSE NULL END AS momentum_30_10_hfq",
        "CASE WHEN lag(ds.close_hfq, 20) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0 AND lag(ds.close_hfq, 120) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0 THEN lag(ds.close_hfq, 20) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) / lag(ds.close_hfq, 120) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) - 1 ELSE NULL END AS momentum_120_20_hfq",
        "CASE WHEN lag(ds.close_hfq, 20) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0 AND lag(ds.close_hfq, 250) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0 THEN lag(ds.close_hfq, 20) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) / lag(ds.close_hfq, 250) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) - 1 ELSE NULL END AS momentum_250_20_hfq",
        *[
            f"-({pct_change_expr(n)}) AS reversal_{n}_hfq"
            for n in SHORT_REVERSAL_PERIODS
            if n != 5
        ],
        *[
            f"{sum_bool_expr('ds.ret_1_hfq > 0', n)} AS up_days_{n}"
            for n in PATH_PERIODS
            if n != 20
        ],
        *[
            f"{sum_bool_expr('ds.ret_1_hfq < 0', n)} AS down_days_{n}"
            for n in PATH_PERIODS
            if n != 20
        ],
        *[
            f"{sum_bool_expr('ds.ret_1_hfq > 0', n)} / {float(n)} AS up_ratio_{n}"
            for n in PATH_PERIODS
        ],
        *[
            f"ds.close_hfq >= {max_expr('ds.close_hfq', n)} AS new_high_{n}_flag"
            for n in [5, 10, 20, 30, 60, 120, 250]
        ],
        *[
            f"ds.close_hfq <= {min_expr('ds.close_hfq', n)} AS new_low_{n}_flag"
            for n in [5, 10, 20, 30, 60, 120, 250]
        ],
        *[
            f"ds.close_hfq / nullif({max_expr('ds.close_hfq', n)}, 0) - 1 AS drawdown_from_high_{n}_hfq"
            for n in [5, 10, 20, 30, 60, 120, 250]
        ],
        *[
            f"ds.close_hfq / nullif({min_expr('ds.close_hfq', n)}, 0) - 1 AS bounce_from_low_{n}_hfq"
            for n in [5, 10, 20, 30, 60, 120, 250]
        ],
        "rm.updated_at",
    ]
    return f"""
    CREATE OR REPLACE VIEW derived_return_momentum_full_v AS
    SELECT
        {",\n        ".join(fields)}
    FROM derived_return_momentum rm
    JOIN derived_daily_spine ds USING (ts_code, trade_date)
    """


def volatility_risk_view() -> str:
    var_windows = [20, 30, 60, 120, 250]
    drawdown_windows = [5, 10, 30, 120, 250]
    downside_windows = [20, 30, 120, 250]
    max_drawdown_fields = [
        f"""
        CASE WHEN count(close_hfq) OVER (PARTITION BY {win('b', n)}) >= {n}
        THEN (
            SELECT min(
                trough.close_hfq / nullif(
                    (
                        SELECT max(peak.close_hfq)
                        FROM b AS peak
                        WHERE peak.ts_code = b.ts_code
                          AND peak.rn BETWEEN b.rn - {n - 1} AND trough.rn
                    ),
                    0
                ) - 1
            )
            FROM b AS trough
            WHERE trough.ts_code = b.ts_code
              AND trough.rn BETWEEN b.rn - {n - 1} AND b.rn
        )
        ELSE NULL END AS max_drawdown_{n}_hfq
        """
        for n in drawdown_windows
    ]
    downside_fields = [
        f"""
        CASE
            WHEN count(CASE WHEN log_ret_1_hfq < 0 THEN log_ret_1_hfq END) OVER (PARTITION BY {win('b', n)}) >= 2
            THEN stddev_samp(CASE WHEN log_ret_1_hfq < 0 THEN log_ret_1_hfq ELSE NULL END)
                 OVER (PARTITION BY {win('b', n)}) * sqrt(242)
            ELSE NULL
        END AS downside_vol_{n}
        """
        for n in downside_windows
    ]
    base_fields = [
        "vr.*",
        "ds.log_ret_1_hfq",
        "ds.ret_1_hfq",
        "ds.high_hfq",
        "ds.low_hfq",
        "ds.close_hfq",
        "fv.true_range_hfq",
        "row_number() OVER (PARTITION BY vr.ts_code ORDER BY vr.trade_date) AS rn",
        *[
            f"quantile_cont(ds.ret_1_hfq, 0.05) OVER (PARTITION BY {win('ds', n)}) AS var_5pct_{n}_calc"
            for n in var_windows
        ],
    ]
    final_fields = [
        "ts_code",
        "trade_date",
        "hv_20",
        "hv_60",
        "hv_120",
        "parkinson_vol_20",
        "atr_14_hfq",
        "atr_14_pct_hfq",
        "max_drawdown_20_hfq",
        "max_drawdown_60_hfq",
        "downside_vol_60",
        "var_5pct_60",
        *[
            f"{std_expr('log_ret_1_hfq', n, 'b')} * sqrt(242) AS hv_{n}"
            for n in [5, 10, 30, 250]
        ],
        *[
            f"sqrt({avg_expr('power(ln(high_hfq / nullif(low_hfq, 0)), 2)', n, 'b')} / (4 * ln(2)) * 242) AS parkinson_vol_{n}"
            for n in [5, 10, 30, 60, 120]
        ],
        *[f"{avg_expr('true_range_hfq', n, 'b')} AS atr_{n}_hfq" for n in [5, 10, 20, 30, 60]],
        *[
            f"{avg_expr('true_range_hfq', n, 'b')} / nullif(close_hfq, 0) AS atr_{n}_pct_hfq"
            for n in [5, 10, 20, 30, 60]
        ],
        *max_drawdown_fields,
        *downside_fields,
        *[
            f"var_5pct_{n}_calc AS var_5pct_{n}"
            for n in var_windows
            if n != 60
        ],
        *[
            f"{avg_expr(f'CASE WHEN ret_1_hfq <= var_5pct_{n}_calc THEN ret_1_hfq ELSE NULL END', n, 'b')} AS cvar_5pct_{n}"
            for n in var_windows
        ],
        "updated_at",
    ]
    return f"""
    CREATE OR REPLACE VIEW derived_volatility_risk_full_v AS
    WITH b AS (
        SELECT
            {",\n            ".join(base_fields)}
        FROM derived_volatility_risk vr
        JOIN derived_daily_spine ds USING (ts_code, trade_date)
        JOIN derived_daily_spine_full_v fv USING (ts_code, trade_date)
    )
    SELECT
        {",\n        ".join(final_fields)}
    FROM b AS b
    """


def volume_liquidity_view() -> str:
    fields = [
        "vl.ts_code",
        "vl.trade_date",
        "vl.volume_ma_5",
        "vl.volume_ma_20",
        "vl.volume_ma_60",
        "vl.amount_ma_20",
        "vl.amount_ma_60",
        "vl.turnover_rate_ma_20",
        "vl.turnover_rate_free_ma_20",
        "vl.volume_ratio_20",
        "vl.amount_ratio_20",
        "vl.amihud_20",
        "vl.zero_volume_days_20",
        *[
            f"{avg_expr('ds.volume', n)} AS volume_ma_{n}"
            for n in [2, 3, 10, 30, 120]
        ],
        *[
            f"{avg_expr('ds.amount', n)} AS amount_ma_{n}"
            for n in [2, 3, 5, 10, 30, 120]
        ],
        *[
            f"{avg_expr('b.turnover_rate', n)} AS turnover_rate_ma_{n}"
            for n in [2, 3, 5, 10, 30, 60, 120]
        ],
        *[
            f"{avg_expr('b.turnover_rate_free', n)} AS turnover_rate_free_ma_{n}"
            for n in [2, 3, 5, 10, 30, 60, 120]
        ],
        *[
            f"ds.volume / nullif({avg_expr('ds.volume', n)}, 0) AS volume_ratio_{n}"
            for n in [2, 3, 5, 10, 30, 60, 120]
        ],
        *[
            f"ds.amount / nullif({avg_expr('ds.amount', n)}, 0) AS amount_ratio_{n}"
            for n in [2, 3, 5, 10, 30, 60, 120]
        ],
        *[
            f"{avg_expr('CASE WHEN ds.amount > 0 THEN abs(ds.ret_1_hfq) / ds.amount ELSE NULL END', n)} AS amihud_{n}"
            for n in [5, 10, 30, 60, 120]
        ],
        *[
            f"{sum_bool_expr('ds.volume = 0', n)} AS zero_volume_days_{n}"
            for n in [5, 10, 30, 60, 120]
        ],
        *[
            f"{std_expr('ds.amount', n)} / nullif({avg_expr('ds.amount', n)}, 0) AS amount_cv_{n}"
            for n in [5, 10, 20, 30, 60, 120]
        ],
        "vl.updated_at",
    ]
    return f"""
    CREATE OR REPLACE VIEW derived_volume_liquidity_full_v AS
    SELECT
        {",\n        ".join(fields)}
    FROM derived_volume_liquidity vl
    JOIN derived_daily_spine ds USING (ts_code, trade_date)
    LEFT JOIN stock_daily_basic b USING (ts_code, trade_date)
    """


def trading_constraint_view() -> str:
    fields = [
        "tc.ts_code",
        "tc.trade_date",
        "tc.limit_up_days_5",
        "tc.limit_up_days_20",
        "tc.limit_down_days_5",
        "tc.limit_down_days_20",
        "tc.touch_limit_up_days_20",
        "tc.touch_limit_down_days_20",
        "tc.consecutive_limit_up_days",
        "tc.consecutive_limit_down_days",
        "tc.one_price_limit_up_flag",
        "tc.one_price_limit_down_flag",
        "tc.tradable_state",
        *[
            f"{sum_bool_expr('ds.limit_up_flag', n)} AS limit_up_days_{n}"
            for n in [2, 3, 10, 30, 60, 120]
        ],
        *[
            f"{sum_bool_expr('ds.limit_down_flag', n)} AS limit_down_days_{n}"
            for n in [2, 3, 10, 30, 60, 120]
        ],
        *[
            f"{sum_bool_expr('ds.touch_limit_up_flag', n)} AS touch_limit_up_days_{n}"
            for n in [2, 3, 5, 10, 30, 60, 120]
        ],
        *[
            f"{sum_bool_expr('ds.touch_limit_down_flag', n)} AS touch_limit_down_days_{n}"
            for n in [2, 3, 5, 10, 30, 60, 120]
        ],
        *[
            f"{sum_bool_expr('ds.open_limit_up_flag', n)} AS open_limit_up_days_{n}"
            for n in LIMIT_PERIODS
        ],
        *[
            f"{sum_bool_expr('ds.open_limit_down_flag', n)} AS open_limit_down_days_{n}"
            for n in LIMIT_PERIODS
        ],
        "tc.one_price_limit_up_flag OR tc.one_price_limit_down_flag AS limit_locked_flag",
        *[
            f"{sum_bool_expr('NOT ds.has_price', n)} AS missing_price_days_{n}"
            for n in [5, 10, 20, 30, 60, 120]
        ],
        *[
            f"{sum_bool_expr('ds.volume IS NULL OR ds.volume = 0', n)} AS suspended_days_{n}"
            for n in [5, 10, 20, 30, 60, 120]
        ],
        "tc.updated_at",
    ]
    return f"""
    CREATE OR REPLACE VIEW derived_trading_constraint_full_v AS
    SELECT
        {",\n        ".join(fields)}
    FROM derived_trading_constraint tc
    JOIN derived_daily_spine ds USING (ts_code, trade_date)
    """


VIEW_BUILDERS = [
    daily_spine_view,
    price_technical_view,
    return_momentum_view,
    volatility_risk_view,
    volume_liquidity_view,
    trading_constraint_view,
]


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    for builder in VIEW_BUILDERS:
        con.execute(builder())
    for view_name in [
        "derived_daily_spine_full_v",
        "derived_price_technical_full_v",
        "derived_return_momentum_full_v",
        "derived_volatility_risk_full_v",
        "derived_volume_liquidity_full_v",
        "derived_trading_constraint_full_v",
    ]:
        columns = len(con.execute(f"PRAGMA table_info('{view_name}')").fetchall())
        print({"view": view_name, "columns": columns})


if __name__ == "__main__":
    main()
