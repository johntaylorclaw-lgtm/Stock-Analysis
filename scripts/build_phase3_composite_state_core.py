from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
REPORT_PATH = ROOT / "reports" / "phase3_composite_state_core_run.jsonl"
TABLE_NAME = "derived_composite_state"
MODULE_COUNT = 15
CONDITION_COUNT = 33


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_fields() -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return [field["name"] for item in schema["tables"] if item["name"] == TABLE_NAME for field in item["fields"]]


def pct_state(expr: str) -> str:
    return f"CASE WHEN {expr} IS NULL THEN 'unknown' WHEN {expr} < 0.2 THEN 'low' WHEN {expr} > 0.8 THEN 'high' ELSE 'mid' END"


def z_state(expr: str) -> str:
    return f"CASE WHEN {expr} IS NULL THEN 'unknown' WHEN {expr} <= -1 THEN 'low' WHEN {expr} >= 1 THEN 'high' ELSE 'mid' END"


def bool_int(expr: str) -> str:
    return f"CASE WHEN {expr} THEN 1 ELSE 0 END"


def non_null_int(expr: str) -> str:
    return f"CASE WHEN {expr} IS NOT NULL THEN 1 ELSE 0 END"


def build_insert_sql(start: str, end: str) -> str:
    fields = table_fields()
    column_list = ", ".join(q(name) for name in fields)
    select_list = ",\n        ".join(q(name) for name in fields)

    module_flags = [
        ("price_technical", "price_technical_available_flag"),
        ("volume_liquidity", "volume_liquidity_available_flag"),
        ("return_momentum", "return_momentum_available_flag"),
        ("volatility_risk", "volatility_risk_available_flag"),
        ("trading_constraint", "trading_constraint_available_flag"),
        ("valuation_size", "valuation_size_available_flag"),
        ("financial_asof", "financial_asof_available_flag"),
        ("financial_quality", "financial_quality_available_flag"),
        ("financial_growth", "financial_growth_available_flag"),
        ("capital_flow", "capital_flow_source_available_flag"),
        ("sector_concept", "sector_source_available_flag"),
        ("index_market", "index_market_available_flag"),
        ("cross_sectional", "cross_sectional_available_flag"),
        ("corporate_action", "corp_action_source_available_flag"),
        ("ownership_governance", "ownership_source_available_flag"),
    ]
    module_available = " + ".join(bool_int(expr) for _, expr in module_flags)
    missing_modules = " || ".join(
        f"CASE WHEN {expr} THEN '' ELSE '{name};' END" for name, expr in module_flags
    )

    condition_exprs = [
        "price_above_ma20_flag",
        "price_above_ma60_flag",
        "ma20_above_ma60_flag",
        "ma60_above_ma120_flag",
        "ret_20_positive_flag",
        "ret_60_positive_flag",
        "ret_250_positive_flag",
        "momentum_spread_positive_flag",
        "liquidity_available_flag",
        "pe_ttm_valid_flag",
        "pb_valid_flag",
        "has_complete_statement_set_asof",
        "profitability_positive_flag",
        "cashflow_profit_match_flag",
        "growth_revenue_positive_flag",
        "growth_profit_positive_flag",
        "capital_flow_available_flag",
        "main_flow_20_positive_flag",
        "top_list_recent_flag",
        "sector_context_available_flag",
        "corp_action_available_flag",
        "repurchase_recent_flag",
        "ownership_available_flag",
        "pledge_ratio_ge_10_flag",
        "pledge_ratio_ge_30_flag",
        "pledge_ratio_ge_50_flag",
        "size_exposure_z IS NOT NULL",
        "value_exposure_z IS NOT NULL",
        "momentum_exposure_z IS NOT NULL",
        "quality_exposure_z IS NOT NULL",
        "growth_exposure_z IS NOT NULL",
        "flow_exposure_z IS NOT NULL",
        "volatility_exposure_z IS NOT NULL",
    ]
    condition_count = " + ".join(bool_int(expr) for expr in condition_exprs)
    condition_available_count = " + ".join(non_null_int(expr) for expr in condition_exprs)
    exposure_count = " + ".join(non_null_int(name) for name in [
        "size_exposure_z",
        "value_exposure_z",
        "momentum_exposure_z",
        "reversal_exposure_z",
        "volatility_exposure_z",
        "liquidity_exposure_z",
        "quality_exposure_z",
        "growth_exposure_z",
        "flow_exposure_z",
    ])

    return f"""
    INSERT INTO {q(TABLE_NAME)} ({column_list})
    WITH joined AS (
        SELECT
            ds.ts_code,
            ds.trade_date,
            ds.is_listed_asof,
            ds.list_status_asof,
            ds.market,
            ds.exchange,
            ds.days_since_list,
            ds.has_price,
            ds.price_valid_flag,
            ds.limit_up_flag,
            ds.limit_down_flag,
            ds.close_hfq,
            pt.ts_code IS NOT NULL AS price_technical_available_flag,
            pt.ma_20_hfq,
            pt.ma_60_hfq,
            pt.ma_120_hfq,
            vl.ts_code IS NOT NULL AS volume_liquidity_available_flag,
            rm.ts_code IS NOT NULL AS return_momentum_available_flag,
            vr.ts_code IS NOT NULL AS volatility_risk_available_flag,
            tc.ts_code IS NOT NULL AS trading_constraint_available_flag,
            tc.tradable_state AS tc_tradable_state,
            tc.one_price_limit_up_flag,
            tc.one_price_limit_down_flag,
            tc.limit_up_days_20,
            tc.limit_down_days_20,
            rm.ret_20_hfq,
            rm.ret_60_hfq,
            rm.ret_250_hfq,
            rm.momentum_60_20_hfq,
            vs.pe_ttm_valid_flag,
            vs.ts_code IS NOT NULL AS valuation_size_available_flag,
            vs.pb_valid_flag,
            vs.pe_ttm_pct_5y,
            vs.pb_pct_5y,
            vs.ps_ttm_pct_5y,
            fa.latest_report_end_date,
            fa.latest_report_end_date IS NOT NULL AS financial_asof_available_flag,
            fa.latest_financial_effective_date,
            fa.report_age_days,
            fq.has_complete_statement_set_asof,
            fq.ts_code IS NOT NULL AS financial_quality_available_flag,
            fq.roe_asof,
            fq.roa_asof,
            fq.ocf_to_profit_asof,
            fg.revenue_yoy_asof,
            fg.netprofit_yoy_asof,
            fg.ts_code IS NOT NULL AS financial_growth_available_flag,
            cf.has_moneyflow,
            cf.has_margin,
            cf.has_north_holding,
            (cf.has_moneyflow OR cf.has_margin OR cf.has_north_holding) AS capital_flow_source_available_flag,
            cf.main_flow_sum_20,
            cf.main_flow_persist_ratio_20,
            cf.margin_balance_chg_20,
            cf.north_hold_ratio_chg_20,
            cfe.top_list_days_20,
            sc.sw_l1_code,
            sc.sw_l2_code,
            sc.sw_l1_code IS NOT NULL AS sector_source_available_flag,
            sc.concept_count,
            sc.stock_excess_sw_l2_20,
            sc.concept_hot_count_20,
            im.is_hs300_member,
            im.is_zz500_member,
            im.is_zz1000_member,
            im.is_sse50_member,
            im.is_star50_member,
            im.is_chinext_member,
            im.market_up_ratio,
            im.ts_code IS NOT NULL AS index_market_available_flag,
            xs.xs_universe_flag,
            xs.xs_universe_flag AS cross_sectional_available_flag,
            xs.amount_ma_20_pct_all_desc,
            xs.turnover_rate_ma_20_pct_all_desc,
            xs.amihud_20_pct_all_desc,
            xs.hv_60_pct_all_desc,
            xs.max_drawdown_60_hfq_pct_all_desc,
            xs.log_total_mv_pct_all_desc,
            xs.log_total_mv_pct_sw_l2_desc,
            xs.debt_to_assets_asof_pct_all_desc,
            xs.size_exposure_z,
            xs.value_exposure_z,
            xs.momentum_exposure_z,
            xs.reversal_exposure_z,
            xs.volatility_exposure_z,
            xs.liquidity_exposure_z,
            xs.quality_exposure_z,
            xs.growth_exposure_z,
            xs.flow_exposure_z,
            ca.corp_action_available_flag,
            ca.corp_action_available_flag AS corp_action_source_available_flag,
            ca.latest_corp_action_date,
            ca.cash_dividend_ttm,
            ca.dividend_event_count_365d,
            ca.has_forecast_asof,
            ca.audit_opinion_code_latest,
            ca.non_standard_audit_flag_latest,
            ca.repurchase_amount_365d,
            ca.next_share_float_share_30d,
            ca.next_share_float_share_90d,
            og.ownership_available_flag,
            og.ownership_available_flag AS ownership_source_available_flag,
            og.latest_ownership_event_date,
            og.pledge_ratio_asof,
            og.pledge_ratio_ge_10_flag,
            og.pledge_ratio_ge_30_flag,
            og.pledge_ratio_ge_50_flag,
            og.holder_num_chg_rate_1report,
            og.holder_num_chg_rate_4report,
            og.top10_holder_ratio_latest
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
        LEFT JOIN derived_capital_flow_event_cache cfe ON ds.ts_code = cfe.ts_code AND ds.trade_date = cfe.trade_date
        LEFT JOIN derived_sector_concept_context sc ON ds.ts_code = sc.ts_code AND ds.trade_date = sc.trade_date
        LEFT JOIN derived_index_market_context im ON ds.ts_code = im.ts_code AND ds.trade_date = im.trade_date
        LEFT JOIN derived_cross_sectional xs ON ds.ts_code = xs.ts_code AND ds.trade_date = xs.trade_date
        LEFT JOIN derived_corporate_action ca ON ds.ts_code = ca.ts_code AND ds.trade_date = ca.trade_date
        LEFT JOIN derived_ownership_governance og ON ds.ts_code = og.ts_code AND ds.trade_date = og.trade_date
        WHERE ds.trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    ),
    flags AS (
        SELECT
            *,
            close_hfq > ma_20_hfq AS price_above_ma20_flag,
            round(close_hfq, 10) > round(ma_60_hfq, 10) AS price_above_ma60_flag,
            round(ma_20_hfq, 10) > round(ma_60_hfq, 10) AS ma20_above_ma60_flag,
            round(ma_60_hfq, 10) > round(ma_120_hfq, 10) AS ma60_above_ma120_flag,
            ret_20_hfq > 0 AS ret_20_positive_flag,
            ret_60_hfq > 0 AS ret_60_positive_flag,
            ret_250_hfq > 0 AS ret_250_positive_flag,
            momentum_60_20_hfq > 0 AS momentum_spread_positive_flag,
            (amount_ma_20_pct_all_desc IS NOT NULL OR turnover_rate_ma_20_pct_all_desc IS NOT NULL OR amihud_20_pct_all_desc IS NOT NULL) AS liquidity_available_flag,
            latest_report_end_date IS NOT NULL AS financial_available_flag,
            (roe_asof > 0 OR roa_asof > 0) AS profitability_positive_flag,
            ocf_to_profit_asof > 0 AS cashflow_profit_match_flag,
            revenue_yoy_asof > 0 AS growth_revenue_positive_flag,
            netprofit_yoy_asof > 0 AS growth_profit_positive_flag,
            (has_moneyflow OR has_margin OR has_north_holding) AS capital_flow_available_flag,
            main_flow_sum_20 > 0 AS main_flow_20_positive_flag,
            top_list_days_20 > 0 AS top_list_recent_flag,
            sw_l1_code IS NOT NULL AS sector_context_available_flag,
            repurchase_amount_365d > 0 AS repurchase_recent_flag
        FROM joined
    ),
    payload AS (
        SELECT
            ts_code,
            trade_date,
            ({module_available}) > 0 AS composite_available_flag,
            ({module_available})::INTEGER AS module_available_count,
            ({module_available}) / {MODULE_COUNT}.0 AS module_available_ratio,
            nullif(trim(trailing ';' FROM ({missing_modules})), '') AS missing_module_names,
            ({condition_count})::INTEGER AS state_condition_count,
            ({condition_available_count})::INTEGER AS state_condition_available_count,
            ({condition_available_count}) / {CONDITION_COUNT}.0 AS state_condition_available_ratio,
            nullif(greatest(coalesce(latest_financial_effective_date, DATE '1900-01-01'), coalesce(latest_corp_action_date, DATE '1900-01-01'), coalesce(latest_ownership_event_date, DATE '1900-01-01')), DATE '1900-01-01') AS latest_low_freq_event_date,
            CASE WHEN latest_low_freq_event_date IS NOT NULL THEN (trade_date - latest_low_freq_event_date)::INTEGER ELSE NULL END AS days_since_latest_low_freq_event,
            is_listed_asof,
            list_status_asof,
            coalesce(exchange, 'unknown') || ':' || coalesce(market, 'unknown') AS market_board_state,
            CASE WHEN days_since_list IS NULL THEN 'unknown' WHEN days_since_list < 365 THEN 'lt1y' WHEN days_since_list < 365*3 THEN '1to3y' WHEN days_since_list < 365*5 THEN '3to5y' WHEN days_since_list < 365*10 THEN '5to10y' ELSE 'ge10y' END AS list_age_bucket,
            coalesce(tc_tradable_state, 'unknown') AS tradable_state,
            CASE WHEN price_valid_flag THEN 'valid_price' WHEN has_price THEN 'invalid_price' WHEN is_listed_asof THEN 'trading_no_price' ELSE 'no_price' END AS price_valid_state,
            CASE WHEN one_price_limit_up_flag OR one_price_limit_down_flag THEN 'one_price_limit' WHEN limit_up_flag THEN 'limit_up' WHEN limit_down_flag THEN 'limit_down' WHEN limit_up_flag IS NULL AND limit_down_flag IS NULL THEN 'unknown' ELSE 'none' END AS limit_lock_state,
            CASE WHEN tc_tradable_state IS NULL THEN 'unknown' WHEN tc_tradable_state = 'suspended' THEN 'recent' WHEN coalesce(limit_up_days_20, 0) + coalesce(limit_down_days_20, 0) >= 10 THEN 'frequent' WHEN coalesce(limit_up_days_20, 0) + coalesce(limit_down_days_20, 0) >= 3 THEN 'mild' ELSE 'none' END AS recent_suspend_state,
            price_above_ma20_flag,
            price_above_ma60_flag,
            ma20_above_ma60_flag,
            ma60_above_ma120_flag,
            CASE
                WHEN ma_20_hfq IS NULL OR ma_60_hfq IS NULL OR ma_120_hfq IS NULL THEN 'unknown'
                WHEN round(ma_20_hfq, 10) > round(ma_60_hfq, 10) AND round(ma_60_hfq, 10) > round(ma_120_hfq, 10) THEN 'bull'
                WHEN round(ma_20_hfq, 10) < round(ma_60_hfq, 10) AND round(ma_60_hfq, 10) < round(ma_120_hfq, 10) THEN 'bear'
                WHEN round(ma_20_hfq, 10) > round(ma_60_hfq, 10) THEN 'partial_bull'
                WHEN round(ma_20_hfq, 10) < round(ma_60_hfq, 10) THEN 'partial_bear'
                ELSE 'mixed'
            END AS ma_alignment_state,
            ret_20_positive_flag,
            ret_60_positive_flag,
            ret_250_positive_flag,
            momentum_spread_positive_flag,
            ({bool_int("price_above_ma20_flag")} + {bool_int("price_above_ma60_flag")} + {bool_int("ma20_above_ma60_flag")} + {bool_int("ma60_above_ma120_flag")} + {bool_int("ret_20_positive_flag")} + {bool_int("ret_60_positive_flag")} + {bool_int("ret_250_positive_flag")} + {bool_int("momentum_spread_positive_flag")})::INTEGER AS trend_condition_count,
            (
                (price_above_ma20_flag IS NOT NULL)::INTEGER
              + (price_above_ma60_flag IS NOT NULL)::INTEGER
              + (ma20_above_ma60_flag IS NOT NULL)::INTEGER
              + (ma60_above_ma120_flag IS NOT NULL)::INTEGER
              + (ret_20_positive_flag IS NOT NULL)::INTEGER
              + (ret_60_positive_flag IS NOT NULL)::INTEGER
              + (ret_250_positive_flag IS NOT NULL)::INTEGER
              + (momentum_spread_positive_flag IS NOT NULL)::INTEGER
            ) AS trend_observation_count,
            CASE
                WHEN trend_observation_count = 0 THEN 'unknown'
                WHEN trend_condition_count >= 7 THEN 'bull'
                WHEN trend_condition_count >= 5 THEN 'partial_bull'
                WHEN trend_condition_count >= 3 THEN 'mixed'
                WHEN trend_condition_count >= 1 THEN 'partial_bear'
                ELSE 'bear'
            END AS trend_state,
            liquidity_available_flag,
            {pct_state("amount_ma_20_pct_all_desc")} AS amount_activity_state,
            {pct_state("turnover_rate_ma_20_pct_all_desc")} AS turnover_activity_state,
            {pct_state("amihud_20_pct_all_desc")} AS liquidity_cost_state,
            {pct_state("hv_60_pct_all_desc")} AS volatility_state,
            {pct_state("max_drawdown_60_hfq_pct_all_desc")} AS drawdown_state,
            ({bool_int("amount_ma_20_pct_all_desc > 0.8")} + {bool_int("turnover_rate_ma_20_pct_all_desc > 0.8")} + {bool_int("amihud_20_pct_all_desc < 0.2")})::INTEGER AS liquidity_condition_count,
            ({bool_int("hv_60_pct_all_desc > 0.8")} + {bool_int("max_drawdown_60_hfq_pct_all_desc > 0.8")} + {bool_int("tc_tradable_state != 'normal'")})::INTEGER AS risk_condition_count,
            {pct_state("log_total_mv_pct_all_desc")} AS size_bucket_all,
            {pct_state("log_total_mv_pct_sw_l2_desc")} AS size_bucket_sw_l2,
            pe_ttm_valid_flag AS pe_valid_flag,
            pb_valid_flag AS pb_valid_flag,
            {pct_state("(coalesce(pe_ttm_pct_5y, pb_pct_5y, ps_ttm_pct_5y))")} AS valuation_percentile_state,
            {z_state("value_exposure_z")} AS value_exposure_state,
            {z_state("size_exposure_z")} AS size_exposure_state,
            ({bool_int("pe_ttm_valid_flag")} + {bool_int("pb_valid_flag")} + {bool_int("value_exposure_z IS NOT NULL")})::INTEGER AS valuation_condition_count,
            financial_available_flag,
            has_complete_statement_set_asof AS financial_statement_complete_flag,
            CASE WHEN report_age_days IS NULL THEN 'unknown' WHEN report_age_days <= 120 THEN 'fresh' WHEN report_age_days <= 240 THEN 'normal' ELSE 'stale' END AS financial_staleness_state,
            profitability_positive_flag,
            cashflow_profit_match_flag,
            {pct_state("debt_to_assets_asof_pct_all_desc")} AS leverage_state,
            growth_revenue_positive_flag,
            growth_profit_positive_flag,
            {z_state("quality_exposure_z")} AS quality_exposure_state,
            {z_state("growth_exposure_z")} AS growth_exposure_state,
            ({bool_int("has_complete_statement_set_asof")} + {bool_int("profitability_positive_flag")} + {bool_int("cashflow_profit_match_flag")} + {bool_int("growth_revenue_positive_flag")} + {bool_int("growth_profit_positive_flag")})::INTEGER AS financial_condition_count,
            capital_flow_available_flag,
            main_flow_20_positive_flag,
            CASE WHEN main_flow_persist_ratio_20 IS NULL THEN 'unknown' WHEN main_flow_persist_ratio_20 < 0.4 THEN 'low' WHEN main_flow_persist_ratio_20 > 0.6 THEN 'high' ELSE 'mid' END AS main_flow_persist_state,
            CASE WHEN margin_balance_chg_20 IS NULL THEN 'unknown' WHEN margin_balance_chg_20 < -0.01 THEN 'decrease' WHEN margin_balance_chg_20 > 0.01 THEN 'increase' ELSE 'flat' END AS margin_balance_change_state,
            CASE WHEN north_hold_ratio_chg_20 IS NULL THEN 'unknown' WHEN north_hold_ratio_chg_20 < 0 THEN 'decrease' WHEN north_hold_ratio_chg_20 > 0 THEN 'increase' ELSE 'flat' END AS north_holding_change_state,
            top_list_recent_flag,
            {z_state("flow_exposure_z")} AS flow_exposure_state,
            ({bool_int("capital_flow_available_flag")} + {bool_int("main_flow_20_positive_flag")} + {bool_int("main_flow_persist_ratio_20 > 0.6")} + {bool_int("margin_balance_chg_20 > 0.01")} + {bool_int("north_hold_ratio_chg_20 > 0")} + {bool_int("top_list_recent_flag")})::INTEGER AS capital_flow_condition_count,
            sector_context_available_flag,
            sw_l1_code,
            sw_l2_code,
            CASE WHEN stock_excess_sw_l2_20 IS NULL THEN 'unknown' WHEN stock_excess_sw_l2_20 < 0 THEN 'lag' WHEN stock_excess_sw_l2_20 > 0 THEN 'lead' ELSE 'mid' END AS sector_relative_return_state,
            CASE WHEN concept_count IS NULL THEN 'unknown' WHEN concept_count = 0 THEN 'none' WHEN concept_count = 1 THEN 'single' ELSE 'multiple' END AS concept_membership_state,
            CASE WHEN concept_hot_count_20 IS NULL THEN 'unknown' WHEN concept_hot_count_20 = 0 THEN 'low' WHEN concept_hot_count_20 >= 3 THEN 'high' ELSE 'mid' END AS concept_heat_state,
            CASE WHEN is_hs300_member OR is_sse50_member THEN 'major' WHEN is_zz500_member OR is_zz1000_member OR is_star50_member OR is_chinext_member THEN 'broad' WHEN is_hs300_member IS NULL THEN 'unknown' ELSE 'none' END AS index_membership_state,
            CASE WHEN market_up_ratio IS NULL THEN 'unknown' WHEN market_up_ratio < 0.4 THEN 'down' WHEN market_up_ratio > 0.6 THEN 'up' ELSE 'mixed' END AS market_context_state,
            ({bool_int("sector_context_available_flag")} + {bool_int("stock_excess_sw_l2_20 > 0")} + {bool_int("concept_hot_count_20 > 0")} + {bool_int("market_up_ratio > 0.6")})::INTEGER AS sector_market_condition_count,
            corp_action_available_flag AS corporate_action_available_flag,
            CASE WHEN dividend_event_count_365d IS NULL THEN 'unknown' WHEN dividend_event_count_365d = 0 THEN 'none' WHEN cash_dividend_ttm > 0 THEN 'active' ELSE 'recent' END AS dividend_recent_state,
            CASE WHEN has_forecast_asof IS NULL THEN 'unknown' WHEN has_forecast_asof THEN 'available' ELSE 'none' END AS forecast_recent_state,
            CASE WHEN audit_opinion_code_latest IS NULL THEN 'unknown' WHEN non_standard_audit_flag_latest THEN 'non_standard' ELSE 'standard' END AS audit_opinion_state,
            repurchase_recent_flag,
            CASE WHEN next_share_float_share_30d IS NOT NULL THEN 'within30d' WHEN next_share_float_share_90d IS NOT NULL THEN 'within90d' WHEN latest_corp_action_date IS NULL THEN 'unknown' ELSE 'none' END AS unlock_future_state,
            ownership_available_flag,
            CASE WHEN pledge_ratio_asof IS NULL THEN 'unknown' WHEN pledge_ratio_ge_50_flag THEN 'ge50' WHEN pledge_ratio_ge_30_flag THEN 'ge30' WHEN pledge_ratio_ge_10_flag THEN 'ge10' ELSE 'below10' END AS pledge_ratio_state,
            CASE WHEN coalesce(holder_num_chg_rate_1report, holder_num_chg_rate_4report) IS NULL THEN 'unknown' WHEN coalesce(holder_num_chg_rate_1report, holder_num_chg_rate_4report) < 0 THEN 'decrease' WHEN coalesce(holder_num_chg_rate_1report, holder_num_chg_rate_4report) > 0 THEN 'increase' ELSE 'flat' END AS holder_number_change_state,
            CASE WHEN top10_holder_ratio_latest IS NULL THEN 'unknown' WHEN top10_holder_ratio_latest < 30 THEN 'low' WHEN top10_holder_ratio_latest >= 60 THEN 'high' ELSE 'mid' END AS holder_concentration_state,
            ({bool_int("corp_action_available_flag")} + {bool_int("dividend_event_count_365d > 0")} + {bool_int("has_forecast_asof")} + {bool_int("repurchase_recent_flag")} + {bool_int("ownership_available_flag")} + {bool_int("pledge_ratio_ge_10_flag")})::INTEGER AS event_condition_count,
            ({exposure_count})::INTEGER AS exposure_available_count,
            {z_state("value_exposure_z")} || '_' || {z_state("quality_exposure_z")} AS value_quality_pair_state,
            {z_state("momentum_exposure_z")} || '_' || {z_state("flow_exposure_z")} AS momentum_flow_pair_state,
            {z_state("growth_exposure_z")} || '_' || {z_state("quality_exposure_z")} AS growth_quality_pair_state,
            {z_state("volatility_exposure_z")} || '_' || {z_state("liquidity_exposure_z")} AS risk_liquidity_pair_state,
            (trend_condition_count + liquidity_condition_count + financial_condition_count + capital_flow_condition_count + sector_market_condition_count + event_condition_count)::INTEGER AS multi_domain_condition_count,
            current_timestamp AS updated_at
        FROM flags
    )
    SELECT
        {select_list}
    FROM payload
    """


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2006)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--no-delete", action="store_true")
    args = parser.parse_args()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(DB_PATH) as con, REPORT_PATH.open("a", encoding="utf-8") as report:
        if not args.no_delete:
            con.execute(f"DELETE FROM {q(TABLE_NAME)}")
        for year in range(args.start_year, args.end_year + 1):
            start = f"{year}-01-01"
            end = f"{year}-12-31"
            started_at = datetime.now().isoformat(timespec="seconds")
            con.execute(build_insert_sql(start, end))
            rows = con.execute(
                f"SELECT count(*) FROM {q(TABLE_NAME)} WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}'"
            ).fetchone()[0]
            payload = {
                "year": year,
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "rows": rows,
            }
            line = json.dumps(payload, ensure_ascii=False)
            report.write(line + "\n")
            report.flush()
            print(line)


if __name__ == "__main__":
    main()
