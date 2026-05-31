from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .context import FeatureBuildContext
from .planner import MODULE_ORDER
from .writer import delete_write_window
from ..schema import quote_ident


@dataclass(frozen=True)
class FeatureBuildResult:
    module: str
    status: str
    rows_written: int = 0
    message: str = ""


FeatureBuilder = Callable[[FeatureBuildContext], FeatureBuildResult]


def placeholder_builder(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return FeatureBuildResult(
        module=ctx.module,
        status="planned",
        rows_written=0,
        message="builder not implemented yet",
    )


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
                open_qfq, high_qfq, low_qfq, close_qfq, pre_close_qfq,
                ret_1_raw, ret_1_hfq, log_ret_1, log_ret_1_hfq,
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
                d.open * a.adj_factor / nullif(la.latest_adj_factor_asof, 0) AS open_qfq,
                d.high * a.adj_factor / nullif(la.latest_adj_factor_asof, 0) AS high_qfq,
                d.low * a.adj_factor / nullif(la.latest_adj_factor_asof, 0) AS low_qfq,
                d.close * a.adj_factor / nullif(la.latest_adj_factor_asof, 0) AS close_qfq,
                d.pre_close * a.adj_factor / nullif(la.latest_adj_factor_asof, 0) AS pre_close_qfq,
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
            open_qfq,
            high_qfq,
            low_qfq,
            close_qfq,
            pre_close_qfq,
            ret_1_raw,
            ret_1_hfq,
            log_ret_1_hfq AS log_ret_1,
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
                ELSE close_raw >= up_limit * 0.9999
            END AS limit_up_flag,
            CASE
                WHEN close_raw IS NULL OR down_limit IS NULL THEN NULL
                ELSE close_raw <= down_limit * 1.0001
            END AS limit_down_flag,
            CASE
                WHEN high_raw IS NULL OR up_limit IS NULL THEN NULL
                ELSE high_raw >= up_limit * 0.9999
            END AS touch_limit_up_flag,
            CASE
                WHEN low_raw IS NULL OR down_limit IS NULL THEN NULL
                ELSE low_raw <= down_limit * 1.0001
            END AS touch_limit_down_flag,
            CASE
                WHEN open_raw IS NULL OR up_limit IS NULL THEN NULL
                ELSE open_raw >= up_limit * 0.9999
            END AS open_limit_up_flag,
            CASE
                WHEN open_raw IS NULL OR down_limit IS NULL THEN NULL
                ELSE open_raw <= down_limit * 1.0001
            END AS open_limit_down_flag,
            CASE
                WHEN close_raw > 0 AND up_limit IS NOT NULL THEN up_limit / close_raw - 1
                ELSE NULL
            END AS limit_up_gap,
            CASE
                WHEN close_raw > 0 AND down_limit IS NOT NULL THEN close_raw / down_limit - 1
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
        ["ts_code", "trade_date", "rsi_14", "updated_at"],
        """
        WITH base AS (
            SELECT
                d.ts_code,
                d.trade_date,
                d.close * a.adj_factor AS close_hfq
            FROM stock_daily d
            LEFT JOIN stock_adj_factor a
                ON d.ts_code = a.ts_code
               AND d.trade_date = a.trade_date
            WHERE d.trade_date BETWEEN ? AND ?
        ),
        ordered AS (
            SELECT
                ts_code,
                trade_date,
                close_hfq - lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) AS delta
            FROM base
        ),
        rolling AS (
            SELECT
                ts_code,
                trade_date,
                avg(CASE WHEN delta > 0 THEN delta ELSE 0 END)
                    OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_gain,
                avg(CASE WHEN delta < 0 THEN -delta ELSE 0 END)
                    OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS avg_loss,
                count(delta)
                    OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS obs
            FROM ordered
        )
        SELECT
            ts_code,
            trade_date,
            CASE
                WHEN obs < 14 THEN NULL
                WHEN avg_loss = 0 AND avg_gain > 0 THEN 100
                WHEN avg_loss = 0 THEN NULL
                ELSE 100 - 100 / (1 + avg_gain / avg_loss)
            END AS rsi_14,
            CURRENT_TIMESTAMP AS updated_at
        FROM rolling
        WHERE trade_date BETWEEN ? AND ?
        """,
    )


def build_volume_liquidity(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_volume_liquidity",
        ["ts_code", "trade_date", "volume_ma_20", "updated_at"],
        """
        WITH rolling AS (
            SELECT
                ts_code,
                trade_date,
                avg(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS volume_ma_20,
                count(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS obs
            FROM stock_daily
            WHERE trade_date BETWEEN ? AND ?
        )
        SELECT
            ts_code,
            trade_date,
            CASE WHEN obs >= 20 THEN volume_ma_20 ELSE NULL END AS volume_ma_20,
            CURRENT_TIMESTAMP AS updated_at
        FROM rolling
        WHERE trade_date BETWEEN ? AND ?
        """,
    )


def build_return_momentum(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_return_momentum",
        ["ts_code", "trade_date", "ret_20", "updated_at"],
        """
        WITH ordered AS (
            SELECT
                d.ts_code,
                d.trade_date,
                d.close * a.adj_factor AS close_hfq,
                lag(d.close * a.adj_factor, 20) OVER (PARTITION BY d.ts_code ORDER BY d.trade_date) AS lag_close_hfq
            FROM stock_daily d
            LEFT JOIN stock_adj_factor a
                ON d.ts_code = a.ts_code
               AND d.trade_date = a.trade_date
            WHERE d.trade_date BETWEEN ? AND ?
        )
        SELECT
            ts_code,
            trade_date,
            CASE
                WHEN close_hfq > 0 AND lag_close_hfq > 0 THEN close_hfq / lag_close_hfq - 1
                ELSE NULL
            END AS ret_20,
            CURRENT_TIMESTAMP AS updated_at
        FROM ordered
        WHERE trade_date BETWEEN ? AND ?
        """,
    )


def build_volatility_risk(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_volatility_risk",
        ["ts_code", "trade_date", "hv_60", "updated_at"],
        """
        WITH base AS (
            SELECT
                d.ts_code,
                d.trade_date,
                d.close * a.adj_factor AS close_hfq
            FROM stock_daily d
            LEFT JOIN stock_adj_factor a
                ON d.ts_code = a.ts_code
               AND d.trade_date = a.trade_date
            WHERE d.trade_date BETWEEN ? AND ?
        ),
        returns AS (
            SELECT
                ts_code,
                trade_date,
                CASE
                    WHEN close_hfq > 0
                     AND lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date) > 0
                    THEN ln(close_hfq / lag(close_hfq) OVER (PARTITION BY ts_code ORDER BY trade_date))
                    ELSE NULL
                END AS log_ret_1
            FROM base
        ),
        rolling AS (
            SELECT
                ts_code,
                trade_date,
                stddev_samp(log_ret_1) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) * sqrt(242) AS hv_60,
                count(log_ret_1) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS obs
            FROM returns
        )
        SELECT
            ts_code,
            trade_date,
            CASE WHEN obs >= 40 THEN hv_60 ELSE NULL END AS hv_60,
            CURRENT_TIMESTAMP AS updated_at
        FROM rolling
        WHERE trade_date BETWEEN ? AND ?
        """,
    )


def build_trading_constraint(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_trading_constraint",
        ["ts_code", "trade_date", "limit_up_days_5", "updated_at"],
        """
        WITH rolling AS (
            SELECT
                d.ts_code,
                d.trade_date,
                sum(CASE WHEN d.close IS NOT NULL AND l.up_limit IS NOT NULL AND d.close >= l.up_limit * 0.9999 THEN 1 ELSE 0 END)
                    OVER (PARTITION BY d.ts_code ORDER BY d.trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS limit_up_days_5
            FROM stock_daily d
            LEFT JOIN stock_limit_price l
                ON d.ts_code = l.ts_code
               AND d.trade_date = l.trade_date
            WHERE d.trade_date BETWEEN ? AND ?
        )
        SELECT
            ts_code,
            trade_date,
            CAST(limit_up_days_5 AS INTEGER) AS limit_up_days_5,
            CURRENT_TIMESTAMP AS updated_at
        FROM rolling
        WHERE trade_date BETWEEN ? AND ?
        """,
    )


def build_valuation_size(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_valuation_size",
        ["ts_code", "trade_date", "pe_ttm_pct_5y", "updated_at"],
        """
        WITH current_rows AS (
            SELECT ts_code, trade_date, pe_ttm
            FROM stock_daily_basic
            WHERE trade_date BETWEEN ? AND ?
        )
        SELECT
            c.ts_code,
            c.trade_date,
            CASE
                WHEN c.pe_ttm IS NULL OR count(h.pe_ttm) = 0 THEN NULL
                ELSE avg(CASE WHEN h.pe_ttm <= c.pe_ttm THEN 1.0 ELSE 0.0 END)
            END AS pe_ttm_pct_5y,
            CURRENT_TIMESTAMP AS updated_at
        FROM current_rows c
        LEFT JOIN stock_daily_basic h
            ON c.ts_code = h.ts_code
           AND h.trade_date BETWEEN c.trade_date - INTERVAL 5 YEAR AND c.trade_date
           AND h.pe_ttm IS NOT NULL
        GROUP BY c.ts_code, c.trade_date, c.pe_ttm
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_financial_asof(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_financial_asof",
        ["ts_code", "trade_date", "latest_report_end_date", "updated_at"],
        """
        WITH candidates AS (
            SELECT
                d.ts_code,
                d.trade_date,
                f.end_date,
                row_number() OVER (
                    PARTITION BY d.ts_code, d.trade_date
                    ORDER BY f.effective_date DESC NULLS LAST, f.end_date DESC NULLS LAST, f.ann_date DESC NULLS LAST
                ) AS rn
            FROM stock_daily d
            LEFT JOIN financial_indicator f
                ON d.ts_code = f.ts_code
               AND f.effective_date <= d.trade_date
            WHERE d.trade_date BETWEEN ? AND ?
        )
        SELECT
            ts_code,
            trade_date,
            end_date AS latest_report_end_date,
            CURRENT_TIMESTAMP AS updated_at
        FROM candidates
        WHERE rn = 1
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_financial_quality(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_financial_quality",
        ["ts_code", "trade_date", "roe_asof", "updated_at"],
        """
        WITH candidates AS (
            SELECT
                d.ts_code,
                d.trade_date,
                f.roe,
                row_number() OVER (
                    PARTITION BY d.ts_code, d.trade_date
                    ORDER BY f.effective_date DESC NULLS LAST, f.end_date DESC NULLS LAST, f.ann_date DESC NULLS LAST
                ) AS rn
            FROM stock_daily d
            LEFT JOIN financial_indicator f
                ON d.ts_code = f.ts_code
               AND f.effective_date <= d.trade_date
            WHERE d.trade_date BETWEEN ? AND ?
        )
        SELECT
            ts_code,
            trade_date,
            roe AS roe_asof,
            CURRENT_TIMESTAMP AS updated_at
        FROM candidates
        WHERE rn = 1
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_financial_growth(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_financial_growth",
        ["ts_code", "trade_date", "revenue_yoy_asof", "updated_at"],
        """
        WITH candidates AS (
            SELECT
                d.ts_code,
                d.trade_date,
                f.or_yoy,
                row_number() OVER (
                    PARTITION BY d.ts_code, d.trade_date
                    ORDER BY f.effective_date DESC NULLS LAST, f.end_date DESC NULLS LAST, f.ann_date DESC NULLS LAST
                ) AS rn
            FROM stock_daily d
            LEFT JOIN financial_indicator f
                ON d.ts_code = f.ts_code
               AND f.effective_date <= d.trade_date
            WHERE d.trade_date BETWEEN ? AND ?
        )
        SELECT
            ts_code,
            trade_date,
            or_yoy AS revenue_yoy_asof,
            CURRENT_TIMESTAMP AS updated_at
        FROM candidates
        WHERE rn = 1
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_capital_flow(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_capital_flow",
        ["ts_code", "trade_date", "main_flow_ma_20", "updated_at"],
        """
        WITH rolling AS (
            SELECT
                ts_code,
                trade_date,
                avg(net_mf_amount) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS main_flow_ma_20,
                count(net_mf_amount) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS obs
            FROM stock_moneyflow_daily
            WHERE trade_date BETWEEN ? AND ?
        )
        SELECT
            ts_code,
            trade_date,
            CASE WHEN obs >= 20 THEN main_flow_ma_20 ELSE NULL END AS main_flow_ma_20,
            CURRENT_TIMESTAMP AS updated_at
        FROM rolling
        WHERE trade_date BETWEEN ? AND ?
        """,
    )


def build_sector_concept_context(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_sector_concept_context",
        ["ts_code", "trade_date", "sector_ret_20", "updated_at"],
        """
        WITH stock_industry AS (
            SELECT
                r.ts_code,
                r.trade_date,
                m.industry_code,
                r.ret_20
            FROM derived_return_momentum r
            LEFT JOIN sw_industry_member m
                ON r.ts_code = m.ts_code
               AND m.in_date <= r.trade_date
               AND (m.out_date IS NULL OR m.out_date > r.trade_date)
            WHERE r.trade_date BETWEEN ? AND ?
        ),
        sector_ret AS (
            SELECT
                industry_code,
                trade_date,
                avg(ret_20) AS sector_ret_20
            FROM stock_industry
            GROUP BY industry_code, trade_date
        )
        SELECT
            s.ts_code,
            s.trade_date,
            sr.sector_ret_20,
            CURRENT_TIMESTAMP AS updated_at
        FROM stock_industry s
        LEFT JOIN sector_ret sr
            ON s.industry_code = sr.industry_code
           AND s.trade_date = sr.trade_date
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_index_market_context(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_index_market_context",
        ["ts_code", "trade_date", "market_up_ratio", "updated_at"],
        """
        SELECT
            d.ts_code,
            d.trade_date,
            CASE
                WHEN b.stock_count > 0 THEN CAST(b.up_count AS DOUBLE) / CAST(b.stock_count AS DOUBLE)
                ELSE NULL
            END AS market_up_ratio,
            CURRENT_TIMESTAMP AS updated_at
        FROM stock_daily d
        LEFT JOIN market_breadth_daily b
            ON d.trade_date = b.trade_date
        WHERE d.trade_date BETWEEN ? AND ?
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_cross_sectional(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_cross_sectional",
        ["ts_code", "trade_date", "ret_20_rank_all", "updated_at"],
        """
        SELECT
            ts_code,
            trade_date,
            CASE
                WHEN ret_20 IS NULL THEN NULL
                ELSE rank() OVER (PARTITION BY trade_date ORDER BY ret_20 DESC NULLS LAST)
            END AS ret_20_rank_all,
            CURRENT_TIMESTAMP AS updated_at
        FROM derived_return_momentum
        WHERE trade_date BETWEEN ? AND ?
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_corporate_action(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_corporate_action",
        ["ts_code", "trade_date", "cash_dividend_ttm", "updated_at"],
        """
        SELECT
            d.ts_code,
            d.trade_date,
            sum(CASE WHEN v.cash_div IS NOT NULL THEN v.cash_div ELSE 0 END) AS cash_dividend_ttm,
            CURRENT_TIMESTAMP AS updated_at
        FROM stock_daily d
        LEFT JOIN financial_dividend v
            ON d.ts_code = v.ts_code
           AND coalesce(v.ex_date, v.record_date, v.ann_date) BETWEEN d.trade_date - INTERVAL 365 DAY AND d.trade_date
        WHERE d.trade_date BETWEEN ? AND ?
        GROUP BY d.ts_code, d.trade_date
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_ownership_governance(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_ownership_governance",
        ["ts_code", "trade_date", "pledge_ratio_asof", "updated_at"],
        """
        WITH candidates AS (
            SELECT
                d.ts_code,
                d.trade_date,
                p.pledge_ratio,
                row_number() OVER (
                    PARTITION BY d.ts_code, d.trade_date
                    ORDER BY p.end_date DESC NULLS LAST
                ) AS rn
            FROM stock_daily d
            LEFT JOIN financial_pledge_stat p
                ON d.ts_code = p.ts_code
               AND p.end_date <= d.trade_date
            WHERE d.trade_date BETWEEN ? AND ?
        )
        SELECT
            ts_code,
            trade_date,
            pledge_ratio AS pledge_ratio_asof,
            CURRENT_TIMESTAMP AS updated_at
        FROM candidates
        WHERE rn = 1
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


def build_composite_state(ctx: FeatureBuildContext) -> FeatureBuildResult:
    return _rebuild_table(
        ctx,
        "derived_composite_state",
        ["ts_code", "trade_date", "value_quality_score", "updated_at"],
        """
        SELECT
            q.ts_code,
            q.trade_date,
            CASE
                WHEN v.pe_ttm_pct_5y IS NULL OR q.roe_asof IS NULL THEN NULL
                ELSE (1 - v.pe_ttm_pct_5y) + percent_rank() OVER (PARTITION BY q.trade_date ORDER BY q.roe_asof)
            END AS value_quality_score,
            CURRENT_TIMESTAMP AS updated_at
        FROM derived_financial_quality q
        LEFT JOIN derived_valuation_size v
            ON q.ts_code = v.ts_code
           AND q.trade_date = v.trade_date
        WHERE q.trade_date BETWEEN ? AND ?
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )


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
