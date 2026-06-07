from __future__ import annotations

import duckdb

from .database import connect
from .schema import quote_ident


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
        business_tax_surcharge,
        selling_expense,
        admin_expense,
        rd_expense,
        finance_expense,
        operating_expense,
        asset_impairment_loss,
        investment_income,
        associate_investment_income,
        fair_value_change_income,
        foreign_exchange_gain,
        operating_profit,
        non_operating_income,
        non_operating_expense,
        total_profit,
        income_tax,
        net_profit,
        net_profit_attr_parent,
        minority_profit,
        continued_net_profit,
        total_comprehensive_income,
        comprehensive_income_parent,
        comprehensive_income_minority,
        basic_eps,
        diluted_eps,
        ebit,
        ebitda,
        interest_income,
        interest_expense,
        commission_income,
        commission_expense,
        premium_income,
        premium_earned,
        insurance_expense,
        compensation_payout,
        undistributed_profit
    FROM financial_income_raw
    """,
    """
    CREATE OR REPLACE VIEW financial_income_statement AS
    SELECT * EXCLUDE (payload_json, updated_at)
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
        trading_financial_assets,
        derivative_financial_assets,
        notes_receivable,
        accounts_receivable,
        accounts_receivable_bill,
        prepayment,
        other_receivable,
        total_other_receivable,
        inventories,
        contract_assets,
        other_current_assets,
        current_assets,
        total_noncurrent_assets,
        long_term_equity_investment,
        investment_property,
        fixed_assets,
        fixed_assets_total,
        construction_in_process,
        construction_in_process_total,
        right_of_use_assets,
        intangible_assets,
        development_expenditure,
        goodwill,
        long_term_deferred_expense,
        deferred_tax_assets,
        other_noncurrent_assets,
        total_assets,
        short_term_borrowings,
        notes_payable,
        accounts_payable,
        advance_receipts,
        contract_liabilities,
        payroll_payable,
        taxes_payable,
        interest_payable,
        dividend_payable,
        other_payable,
        total_other_payable,
        noncurrent_liability_due_1y,
        other_current_liabilities,
        current_liabilities,
        total_noncurrent_liabilities,
        long_term_borrowings,
        bonds_payable,
        long_term_payable,
        estimated_liabilities,
        deferred_income,
        deferred_tax_liabilities,
        other_noncurrent_liabilities,
        total_liabilities,
        total_liabilities_and_equity,
        capital_reserve,
        surplus_reserve,
        undistributed_profit,
        treasury_share,
        other_comprehensive_income,
        special_reserve,
        total_equity,
        equity_attr_parent,
        minority_interest
    FROM financial_balance_raw
    """,
    """
    CREATE OR REPLACE VIEW financial_balance_sheet AS
    SELECT * EXCLUDE (payload_json, updated_at)
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
        tax_refund_received,
        other_operating_cash_received,
        total_operating_cash_inflow,
        cash_paid_for_goods,
        cash_paid_to_employees,
        taxes_paid,
        other_operating_cash_paid,
        total_operating_cash_outflow,
        cf_from_operating,
        cash_received_from_investment_withdrawal,
        cash_received_from_asset_disposal,
        cash_received_from_subsidiary_disposal,
        total_investing_cash_inflow,
        cash_paid_for_capex,
        cash_paid_for_investment,
        cash_paid_for_subsidiary_acquisition,
        other_investing_cash_paid,
        total_investing_cash_outflow,
        cf_from_investing,
        cash_received_from_investors,
        cash_received_from_borrowing,
        cash_received_from_bond_issue,
        other_financing_cash_received,
        total_financing_cash_inflow,
        cash_paid_for_debt,
        cash_paid_for_dividend_interest,
        other_financing_cash_paid,
        total_financing_cash_outflow,
        cf_from_financing,
        fx_effect_on_cash,
        free_cashflow,
        net_increase_in_cash,
        cash_at_beginning,
        cash_at_end,
        begin_cash_balance,
        end_cash_balance,
        net_profit_indirect,
        asset_depreciation,
        intangible_asset_amortization,
        deferred_expense_amortization,
        financial_expense_indirect,
        investment_loss_indirect,
        credit_impairment_loss_indirect,
        inventory_decrease,
        operating_receivable_decrease,
        operating_payable_increase
    FROM financial_cashflow_raw
    """,
    """
    CREATE OR REPLACE VIEW financial_cashflow_statement AS
    SELECT * EXCLUDE (payload_json, updated_at)
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
    CREATE OR REPLACE VIEW financial_indicator_statement AS
    SELECT * EXCLUDE (payload_json, updated_at)
    FROM financial_indicator_raw
    """,
    """
    CREATE OR REPLACE VIEW financial_statement_latest AS
    WITH versions AS (
        SELECT 'income' AS statement_type, ts_code, end_date, report_type, comp_type, ann_date, first_ann_date, effective_date
        FROM financial_income_raw
        UNION ALL
        SELECT 'balance' AS statement_type, ts_code, end_date, report_type, comp_type, ann_date, first_ann_date, effective_date
        FROM financial_balance_raw
        UNION ALL
        SELECT 'cashflow' AS statement_type, ts_code, end_date, report_type, comp_type, ann_date, first_ann_date, effective_date
        FROM financial_cashflow_raw
        UNION ALL
        SELECT 'indicator' AS statement_type, ts_code, end_date, NULL AS report_type, NULL AS comp_type, ann_date, NULL AS first_ann_date, effective_date
        FROM financial_indicator_raw
    )
    SELECT *
    FROM versions
    QUALIFY row_number() OVER (
        PARTITION BY statement_type, ts_code, end_date
        ORDER BY effective_date DESC NULLS LAST, ann_date DESC NULLS LAST
    ) = 1
    """,
    """
    CREATE OR REPLACE VIEW financial_indicator_asof AS
    SELECT
        d.ts_code,
        d.trade_date,
        fi.end_date AS latest_report_end_date,
        fi.effective_date AS latest_financial_effective_date,
        fi.ann_date AS latest_financial_ann_date,
        fi.eps,
        fi.dt_eps,
        fi.bps,
        fi.ocfps,
        fi.cfps,
        fi.gross_margin,
        fi.netprofit_margin,
        fi.grossprofit_margin,
        fi.roe,
        fi.roe_waa,
        fi.roe_dt,
        fi.roa,
        fi.roic,
        fi.debt_to_assets,
        fi.current_ratio,
        fi.quick_ratio,
        fi.cash_ratio,
        fi.assets_turn,
        fi.netprofit_yoy,
        fi.dt_netprofit_yoy,
        fi.tr_yoy,
        fi.or_yoy,
        fi.rd_exp
    FROM (
        SELECT ts_code, trade_date FROM stock_daily
    ) d
    ASOF LEFT JOIN (
        SELECT *
        FROM financial_indicator
        WHERE effective_date IS NOT NULL
        ORDER BY ts_code, effective_date
    ) fi
      ON d.ts_code = fi.ts_code
     AND d.trade_date >= fi.effective_date
    """,
    """
    CREATE OR REPLACE VIEW financial_statement_asof AS
    SELECT * FROM financial_indicator_asof
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
    CREATE OR REPLACE VIEW financial_forecast AS
    SELECT * FROM financial_event_forecast
    """,
    """
    CREATE OR REPLACE VIEW financial_express AS
    SELECT
        ts_code,
        record_key,
        ann_date,
        end_date,
        TRY_CAST(json_extract_string(payload_json, '$.revenue') AS DOUBLE) AS revenue,
        TRY_CAST(json_extract_string(payload_json, '$.operate_profit') AS DOUBLE) AS operating_profit,
        TRY_CAST(json_extract_string(payload_json, '$.total_profit') AS DOUBLE) AS total_profit,
        TRY_CAST(json_extract_string(payload_json, '$.n_income') AS DOUBLE) AS net_profit,
        TRY_CAST(json_extract_string(payload_json, '$.total_assets') AS DOUBLE) AS total_assets,
        TRY_CAST(json_extract_string(payload_json, '$.total_hldr_eqy_exc_min_int') AS DOUBLE) AS equity_attr_parent,
        TRY_CAST(json_extract_string(payload_json, '$.diluted_eps') AS DOUBLE) AS diluted_eps,
        TRY_CAST(json_extract_string(payload_json, '$.diluted_roe') AS DOUBLE) AS diluted_roe,
        TRY_CAST(json_extract_string(payload_json, '$.yoy_net_profit') AS DOUBLE) AS yoy_net_profit,
        json_extract_string(payload_json, '$.perf_summary') AS performance_summary
    FROM financial_event_raw
    WHERE api_name = 'express'
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
    CREATE OR REPLACE VIEW financial_audit_opinion AS
    SELECT * FROM financial_event_audit
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
    CREATE OR REPLACE VIEW financial_main_business AS
    SELECT * FROM financial_event_mainbz
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
    CREATE OR REPLACE VIEW financial_holder_number AS
    SELECT * FROM financial_event_holdernumber
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
    CREATE OR REPLACE VIEW financial_top10_holders AS
    SELECT * EXCLUDE (api_name)
    FROM financial_event_top10_holders
    WHERE api_name = 'top10_holders'
    """,
    """
    CREATE OR REPLACE VIEW financial_top10_float_holders AS
    SELECT * EXCLUDE (api_name)
    FROM financial_event_top10_holders
    WHERE api_name = 'top10_floatholders'
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
    CREATE OR REPLACE VIEW financial_pledge_detail AS
    SELECT * FROM financial_event_pledge_detail
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
    CREATE OR REPLACE VIEW financial_repurchase AS
    SELECT * FROM financial_event_repurchase
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
    CREATE OR REPLACE VIEW financial_share_float AS
    SELECT * FROM financial_event_share_float
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
        pt.ma_20_hfq,
        pt.ma_60_hfq,
        pt.ma_120_hfq,
        pt.close_to_ma_20_hfq,
        pt.close_to_ma_60_hfq,
        pt.rsi_14,
        pt.price_position_20_hfq,
        vl.volume_ma_20,
        vl.amount_ma_20,
        vl.turnover_rate_ma_20,
        vl.amihud_20,
        rm.ret_20_hfq,
        rm.ret_60_hfq,
        rm.ret_250_hfq,
        rm.momentum_60_20_hfq,
        rm.reversal_5_hfq,
        rm.up_days_20,
        vr.hv_60,
        vr.max_drawdown_60_hfq,
        vr.downside_vol_60,
        tc.limit_up_days_5,
        tc.limit_up_days_20,
        tc.limit_down_days_20,
        tc.consecutive_limit_up_days,
        tc.tradable_state,
        vs.pe_ttm,
        vs.pb,
        vs.total_mv,
        vs.circ_mv,
        vs.free_float_mv,
        vs.pe_ttm_pct_5y,
        vs.pb_pct_5y,
        vs.log_total_mv,
        fa.latest_report_end_date,
        fa.latest_financial_ann_date,
        fa.report_age_days,
        fa.statement_available_count,
        fq.roe_asof,
        fq.roa_asof,
        fq.gross_margin_asof,
        fq.netprofit_margin_asof,
        fq.ocf_to_profit_asof,
        fq.debt_to_assets_asof,
        fg.revenue_yoy_asof,
        fg.netprofit_yoy_asof,
        fg.q_revenue_yoy_asof,
        fg.q_netprofit_yoy_asof,
        cf.main_net_amount,
        cf.main_flow_sum_20,
        sc.sw_l1_ret_20,
        sc.stock_excess_sw_l1_20,
        sc.sw_l1_code,
        sc.sw_l1_name,
        sc.sw_l2_code,
        sc.sw_l2_name,
        sc.concept_count,
        sc.concept_names_all,
        im.market_up_ratio,
        im.market_amount,
        im.primary_index_name,
        xs.ret_20_hfq_rank_all_desc,
        xs.ret_20_hfq_pct_all_desc,
        xs.log_total_mv_pct_all_desc,
        xs.value_exposure_z,
        xs.quality_exposure_z,
        xs.growth_exposure_z,
        xs.momentum_exposure_z,
        xs.volatility_exposure_z,
        xs.liquidity_exposure_z,
        xs.flow_exposure_z
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
        ca.corp_action_available_flag,
        ca.latest_corp_action_date,
        ca.cash_dividend_ttm,
        ca.has_forecast_asof AS corp_has_forecast_asof,
        ca.forecast_type_latest,
        ca.has_express_asof AS corp_has_express_asof,
        ca.repurchase_amount_365d,
        ca.next_share_float_ratio_90d,
        og.ownership_available_flag,
        og.latest_ownership_event_date,
        og.pledge_ratio_asof,
        og.holder_num_asof,
        og.holder_num_chg_rate_1report,
        og.top10_holder_ratio_latest,
        og.top10_float_holder_ratio_latest,
        cs.composite_available_flag,
        cs.module_available_count,
        cs.module_available_ratio,
        cs.state_condition_count,
        cs.trend_state,
        cs.valuation_percentile_state,
        cs.financial_staleness_state,
        cs.main_flow_persist_state,
        cs.sector_relative_return_state,
        cs.concept_heat_state,
        cs.dividend_recent_state,
        cs.pledge_ratio_state,
        cs.value_quality_pair_state,
        cs.momentum_flow_pair_state,
        cs.growth_quality_pair_state,
        cs.risk_liquidity_pair_state,
        cs.multi_domain_condition_count
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
        b.market AS security_market,
        b.exchange AS security_exchange,
        b.list_status,
        b.open_qfq_current,
        b.high_qfq_current,
        b.low_qfq_current,
        b.close_qfq_current,
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
        b.pe AS base_pe,
        b.pb AS base_pb,
        b.ps AS base_ps,
        b.ps_ttm AS base_ps_ttm,
        b.total_mv,
        b.circ_mv,
        b.free_share,
        b.up_limit AS base_up_limit,
        b.down_limit AS base_down_limit,
        b.net_mf_amount,
        b.main_net_inflow,
        b.margin_balance,
        b.short_balance,
        b.northbound_hold_shares,
        b.northbound_hold_ratio
    FROM stock_features_plus p
    LEFT JOIN stock_base_daily_enriched b
      ON p.ts_code = b.ts_code
     AND p.trade_date = b.trade_date
    """,
]


FEATURE_MODULES = {
    "pt": ("derived_price_technical", "price"),
    "vl": ("derived_volume_liquidity", "liquidity"),
    "rm": ("derived_return_momentum", "momentum"),
    "vr": ("derived_volatility_risk", "risk"),
    "tc": ("derived_trading_constraint", "constraint"),
    "vs": ("derived_valuation_size", "valuation"),
    "fa": ("derived_financial_asof", "fin_asof"),
    "fq": ("derived_financial_quality", "fin_quality"),
    "fg": ("derived_financial_growth", "fin_growth"),
    "cf": ("derived_capital_flow", "capital"),
    "sc": ("derived_sector_concept_context", "sector"),
    "im": ("derived_index_market_context", "index"),
    "xs": ("derived_cross_sectional", "cross"),
    "ca": ("derived_corporate_action", "corp"),
    "og": ("derived_ownership_governance", "owner"),
    "cs": ("derived_composite_state", "state"),
}

FEATURE_KEYS = {"ts_code", "trade_date"}
FEATURE_SKIP = {"updated_at"}

CORE_ALL_MODULE_ALIASES = ["pt", "vl", "rm", "vr", "tc", "vs", "fa"]
PLUS_ALL_MODULE_ALIASES = ["fq", "fg", "cf", "sc", "im", "ca", "og", "cs"]
FULL_ALL_MODULE_ALIASES = ["pt", "vl", "rm", "vr", "tc", "vs", "fa", "fq", "fg", "cf", "sc", "im", "xs", "ca", "og", "cs"]

CORE_SELECTED_COLUMNS = {
    "fq": {
        "roe_asof",
        "roe_waa_asof",
        "roe_dt_asof",
        "roa_asof",
        "roic_asof",
        "gross_margin_asof",
        "grossprofit_margin_asof",
        "netprofit_margin_asof",
        "operating_profit_margin_asof",
        "ocf_to_profit_asof",
        "ocf_to_revenue_asof",
        "free_cashflow_to_revenue_asof",
        "cash_to_assets_asof",
        "goodwill_to_assets_asof",
        "working_capital_to_assets_asof",
        "debt_to_assets_asof",
        "interestdebt_to_assets_asof",
        "netdebt_to_assets_asof",
        "current_ratio_asof",
        "quick_ratio_asof",
        "assets_turn_asof",
        "revenue_to_assets_asof",
    },
    "fg": {
        "current_report_end_date",
        "prev_report_end_date",
        "same_period_1y_end_date",
        "revenue_yoy_asof",
        "total_revenue_yoy_asof",
        "netprofit_yoy_asof",
        "deducted_netprofit_yoy_asof",
        "ocf_yoy_asof",
        "eps_yoy_asof",
        "roe_yoy_asof",
        "assets_yoy_asof",
        "equity_yoy_asof",
        "q_revenue_yoy_asof",
        "q_revenue_qoq_asof",
        "q_operating_profit_yoy_asof",
        "q_operating_profit_qoq_asof",
        "q_netprofit_yoy_asof",
        "q_netprofit_qoq_asof",
        "revenue_cagr_2y_asof",
        "revenue_cagr_3y_asof",
        "net_profit_cagr_2y_asof",
        "net_profit_cagr_3y_asof",
    },
    "cf": {
        "small_net_amount",
        "medium_net_amount",
        "large_net_amount",
        "extra_large_net_amount",
        "main_net_amount",
        "retail_net_amount",
        "net_mf_amount",
        "main_net_amount_rate",
        "large_net_amount_rate",
        "extra_large_net_amount_rate",
        "main_flow_ma_5",
        "main_flow_ma_20",
        "main_flow_ma_60",
        "main_flow_sum_5",
        "main_flow_sum_20",
        "main_flow_sum_60",
        "main_flow_positive_days_20",
        "main_flow_persist_ratio_20",
        "main_flow_to_total_mv_20",
        "main_flow_to_circ_mv_20",
        "margin_balance",
        "short_balance",
        "margin_balance_chg_20",
        "margin_buy_to_amount",
        "north_hold_shares",
        "north_hold_ratio",
        "north_hold_shares_chg_20",
        "north_hold_ratio_chg_20",
        "has_moneyflow",
        "has_margin",
        "has_north_holding",
    },
    "sc": {
        "sw_l1_code",
        "sw_l1_name",
        "sw_l2_code",
        "sw_l2_name",
        "has_sw_industry",
        "industry_member_days",
        "sw_l1_ret_20",
        "stock_excess_sw_l1_20",
        "sw_l1_ret_rank_all_20",
        "sw_l1_ret_pct_all_20",
        "sw_l2_ret_20",
        "stock_excess_sw_l2_20",
        "sw_l2_ret_rank_all_20",
        "sw_l2_ret_pct_all_20",
        "sw_l1_ret_60",
        "stock_excess_sw_l1_60",
        "sw_l2_ret_60",
        "stock_excess_sw_l2_60",
        "stock_ret_rank_industry_20",
        "stock_ret_pct_industry_20",
        "stock_mv_pct_industry",
        "concept_count",
        "concept_ids_all",
        "concept_names_all",
        "concept_broad_count",
        "concept_narrow_count",
        "concept_ids_top_20",
        "concept_names_top_20",
        "concept_ids_top_negative_20",
        "concept_names_top_negative_20",
    },
    "im": {
        "is_hs300_member",
        "hs300_weight",
        "is_zz500_member",
        "zz500_weight",
        "is_zz1000_member",
        "zz1000_weight",
        "is_sse50_member",
        "sse50_weight",
        "index_member_count",
        "primary_index_code",
        "primary_index_name",
        "has_index_weight",
        "market_stock_count",
        "market_up_ratio",
        "market_down_ratio",
        "market_limit_up_ratio",
        "market_limit_down_ratio",
        "market_amount",
        "market_amount_ma_20",
        "market_up_ratio_ma_20",
        "hs300_ret_20",
        "zz500_ret_20",
        "zz1000_ret_20",
        "primary_index_ret_20",
        "stock_excess_hs300_20",
        "stock_excess_zz500_20",
        "stock_excess_primary_index_20",
        "large_vs_small_ret_20",
        "growth_vs_broad_ret_20",
    },
    "xs": {
        "xs_universe_flag",
        "xs_sample_all_count",
        "xs_core_available_count",
        "xs_core_available_ratio",
        "ret_20_hfq_rank_all_desc",
        "ret_20_hfq_pct_all_desc",
        "ret_60_hfq_rank_all_desc",
        "ret_60_hfq_pct_all_desc",
        "ret_120_hfq_rank_all_desc",
        "ret_120_hfq_pct_all_desc",
        "ret_250_hfq_rank_all_desc",
        "ret_250_hfq_pct_all_desc",
        "log_total_mv_pct_all_desc",
        "pe_ttm_pct_all_asc",
        "pb_pct_all_asc",
        "turnover_rate_ma_20_pct_all_desc",
        "amihud_20_pct_all_asc",
        "value_exposure_z",
        "quality_exposure_z",
        "growth_exposure_z",
        "momentum_exposure_z",
        "volatility_exposure_z",
        "liquidity_exposure_z",
        "flow_exposure_z",
    },
}


def _table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
    return [row[1] for row in con.execute(f"PRAGMA table_info({quote_ident(table_name)})").fetchall()]


def _qualified_select_expr(alias: str, column: str, output_name: str) -> str:
    return f"{alias}.{quote_ident(column)} AS {quote_ident(output_name)}"


def _unique_output_name(name: str, selected: set[str], prefix: str) -> str:
    if name not in selected:
        return name
    candidate = f"{prefix}_{name}"
    counter = 2
    while candidate in selected:
        candidate = f"{prefix}_{counter}_{name}"
        counter += 1
    return candidate


def _module_select_exprs(
    con: duckdb.DuckDBPyConnection,
    *,
    module_alias: str,
    selected: set[str],
    include_columns: set[str] | None = None,
) -> list[str]:
    table_name, prefix = FEATURE_MODULES[module_alias]
    exprs = []
    for column in _table_columns(con, table_name):
        if column in FEATURE_KEYS or column in FEATURE_SKIP:
            continue
        if "score" in column.lower():
            continue
        if include_columns is not None and column not in include_columns:
            continue
        output_name = _unique_output_name(column, selected, prefix)
        selected.add(output_name)
        exprs.append(_qualified_select_expr(module_alias, column, output_name))
    return exprs


def _feature_joins(module_aliases: list[str]) -> str:
    joins = []
    for module_alias in module_aliases:
        table_name, _ = FEATURE_MODULES[module_alias]
        joins.append(
            f"""
            LEFT JOIN {quote_ident(table_name)} {module_alias}
              ON ds.ts_code = {module_alias}.ts_code
             AND ds.trade_date = {module_alias}.trade_date
            """
        )
    return "\n".join(joins)


def _create_stock_features_core(con: duckdb.DuckDBPyConnection) -> None:
    selected = set(_table_columns(con, "derived_daily_spine"))
    exprs = ["ds.*"]
    for module_alias in CORE_ALL_MODULE_ALIASES:
        exprs.extend(_module_select_exprs(con, module_alias=module_alias, selected=selected))
    for module_alias, columns in CORE_SELECTED_COLUMNS.items():
        exprs.extend(_module_select_exprs(con, module_alias=module_alias, selected=selected, include_columns=columns))
    joins = _feature_joins([*CORE_ALL_MODULE_ALIASES, *CORE_SELECTED_COLUMNS.keys()])
    con.execute(
        f"""
        CREATE OR REPLACE VIEW stock_features_core AS
        SELECT
            {",\n            ".join(exprs)}
        FROM derived_daily_spine ds
        {joins}
        """
    )


def _create_stock_features_plus(con: duckdb.DuckDBPyConnection) -> None:
    selected = set(_table_columns(con, "stock_features_core"))
    exprs = ["c.*"]
    for module_alias in PLUS_ALL_MODULE_ALIASES:
        exprs.extend(_module_select_exprs(con, module_alias=module_alias, selected=selected))
    joins = []
    for module_alias in PLUS_ALL_MODULE_ALIASES:
        table_name, _ = FEATURE_MODULES[module_alias]
        joins.append(
            f"""
            LEFT JOIN {quote_ident(table_name)} {module_alias}
              ON c.ts_code = {module_alias}.ts_code
             AND c.trade_date = {module_alias}.trade_date
            """
        )
    con.execute(
        f"""
        CREATE OR REPLACE VIEW stock_features_plus AS
        SELECT
            {",\n            ".join(exprs)}
        FROM stock_features_core c
        {"".join(joins)}
        """
    )


def _create_stock_features_full(con: duckdb.DuckDBPyConnection) -> None:
    selected = set(_table_columns(con, "stock_features_plus"))
    exprs = ["p.*"]
    for column in _table_columns(con, "stock_base_daily_enriched"):
        if column in FEATURE_KEYS or column in FEATURE_SKIP:
            continue
        output_name = _unique_output_name(column, selected, "base")
        selected.add(output_name)
        exprs.append(_qualified_select_expr("b", column, output_name))
    for module_alias in ["xs"]:
        exprs.extend(_module_select_exprs(con, module_alias=module_alias, selected=selected))
    joins = []
    for module_alias in ["xs"]:
        table_name, _ = FEATURE_MODULES[module_alias]
        joins.append(
            f"""
            LEFT JOIN {quote_ident(table_name)} {module_alias}
              ON p.ts_code = {module_alias}.ts_code
             AND p.trade_date = {module_alias}.trade_date
            """
        )
    con.execute(
        f"""
        CREATE OR REPLACE VIEW stock_features_full AS
        SELECT
            {",\n            ".join(exprs)}
        FROM stock_features_plus p
        LEFT JOIN stock_base_daily_enriched b
          ON p.ts_code = b.ts_code
         AND p.trade_date = b.trade_date
        {"".join(joins)}
        """
    )


def _create_expanded_feature_views(con: duckdb.DuckDBPyConnection) -> None:
    _create_stock_features_core(con)
    _create_stock_features_plus(con)
    _create_stock_features_full(con)


def create_views(con: duckdb.DuckDBPyConnection | None = None) -> None:
    close = con is None
    con = con or connect()
    try:
        for sql in VIEW_SQL:
            con.execute(sql)
        _create_expanded_feature_views(con)
    finally:
        if close:
            con.close()
