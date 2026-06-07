from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .context import FeatureBuildContext
from .planner import MODULE_ORDER
from .writer import delete_write_window
from ..schema import quote_ident

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class FeatureBuildResult:
    module: str
    status: str
    rows_written: int = 0
    message: str = ""
    elapsed_seconds: float | None = None


FeatureBuilder = Callable[[FeatureBuildContext], FeatureBuildResult]


def placeholder_builder(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return FeatureBuildResult(
        module=ctx.module,
        status="planned",
        rows_written=0,
        message="builder not implemented yet",
    )


def _require_connection(ctx: FeatureBuildContext):
    if ctx.con is None:
        raise ValueError("feature build context has no database connection")
    return ctx.con


def _load_phase3_script(script_name: str):
    script_path = REPO_ROOT / "scripts" / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"phase3 backend script not found: {script_path}")
    module_name = f"_stock_maintainance_phase3_{script_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load phase3 backend script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    scripts_path = str(script_path.parent)
    added_path = scripts_path not in sys.path
    if added_path:
        sys.path.insert(0, scripts_path)
    try:
        spec.loader.exec_module(module)
    finally:
        if added_path:
            sys.path.remove(scripts_path)
    return module


def _count_write_window(ctx: FeatureBuildContext, table_name: str) -> int:
    con = _require_connection(ctx)
    rows = con.execute(
        f"""
        SELECT COUNT(*)
        FROM {quote_ident(table_name)}
        WHERE trade_date BETWEEN ? AND ?
        """,
        [ctx.write_start_date, ctx.write_end_date],
    ).fetchone()[0]
    return int(rows)


def build_daily_spine(ctx: FeatureBuildContext) -> FeatureBuildResult:
    table_name = "derived_daily_spine"
    if ctx.dry_run:
        return FeatureBuildResult(
            module=ctx.module,
            status="dry_run",
            rows_written=0,
            message=f"would rebuild {table_name} from {ctx.write_start_date} to {ctx.write_end_date}",
        )

    delete_write_window(ctx, table_name)
    ctx.con.execute(
        f"""
        INSERT INTO {quote_ident(table_name)}
            (
                ts_code, trade_date,
                is_trade, is_listed_asof, list_status_asof, days_since_list, market, exchange,
                open_raw, high_raw, low_raw, close_raw, pre_close_raw, change_raw, pct_chg_raw,
                volume, amount, amplitude_raw,
                adj_factor, latest_adj_factor_asof,
                open_hfq, high_hfq, low_hfq, close_hfq, pre_close_hfq,
                ret_1_raw, ret_1_hfq, log_ret_1_hfq,
                overnight_ret_hfq, intraday_ret_hfq, high_low_range_hfq, gap_open_hfq, close_position_hfq,
                up_limit, down_limit,
                limit_up_flag, limit_down_flag, touch_limit_up_flag, touch_limit_down_flag,
                open_limit_up_flag, open_limit_down_flag, limit_up_gap, limit_down_gap,
                has_price, has_adj_factor, has_limit_price, price_valid_flag, missing_reason,
                updated_at
            )
        WITH latest_adj AS (
            SELECT ts_code, adj_factor AS latest_adj_factor_asof
            FROM stock_adj_factor
            QUALIFY row_number() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) = 1
        ),
        status_asof AS (
            SELECT
                d.ts_code,
                d.trade_date,
                h.list_status,
                row_number() OVER (
                    PARTITION BY d.ts_code, d.trade_date
                    ORDER BY h.effective_date DESC
                ) AS rn
            FROM stock_daily d
            LEFT JOIN stock_status_history h
                ON d.ts_code = h.ts_code
               AND h.effective_date <= d.trade_date
            WHERE d.trade_date BETWEEN ? AND ?
        ),
        base AS (
            SELECT
                d.ts_code,
                d.trade_date,
                TRUE AS is_trade,
                CASE
                    WHEN s.list_date IS NULL THEN NULL
                    WHEN d.trade_date < s.list_date THEN FALSE
                    WHEN s.delist_date IS NOT NULL AND d.trade_date > s.delist_date THEN FALSE
                    ELSE TRUE
                END AS is_listed_asof,
                coalesce(sa.list_status, s.list_status) AS list_status_asof,
                CASE
                    WHEN s.list_date IS NULL THEN NULL
                    ELSE date_diff('day', s.list_date, d.trade_date)
                END AS days_since_list,
                s.market,
                s.exchange,
                d.open AS open_raw,
                d.high AS high_raw,
                d.low AS low_raw,
                d.close AS close_raw,
                d.pre_close AS pre_close_raw,
                d.change AS change_raw,
                d.pct_chg AS pct_chg_raw,
                d.volume,
                d.amount,
                d.amplitude AS amplitude_raw,
                a.adj_factor,
                la.latest_adj_factor_asof,
                l.up_limit,
                l.down_limit,
                d.open * a.adj_factor AS open_hfq,
                d.high * a.adj_factor AS high_hfq,
                d.low * a.adj_factor AS low_hfq,
                d.close * a.adj_factor AS close_hfq,
                d.pre_close * a.adj_factor AS pre_close_hfq,
                d.open IS NOT NULL
                    AND d.high IS NOT NULL
                    AND d.low IS NOT NULL
                    AND d.close IS NOT NULL AS has_price,
                a.adj_factor IS NOT NULL AS has_adj_factor,
                l.up_limit IS NOT NULL AND l.down_limit IS NOT NULL AS has_limit_price,
                d.open IS NOT NULL
                    AND d.high IS NOT NULL
                    AND d.low IS NOT NULL
                    AND d.close IS NOT NULL
                    AND d.close > 0
                    AND d.high >= d.low
                    AND d.high >= d.open
                    AND d.high >= d.close
                    AND d.low <= d.open
                    AND d.low <= d.close
                    AND coalesce(d.volume, 0) >= 0 AS price_valid_flag
            FROM stock_daily d
            LEFT JOIN stock_basic_info s
                ON d.ts_code = s.ts_code
            LEFT JOIN stock_adj_factor a
                ON d.ts_code = a.ts_code
               AND d.trade_date = a.trade_date
            LEFT JOIN latest_adj la
                ON d.ts_code = la.ts_code
            LEFT JOIN stock_limit_price l
                ON d.ts_code = l.ts_code
               AND d.trade_date = l.trade_date
            LEFT JOIN status_asof sa
                ON d.ts_code = sa.ts_code
               AND d.trade_date = sa.trade_date
               AND sa.rn = 1
            WHERE d.trade_date BETWEEN ? AND ?
        ),
        enriched AS (
            SELECT
                *,
                CASE
                    WHEN close_raw > 0
                     AND lag(close_raw) OVER (PARTITION BY ts_code ORDER BY trade_date) > 0
                    THEN close_raw / lag(close_raw) OVER (PARTITION BY ts_code ORDER BY trade_date) - 1
                    ELSE NULL
                END AS ret_1_raw,
                CASE
                    WHEN close_hfq > 0
                     AND lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) > 0
                    THEN close_hfq / lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) - 1
                    ELSE NULL
                END AS ret_1_hfq,
                CASE
                    WHEN close_hfq > 0
                     AND lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) > 0
                    THEN ln(close_hfq / lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date))
                    ELSE NULL
                END AS log_ret_1_hfq,
                CASE
                    WHEN open_hfq > 0
                     AND lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) > 0
                    THEN open_hfq / lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) - 1
                    ELSE NULL
                END AS overnight_ret_hfq,
                CASE
                    WHEN close_hfq > 0 AND open_hfq > 0 THEN close_hfq / open_hfq - 1
                    ELSE NULL
                END AS intraday_ret_hfq,
                CASE
                    WHEN high_hfq IS NOT NULL
                     AND low_hfq IS NOT NULL
                     AND lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) > 0
                    THEN (high_hfq - low_hfq) / lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date)
                    ELSE NULL
                END AS high_low_range_hfq,
                CASE
                    WHEN open_hfq > 0
                     AND lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) > 0
                    THEN open_hfq / lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) - 1
                    ELSE NULL
                END AS gap_open_hfq,
                CASE
                    WHEN high_hfq > low_hfq THEN (close_hfq - low_hfq) / nullif(high_hfq - low_hfq, 0)
                    ELSE NULL
                END AS close_position_hfq
            FROM base
        )
        SELECT
            ts_code,
            trade_date,
            is_trade,
            is_listed_asof,
            list_status_asof,
            days_since_list,
            market,
            exchange,
            open_raw,
            high_raw,
            low_raw,
            close_raw,
            pre_close_raw,
            change_raw,
            pct_chg_raw,
            volume,
            amount,
            amplitude_raw,
            adj_factor,
            latest_adj_factor_asof,
            open_hfq,
            high_hfq,
            low_hfq,
            close_hfq,
            pre_close_hfq,
            ret_1_raw,
            ret_1_hfq,
            log_ret_1_hfq,
            overnight_ret_hfq,
            intraday_ret_hfq,
            high_low_range_hfq,
            gap_open_hfq,
            close_position_hfq,
            up_limit,
            down_limit,
            CASE
                WHEN close_raw IS NULL OR up_limit IS NULL THEN NULL
                ELSE close_raw >= up_limit - 0.005
            END AS limit_up_flag,
            CASE
                WHEN close_raw IS NULL OR down_limit IS NULL THEN NULL
                ELSE close_raw <= down_limit + 0.005
            END AS limit_down_flag,
            CASE
                WHEN high_raw IS NULL OR up_limit IS NULL THEN NULL
                ELSE high_raw >= up_limit - 0.005
            END AS touch_limit_up_flag,
            CASE
                WHEN low_raw IS NULL OR down_limit IS NULL THEN NULL
                ELSE low_raw <= down_limit + 0.005
            END AS touch_limit_down_flag,
            CASE
                WHEN open_raw IS NULL OR up_limit IS NULL THEN NULL
                ELSE open_raw >= up_limit - 0.005
            END AS open_limit_up_flag,
            CASE
                WHEN open_raw IS NULL OR down_limit IS NULL THEN NULL
                ELSE open_raw <= down_limit + 0.005
            END AS open_limit_down_flag,
            CASE
                WHEN close_raw > 0 AND up_limit > 0 THEN up_limit / close_raw - 1
                ELSE NULL
            END AS limit_up_gap,
            CASE
                WHEN close_raw > 0 AND down_limit > 0 THEN close_raw / down_limit - 1
                ELSE NULL
            END AS limit_down_gap,
            has_price,
            has_adj_factor,
            has_limit_price,
            price_valid_flag,
            CASE
                WHEN NOT has_price THEN 'missing_price'
                WHEN NOT has_adj_factor THEN 'missing_adj_factor'
                WHEN NOT has_limit_price THEN 'missing_limit_price'
                WHEN NOT price_valid_flag THEN 'invalid_price_relation'
                ELSE NULL
            END AS missing_reason,
            CURRENT_TIMESTAMP AS updated_at
        FROM enriched
        WHERE trade_date BETWEEN ? AND ?
        """,
        [
            ctx.read_start_date,
            ctx.write_end_date,
            ctx.read_start_date,
            ctx.write_end_date,
            ctx.write_start_date,
            ctx.write_end_date,
        ],
    )
    rows = ctx.con.execute(
        f"""
        SELECT COUNT(*)
        FROM {quote_ident(table_name)}
        WHERE trade_date BETWEEN ? AND ?
        """,
        [ctx.write_start_date, ctx.write_end_date],
    ).fetchone()[0]
    return FeatureBuildResult(
        module=ctx.module,
        status="success",
        rows_written=int(rows),
        message=f"rebuilt {table_name}",
    )


def _rebuild_table(
    ctx: FeatureBuildContext,
    table_name: str,
    columns: list[str],
    select_sql: str,
    params: list[str] | None = None,
) -> FeatureBuildResult:
    if ctx.dry_run:
        return FeatureBuildResult(
            module=ctx.module,
            status="dry_run",
            rows_written=0,
            message=f"would rebuild {table_name} from {ctx.write_start_date} to {ctx.write_end_date}",
        )

    delete_write_window(ctx, table_name)
    quoted_columns = ", ".join(quote_ident(item) for item in columns)
    ctx.con.execute(
        f"""
        INSERT INTO {quote_ident(table_name)}
            ({quoted_columns})
        {select_sql}
        """,
        params or [ctx.read_start_date, ctx.write_end_date, ctx.write_start_date, ctx.write_end_date],
    )
    rows = ctx.con.execute(
        f"""
        SELECT COUNT(*)
        FROM {quote_ident(table_name)}
        WHERE trade_date BETWEEN ? AND ?
        """,
        [ctx.write_start_date, ctx.write_end_date],
    ).fetchone()[0]
    return FeatureBuildResult(ctx.module, "success", int(rows), f"rebuilt {table_name}")


def build_price_technical(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_price_technical",
        [
            "ts_code", "trade_date",
            "ma_5_hfq", "ma_10_hfq", "ma_20_hfq", "ma_60_hfq", "ma_120_hfq", "ma_250_hfq",
            "close_to_ma_20_hfq", "close_to_ma_60_hfq",
            "ma_20_slope_20_hfq", "ma_60_slope_60_hfq",
            "rsi_14",
            "price_position_20_hfq", "price_position_60_hfq",
            "updated_at",
        ],
        """
        WITH ordered AS (
            SELECT
                ts_code,
                trade_date,
                close_hfq,
                high_hfq,
                low_hfq,
                close_hfq - lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) AS delta
            FROM derived_daily_spine
            WHERE trade_date BETWEEN ? AND ?
        ),
        rolling AS (
            SELECT
                ts_code,
                trade_date,
                close_hfq,
                avg(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS ma_5_hfq,
                avg(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS ma_10_hfq,
                avg(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma_20_hfq,
                avg(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS ma_60_hfq,
                avg(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS ma_120_hfq,
                avg(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 249 PRECEDING AND CURRENT ROW) AS ma_250_hfq,
                min(low_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS low_20_hfq,
                max(high_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS high_20_hfq,
                min(low_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS low_60_hfq,
                max(high_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS high_60_hfq,
                avg(CASE WHEN delta > 0 THEN delta ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_gain,
                avg(CASE WHEN delta < 0 THEN -delta ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_loss,
                count(delta) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS rsi_obs,
                count(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 249 PRECEDING AND CURRENT ROW) AS obs_250
            FROM ordered
        ),
        enriched AS (
            SELECT
                *,
                lag(ma_20_hfq, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_ma_20_hfq,
                lag(ma_60_hfq, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_ma_60_hfq
            FROM rolling
        )
        SELECT
            ts_code,
            trade_date,
            CASE WHEN obs_250 >= 5 THEN ma_5_hfq ELSE NULL END AS ma_5_hfq,
            CASE WHEN obs_250 >= 10 THEN ma_10_hfq ELSE NULL END AS ma_10_hfq,
            CASE WHEN obs_250 >= 20 THEN ma_20_hfq ELSE NULL END AS ma_20_hfq,
            CASE WHEN obs_250 >= 60 THEN ma_60_hfq ELSE NULL END AS ma_60_hfq,
            CASE WHEN obs_250 >= 120 THEN ma_120_hfq ELSE NULL END AS ma_120_hfq,
            CASE WHEN obs_250 >= 250 THEN ma_250_hfq ELSE NULL END AS ma_250_hfq,
            CASE WHEN ma_20_hfq > 0 THEN close_hfq / ma_20_hfq - 1 ELSE NULL END AS close_to_ma_20_hfq,
            CASE WHEN ma_60_hfq > 0 THEN close_hfq / ma_60_hfq - 1 ELSE NULL END AS close_to_ma_60_hfq,
            CASE WHEN lag_ma_20_hfq > 0 THEN ma_20_hfq / lag_ma_20_hfq - 1 ELSE NULL END AS ma_20_slope_20_hfq,
            CASE WHEN lag_ma_60_hfq > 0 THEN ma_60_hfq / lag_ma_60_hfq - 1 ELSE NULL END AS ma_60_slope_60_hfq,
            CASE
                WHEN rsi_obs < 14 THEN NULL
                WHEN avg_loss = 0 AND avg_gain > 0 THEN 100
                WHEN avg_loss = 0 THEN NULL
                ELSE 100 - 100 / (1 + avg_gain / avg_loss)
            END AS rsi_14,
            CASE WHEN high_20_hfq > low_20_hfq THEN (close_hfq - low_20_hfq) / (high_20_hfq - low_20_hfq) ELSE NULL END AS price_position_20_hfq,
            CASE WHEN high_60_hfq > low_60_hfq THEN (close_hfq - low_60_hfq) / (high_60_hfq - low_60_hfq) ELSE NULL END AS price_position_60_hfq,
            CURRENT_TIMESTAMP AS updated_at
        FROM enriched
        WHERE trade_date BETWEEN ? AND ?
        """,
    )


def build_volume_liquidity(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_volume_liquidity",
        [
            "ts_code", "trade_date",
            "volume_ma_5", "volume_ma_20", "volume_ma_60",
            "amount_ma_20", "amount_ma_60",
            "turnover_rate_ma_20", "turnover_rate_free_ma_20",
            "volume_ratio_20", "amount_ratio_20",
            "amihud_20", "zero_volume_days_20",
            "updated_at",
        ],
        """
        WITH base AS (
            SELECT
                ds.ts_code,
                ds.trade_date,
                ds.volume,
                ds.amount,
                ds.ret_1_hfq,
                b.turnover_rate,
                b.turnover_rate_free
            FROM derived_daily_spine ds
            LEFT JOIN stock_daily_basic b
                ON ds.ts_code = b.ts_code
               AND ds.trade_date = b.trade_date
            WHERE ds.trade_date BETWEEN ? AND ?
        ),
        rolling AS (
            SELECT
                ts_code,
                trade_date,
                volume,
                amount,
                avg(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS volume_ma_5,
                avg(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS volume_ma_20,
                avg(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS volume_ma_60,
                avg(amount) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS amount_ma_20,
                avg(amount) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS amount_ma_60,
                avg(turnover_rate) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS turnover_rate_ma_20,
                avg(turnover_rate_free) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS turnover_rate_free_ma_20,
                avg(CASE WHEN amount > 0 THEN abs(ret_1_hfq) / amount ELSE NULL END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS amihud_20,
                sum(CASE WHEN coalesce(volume, 0) = 0 THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS zero_volume_days_20,
                count(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS obs_60
            FROM base
        )
        SELECT
            ts_code,
            trade_date,
            CASE WHEN obs_60 >= 5 THEN volume_ma_5 ELSE NULL END AS volume_ma_5,
            CASE WHEN obs_60 >= 20 THEN volume_ma_20 ELSE NULL END AS volume_ma_20,
            CASE WHEN obs_60 >= 60 THEN volume_ma_60 ELSE NULL END AS volume_ma_60,
            CASE WHEN obs_60 >= 20 THEN amount_ma_20 ELSE NULL END AS amount_ma_20,
            CASE WHEN obs_60 >= 60 THEN amount_ma_60 ELSE NULL END AS amount_ma_60,
            CASE WHEN obs_60 >= 20 THEN turnover_rate_ma_20 ELSE NULL END AS turnover_rate_ma_20,
            CASE WHEN obs_60 >= 20 THEN turnover_rate_free_ma_20 ELSE NULL END AS turnover_rate_free_ma_20,
            CASE WHEN volume_ma_20 > 0 THEN volume / volume_ma_20 ELSE NULL END AS volume_ratio_20,
            CASE WHEN amount_ma_20 > 0 THEN amount / amount_ma_20 ELSE NULL END AS amount_ratio_20,
            CASE WHEN obs_60 >= 20 THEN amihud_20 ELSE NULL END AS amihud_20,
            CASE WHEN obs_60 >= 20 THEN CAST(zero_volume_days_20 AS INTEGER) ELSE NULL END AS zero_volume_days_20,
            CURRENT_TIMESTAMP AS updated_at
        FROM rolling
        WHERE trade_date BETWEEN ? AND ?
        """,
    )


def build_return_momentum(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_return_momentum",
        [
            "ts_code", "trade_date",
            "ret_2_hfq", "ret_5_hfq", "ret_10_hfq", "ret_20_hfq", "ret_60_hfq", "ret_120_hfq", "ret_250_hfq",
            "log_ret_sum_20_hfq",
            "momentum_20_5_hfq", "momentum_60_20_hfq",
            "reversal_5_hfq",
            "up_days_20", "down_days_20",
            "updated_at",
        ],
        """
        WITH ordered AS (
            SELECT
                ts_code,
                trade_date,
                close_hfq,
                log_ret_1_hfq,
                ret_1_hfq,
                lag(close_hfq, 2) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_2,
                lag(close_hfq, 5) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_5,
                lag(close_hfq, 10) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_10,
                lag(close_hfq, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_20,
                lag(close_hfq, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_60,
                lag(close_hfq, 120) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_120,
                lag(close_hfq, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_250
            FROM derived_daily_spine
            WHERE trade_date BETWEEN ? AND ?
        ),
        rolling AS (
            SELECT
                *,
                sum(log_ret_1_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS log_ret_sum_20_hfq,
                sum(CASE WHEN ret_1_hfq > 0 THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS up_days_20,
                sum(CASE WHEN ret_1_hfq < 0 THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS down_days_20,
                count(ret_1_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS obs_20
            FROM ordered
        )
        SELECT
            ts_code,
            trade_date,
            CASE WHEN close_hfq > 0 AND lag_2 > 0 THEN close_hfq / lag_2 - 1 ELSE NULL END AS ret_2_hfq,
            CASE WHEN close_hfq > 0 AND lag_5 > 0 THEN close_hfq / lag_5 - 1 ELSE NULL END AS ret_5_hfq,
            CASE WHEN close_hfq > 0 AND lag_10 > 0 THEN close_hfq / lag_10 - 1 ELSE NULL END AS ret_10_hfq,
            CASE WHEN close_hfq > 0 AND lag_20 > 0 THEN close_hfq / lag_20 - 1 ELSE NULL END AS ret_20_hfq,
            CASE WHEN close_hfq > 0 AND lag_60 > 0 THEN close_hfq / lag_60 - 1 ELSE NULL END AS ret_60_hfq,
            CASE WHEN close_hfq > 0 AND lag_120 > 0 THEN close_hfq / lag_120 - 1 ELSE NULL END AS ret_120_hfq,
            CASE WHEN close_hfq > 0 AND lag_250 > 0 THEN close_hfq / lag_250 - 1 ELSE NULL END AS ret_250_hfq,
            CASE WHEN obs_20 >= 20 THEN log_ret_sum_20_hfq ELSE NULL END AS log_ret_sum_20_hfq,
            CASE WHEN lag_5 > 0 AND lag_20 > 0 THEN lag_5 / lag_20 - 1 ELSE NULL END AS momentum_20_5_hfq,
            CASE WHEN lag_20 > 0 AND lag_60 > 0 THEN lag_20 / lag_60 - 1 ELSE NULL END AS momentum_60_20_hfq,
            CASE WHEN close_hfq > 0 AND lag_5 > 0 THEN -(close_hfq / lag_5 - 1) ELSE NULL END AS reversal_5_hfq,
            CASE WHEN obs_20 >= 20 THEN CAST(up_days_20 AS INTEGER) ELSE NULL END AS up_days_20,
            CASE WHEN obs_20 >= 20 THEN CAST(down_days_20 AS INTEGER) ELSE NULL END AS down_days_20,
            CURRENT_TIMESTAMP AS updated_at
        FROM rolling
        WHERE trade_date BETWEEN ? AND ?
        """,
        [
            ctx.read_start_date,
            ctx.write_end_date,
            ctx.write_start_date,
            ctx.write_end_date,
        ],
    )


def build_volatility_risk(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_volatility_risk",
        [
            "ts_code", "trade_date",
            "hv_20", "hv_60", "hv_120",
            "parkinson_vol_20",
            "atr_14_hfq", "atr_14_pct_hfq",
            "max_drawdown_20_hfq", "max_drawdown_60_hfq",
            "downside_vol_60",
            "var_5pct_60",
            "updated_at",
        ],
        """
        WITH base AS (
            SELECT
                ts_code,
                trade_date,
                close_hfq,
                high_hfq,
                low_hfq,
                log_ret_1_hfq,
                ret_1_hfq,
                CASE
                    WHEN high_hfq IS NOT NULL AND low_hfq IS NOT NULL AND lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) IS NOT NULL
                    THEN greatest(
                        high_hfq - low_hfq,
                        abs(high_hfq - lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date)),
                        abs(low_hfq - lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date))
                    )
                    ELSE NULL
                END AS true_range_hfq
            FROM derived_daily_spine
            WHERE trade_date BETWEEN ? AND ?
        ),
        rolling AS (
            SELECT
                ts_code,
                trade_date,
                close_hfq,
                stddev_samp(log_ret_1_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) * sqrt(242) AS hv_20,
                stddev_samp(log_ret_1_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) * sqrt(242) AS hv_60,
                stddev_samp(log_ret_1_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) * sqrt(242) AS hv_120,
                sqrt(avg(power(ln(high_hfq / nullif(low_hfq, 0)), 2)) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) / (4 * ln(2)) * 242) AS parkinson_vol_20,
                avg(true_range_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS atr_14_hfq,
                max(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS high_close_20,
                max(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS high_close_60,
                stddev_samp(CASE WHEN log_ret_1_hfq < 0 THEN log_ret_1_hfq ELSE NULL END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) * sqrt(242) AS downside_vol_60,
                quantile_cont(ret_1_hfq, 0.05) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS var_5pct_60,
                count(log_ret_1_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS obs_120
            FROM base
        ),
        drawdown AS (
            SELECT
                *,
                close_hfq / nullif(high_close_20, 0) - 1 AS drawdown_20,
                close_hfq / nullif(high_close_60, 0) - 1 AS drawdown_60
            FROM rolling
        ),
        enriched AS (
            SELECT
                *,
                min(drawdown_20) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS max_drawdown_20_hfq,
                min(drawdown_60) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS max_drawdown_60_hfq
            FROM drawdown
        )
        SELECT
            ts_code,
            trade_date,
            CASE WHEN obs_120 >= 20 THEN hv_20 ELSE NULL END AS hv_20,
            CASE WHEN obs_120 >= 60 THEN hv_60 ELSE NULL END AS hv_60,
            CASE WHEN obs_120 >= 120 THEN hv_120 ELSE NULL END AS hv_120,
            CASE WHEN obs_120 >= 20 THEN parkinson_vol_20 ELSE NULL END AS parkinson_vol_20,
            CASE WHEN obs_120 >= 14 THEN atr_14_hfq ELSE NULL END AS atr_14_hfq,
            CASE WHEN close_hfq > 0 AND obs_120 >= 14 THEN atr_14_hfq / close_hfq ELSE NULL END AS atr_14_pct_hfq,
            CASE WHEN obs_120 >= 20 THEN max_drawdown_20_hfq ELSE NULL END AS max_drawdown_20_hfq,
            CASE WHEN obs_120 >= 60 THEN max_drawdown_60_hfq ELSE NULL END AS max_drawdown_60_hfq,
            CASE WHEN obs_120 >= 60 THEN downside_vol_60 ELSE NULL END AS downside_vol_60,
            CASE WHEN obs_120 >= 60 THEN var_5pct_60 ELSE NULL END AS var_5pct_60,
            CURRENT_TIMESTAMP AS updated_at
        FROM enriched
        WHERE trade_date BETWEEN ? AND ?
        """,
    )


def build_trading_constraint(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_trading_constraint",
        [
            "ts_code", "trade_date",
            "limit_up_days_5", "limit_up_days_20",
            "limit_down_days_5", "limit_down_days_20",
            "touch_limit_up_days_20", "touch_limit_down_days_20",
            "consecutive_limit_up_days", "consecutive_limit_down_days",
            "one_price_limit_up_flag", "one_price_limit_down_flag",
            "tradable_state",
            "updated_at",
        ],
        """
        WITH flags AS (
            SELECT
                *,
                open_raw BETWEEN up_limit - 0.005 AND up_limit + 0.005
                    AND high_raw BETWEEN up_limit - 0.005 AND up_limit + 0.005
                    AND low_raw BETWEEN up_limit - 0.005 AND up_limit + 0.005
                    AND close_raw BETWEEN up_limit - 0.005 AND up_limit + 0.005 AS one_price_limit_up_flag,
                open_raw BETWEEN down_limit - 0.005 AND down_limit + 0.005
                    AND high_raw BETWEEN down_limit - 0.005 AND down_limit + 0.005
                    AND low_raw BETWEEN down_limit - 0.005 AND down_limit + 0.005
                    AND close_raw BETWEEN down_limit - 0.005 AND down_limit + 0.005 AS one_price_limit_down_flag
            FROM derived_daily_spine
            WHERE trade_date BETWEEN ? AND ?
        ),
        grouped AS (
            SELECT
                *,
                sum(CASE WHEN coalesce(limit_up_flag, false) THEN 0 ELSE 1 END) OVER (PARTITION BY ts_code ORDER BY trade_date) AS up_group,
                sum(CASE WHEN coalesce(limit_down_flag, false) THEN 0 ELSE 1 END) OVER (PARTITION BY ts_code ORDER BY trade_date) AS down_group
            FROM flags
        ),
        streaks AS (
            SELECT
                *,
                CASE
                    WHEN coalesce(limit_up_flag, false)
                    THEN count(*) OVER (PARTITION BY ts_code, up_group ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                    ELSE 0
                END AS consecutive_limit_up_days,
                CASE
                    WHEN coalesce(limit_down_flag, false)
                    THEN count(*) OVER (PARTITION BY ts_code, down_group ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                    ELSE 0
                END AS consecutive_limit_down_days
            FROM grouped
        ),
        rolling AS (
            SELECT
                *,
                sum(CASE WHEN limit_up_flag THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS limit_up_days_5,
                sum(CASE WHEN limit_up_flag THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS limit_up_days_20,
                sum(CASE WHEN limit_down_flag THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS limit_down_days_5,
                sum(CASE WHEN limit_down_flag THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS limit_down_days_20,
                sum(CASE WHEN touch_limit_up_flag THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS touch_limit_up_days_20,
                sum(CASE WHEN touch_limit_down_flag THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS touch_limit_down_days_20
            FROM streaks
        )
        SELECT
            ts_code,
            trade_date,
            CAST(limit_up_days_5 AS INTEGER) AS limit_up_days_5,
            CAST(limit_up_days_20 AS INTEGER) AS limit_up_days_20,
            CAST(limit_down_days_5 AS INTEGER) AS limit_down_days_5,
            CAST(limit_down_days_20 AS INTEGER) AS limit_down_days_20,
            CAST(touch_limit_up_days_20 AS INTEGER) AS touch_limit_up_days_20,
            CAST(touch_limit_down_days_20 AS INTEGER) AS touch_limit_down_days_20,
            CAST(consecutive_limit_up_days AS INTEGER) AS consecutive_limit_up_days,
            CAST(consecutive_limit_down_days AS INTEGER) AS consecutive_limit_down_days,
            one_price_limit_up_flag,
            one_price_limit_down_flag,
            CASE
                WHEN NOT has_price THEN 'missing'
                WHEN coalesce(one_price_limit_up_flag, false) OR coalesce(one_price_limit_down_flag, false) THEN 'limit_locked'
                WHEN coalesce(volume, 0) = 0 THEN 'suspended'
                ELSE 'normal'
            END AS tradable_state,
            CURRENT_TIMESTAMP AS updated_at
        FROM rolling
        WHERE trade_date BETWEEN ? AND ?
        """,
        [
            ctx.read_start_date,
            ctx.write_end_date,
            ctx.write_start_date,
            ctx.write_end_date,
        ],
    )


def build_valuation_size(ctx: FeatureBuildContext) -> FeatureBuildResult:
    table_name = "derived_valuation_size"
    if ctx.dry_run:
        return FeatureBuildResult(
            module=ctx.module,
            status="dry_run",
            rows_written=0,
            message=f"would rebuild {table_name} from {ctx.write_start_date} to {ctx.write_end_date}",
        )

    delete_write_window(ctx, table_name)
    ctx.con.execute(
        f"""
        INSERT INTO {quote_ident(table_name)}
            (
                ts_code, trade_date,
                pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm,
                total_share, float_share, free_share,
                total_mv, circ_mv, free_float_mv,
                log_total_mv, log_circ_mv, log_free_float_mv,
                float_share_ratio, free_share_ratio,
                earnings_yield_ttm, book_to_price, sales_yield_ttm, dividend_yield_ttm,
                pe_ttm_pct_5y, pb_pct_5y, ps_ttm_pct_5y, total_mv_pct_5y,
                pe_ttm_valid_flag, pb_valid_flag, ps_ttm_valid_flag, mv_valid_flag,
                valuation_missing_reason,
                updated_at
            )
        WITH base AS (
            SELECT
                ds.ts_code,
                ds.trade_date,
                ds.close_raw,
                ds.has_price,
                b.pe,
                b.pe_ttm,
                b.pb,
                b.ps,
                b.ps_ttm,
                b.dv_ratio,
                b.dv_ttm,
                b.total_share,
                b.float_share,
                b.free_share,
                b.total_mv,
                b.circ_mv,
                CASE
                    WHEN ds.close_raw > 0 AND b.free_share > 0 THEN ds.close_raw * b.free_share
                    ELSE NULL
                END AS free_float_mv
            FROM derived_daily_spine ds
            LEFT JOIN stock_daily_basic b
                ON ds.ts_code = b.ts_code
               AND ds.trade_date = b.trade_date
            WHERE ds.trade_date BETWEEN ? AND ?
        ),
        calc AS (
            SELECT
                *,
                CASE WHEN total_mv > 0 THEN ln(total_mv) ELSE NULL END AS log_total_mv,
                CASE WHEN circ_mv > 0 THEN ln(circ_mv) ELSE NULL END AS log_circ_mv,
                CASE WHEN free_float_mv > 0 THEN ln(free_float_mv) ELSE NULL END AS log_free_float_mv,
                CASE WHEN total_share > 0 THEN float_share / total_share ELSE NULL END AS float_share_ratio,
                CASE WHEN total_share > 0 THEN free_share / total_share ELSE NULL END AS free_share_ratio,
                CASE WHEN pe_ttm > 0 THEN 1.0 / pe_ttm ELSE NULL END AS earnings_yield_ttm,
                CASE WHEN pb > 0 THEN 1.0 / pb ELSE NULL END AS book_to_price,
                CASE WHEN ps_ttm > 0 THEN 1.0 / ps_ttm ELSE NULL END AS sales_yield_ttm,
                dv_ttm / 100.0 AS dividend_yield_ttm,
                pe_ttm > 0 AS pe_ttm_valid_flag,
                pb > 0 AS pb_valid_flag,
                ps_ttm > 0 AS ps_ttm_valid_flag,
                total_mv > 0 AND circ_mv > 0 AS mv_valid_flag
            FROM base
        )
        SELECT
            ts_code,
            trade_date,
            pe,
            pe_ttm,
            pb,
            ps,
            ps_ttm,
            dv_ratio,
            dv_ttm,
            total_share,
            float_share,
            free_share,
            total_mv,
            circ_mv,
            free_float_mv,
            log_total_mv,
            log_circ_mv,
            log_free_float_mv,
            float_share_ratio,
            free_share_ratio,
            earnings_yield_ttm,
            book_to_price,
            sales_yield_ttm,
            dividend_yield_ttm,
            NULL::DOUBLE AS pe_ttm_pct_5y,
            NULL::DOUBLE AS pb_pct_5y,
            NULL::DOUBLE AS ps_ttm_pct_5y,
            NULL::DOUBLE AS total_mv_pct_5y,
            pe_ttm_valid_flag,
            pb_valid_flag,
            ps_ttm_valid_flag,
            mv_valid_flag,
            CASE
                WHEN pe IS NULL AND pe_ttm IS NULL AND pb IS NULL AND ps IS NULL AND ps_ttm IS NULL
                    AND total_mv IS NULL AND circ_mv IS NULL THEN 'missing_daily_basic'
                WHEN NOT coalesce(has_price, false) THEN 'missing_price'
                WHEN NOT coalesce(pe_ttm_valid_flag, false)
                    AND NOT coalesce(pb_valid_flag, false)
                    AND NOT coalesce(ps_ttm_valid_flag, false) THEN 'invalid_valuation'
                ELSE NULL
            END AS valuation_missing_reason,
            CURRENT_TIMESTAMP AS updated_at
        FROM calc
        WHERE trade_date BETWEEN ? AND ?
        """,
        [ctx.read_start_date, ctx.write_end_date, ctx.write_start_date, ctx.write_end_date],
    )
    rows = ctx.con.execute(
        f"SELECT count(*) FROM {quote_ident(table_name)} WHERE trade_date BETWEEN ? AND ?",
        [ctx.write_start_date, ctx.write_end_date],
    ).fetchone()[0]
    return FeatureBuildResult(module=ctx.module, status="built", rows_written=rows)


def build_financial_asof(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_financial_asof",
        [
            "ts_code",
            "trade_date",
            "latest_report_end_date",
            "latest_financial_effective_date",
            "latest_financial_ann_date",
            "report_age_days",
            "report_lag_days",
            "report_year",
            "report_quarter",
            "report_period_type",
            "is_annual_report",
            "is_interim_report",
            "is_q1_report",
            "is_q3_report",
            "income_report_end_date",
            "balance_report_end_date",
            "cashflow_report_end_date",
            "indicator_report_end_date",
            "statement_available_count",
            "has_income_statement",
            "has_balance_sheet",
            "has_cashflow_statement",
            "has_indicator_statement",
            "next_disclosure_pre_date",
            "days_to_next_disclosure",
            "has_forecast_asof",
            "latest_forecast_end_date",
            "has_express_asof",
            "latest_express_end_date",
            "updated_at",
        ],
        """
        WITH days AS (
            SELECT ts_code, trade_date
            FROM stock_daily
            WHERE trade_date BETWEEN ? AND ?
        ),
        indicator_events AS (
            SELECT
                ts_code,
                coalesce(effective_date, ann_date) AS effective_date,
                max(ann_date) AS ann_date,
                max(end_date) AS event_end_date
            FROM financial_indicator_raw
            WHERE coalesce(effective_date, ann_date) IS NOT NULL
            GROUP BY ts_code, coalesce(effective_date, ann_date)
        ),
        indicator_scan AS (
            SELECT
                *,
                max(event_end_date) OVER (
                    PARTITION BY ts_code ORDER BY effective_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS latest_end_date
            FROM indicator_events
        ),
        indicator_versions AS (
            SELECT ts_code, effective_date, ann_date, latest_end_date AS end_date
            FROM indicator_scan
            WHERE event_end_date = latest_end_date
        ),
        income_events AS (
            SELECT
                ts_code,
                coalesce(effective_date, first_ann_date, ann_date) AS effective_date,
                max(ann_date) AS ann_date,
                max(end_date) AS event_end_date
            FROM financial_income_raw
            WHERE coalesce(effective_date, first_ann_date, ann_date) IS NOT NULL
            GROUP BY ts_code, coalesce(effective_date, first_ann_date, ann_date)
        ),
        income_scan AS (
            SELECT
                *,
                max(event_end_date) OVER (
                    PARTITION BY ts_code ORDER BY effective_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS latest_end_date
            FROM income_events
        ),
        income_versions AS (
            SELECT ts_code, effective_date, ann_date, latest_end_date AS end_date
            FROM income_scan
            WHERE event_end_date = latest_end_date
        ),
        balance_events AS (
            SELECT
                ts_code,
                coalesce(effective_date, first_ann_date, ann_date) AS effective_date,
                max(ann_date) AS ann_date,
                max(end_date) AS event_end_date
            FROM financial_balance_raw
            WHERE coalesce(effective_date, first_ann_date, ann_date) IS NOT NULL
            GROUP BY ts_code, coalesce(effective_date, first_ann_date, ann_date)
        ),
        balance_scan AS (
            SELECT
                *,
                max(event_end_date) OVER (
                    PARTITION BY ts_code ORDER BY effective_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS latest_end_date
            FROM balance_events
        ),
        balance_versions AS (
            SELECT ts_code, effective_date, ann_date, latest_end_date AS end_date
            FROM balance_scan
            WHERE event_end_date = latest_end_date
        ),
        cashflow_events AS (
            SELECT
                ts_code,
                coalesce(effective_date, first_ann_date, ann_date) AS effective_date,
                max(ann_date) AS ann_date,
                max(end_date) AS event_end_date
            FROM financial_cashflow_raw
            WHERE coalesce(effective_date, first_ann_date, ann_date) IS NOT NULL
            GROUP BY ts_code, coalesce(effective_date, first_ann_date, ann_date)
        ),
        cashflow_scan AS (
            SELECT
                *,
                max(event_end_date) OVER (
                    PARTITION BY ts_code ORDER BY effective_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS latest_end_date
            FROM cashflow_events
        ),
        cashflow_versions AS (
            SELECT ts_code, effective_date, ann_date, latest_end_date AS end_date
            FROM cashflow_scan
            WHERE event_end_date = latest_end_date
        ),
        forecast_versions AS (
            SELECT ts_code, ann_date AS effective_date, end_date
            FROM financial_forecast
            WHERE ann_date IS NOT NULL
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, ann_date
                ORDER BY end_date DESC NULLS LAST
            ) = 1
        ),
        express_versions AS (
            SELECT ts_code, ann_date AS effective_date, end_date
            FROM financial_express
            WHERE ann_date IS NOT NULL
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, ann_date
                ORDER BY end_date DESC NULLS LAST
            ) = 1
        ),
        asof_base AS (
            SELECT
                d.ts_code,
                d.trade_date,
                i.end_date AS latest_report_end_date,
                i.effective_date AS latest_financial_effective_date,
                i.ann_date AS latest_financial_ann_date,
                inc.end_date AS income_report_end_date,
                bal.end_date AS balance_report_end_date,
                cf.end_date AS cashflow_report_end_date,
                i.end_date AS indicator_report_end_date,
                fc.end_date AS latest_forecast_end_date,
                ex.end_date AS latest_express_end_date
            FROM days d
            ASOF LEFT JOIN (
                SELECT * FROM indicator_versions ORDER BY ts_code, effective_date
            ) i
              ON d.ts_code = i.ts_code
             AND d.trade_date >= i.effective_date
            ASOF LEFT JOIN (
                SELECT * FROM income_versions ORDER BY ts_code, effective_date
            ) inc
              ON d.ts_code = inc.ts_code
             AND d.trade_date >= inc.effective_date
            ASOF LEFT JOIN (
                SELECT * FROM balance_versions ORDER BY ts_code, effective_date
            ) bal
              ON d.ts_code = bal.ts_code
             AND d.trade_date >= bal.effective_date
            ASOF LEFT JOIN (
                SELECT * FROM cashflow_versions ORDER BY ts_code, effective_date
            ) cf
              ON d.ts_code = cf.ts_code
             AND d.trade_date >= cf.effective_date
            ASOF LEFT JOIN (
                SELECT * FROM forecast_versions ORDER BY ts_code, effective_date
            ) fc
              ON d.ts_code = fc.ts_code
             AND d.trade_date >= fc.effective_date
            ASOF LEFT JOIN (
                SELECT * FROM express_versions ORDER BY ts_code, effective_date
            ) ex
              ON d.ts_code = ex.ts_code
             AND d.trade_date >= ex.effective_date
        )
        SELECT
            ts_code,
            trade_date,
            latest_report_end_date,
            latest_financial_effective_date,
            latest_financial_ann_date,
            CASE
                WHEN latest_financial_effective_date IS NULL THEN NULL
                ELSE date_diff('day', latest_financial_effective_date, trade_date)
            END AS report_age_days,
            CASE
                WHEN latest_report_end_date IS NULL OR latest_financial_effective_date IS NULL THEN NULL
                ELSE date_diff('day', latest_report_end_date, latest_financial_effective_date)
            END AS report_lag_days,
            CAST(EXTRACT(year FROM latest_report_end_date) AS INTEGER) AS report_year,
            CAST(EXTRACT(quarter FROM latest_report_end_date) AS INTEGER) AS report_quarter,
            CASE
                WHEN latest_report_end_date IS NULL THEN NULL
                WHEN EXTRACT(month FROM latest_report_end_date) = 3 THEN 'Q1'
                WHEN EXTRACT(month FROM latest_report_end_date) = 6 THEN 'H1'
                WHEN EXTRACT(month FROM latest_report_end_date) = 9 THEN 'Q3'
                WHEN EXTRACT(month FROM latest_report_end_date) = 12 THEN 'FY'
                ELSE 'OTHER'
            END AS report_period_type,
            latest_report_end_date IS NOT NULL AND EXTRACT(month FROM latest_report_end_date) = 12 AS is_annual_report,
            latest_report_end_date IS NOT NULL AND EXTRACT(month FROM latest_report_end_date) = 6 AS is_interim_report,
            latest_report_end_date IS NOT NULL AND EXTRACT(month FROM latest_report_end_date) = 3 AS is_q1_report,
            latest_report_end_date IS NOT NULL AND EXTRACT(month FROM latest_report_end_date) = 9 AS is_q3_report,
            income_report_end_date,
            balance_report_end_date,
            cashflow_report_end_date,
            indicator_report_end_date,
            CAST(
                (CASE WHEN income_report_end_date = latest_report_end_date THEN 1 ELSE 0 END)
              + (CASE WHEN balance_report_end_date = latest_report_end_date THEN 1 ELSE 0 END)
              + (CASE WHEN cashflow_report_end_date = latest_report_end_date THEN 1 ELSE 0 END)
              + (CASE WHEN indicator_report_end_date = latest_report_end_date THEN 1 ELSE 0 END)
              AS INTEGER
            ) AS statement_available_count,
            income_report_end_date = latest_report_end_date AS has_income_statement,
            balance_report_end_date = latest_report_end_date AS has_balance_sheet,
            cashflow_report_end_date = latest_report_end_date AS has_cashflow_statement,
            indicator_report_end_date = latest_report_end_date AS has_indicator_statement,
            NULL::DATE AS next_disclosure_pre_date,
            NULL::BIGINT AS days_to_next_disclosure,
            latest_forecast_end_date IS NOT NULL AS has_forecast_asof,
            latest_forecast_end_date,
            latest_express_end_date IS NOT NULL AS has_express_asof,
            latest_express_end_date,
            CURRENT_TIMESTAMP AS updated_at
        FROM asof_base
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_financial_quality(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_financial_quality",
        [
            "ts_code", "trade_date",
            "roe_asof", "roe_waa_asof", "roe_dt_asof", "roa_asof", "roic_asof",
            "gross_margin_asof", "grossprofit_margin_asof", "netprofit_margin_asof",
            "operating_profit_margin_asof", "total_profit_margin_asof",
            "net_profit_margin_calc_asof", "parent_net_profit_margin_asof",
            "minority_profit_ratio_asof", "non_operating_income_ratio_asof",
            "investment_income_ratio_asof", "fair_value_gain_ratio_asof",
            "asset_impairment_to_profit_asof", "deducted_profit_to_net_profit_asof",
            "eps_asof", "dt_eps_asof", "bps_asof", "ocfps_asof", "cfps_asof",
            "ocf_to_profit_asof", "ocf_to_revenue_asof", "free_cashflow_to_revenue_asof",
            "cash_received_to_revenue_asof", "cash_paid_goods_to_cost_asof",
            "capex_to_revenue_asof", "capex_to_ocf_asof", "fcf_to_ocf_asof",
            "cash_end_to_assets_asof", "cash_net_increase_to_assets_asof", "accrual_ratio_asof",
            "cash_to_assets_asof", "current_assets_to_assets_asof", "noncurrent_assets_to_assets_asof",
            "fixed_assets_to_assets_asof", "construction_to_assets_asof", "goodwill_to_assets_asof",
            "intangible_to_assets_asof", "development_exp_to_assets_asof",
            "accounts_receivable_to_revenue_asof", "inventory_to_revenue_asof",
            "contract_assets_to_revenue_asof", "contract_liability_to_revenue_asof",
            "working_capital_asof", "working_capital_to_assets_asof",
            "net_working_capital_asof", "net_working_capital_to_assets_asof",
            "debt_to_assets_asof", "assets_to_equity_asof", "interestdebt_asof", "netdebt_asof",
            "interestdebt_to_assets_asof", "netdebt_to_assets_asof",
            "short_borrowing_to_assets_asof", "long_borrowing_to_assets_asof",
            "bonds_payable_to_assets_asof", "current_debt_to_total_debt_asof",
            "longdebt_to_total_debt_asof", "current_ratio_asof", "quick_ratio_asof",
            "cash_ratio_asof", "ocf_to_debt_asof", "ocf_to_interestdebt_asof",
            "ebit_to_interest_asof", "ebitda_to_debt_asof", "liabilities_to_equity_asof",
            "current_liabilities_to_liabilities_asof",
            "ar_turn_asof", "current_asset_turn_asof", "fixed_asset_turn_asof",
            "assets_turn_asof", "turn_days_asof", "total_fa_turn_asof",
            "revenue_to_assets_asof", "revenue_to_fixed_assets_asof",
            "selling_expense_to_revenue_asof", "admin_expense_to_revenue_asof",
            "rd_exp_to_revenue_asof", "finance_expense_to_revenue_asof",
            "expense_to_revenue_asof", "business_tax_to_revenue_asof", "income_tax_to_profit_asof",
            "rd_exp_asof", "selling_expense_asof", "admin_expense_asof", "finance_expense_asof",
            "dupont_net_margin_asof", "dupont_asset_turnover_asof",
            "dupont_equity_multiplier_asof", "dupont_roe_calc_asof", "roe_calc_gap_asof",
            "negative_equity_flag", "negative_net_profit_flag", "negative_parent_net_profit_flag",
            "negative_ocf_flag", "high_goodwill_flag", "high_receivable_flag", "high_inventory_flag",
            "high_leverage_flag", "low_current_ratio_flag", "ocf_profit_mismatch_flag",
            "liability_equity_balance_gap_asof", "liability_equity_balance_gap_ratio_asof",
            "cashflow_cash_balance_gap_asof", "cashflow_cash_balance_gap_ratio_asof",
            "statement_available_count_asof", "has_complete_statement_set_asof",
            "report_age_days_asof", "report_lag_days_asof", "forecast_available_flag", "express_available_flag",
            "updated_at",
        ],
        """
        WITH indicator_latest AS (
            SELECT *
            FROM financial_indicator_raw
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, end_date
                ORDER BY coalesce(effective_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
            ) = 1
        ),
        income_latest AS (
            SELECT *
            FROM financial_income_raw
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, end_date
                ORDER BY coalesce(effective_date, first_ann_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
            ) = 1
        ),
        balance_latest AS (
            SELECT *
            FROM financial_balance_raw
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, end_date
                ORDER BY coalesce(effective_date, first_ann_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
            ) = 1
        ),
        cashflow_latest AS (
            SELECT *
            FROM financial_cashflow_raw
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, end_date
                ORDER BY coalesce(effective_date, first_ann_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
            ) = 1
        ),
        joined AS (
            SELECT
                a.ts_code,
                a.trade_date,
                a.statement_available_count,
                a.report_age_days,
                a.report_lag_days,
                a.has_forecast_asof,
                a.has_express_asof,
                i.* EXCLUDE (ts_code, ann_date, end_date, payload_json, effective_date, updated_at),
                inc.* EXCLUDE (ts_code, ann_date, first_ann_date, end_date, report_type, comp_type, payload_json, effective_date, updated_at),
                bal.* EXCLUDE (ts_code, ann_date, first_ann_date, end_date, report_type, comp_type, payload_json, effective_date, updated_at),
                cf.* EXCLUDE (ts_code, ann_date, first_ann_date, end_date, report_type, comp_type, payload_json, effective_date, updated_at)
            FROM derived_financial_asof a
            LEFT JOIN indicator_latest i
                ON a.ts_code = i.ts_code
               AND a.latest_report_end_date = i.end_date
            LEFT JOIN income_latest inc
                ON a.ts_code = inc.ts_code
               AND a.latest_report_end_date = inc.end_date
            LEFT JOIN balance_latest bal
                ON a.ts_code = bal.ts_code
               AND a.latest_report_end_date = bal.end_date
            LEFT JOIN cashflow_latest cf
                ON a.ts_code = cf.ts_code
               AND a.latest_report_end_date = cf.end_date
            WHERE a.trade_date BETWEEN ? AND ?
        ),
        calc AS (
            SELECT
                *,
                CASE WHEN revenue != 0 THEN operating_profit / revenue ELSE NULL END AS operating_profit_margin_calc,
                CASE WHEN revenue != 0 THEN total_profit / revenue ELSE NULL END AS total_profit_margin_calc,
                CASE WHEN revenue != 0 THEN net_profit / revenue ELSE NULL END AS net_profit_margin_calc,
                CASE WHEN revenue != 0 THEN net_profit_attr_parent / revenue ELSE NULL END AS parent_net_profit_margin_calc,
                CASE WHEN net_profit != 0 THEN minority_profit / net_profit ELSE NULL END AS minority_profit_ratio_calc,
                CASE WHEN total_profit != 0 THEN non_operating_income / total_profit ELSE NULL END AS non_operating_income_ratio_calc,
                CASE WHEN total_profit != 0 THEN investment_income / total_profit ELSE NULL END AS investment_income_ratio_calc,
                CASE WHEN total_profit != 0 THEN fair_value_change_income / total_profit ELSE NULL END AS fair_value_gain_ratio_calc,
                CASE WHEN total_profit != 0 THEN asset_impairment_loss / total_profit ELSE NULL END AS asset_impairment_to_profit_calc,
                CASE WHEN net_profit != 0 THEN profit_dedt / net_profit ELSE NULL END AS deducted_profit_to_net_profit_calc,
                CASE WHEN revenue != 0 THEN cf_from_operating / revenue ELSE NULL END AS ocf_to_revenue_calc,
                CASE WHEN revenue != 0 THEN free_cashflow / revenue ELSE NULL END AS free_cashflow_to_revenue_calc,
                CASE WHEN revenue != 0 THEN cash_received_from_sales / revenue ELSE NULL END AS cash_received_to_revenue_calc,
                CASE WHEN operating_cost != 0 THEN cash_paid_for_goods / operating_cost ELSE NULL END AS cash_paid_goods_to_cost_calc,
                CASE WHEN revenue != 0 THEN cash_paid_for_capex / revenue ELSE NULL END AS capex_to_revenue_calc,
                CASE WHEN cf_from_operating != 0 THEN cash_paid_for_capex / cf_from_operating ELSE NULL END AS capex_to_ocf_calc,
                CASE WHEN cf_from_operating != 0 THEN free_cashflow / cf_from_operating ELSE NULL END AS fcf_to_ocf_calc,
                CASE WHEN total_assets != 0 THEN cash_at_end / total_assets ELSE NULL END AS cash_end_to_assets_calc,
                CASE WHEN total_assets != 0 THEN net_increase_in_cash / total_assets ELSE NULL END AS cash_net_increase_to_assets_calc,
                CASE WHEN total_assets != 0 THEN (net_profit - cf_from_operating) / total_assets ELSE NULL END AS accrual_ratio_calc,
                CASE WHEN total_assets != 0 THEN cash_and_equivalents / total_assets ELSE NULL END AS cash_to_assets_calc,
                CASE WHEN total_assets != 0 THEN current_assets / total_assets ELSE NULL END AS current_assets_to_assets_calc,
                CASE WHEN total_assets != 0 THEN total_noncurrent_assets / total_assets ELSE NULL END AS noncurrent_assets_to_assets_calc,
                CASE WHEN total_assets != 0 THEN fixed_assets / total_assets ELSE NULL END AS fixed_assets_to_assets_calc,
                CASE WHEN total_assets != 0 THEN construction_in_process / total_assets ELSE NULL END AS construction_to_assets_calc,
                CASE WHEN total_assets != 0 THEN goodwill / total_assets ELSE NULL END AS goodwill_to_assets_calc,
                CASE WHEN total_assets != 0 THEN intangible_assets / total_assets ELSE NULL END AS intangible_to_assets_calc,
                CASE WHEN total_assets != 0 THEN development_expenditure / total_assets ELSE NULL END AS development_exp_to_assets_calc,
                CASE WHEN revenue != 0 THEN accounts_receivable / revenue ELSE NULL END AS accounts_receivable_to_revenue_calc,
                CASE WHEN revenue != 0 THEN inventories / revenue ELSE NULL END AS inventory_to_revenue_calc,
                CASE WHEN revenue != 0 THEN contract_assets / revenue ELSE NULL END AS contract_assets_to_revenue_calc,
                CASE WHEN revenue != 0 THEN contract_liabilities / revenue ELSE NULL END AS contract_liability_to_revenue_calc,
                current_assets - current_liabilities AS working_capital_calc,
                CASE WHEN total_assets != 0 THEN (current_assets - current_liabilities) / total_assets ELSE NULL END AS working_capital_to_assets_calc,
                CASE WHEN total_assets != 0 THEN networking_capital / total_assets ELSE NULL END AS net_working_capital_to_assets_calc,
                CASE WHEN total_assets != 0 THEN interestdebt / total_assets ELSE NULL END AS interestdebt_to_assets_calc,
                CASE WHEN total_assets != 0 THEN netdebt / total_assets ELSE NULL END AS netdebt_to_assets_calc,
                CASE WHEN total_assets != 0 THEN short_term_borrowings / total_assets ELSE NULL END AS short_borrowing_to_assets_calc,
                CASE WHEN total_assets != 0 THEN long_term_borrowings / total_assets ELSE NULL END AS long_borrowing_to_assets_calc,
                CASE WHEN total_assets != 0 THEN bonds_payable / total_assets ELSE NULL END AS bonds_payable_to_assets_calc,
                CASE WHEN total_equity != 0 THEN total_liabilities / total_equity ELSE NULL END AS liabilities_to_equity_calc,
                CASE WHEN total_liabilities != 0 THEN current_liabilities / total_liabilities ELSE NULL END AS current_liabilities_to_liabilities_calc,
                CASE WHEN total_assets != 0 THEN revenue / total_assets ELSE NULL END AS revenue_to_assets_calc,
                CASE WHEN fixed_assets != 0 THEN revenue / fixed_assets ELSE NULL END AS revenue_to_fixed_assets_calc,
                CASE WHEN revenue != 0 THEN selling_expense / revenue ELSE NULL END AS selling_expense_to_revenue_calc,
                CASE WHEN revenue != 0 THEN admin_expense / revenue ELSE NULL END AS admin_expense_to_revenue_calc,
                CASE WHEN revenue != 0 THEN rd_expense / revenue ELSE NULL END AS rd_exp_to_revenue_calc,
                CASE WHEN revenue != 0 THEN finance_expense / revenue ELSE NULL END AS finance_expense_to_revenue_calc,
                CASE WHEN revenue != 0 THEN (coalesce(selling_expense,0) + coalesce(admin_expense,0) + coalesce(rd_expense,0) + coalesce(finance_expense,0)) / revenue ELSE NULL END AS expense_to_revenue_calc,
                CASE WHEN revenue != 0 THEN business_tax_surcharge / revenue ELSE NULL END AS business_tax_to_revenue_calc,
                CASE WHEN total_profit != 0 THEN income_tax / total_profit ELSE NULL END AS income_tax_to_profit_calc,
                CASE WHEN equity_attr_parent != 0 THEN total_assets / equity_attr_parent ELSE NULL END AS dupont_equity_multiplier_calc,
                total_assets - total_liabilities - total_equity AS liability_equity_balance_gap_calc,
                cash_at_beginning + net_increase_in_cash + coalesce(fx_effect_on_cash, 0) - cash_at_end AS cashflow_cash_balance_gap_calc
            FROM joined
        )
        SELECT
            ts_code,
            trade_date,
            roe AS roe_asof,
            roe_waa AS roe_waa_asof,
            roe_dt AS roe_dt_asof,
            roa AS roa_asof,
            roic AS roic_asof,
            gross_margin AS gross_margin_asof,
            grossprofit_margin AS grossprofit_margin_asof,
            netprofit_margin AS netprofit_margin_asof,
            operating_profit_margin_calc AS operating_profit_margin_asof,
            total_profit_margin_calc AS total_profit_margin_asof,
            net_profit_margin_calc AS net_profit_margin_calc_asof,
            parent_net_profit_margin_calc AS parent_net_profit_margin_asof,
            minority_profit_ratio_calc AS minority_profit_ratio_asof,
            non_operating_income_ratio_calc AS non_operating_income_ratio_asof,
            investment_income_ratio_calc AS investment_income_ratio_asof,
            fair_value_gain_ratio_calc AS fair_value_gain_ratio_asof,
            asset_impairment_to_profit_calc AS asset_impairment_to_profit_asof,
            deducted_profit_to_net_profit_calc AS deducted_profit_to_net_profit_asof,
            eps AS eps_asof,
            dt_eps AS dt_eps_asof,
            bps AS bps_asof,
            ocfps AS ocfps_asof,
            cfps AS cfps_asof,
            coalesce(
                ocf_to_profit,
                CASE WHEN net_profit != 0 THEN cf_from_operating / net_profit ELSE NULL END
            ) AS ocf_to_profit_asof,
            ocf_to_revenue_calc AS ocf_to_revenue_asof,
            free_cashflow_to_revenue_calc AS free_cashflow_to_revenue_asof,
            cash_received_to_revenue_calc AS cash_received_to_revenue_asof,
            cash_paid_goods_to_cost_calc AS cash_paid_goods_to_cost_asof,
            capex_to_revenue_calc AS capex_to_revenue_asof,
            capex_to_ocf_calc AS capex_to_ocf_asof,
            fcf_to_ocf_calc AS fcf_to_ocf_asof,
            cash_end_to_assets_calc AS cash_end_to_assets_asof,
            cash_net_increase_to_assets_calc AS cash_net_increase_to_assets_asof,
            accrual_ratio_calc AS accrual_ratio_asof,
            cash_to_assets_calc AS cash_to_assets_asof,
            current_assets_to_assets_calc AS current_assets_to_assets_asof,
            noncurrent_assets_to_assets_calc AS noncurrent_assets_to_assets_asof,
            fixed_assets_to_assets_calc AS fixed_assets_to_assets_asof,
            construction_to_assets_calc AS construction_to_assets_asof,
            goodwill_to_assets_calc AS goodwill_to_assets_asof,
            intangible_to_assets_calc AS intangible_to_assets_asof,
            development_exp_to_assets_calc AS development_exp_to_assets_asof,
            accounts_receivable_to_revenue_calc AS accounts_receivable_to_revenue_asof,
            inventory_to_revenue_calc AS inventory_to_revenue_asof,
            contract_assets_to_revenue_calc AS contract_assets_to_revenue_asof,
            contract_liability_to_revenue_calc AS contract_liability_to_revenue_asof,
            working_capital_calc AS working_capital_asof,
            working_capital_to_assets_calc AS working_capital_to_assets_asof,
            networking_capital AS net_working_capital_asof,
            net_working_capital_to_assets_calc AS net_working_capital_to_assets_asof,
            debt_to_assets AS debt_to_assets_asof,
            assets_to_eqt AS assets_to_equity_asof,
            interestdebt AS interestdebt_asof,
            netdebt AS netdebt_asof,
            interestdebt_to_assets_calc AS interestdebt_to_assets_asof,
            netdebt_to_assets_calc AS netdebt_to_assets_asof,
            short_borrowing_to_assets_calc AS short_borrowing_to_assets_asof,
            long_borrowing_to_assets_calc AS long_borrowing_to_assets_asof,
            bonds_payable_to_assets_calc AS bonds_payable_to_assets_asof,
            currentdebt_to_debt AS current_debt_to_total_debt_asof,
            longdeb_to_debt AS longdebt_to_total_debt_asof,
            current_ratio AS current_ratio_asof,
            quick_ratio AS quick_ratio_asof,
            cash_ratio AS cash_ratio_asof,
            ocf_to_debt AS ocf_to_debt_asof,
            coalesce(
                ocf_to_interestdebt,
                CASE WHEN interestdebt != 0 THEN cf_from_operating / interestdebt ELSE NULL END
            ) AS ocf_to_interestdebt_asof,
            ebit_to_interest AS ebit_to_interest_asof,
            ebitda_to_debt AS ebitda_to_debt_asof,
            liabilities_to_equity_calc AS liabilities_to_equity_asof,
            current_liabilities_to_liabilities_calc AS current_liabilities_to_liabilities_asof,
            ar_turn AS ar_turn_asof,
            ca_turn AS current_asset_turn_asof,
            fa_turn AS fixed_asset_turn_asof,
            assets_turn AS assets_turn_asof,
            turn_days AS turn_days_asof,
            total_fa_trun AS total_fa_turn_asof,
            revenue_to_assets_calc AS revenue_to_assets_asof,
            revenue_to_fixed_assets_calc AS revenue_to_fixed_assets_asof,
            selling_expense_to_revenue_calc AS selling_expense_to_revenue_asof,
            admin_expense_to_revenue_calc AS admin_expense_to_revenue_asof,
            rd_exp_to_revenue_calc AS rd_exp_to_revenue_asof,
            finance_expense_to_revenue_calc AS finance_expense_to_revenue_asof,
            expense_to_revenue_calc AS expense_to_revenue_asof,
            business_tax_to_revenue_calc AS business_tax_to_revenue_asof,
            income_tax_to_profit_calc AS income_tax_to_profit_asof,
            rd_expense AS rd_exp_asof,
            selling_expense AS selling_expense_asof,
            admin_expense AS admin_expense_asof,
            finance_expense AS finance_expense_asof,
            parent_net_profit_margin_calc AS dupont_net_margin_asof,
            revenue_to_assets_calc AS dupont_asset_turnover_asof,
            dupont_equity_multiplier_calc AS dupont_equity_multiplier_asof,
            parent_net_profit_margin_calc * revenue_to_assets_calc * dupont_equity_multiplier_calc AS dupont_roe_calc_asof,
            roe - parent_net_profit_margin_calc * revenue_to_assets_calc * dupont_equity_multiplier_calc AS roe_calc_gap_asof,
            equity_attr_parent < 0 AS negative_equity_flag,
            net_profit < 0 AS negative_net_profit_flag,
            net_profit_attr_parent < 0 AS negative_parent_net_profit_flag,
            cf_from_operating < 0 AS negative_ocf_flag,
            goodwill_to_assets_calc >= 0.2 AS high_goodwill_flag,
            accounts_receivable_to_revenue_calc >= 0.5 AS high_receivable_flag,
            inventory_to_revenue_calc >= 0.5 AS high_inventory_flag,
            debt_to_assets >= 70 AS high_leverage_flag,
            current_ratio < 1 AS low_current_ratio_flag,
            net_profit > 0 AND cf_from_operating < 0 AS ocf_profit_mismatch_flag,
            liability_equity_balance_gap_calc AS liability_equity_balance_gap_asof,
            CASE WHEN total_assets != 0 THEN liability_equity_balance_gap_calc / total_assets ELSE NULL END AS liability_equity_balance_gap_ratio_asof,
            cashflow_cash_balance_gap_calc AS cashflow_cash_balance_gap_asof,
            CASE WHEN cash_at_end != 0 THEN cashflow_cash_balance_gap_calc / cash_at_end ELSE NULL END AS cashflow_cash_balance_gap_ratio_asof,
            statement_available_count AS statement_available_count_asof,
            statement_available_count >= 4 AS has_complete_statement_set_asof,
            report_age_days AS report_age_days_asof,
            report_lag_days AS report_lag_days_asof,
            has_forecast_asof AS forecast_available_flag,
            has_express_asof AS express_available_flag,
            CURRENT_TIMESTAMP AS updated_at
        FROM calc
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_financial_growth(ctx: FeatureBuildContext) -> FeatureBuildResult:
    amount_metrics = [
        ("revenue", "cur.revenue", True),
        ("total_revenue", "cur.total_revenue", True),
        ("operating_cost", "cur.operating_cost", True),
        ("total_cogs", "cur.total_cogs", True),
        ("operating_profit", "cur.operating_profit", True),
        ("total_profit", "cur.total_profit", True),
        ("net_profit", "cur.net_profit", True),
        ("parent_net_profit", "cur.parent_net_profit", True),
        ("deducted_profit", "cur.deducted_profit", True),
        ("ebit", "cur.ebit", True),
        ("ebitda", "cur.ebitda", True),
        ("ocf", "cur.ocf", True),
        ("icf", "cur.icf", True),
        ("fcf", "cur.fcf", True),
        ("free_cashflow", "cur.free_cashflow", True),
        ("cash_received_from_sales", "cur.cash_received_from_sales", True),
        ("cash_paid_for_goods", "cur.cash_paid_for_goods", True),
        ("cash_paid_for_capex", "cur.cash_paid_for_capex", True),
        ("total_assets", "cur.total_assets", False),
        ("current_assets", "cur.current_assets", False),
        ("noncurrent_assets", "cur.noncurrent_assets", False),
        ("total_liabilities", "cur.total_liabilities", False),
        ("current_liabilities", "cur.current_liabilities", False),
        ("total_equity", "cur.total_equity", False),
        ("equity_attr_parent", "cur.equity_attr_parent", False),
        ("interestdebt", "cur.interestdebt", False),
        ("netdebt", "cur.netdebt", False),
        ("rd_expense", "cur.rd_expense", True),
        ("selling_expense", "cur.selling_expense", True),
        ("admin_expense", "cur.admin_expense", True),
        ("finance_expense", "cur.finance_expense", True),
    ]
    core_amount_metrics = {
        "revenue",
        "total_revenue",
        "parent_net_profit",
        "net_profit",
        "deducted_profit",
        "ocf",
        "free_cashflow",
        "total_assets",
        "equity_attr_parent",
        "interestdebt",
        "netdebt",
        "rd_expense",
    }
    amount_metrics = [item for item in amount_metrics if item[0] in core_amount_metrics]
    tushare_fields = [
        ("revenue_yoy_asof", "cur.or_yoy"),
        ("total_revenue_yoy_asof", "cur.tr_yoy"),
        ("netprofit_yoy_asof", "cur.netprofit_yoy"),
        ("deducted_netprofit_yoy_asof", "cur.dt_netprofit_yoy"),
        ("ocf_yoy_asof", "cur.ocf_yoy"),
        ("eps_yoy_asof", "cur.basic_eps_yoy"),
        ("dt_eps_yoy_asof", "cur.dt_eps_yoy"),
        ("cfps_yoy_asof", "cur.cfps_yoy"),
        ("roe_yoy_asof", "cur.roe_yoy"),
        ("bps_yoy_asof", "cur.bps_yoy"),
        ("assets_yoy_asof", "cur.assets_yoy"),
        ("equity_yoy_asof", "cur.eqt_yoy"),
        ("q_revenue_yoy_asof", "cur.q_sales_yoy"),
        ("q_revenue_qoq_asof", "cur.q_sales_qoq"),
        ("q_operating_profit_yoy_asof", "cur.q_op_yoy"),
        ("q_operating_profit_qoq_asof", "cur.q_op_qoq"),
        ("q_netprofit_yoy_asof", "cur.q_netprofit_yoy"),
        ("q_netprofit_qoq_asof", "cur.q_netprofit_qoq"),
    ]

    def special_code(num: str, den: str) -> str:
        return (
            "CAST(('-9' || "
            f"CASE WHEN {num} = 0 THEN '1' ELSE '0' END || "
            f"CASE WHEN {num} IS NULL THEN '1' ELSE '0' END || "
            f"CASE WHEN {num} < 0 THEN '1' ELSE '0' END || "
            f"CASE WHEN {den} = 0 THEN '1' ELSE '0' END || "
            f"CASE WHEN {den} IS NULL THEN '1' ELSE '0' END || "
            f"CASE WHEN {den} < 0 THEN '1' ELSE '0' END) AS DOUBLE)"
        )

    def safe_growth(num: str, den: str) -> str:
        return (
            f"CASE WHEN {num} > 0 AND {den} > 0 "
            f"THEN {num} / {den} - 1 ELSE {special_code(num, den)} END"
        )

    def safe_cagr(num: str, den: str, years: int) -> str:
        return (
            f"CASE WHEN {num} > 0 AND {den} > 0 "
            f"THEN power({num} / {den}, 1.0 / {years}) - 1 ELSE {special_code(num, den)} END"
        )

    columns = [
        "ts_code",
        "trade_date",
        "current_report_end_date",
        "prev_report_end_date",
        "lag_2report_end_date",
        "lag_4report_end_date",
        "lag_8report_end_date",
        "same_period_1y_end_date",
        "same_period_2y_end_date",
        "same_period_3y_end_date",
    ]
    select_items = [
        "a.ts_code",
        "a.trade_date",
        "a.latest_report_end_date AS current_report_end_date",
        "seq.prev_report_end_date",
        "seq.lag_2report_end_date",
        "seq.lag_4report_end_date",
        "seq.lag_8report_end_date",
        "seq.same_period_1y_end_date",
        "seq.same_period_2y_end_date",
        "seq.same_period_3y_end_date",
    ]

    for column_name, source_expr in tushare_fields:
        columns.append(column_name)
        select_items.append(f"{source_expr} AS {column_name}")

    for metric, cur_expr, is_flow in amount_metrics:
        comparisons = [
            ("qoq_report_asof", cur_expr, f"prev.{metric}"),
            ("change_2report_asof", cur_expr, f"lag2.{metric}"),
            ("change_4report_asof", cur_expr, f"lag4.{metric}"),
            ("change_8report_asof", cur_expr, f"lag8.{metric}"),
            ("yoy_1y_calc_asof", cur_expr, f"same1.{metric}"),
            ("yoy_2y_calc_asof", cur_expr, f"same2.{metric}"),
            ("yoy_3y_calc_asof", cur_expr, f"same3.{metric}"),
        ]
        for suffix, num, den in comparisons:
            column_name = f"{metric}_{suffix}"
            columns.append(column_name)
            select_items.append(f"{safe_growth(num, den)} AS {column_name}")
        for suffix, years, den in [
            ("cagr_2y_asof", 2, f"same2.{metric}"),
            ("cagr_3y_asof", 3, f"same3.{metric}"),
        ]:
            column_name = f"{metric}_{suffix}"
            columns.append(column_name)
            select_items.append(f"{safe_cagr(cur_expr, den, years)} AS {column_name}")
        if is_flow:
            current_single = f"cur.{metric}_single_quarter_value"
            for suffix, expr in [
                ("single_quarter_value_asof", current_single),
                ("single_quarter_yoy_asof", safe_growth(current_single, f"same1.{metric}_single_quarter_value")),
                ("single_quarter_qoq_asof", safe_growth(current_single, f"prev.{metric}_single_quarter_value")),
            ]:
                column_name = f"{metric}_{suffix}"
                columns.append(column_name)
                select_items.append(f"{expr} AS {column_name}")

    status_fields = [
        ("revenue_positive_growth_flag", "revenue_yoy_1y_calc_asof > 0"),
        ("profit_positive_growth_flag", "parent_net_profit_yoy_1y_calc_asof > 0"),
        ("deducted_profit_positive_growth_flag", "deducted_profit_yoy_1y_calc_asof > 0"),
        ("ocf_positive_growth_flag", "ocf_yoy_1y_calc_asof > 0"),
        (
            "revenue_profit_same_direction_flag",
            "(revenue_yoy_1y_calc_asof > 0 AND parent_net_profit_yoy_1y_calc_asof > 0) "
            "OR (revenue_yoy_1y_calc_asof < 0 AND parent_net_profit_yoy_1y_calc_asof < 0)",
        ),
        (
            "profit_ocf_same_direction_flag",
            "(parent_net_profit_yoy_1y_calc_asof > 0 AND ocf_yoy_1y_calc_asof > 0) "
            "OR (parent_net_profit_yoy_1y_calc_asof < 0 AND ocf_yoy_1y_calc_asof < 0)",
        ),
    ]
    # Status fields depend on aliases, so evaluate them in an outer SELECT.
    inner_columns = columns.copy()
    columns.extend([name for name, _expr in status_fields])
    columns.append("updated_at")
    inner_select = ",\n            ".join(select_items)
    outer_select = [*inner_columns]
    outer_select.extend(f"({expr}) AS {name}" for name, expr in status_fields)
    outer_select.append("CURRENT_TIMESTAMP AS updated_at")
    final_select = ",\n            ".join(outer_select)

    metric_names = [name for name, _expr, _is_flow in amount_metrics]
    raw_value_select = [
        "rs.ts_code",
        "rs.current_report_end_date",
        "EXTRACT(year FROM rs.current_report_end_date) AS report_year",
        "EXTRACT(quarter FROM rs.current_report_end_date) AS report_quarter",
        "i.or_yoy",
        "i.tr_yoy",
        "i.netprofit_yoy",
        "i.dt_netprofit_yoy",
        "i.ocf_yoy",
        "i.basic_eps_yoy",
        "i.dt_eps_yoy",
        "i.cfps_yoy",
        "i.roe_yoy",
        "i.bps_yoy",
        "i.assets_yoy",
        "i.eqt_yoy",
        "i.q_sales_yoy",
        "i.q_sales_qoq",
        "i.q_op_yoy",
        "i.q_op_qoq",
        "i.q_netprofit_yoy",
        "i.q_netprofit_qoq",
        "inc.revenue",
        "inc.total_revenue",
        "inc.operating_cost",
        "inc.total_cogs",
        "inc.operating_profit",
        "inc.total_profit",
        "inc.net_profit",
        "inc.net_profit_attr_parent AS parent_net_profit",
        "i.profit_dedt AS deducted_profit",
        "inc.ebit",
        "inc.ebitda",
        "cf.cf_from_operating AS ocf",
        "cf.cf_from_investing AS icf",
        "cf.cf_from_financing AS fcf",
        "cf.free_cashflow",
        "cf.cash_received_from_sales",
        "cf.cash_paid_for_goods",
        "cf.cash_paid_for_capex",
        "bal.total_assets",
        "bal.current_assets",
        "bal.total_noncurrent_assets AS noncurrent_assets",
        "bal.total_liabilities",
        "bal.current_liabilities",
        "bal.total_equity",
        "bal.equity_attr_parent",
        "i.interestdebt",
        "i.netdebt",
        "inc.rd_expense",
        "inc.selling_expense",
        "inc.admin_expense",
        "inc.finance_expense",
    ]
    raw_select_sql = ",\n                ".join(raw_value_select)
    single_quarter_select = []
    for metric in metric_names:
        if next(item for item in amount_metrics if item[0] == metric)[2]:
            single_quarter_select.append(
                f"""
                CASE
                    WHEN report_quarter = 1 THEN {metric}
                    ELSE {metric} - lag({metric}) OVER (
                        PARTITION BY ts_code, report_year ORDER BY current_report_end_date
                    )
                END AS {metric}_single_quarter_value
                """.strip()
            )
    single_quarter_sql = ",\n                ".join(single_quarter_select)

    return _rebuild_table(
        ctx,
        "derived_financial_growth",
        columns,
        f"""
        WITH affected_stocks AS (
            SELECT DISTINCT ts_code
            FROM derived_financial_asof
            WHERE trade_date BETWEEN ? AND ?
        ),
        report_base AS (
            SELECT DISTINCT ts_code, latest_report_end_date AS current_report_end_date
            FROM derived_financial_asof
            JOIN affected_stocks USING (ts_code)
            WHERE latest_report_end_date IS NOT NULL
        ),
        report_seq AS (
            SELECT
                rb.*,
                lag(rb.current_report_end_date, 1) OVER (
                    PARTITION BY rb.ts_code ORDER BY rb.current_report_end_date
                ) AS prev_report_end_date,
                lag(rb.current_report_end_date, 2) OVER (
                    PARTITION BY rb.ts_code ORDER BY rb.current_report_end_date
                ) AS lag_2report_end_date,
                lag(rb.current_report_end_date, 4) OVER (
                    PARTITION BY rb.ts_code ORDER BY rb.current_report_end_date
                ) AS lag_4report_end_date,
                lag(rb.current_report_end_date, 8) OVER (
                    PARTITION BY rb.ts_code ORDER BY rb.current_report_end_date
                ) AS lag_8report_end_date,
                y1.current_report_end_date AS same_period_1y_end_date,
                y2.current_report_end_date AS same_period_2y_end_date,
                y3.current_report_end_date AS same_period_3y_end_date
            FROM report_base rb
            LEFT JOIN report_base y1
                ON rb.ts_code = y1.ts_code
               AND y1.current_report_end_date = rb.current_report_end_date - INTERVAL 1 YEAR
            LEFT JOIN report_base y2
                ON rb.ts_code = y2.ts_code
               AND y2.current_report_end_date = rb.current_report_end_date - INTERVAL 2 YEAR
            LEFT JOIN report_base y3
                ON rb.ts_code = y3.ts_code
               AND y3.current_report_end_date = rb.current_report_end_date - INTERVAL 3 YEAR
        ),
        indicator_latest AS (
            SELECT *
            FROM financial_indicator_raw
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, end_date
                ORDER BY coalesce(effective_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
            ) = 1
        ),
        income_latest AS (
            SELECT *
            FROM financial_income_raw
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, end_date
                ORDER BY coalesce(effective_date, first_ann_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
            ) = 1
        ),
        balance_latest AS (
            SELECT *
            FROM financial_balance_raw
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, end_date
                ORDER BY coalesce(effective_date, first_ann_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
            ) = 1
        ),
        cashflow_latest AS (
            SELECT *
            FROM financial_cashflow_raw
            QUALIFY row_number() OVER (
                PARTITION BY ts_code, end_date
                ORDER BY coalesce(effective_date, first_ann_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
            ) = 1
        ),
        report_values AS (
            SELECT
                {raw_select_sql}
            FROM report_seq rs
            LEFT JOIN indicator_latest i
                ON rs.ts_code = i.ts_code
               AND rs.current_report_end_date = i.end_date
            LEFT JOIN income_latest inc
                ON rs.ts_code = inc.ts_code
               AND rs.current_report_end_date = inc.end_date
            LEFT JOIN balance_latest bal
                ON rs.ts_code = bal.ts_code
               AND rs.current_report_end_date = bal.end_date
            LEFT JOIN cashflow_latest cf
                ON rs.ts_code = cf.ts_code
               AND rs.current_report_end_date = cf.end_date
        ),
        report_values_enriched AS (
            SELECT
                *,
                {single_quarter_sql}
            FROM report_values
        ),
        growth_base AS (
            SELECT
                {inner_select}
            FROM derived_financial_asof a
            LEFT JOIN report_seq seq
                ON a.ts_code = seq.ts_code
               AND a.latest_report_end_date = seq.current_report_end_date
            LEFT JOIN report_values_enriched cur
                ON a.ts_code = cur.ts_code
               AND a.latest_report_end_date = cur.current_report_end_date
            LEFT JOIN report_values_enriched prev
                ON a.ts_code = prev.ts_code
               AND seq.prev_report_end_date = prev.current_report_end_date
            LEFT JOIN report_values_enriched lag2
                ON a.ts_code = lag2.ts_code
               AND seq.lag_2report_end_date = lag2.current_report_end_date
            LEFT JOIN report_values_enriched lag4
                ON a.ts_code = lag4.ts_code
               AND seq.lag_4report_end_date = lag4.current_report_end_date
            LEFT JOIN report_values_enriched lag8
                ON a.ts_code = lag8.ts_code
               AND seq.lag_8report_end_date = lag8.current_report_end_date
            LEFT JOIN report_values_enriched same1
                ON a.ts_code = same1.ts_code
               AND seq.same_period_1y_end_date = same1.current_report_end_date
            LEFT JOIN report_values_enriched same2
                ON a.ts_code = same2.ts_code
               AND seq.same_period_2y_end_date = same2.current_report_end_date
            LEFT JOIN report_values_enriched same3
                ON a.ts_code = same3.ts_code
               AND seq.same_period_3y_end_date = same3.current_report_end_date
            WHERE a.trade_date BETWEEN ? AND ?
        )
        SELECT
            {final_select}
        FROM growth_base
        """,
        [ctx.write_start_date, ctx.write_end_date, ctx.write_start_date, ctx.write_end_date],
    )


def build_capital_flow(ctx: FeatureBuildContext) -> FeatureBuildResult:
    core_periods = [5, 20, 60, 120]
    columns = [
        "ts_code", "trade_date",
        "small_buy_amount", "small_sell_amount", "small_net_amount",
        "medium_buy_amount", "medium_sell_amount", "medium_net_amount",
        "large_buy_amount", "large_sell_amount", "large_net_amount",
        "extra_large_buy_amount", "extra_large_sell_amount", "extra_large_net_amount",
        "main_net_amount", "main_buy_amount", "main_sell_amount", "retail_net_amount",
        "net_mf_amount", "net_mf_vol",
        "main_net_amount_rate", "large_net_amount_rate", "extra_large_net_amount_rate", "small_net_amount_rate",
        *[f"main_flow_ma_{n}" for n in core_periods],
        *[f"main_flow_sum_{n}" for n in core_periods],
        "main_flow_positive_days_20", "main_flow_persist_ratio_20",
        "main_flow_to_total_mv_20", "main_flow_to_circ_mv_20",
        "margin_balance", "short_balance", "margin_buy", "margin_repay",
        "short_sell_volume", "short_repay_volume", "total_margin_short_balance",
        *[f"margin_balance_chg_{n}" for n in core_periods],
        "margin_buy_to_amount", "margin_short_ratio",
        "north_hold_shares", "north_hold_ratio",
        *[f"north_hold_shares_chg_{n}" for n in core_periods],
        *[f"north_hold_ratio_chg_{n}" for n in core_periods],
        "has_moneyflow", "has_margin", "has_north_holding",
        "capital_flow_missing_reason",
        "updated_at",
    ]
    main_ma_select = []
    main_sum_select = []
    for n in core_periods:
        main_ma_select.append(
            f"CASE WHEN main_obs_{n} >= {n} THEN main_flow_ma_{n}_raw ELSE NULL END AS main_flow_ma_{n}"
        )
        main_sum_select.append(
            f"CASE WHEN main_obs_{n} >= {n} THEN main_flow_sum_{n}_raw ELSE NULL END AS main_flow_sum_{n}"
        )
    margin_chg_select = []
    north_share_chg_select = []
    north_ratio_chg_select = []
    for n in core_periods:
        margin_chg_select.append(
            f"CASE WHEN margin_balance > 0 AND lag_margin_balance_{n} > 0 THEN margin_balance / lag_margin_balance_{n} - 1 ELSE NULL END AS margin_balance_chg_{n}"
        )
        north_share_chg_select.append(
            f"CASE WHEN north_hold_shares > 0 AND lag_north_hold_shares_{n} > 0 THEN north_hold_shares / lag_north_hold_shares_{n} - 1 ELSE NULL END AS north_hold_shares_chg_{n}"
        )
        north_ratio_chg_select.append(
            f"CASE WHEN north_hold_ratio IS NOT NULL AND lag_north_hold_ratio_{n} IS NOT NULL THEN north_hold_ratio - lag_north_hold_ratio_{n} ELSE NULL END AS north_hold_ratio_chg_{n}"
        )
    rolling_fields = []
    lag_fields = []
    for n in core_periods:
        rolling_fields.extend(
            [
                f"avg(main_net_amount) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW) AS main_flow_ma_{n}_raw",
                f"sum(main_net_amount) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW) AS main_flow_sum_{n}_raw",
                f"count(main_net_amount) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW) AS main_obs_{n}",
            ]
        )
        lag_fields.extend(
            [
                f"lag(margin_balance, {n}) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_margin_balance_{n}",
                f"lag(north_hold_shares, {n}) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_north_hold_shares_{n}",
                f"lag(north_hold_ratio, {n}) OVER (PARTITION BY ts_code ORDER BY trade_date) AS lag_north_hold_ratio_{n}",
            ]
        )
    return _rebuild_table(
        ctx,
        "derived_capital_flow",
        columns,
        f"""
        WITH north_holding AS (
            SELECT
                ts_code,
                trade_date,
                sum(hold_shares) AS north_hold_shares,
                max(hold_ratio) AS north_hold_ratio
            FROM northbound_holding
            WHERE trade_date BETWEEN ? AND ?
            GROUP BY ts_code, trade_date
        ),
        base AS (
            SELECT
                ds.ts_code,
                ds.trade_date,
                ds.amount,
                ds.has_price,
                mf.buy_sm_amount AS small_buy_amount,
                mf.sell_sm_amount AS small_sell_amount,
                mf.buy_md_amount AS medium_buy_amount,
                mf.sell_md_amount AS medium_sell_amount,
                mf.buy_lg_amount AS large_buy_amount,
                mf.sell_lg_amount AS large_sell_amount,
                mf.buy_elg_amount AS extra_large_buy_amount,
                mf.sell_elg_amount AS extra_large_sell_amount,
                mf.net_mf_amount,
                mf.net_mf_vol,
                m.margin_balance,
                m.short_balance,
                m.margin_buy,
                m.margin_repay,
                m.short_sell_volume,
                m.short_repay_volume,
                m.total_balance AS total_margin_short_balance,
                nh.north_hold_shares,
                nh.north_hold_ratio,
                v.total_mv,
                v.circ_mv,
                mf.ts_code IS NOT NULL AS has_moneyflow,
                m.ts_code IS NOT NULL AS has_margin,
                nh.ts_code IS NOT NULL AS has_north_holding
            FROM derived_daily_spine ds
            LEFT JOIN stock_moneyflow_daily mf
                ON ds.ts_code = mf.ts_code
               AND ds.trade_date = mf.trade_date
            LEFT JOIN margin_detail m
                ON ds.ts_code = m.ts_code
               AND ds.trade_date = m.trade_date
            LEFT JOIN north_holding nh
                ON ds.ts_code = nh.ts_code
               AND ds.trade_date = nh.trade_date
            LEFT JOIN derived_valuation_size v
                ON ds.ts_code = v.ts_code
               AND ds.trade_date = v.trade_date
            WHERE ds.trade_date BETWEEN ? AND ?
        ),
        calc AS (
            SELECT
                *,
                small_buy_amount - small_sell_amount AS small_net_amount,
                medium_buy_amount - medium_sell_amount AS medium_net_amount,
                large_buy_amount - large_sell_amount AS large_net_amount,
                extra_large_buy_amount - extra_large_sell_amount AS extra_large_net_amount,
                large_buy_amount + extra_large_buy_amount AS main_buy_amount,
                large_sell_amount + extra_large_sell_amount AS main_sell_amount,
                (large_buy_amount - large_sell_amount) + (extra_large_buy_amount - extra_large_sell_amount) AS main_net_amount,
                small_buy_amount - small_sell_amount AS retail_net_amount
            FROM base
        ),
        rolling AS (
            SELECT
                *,
                {", ".join(rolling_fields)},
                sum(CASE WHEN main_net_amount > 0 THEN 1 ELSE 0 END) OVER (
                    PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                ) AS main_flow_positive_days_20_raw,
                count(main_net_amount) OVER (
                    PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                ) AS main_flow_positive_obs_20,
                {", ".join(lag_fields)}
            FROM calc
        )
        SELECT
            ts_code,
            trade_date,
            small_buy_amount,
            small_sell_amount,
            small_net_amount,
            medium_buy_amount,
            medium_sell_amount,
            medium_net_amount,
            large_buy_amount,
            large_sell_amount,
            large_net_amount,
            extra_large_buy_amount,
            extra_large_sell_amount,
            extra_large_net_amount,
            main_net_amount,
            main_buy_amount,
            main_sell_amount,
            retail_net_amount,
            net_mf_amount,
            net_mf_vol,
            CASE WHEN amount > 0 THEN main_net_amount * 10.0 / amount ELSE NULL END AS main_net_amount_rate,
            CASE WHEN amount > 0 THEN large_net_amount * 10.0 / amount ELSE NULL END AS large_net_amount_rate,
            CASE WHEN amount > 0 THEN extra_large_net_amount * 10.0 / amount ELSE NULL END AS extra_large_net_amount_rate,
            CASE WHEN amount > 0 THEN small_net_amount * 10.0 / amount ELSE NULL END AS small_net_amount_rate,
            {", ".join(main_ma_select)},
            {", ".join(main_sum_select)},
            CASE WHEN main_flow_positive_obs_20 >= 20 THEN CAST(main_flow_positive_days_20_raw AS INTEGER) ELSE NULL END AS main_flow_positive_days_20,
            CASE WHEN main_flow_positive_obs_20 >= 20 THEN main_flow_positive_days_20_raw / 20.0 ELSE NULL END AS main_flow_persist_ratio_20,
            CASE WHEN total_mv > 0 AND main_obs_20 >= 20 THEN main_flow_sum_20_raw / total_mv ELSE NULL END AS main_flow_to_total_mv_20,
            CASE WHEN circ_mv > 0 AND main_obs_20 >= 20 THEN main_flow_sum_20_raw / circ_mv ELSE NULL END AS main_flow_to_circ_mv_20,
            margin_balance,
            short_balance,
            margin_buy,
            margin_repay,
            short_sell_volume,
            short_repay_volume,
            total_margin_short_balance,
            {", ".join(margin_chg_select)},
            CASE WHEN amount > 0 THEN margin_buy / (amount * 1000.0) ELSE NULL END AS margin_buy_to_amount,
            CASE WHEN margin_balance > 0 THEN short_balance / margin_balance ELSE NULL END AS margin_short_ratio,
            north_hold_shares,
            north_hold_ratio,
            {", ".join(north_share_chg_select)},
            {", ".join(north_ratio_chg_select)},
            has_moneyflow,
            has_margin,
            has_north_holding,
            CASE
                WHEN NOT has_price THEN 'missing_price'
                WHEN NOT has_moneyflow THEN 'missing_moneyflow'
                WHEN NOT has_margin THEN 'no_margin_coverage'
                WHEN NOT has_north_holding THEN 'no_north_coverage'
                ELSE NULL
            END AS capital_flow_missing_reason,
            CURRENT_TIMESTAMP AS updated_at
        FROM rolling
        WHERE trade_date BETWEEN ? AND ?
        """,
        [
            ctx.read_start_date,
            ctx.write_end_date,
            ctx.read_start_date,
            ctx.write_end_date,
            ctx.write_start_date,
            ctx.write_end_date,
        ],
    )


def build_sector_concept_context(ctx: FeatureBuildContext) -> FeatureBuildResult:
    table_name = "derived_sector_concept_context"
    if ctx.dry_run:
        return FeatureBuildResult(
            module=ctx.module,
            status="dry_run",
            rows_written=0,
            message=(
                f"would rebuild {table_name} from {ctx.write_start_date} to {ctx.write_end_date} "
                "using build_phase3_sector_concept_core.py"
            ),
        )

    con = _require_connection(ctx)
    backend = _load_phase3_script("build_phase3_sector_concept_core.py")
    columns = backend.table_fields(table_name)
    con.execute("BEGIN TRANSACTION")
    try:
        delete_write_window(ctx, table_name)
        con.execute(backend.build_sql(ctx.write_start_date, ctx.write_end_date, columns))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    rows = _count_write_window(ctx, table_name)
    return FeatureBuildResult(ctx.module, "success", rows, f"rebuilt {table_name} via phase3 backend")


def build_index_market_context(ctx: FeatureBuildContext) -> FeatureBuildResult:
    table_name = "derived_index_market_context"
    if ctx.dry_run:
        return FeatureBuildResult(
            module=ctx.module,
            status="dry_run",
            rows_written=0,
            message=(
                f"would rebuild {table_name} from {ctx.write_start_date} to {ctx.write_end_date} "
                "using build_phase3_index_market_core.py"
            ),
        )

    con = _require_connection(ctx)
    backend = _load_phase3_script("build_phase3_index_market_core.py")
    columns = backend.fields(table_name)
    con.execute("BEGIN TRANSACTION")
    try:
        delete_write_window(ctx, table_name)
        con.execute(backend.sql(columns, ctx.write_start_date, ctx.write_end_date, ctx.read_start_date))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    rows = _count_write_window(ctx, table_name)
    return FeatureBuildResult(ctx.module, "success", rows, f"rebuilt {table_name} via phase3 backend")


def build_cross_sectional(ctx: FeatureBuildContext) -> FeatureBuildResult:
    table_name = "derived_cross_sectional"
    if ctx.dry_run:
        return FeatureBuildResult(
            module=ctx.module,
            status="dry_run",
            rows_written=0,
            message=(
                f"would rebuild {table_name} from {ctx.write_start_date} to {ctx.write_end_date} "
                "using build_phase3_cross_sectional_core.py"
            ),
        )

    con = _require_connection(ctx)
    backend = _load_phase3_script("build_phase3_cross_sectional_core.py")
    con.execute("BEGIN TRANSACTION")
    try:
        delete_write_window(ctx, table_name)
        con.execute(backend.insert_metadata_sql(ctx.write_start_date, ctx.write_end_date))
        for variable in backend.PHYSICAL_VARIABLES:
            con.execute(backend.update_variable_sql(variable, ctx.write_start_date, ctx.write_end_date))
        con.execute(backend.update_exposure_sql(ctx.write_start_date, ctx.write_end_date))
        backend.update_residuals_pandas(con, ctx.write_start_date, ctx.write_end_date)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    rows = _count_write_window(ctx, table_name)
    return FeatureBuildResult(ctx.module, "success", rows, f"rebuilt {table_name} via phase3 backend")


def build_corporate_action(ctx: FeatureBuildContext) -> FeatureBuildResult:
    table_name = "derived_corporate_action"
    if ctx.dry_run:
        return FeatureBuildResult(
            module=ctx.module,
            status="dry_run",
            rows_written=0,
            message=(
                f"would rebuild {table_name} from {ctx.write_start_date} to {ctx.write_end_date} "
                "using build_phase3_corporate_action_core.py"
            ),
        )

    con = _require_connection(ctx)
    backend = _load_phase3_script("build_phase3_corporate_action_core.py")
    con.execute("BEGIN TRANSACTION")
    try:
        delete_write_window(ctx, table_name)
        con.execute(backend.build_insert_sql(ctx.read_start_date, ctx.write_end_date, ctx.write_start_date))
        backend.update_share_float_fields(con, ctx.read_start_date, ctx.write_end_date, ctx.write_start_date)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    rows = _count_write_window(ctx, table_name)
    return FeatureBuildResult(ctx.module, "success", rows, f"rebuilt {table_name} via phase3 backend")


def build_ownership_governance(ctx: FeatureBuildContext) -> FeatureBuildResult:
    table_name = "derived_ownership_governance"
    if ctx.dry_run:
        return FeatureBuildResult(
            module=ctx.module,
            status="dry_run",
            rows_written=0,
            message=(
                f"would rebuild {table_name} from {ctx.write_start_date} to {ctx.write_end_date} "
                "using build_phase3_ownership_governance_core.py"
            ),
        )

    con = _require_connection(ctx)
    backend = _load_phase3_script("build_phase3_ownership_governance_core.py")
    con.execute("BEGIN TRANSACTION")
    try:
        delete_write_window(ctx, table_name)
        con.execute(backend.build_insert_sql(ctx.write_start_date, ctx.write_end_date))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    rows = _count_write_window(ctx, table_name)
    return FeatureBuildResult(ctx.module, "success", rows, f"rebuilt {table_name} via phase3 backend")


def build_composite_state(ctx: FeatureBuildContext) -> FeatureBuildResult:
    table_name = "derived_composite_state"
    if ctx.dry_run:
        return FeatureBuildResult(
            module=ctx.module,
            status="dry_run",
            rows_written=0,
            message=(
                f"would rebuild {table_name} from {ctx.write_start_date} to {ctx.write_end_date} "
                "using build_phase3_composite_state_core.py"
            ),
        )

    con = _require_connection(ctx)
    backend = _load_phase3_script("build_phase3_composite_state_core.py")
    con.execute("BEGIN TRANSACTION")
    try:
        delete_write_window(ctx, table_name)
        con.execute(backend.build_insert_sql(ctx.write_start_date, ctx.write_end_date))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    rows = _count_write_window(ctx, table_name)
    return FeatureBuildResult(ctx.module, "success", rows, f"rebuilt {table_name} via phase3 backend")


BUILDERS: dict[str, FeatureBuilder] = {module: placeholder_builder for module in MODULE_ORDER}
BUILDERS["daily_spine"] = build_daily_spine
BUILDERS["price_technical"] = build_price_technical
BUILDERS["volume_liquidity"] = build_volume_liquidity
BUILDERS["return_momentum"] = build_return_momentum
BUILDERS["volatility_risk"] = build_volatility_risk
BUILDERS["trading_constraint"] = build_trading_constraint
BUILDERS["valuation_size"] = build_valuation_size
BUILDERS["financial_asof"] = build_financial_asof
BUILDERS["financial_quality"] = build_financial_quality
BUILDERS["financial_growth"] = build_financial_growth
BUILDERS["capital_flow"] = build_capital_flow
BUILDERS["sector_concept_context"] = build_sector_concept_context
BUILDERS["index_market_context"] = build_index_market_context
BUILDERS["cross_sectional"] = build_cross_sectional
BUILDERS["corporate_action"] = build_corporate_action
BUILDERS["ownership_governance"] = build_ownership_governance
BUILDERS["composite_state"] = build_composite_state
