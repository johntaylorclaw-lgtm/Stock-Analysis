from __future__ import annotations

import duckdb

from .database import connect


VIEW_SQL = [
    """
    CREATE OR REPLACE VIEW stock_price_adjusted AS
    WITH base AS (
        SELECT
            d.ts_code,
            d.trade_date,
            d.open,
            d.high,
            d.low,
            d.close,
            d.pre_close,
            d.change,
            d.pct_chg,
            d.volume,
            d.amount,
            d.amplitude,
            af.adj_factor,
            last_value(af.adj_factor IGNORE NULLS) OVER (
                PARTITION BY d.ts_code
                ORDER BY d.trade_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS latest_adj_factor
        FROM stock_daily d
        LEFT JOIN stock_adj_factor af
          ON d.ts_code = af.ts_code
         AND d.trade_date = af.trade_date
    )
    SELECT
        *,
        open * adj_factor AS open_hfq,
        high * adj_factor AS high_hfq,
        low * adj_factor AS low_hfq,
        close * adj_factor AS close_hfq,
        pre_close * adj_factor AS pre_close_hfq,
        open * adj_factor / NULLIF(latest_adj_factor, 0) AS open_qfq_current,
        high * adj_factor / NULLIF(latest_adj_factor, 0) AS high_qfq_current,
        low * adj_factor / NULLIF(latest_adj_factor, 0) AS low_qfq_current,
        close * adj_factor / NULLIF(latest_adj_factor, 0) AS close_qfq_current,
        pre_close * adj_factor / NULLIF(latest_adj_factor, 0) AS pre_close_qfq_current
    FROM base
    """,
    """
    CREATE OR REPLACE VIEW stock_base_daily AS
    SELECT
        p.ts_code,
        s.symbol,
        s.name,
        s.market,
        s.exchange,
        s.list_status,
        p.trade_date,
        p.open,
        p.high,
        p.low,
        p.close,
        p.pre_close,
        p.change,
        p.pct_chg,
        p.volume,
        p.amount,
        p.amplitude,
        p.adj_factor,
        p.open_hfq,
        p.high_hfq,
        p.low_hfq,
        p.close_hfq,
        p.pre_close_hfq,
        p.open_qfq_current,
        p.high_qfq_current,
        p.low_qfq_current,
        p.close_qfq_current,
        p.pre_close_qfq_current,
        b.turnover_rate,
        b.turnover_rate_free,
        b.volume_ratio,
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
        l.up_limit,
        l.down_limit
    FROM stock_price_adjusted p
    LEFT JOIN stock_basic_info s ON p.ts_code = s.ts_code
    LEFT JOIN stock_daily_basic b ON p.ts_code = b.ts_code AND p.trade_date = b.trade_date
    LEFT JOIN stock_limit_price l ON p.ts_code = l.ts_code AND p.trade_date = l.trade_date
    """,
    """
    CREATE OR REPLACE VIEW market_breadth_daily AS
    SELECT
        d.trade_date,
        count(*) AS stock_count,
        sum(CASE WHEN d.pct_chg > 0 THEN 1 ELSE 0 END) AS up_count,
        sum(CASE WHEN d.pct_chg < 0 THEN 1 ELSE 0 END) AS down_count,
        sum(CASE WHEN d.pct_chg = 0 THEN 1 ELSE 0 END) AS flat_count,
        sum(CASE WHEN l.up_limit IS NOT NULL AND d.close >= l.up_limit THEN 1 ELSE 0 END) AS limit_up_count,
        sum(CASE WHEN l.down_limit IS NOT NULL AND d.close <= l.down_limit THEN 1 ELSE 0 END) AS limit_down_count,
        sum(d.amount) AS amount_total,
        median(d.amount) AS amount_median,
        median(d.pct_chg) AS ret_median,
        avg(d.pct_chg) AS ret_equal_weight
    FROM stock_daily d
    LEFT JOIN stock_limit_price l
      ON d.ts_code = l.ts_code
     AND d.trade_date = l.trade_date
    GROUP BY d.trade_date
    """,
    """
    CREATE OR REPLACE VIEW concept_daily AS
    SELECT
        cm.concept_id,
        cm.concept_name,
        d.trade_date,
        count(*) AS member_count,
        avg(d.pct_chg) AS ret_equal_weight,
        sum(d.amount) AS amount_total,
        avg(b.turnover_rate) AS turnover_rate_avg,
        sum(CASE WHEN l.up_limit IS NOT NULL AND d.close >= l.up_limit THEN 1 ELSE 0 END) AS limit_up_count,
        sum(CASE WHEN l.down_limit IS NOT NULL AND d.close <= l.down_limit THEN 1 ELSE 0 END) AS limit_down_count
    FROM concept_member cm
    JOIN stock_daily d ON cm.ts_code = d.ts_code
    LEFT JOIN stock_daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
    LEFT JOIN stock_limit_price l ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
    GROUP BY cm.concept_id, cm.concept_name, d.trade_date
    """,
    """
    CREATE OR REPLACE VIEW industry_daily AS
    SELECT
        sm.industry_code,
        sm.industry_name,
        d.trade_date,
        count(*) AS member_count,
        avg(d.pct_chg) AS ret_equal_weight,
        sum(d.amount) AS amount_total,
        avg(b.turnover_rate) AS turnover_rate_avg,
        sum(CASE WHEN l.up_limit IS NOT NULL AND d.close >= l.up_limit THEN 1 ELSE 0 END) AS limit_up_count,
        sum(CASE WHEN l.down_limit IS NOT NULL AND d.close <= l.down_limit THEN 1 ELSE 0 END) AS limit_down_count
    FROM sw_industry_member sm
    JOIN stock_daily d ON sm.ts_code = d.ts_code
      AND d.trade_date >= sm.in_date
      AND (sm.out_date IS NULL OR d.trade_date <= sm.out_date)
    LEFT JOIN stock_daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
    LEFT JOIN stock_limit_price l ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
    GROUP BY sm.industry_code, sm.industry_name, d.trade_date
    """,
    """
    CREATE OR REPLACE VIEW stock_base_daily_enriched AS
    SELECT
        b.*,
        mf.buy_lg_amount,
        mf.sell_lg_amount,
        mf.buy_elg_amount,
        mf.sell_elg_amount,
        mf.net_mf_amount,
        (coalesce(mf.buy_lg_amount, 0) + coalesce(mf.buy_elg_amount, 0)
          - coalesce(mf.sell_lg_amount, 0) - coalesce(mf.sell_elg_amount, 0)) AS main_net_inflow,
        m.margin_balance,
        m.short_balance,
        m.margin_buy,
        m.total_balance,
        nb.hold_shares AS northbound_hold_shares,
        nb.hold_ratio AS northbound_hold_ratio
    FROM stock_base_daily b
    LEFT JOIN stock_moneyflow_daily mf ON b.ts_code = mf.ts_code AND b.trade_date = mf.trade_date
    LEFT JOIN margin_detail m ON b.ts_code = m.ts_code AND b.trade_date = m.trade_date
    LEFT JOIN northbound_holding nb ON b.ts_code = nb.ts_code AND b.trade_date = nb.trade_date
    """,
    """
    CREATE OR REPLACE VIEW financial_income AS
    SELECT
        ts_code,
        ann_date,
        first_ann_date,
        COALESCE(first_ann_date, ann_date) AS effective_date,
        end_date,
        report_type,
        comp_type,
        total_revenue,
        revenue,
        total_cogs,
        operating_cost,
        selling_expense,
        admin_expense,
        rd_expense,
        finance_expense,
        operating_profit,
        total_profit,
        income_tax,
        net_profit,
        net_profit_attr_parent,
        ebit,
        ebitda
    FROM financial_income_raw
    """,
    """
    CREATE OR REPLACE VIEW financial_balance AS
    SELECT
        ts_code,
        ann_date,
        first_ann_date,
        COALESCE(first_ann_date, ann_date) AS effective_date,
        end_date,
        report_type,
        comp_type,
        total_share,
        cash_and_equivalents,
        accounts_receivable,
        inventories,
        current_assets,
        fixed_assets,
        construction_in_process,
        intangible_assets,
        goodwill,
        total_assets,
        short_term_borrowings,
        accounts_payable,
        current_liabilities,
        long_term_borrowings,
        bonds_payable,
        total_liabilities,
        total_equity,
        equity_attr_parent,
        minority_interest
    FROM financial_balance_raw
    """,
    """
    CREATE OR REPLACE VIEW financial_cashflow AS
    SELECT
        ts_code,
        ann_date,
        first_ann_date,
        COALESCE(first_ann_date, ann_date) AS effective_date,
        end_date,
        report_type,
        comp_type,
        cash_received_from_sales,
        total_operating_cash_inflow,
        cash_paid_for_goods,
        cash_paid_to_employees,
        taxes_paid,
        cf_from_operating,
        cash_paid_for_capex,
        cash_paid_for_investment,
        cf_from_investing,
        cash_received_from_borrowing,
        cash_paid_for_debt,
        cash_paid_for_dividend_interest,
        cf_from_financing,
        free_cashflow,
        net_increase_in_cash,
        cash_at_beginning,
        cash_at_end
    FROM financial_cashflow_raw
    """,
    """
    CREATE OR REPLACE VIEW financial_indicator AS
    SELECT
        ts_code,
        ann_date,
        ann_date AS effective_date,
        end_date,
        eps,
        dt_eps,
        bps,
        ocfps,
        cfps,
        gross_margin,
        netprofit_margin,
        grossprofit_margin,
        roe,
        roe_waa,
        roe_dt,
        roa,
        roic,
        debt_to_assets,
        current_ratio,
        quick_ratio,
        cash_ratio,
        ar_turn,
        ca_turn,
        fa_turn,
        assets_turn,
        netprofit_yoy,
        dt_netprofit_yoy,
        tr_yoy,
        or_yoy,
        rd_exp
    FROM financial_indicator_raw
    """,
    """
    CREATE OR REPLACE VIEW financial_event_forecast AS
    SELECT
        ts_code,
        record_key,
        ann_date,
        end_date,
        json_extract_string(payload_json, '$.type') AS forecast_type,
        TRY_CAST(json_extract_string(payload_json, '$.p_change_min') AS DOUBLE) AS p_change_min,
        TRY_CAST(json_extract_string(payload_json, '$.p_change_max') AS DOUBLE) AS p_change_max,
        TRY_CAST(json_extract_string(payload_json, '$.net_profit_min') AS DOUBLE) AS net_profit_min,
        TRY_CAST(json_extract_string(payload_json, '$.net_profit_max') AS DOUBLE) AS net_profit_max,
        TRY_CAST(json_extract_string(payload_json, '$.last_parent_net') AS DOUBLE) AS last_parent_net,
        json_extract_string(payload_json, '$.summary') AS summary,
        json_extract_string(payload_json, '$.change_reason') AS change_reason
    FROM financial_event_raw
    WHERE api_name = 'forecast'
    """,
    """
    CREATE OR REPLACE VIEW financial_event_audit AS
    SELECT
        ts_code,
        record_key,
        ann_date,
        end_date,
        json_extract_string(payload_json, '$.audit_result') AS audit_result,
        TRY_CAST(json_extract_string(payload_json, '$.audit_fees') AS DOUBLE) AS audit_fees,
        json_extract_string(payload_json, '$.audit_agency') AS audit_agency,
        json_extract_string(payload_json, '$.audit_sign') AS audit_sign
    FROM financial_event_raw
    WHERE api_name = 'fina_audit'
    """,
    """
    CREATE OR REPLACE VIEW financial_event_mainbz AS
    SELECT
        ts_code,
        record_key,
        end_date,
        json_extract_string(payload_json, '$.bz_item') AS bz_item,
        json_extract_string(payload_json, '$.bz_code') AS bz_code,
        TRY_CAST(json_extract_string(payload_json, '$.bz_sales') AS DOUBLE) AS bz_sales,
        TRY_CAST(json_extract_string(payload_json, '$.bz_profit') AS DOUBLE) AS bz_profit,
        TRY_CAST(json_extract_string(payload_json, '$.bz_cost') AS DOUBLE) AS bz_cost,
        json_extract_string(payload_json, '$.curr_type') AS curr_type
    FROM financial_event_raw
    WHERE api_name = 'fina_mainbz'
    """,
    """
    CREATE OR REPLACE VIEW financial_event_holdernumber AS
    SELECT
        ts_code,
        record_key,
        ann_date,
        end_date,
        TRY_CAST(json_extract_string(payload_json, '$.holder_num') AS BIGINT) AS holder_num
    FROM financial_event_raw
    WHERE api_name = 'stk_holdernumber'
    """,
    """
    CREATE OR REPLACE VIEW financial_event_top10_holders AS
    SELECT
        api_name,
        ts_code,
        record_key,
        ann_date,
        end_date,
        json_extract_string(payload_json, '$.holder_name') AS holder_name,
        TRY_CAST(json_extract_string(payload_json, '$.hold_amount') AS DOUBLE) AS hold_amount,
        TRY_CAST(json_extract_string(payload_json, '$.hold_ratio') AS DOUBLE) AS hold_ratio,
        TRY_CAST(json_extract_string(payload_json, '$.hold_float_ratio') AS DOUBLE) AS hold_float_ratio,
        TRY_CAST(json_extract_string(payload_json, '$.hold_change') AS DOUBLE) AS hold_change,
        json_extract_string(payload_json, '$.holder_type') AS holder_type
    FROM financial_event_raw
    WHERE api_name IN ('top10_holders', 'top10_floatholders')
    """,
    """
    CREATE OR REPLACE VIEW financial_event_pledge_detail AS
    SELECT
        ts_code,
        record_key,
        ann_date,
        json_extract_string(payload_json, '$.holder_name') AS holder_name,
        TRY_CAST(json_extract_string(payload_json, '$.pledge_amount') AS DOUBLE) AS pledge_amount,
        COALESCE(
            TRY_CAST(json_extract_string(payload_json, '$.start_date') AS DATE),
            TRY_STRPTIME(json_extract_string(payload_json, '$.start_date'), '%Y%m%d')::DATE
        ) AS start_date,
        COALESCE(
            TRY_CAST(json_extract_string(payload_json, '$.end_date') AS DATE),
            TRY_STRPTIME(json_extract_string(payload_json, '$.end_date'), '%Y%m%d')::DATE
        ) AS end_date,
        json_extract_string(payload_json, '$.is_release') AS is_release,
        json_extract_string(payload_json, '$.pledgor') AS pledgor,
        TRY_CAST(json_extract_string(payload_json, '$.holding_amount') AS DOUBLE) AS holding_amount,
        TRY_CAST(json_extract_string(payload_json, '$.pledged_amount') AS DOUBLE) AS pledged_amount,
        TRY_CAST(json_extract_string(payload_json, '$.p_total_ratio') AS DOUBLE) AS p_total_ratio,
        TRY_CAST(json_extract_string(payload_json, '$.h_total_ratio') AS DOUBLE) AS h_total_ratio,
        json_extract_string(payload_json, '$.is_buyback') AS is_buyback
    FROM financial_event_raw
    WHERE api_name = 'pledge_detail'
    """,
    """
    CREATE OR REPLACE VIEW financial_event_repurchase AS
    SELECT
        ts_code,
        record_key,
        ann_date,
        end_date,
        json_extract_string(payload_json, '$.proc') AS proc,
        TRY_CAST(json_extract_string(payload_json, '$.vol') AS DOUBLE) AS volume,
        TRY_CAST(json_extract_string(payload_json, '$.amount') AS DOUBLE) AS amount,
        TRY_CAST(json_extract_string(payload_json, '$.high_limit') AS DOUBLE) AS high_limit,
        TRY_CAST(json_extract_string(payload_json, '$.low_limit') AS DOUBLE) AS low_limit
    FROM financial_event_raw
    WHERE api_name = 'repurchase'
    """,
    """
    CREATE OR REPLACE VIEW financial_event_share_float AS
    SELECT
        ts_code,
        record_key,
        ann_date,
        COALESCE(
            TRY_CAST(json_extract_string(payload_json, '$.float_date') AS DATE),
            TRY_STRPTIME(json_extract_string(payload_json, '$.float_date'), '%Y%m%d')::DATE
        ) AS float_date,
        TRY_CAST(json_extract_string(payload_json, '$.float_share') AS DOUBLE) AS float_share,
        TRY_CAST(json_extract_string(payload_json, '$.float_ratio') AS DOUBLE) AS float_ratio,
        json_extract_string(payload_json, '$.holder_name') AS holder_name,
        json_extract_string(payload_json, '$.share_type') AS share_type
    FROM financial_event_raw
    WHERE api_name = 'share_float'
    """,
    """
    CREATE OR REPLACE VIEW financial_dividend AS
    SELECT
        ts_code,
        end_date,
        ann_date,
        record_key,
        div_proc,
        stk_div,
        stk_bo_rate,
        stk_co_rate,
        cash_div,
        cash_div_tax,
        record_date,
        ex_date,
        pay_date,
        div_listdate
    FROM financial_dividend_raw
    """,
    """
    CREATE OR REPLACE VIEW financial_pledge_stat AS
    SELECT
        ts_code,
        end_date,
        pledge_count,
        unrest_pledge,
        rest_pledge,
        total_share,
        pledge_ratio
    FROM pledge_stat
    """,
    """
    CREATE OR REPLACE VIEW stock_features_core AS
    SELECT
        ds.*,
        pt.rsi_14,
        vl.volume_ma_20,
        rm.ret_20,
        vr.hv_60,
        tc.limit_up_days_5,
        vs.pe_ttm_pct_5y,
        fa.latest_report_end_date,
        fq.roe_asof,
        fg.revenue_yoy_asof,
        cf.main_flow_ma_20,
        sc.sector_ret_20,
        im.market_up_ratio,
        xs.ret_20_rank_all
    FROM derived_daily_spine ds
    LEFT JOIN derived_price_technical pt ON ds.ts_code = pt.ts_code AND ds.trade_date = pt.trade_date
    LEFT JOIN derived_volume_liquidity vl ON ds.ts_code = vl.ts_code AND ds.trade_date = vl.trade_date
    LEFT JOIN derived_return_momentum rm ON ds.ts_code = rm.ts_code AND ds.trade_date = rm.trade_date
    LEFT JOIN derived_volatility_risk vr ON ds.ts_code = vr.ts_code AND ds.trade_date = vr.trade_date
    LEFT JOIN derived_trading_constraint tc ON ds.ts_code = tc.ts_code AND ds.trade_date = tc.trade_date
    LEFT JOIN derived_valuation_size vs ON ds.ts_code = vs.ts_code AND ds.trade_date = vs.trade_date
    LEFT JOIN derived_financial_asof fa ON ds.ts_code = fa.ts_code AND ds.trade_date = fa.trade_date
    LEFT JOIN derived_financial_quality fq ON ds.ts_code = fq.ts_code AND ds.trade_date = fq.trade_date
    LEFT JOIN derived_financial_growth fg ON ds.ts_code = fg.ts_code AND ds.trade_date = fg.trade_date
    LEFT JOIN derived_capital_flow cf ON ds.ts_code = cf.ts_code AND ds.trade_date = cf.trade_date
    LEFT JOIN derived_sector_concept_context sc ON ds.ts_code = sc.ts_code AND ds.trade_date = sc.trade_date
    LEFT JOIN derived_index_market_context im ON ds.ts_code = im.ts_code AND ds.trade_date = im.trade_date
    LEFT JOIN derived_cross_sectional xs ON ds.ts_code = xs.ts_code AND ds.trade_date = xs.trade_date
    """,
    """
    CREATE OR REPLACE VIEW stock_features_plus AS
    SELECT
        c.*,
        ca.cash_dividend_ttm,
        og.pledge_ratio_asof,
        cs.value_quality_score
    FROM stock_features_core c
    LEFT JOIN derived_corporate_action ca ON c.ts_code = ca.ts_code AND c.trade_date = ca.trade_date
    LEFT JOIN derived_ownership_governance og ON c.ts_code = og.ts_code AND c.trade_date = og.trade_date
    LEFT JOIN derived_composite_state cs ON c.ts_code = cs.ts_code AND c.trade_date = cs.trade_date
    """,
    """
    CREATE OR REPLACE VIEW stock_features_full AS
    SELECT
        p.*,
        b.symbol,
        b.name,
        b.market,
        b.exchange,
        b.list_status,
        b.open AS raw_open,
        b.high AS raw_high,
        b.low AS raw_low,
        b.close AS raw_close,
        b.pct_chg AS raw_pct_chg,
        b.volume AS raw_volume,
        b.amount AS raw_amount,
        b.turnover_rate,
        b.turnover_rate_free,
        b.pe_ttm AS base_pe_ttm,
        b.pb AS base_pb,
        b.ps_ttm AS base_ps_ttm,
        b.total_mv,
        b.circ_mv,
        b.up_limit,
        b.down_limit,
        b.net_mf_amount,
        b.margin_balance,
        b.northbound_hold_shares,
        b.northbound_hold_ratio
    FROM stock_features_plus p
    LEFT JOIN stock_base_daily_enriched b
      ON p.ts_code = b.ts_code
     AND p.trade_date = b.trade_date
    """,
]


def create_views(con: duckdb.DuckDBPyConnection | None = None) -> None:
    close = con is None
    con = con or connect()
    try:
        for sql in VIEW_SQL:
            con.execute(sql)
    finally:
        if close:
            con.close()
