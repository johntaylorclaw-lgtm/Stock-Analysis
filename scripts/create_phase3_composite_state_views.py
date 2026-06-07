from __future__ import annotations

from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"


CONDITIONS = [
    ("trend", "price_above_ma20_flag", "price_above_ma20_flag", "derived_price_technical", "close_hfq,ma_20_hfq", "close_hfq > ma_20_hfq"),
    ("trend", "price_above_ma60_flag", "price_above_ma60_flag", "derived_price_technical", "close_hfq,ma_60_hfq", "close_hfq > ma_60_hfq"),
    ("trend", "ma20_above_ma60_flag", "ma20_above_ma60_flag", "derived_price_technical", "ma_20_hfq,ma_60_hfq", "ma_20_hfq > ma_60_hfq"),
    ("trend", "ma60_above_ma120_flag", "ma60_above_ma120_flag", "derived_price_technical", "ma_60_hfq,ma_120_hfq", "ma_60_hfq > ma_120_hfq"),
    ("trend", "ret_20_positive_flag", "ret_20_positive_flag", "derived_return_momentum", "ret_20_hfq", "ret_20_hfq > 0"),
    ("trend", "ret_60_positive_flag", "ret_60_positive_flag", "derived_return_momentum", "ret_60_hfq", "ret_60_hfq > 0"),
    ("trend", "ret_250_positive_flag", "ret_250_positive_flag", "derived_return_momentum", "ret_250_hfq", "ret_250_hfq > 0"),
    ("trend", "momentum_spread_positive_flag", "momentum_spread_positive_flag", "derived_return_momentum", "momentum_60_20_hfq", "momentum_60_20_hfq > 0"),
    ("liquidity", "liquidity_available_flag", "liquidity_available_flag", "derived_volume_liquidity", "amount/turnover/amihud", "liquidity source available"),
    ("valuation", "pe_valid_flag", "pe_valid_flag", "derived_valuation_size", "pe_ttm_valid_flag", "PE valid"),
    ("valuation", "pb_valid_flag", "pb_valid_flag", "derived_valuation_size", "pb_valid_flag", "PB valid"),
    ("financial", "financial_statement_complete_flag", "financial_statement_complete_flag", "derived_financial_quality", "has_complete_statement_set_asof", "current report has complete statement set"),
    ("financial", "profitability_positive_flag", "profitability_positive_flag", "derived_financial_quality", "roe_asof,roa_asof", "roe_asof > 0 or roa_asof > 0"),
    ("financial", "cashflow_profit_match_flag", "cashflow_profit_match_flag", "derived_financial_quality", "ocf_to_profit_asof", "ocf_to_profit_asof > 0"),
    ("financial", "growth_revenue_positive_flag", "growth_revenue_positive_flag", "derived_financial_growth", "revenue_yoy_asof", "revenue_yoy_asof > 0"),
    ("financial", "growth_profit_positive_flag", "growth_profit_positive_flag", "derived_financial_growth", "netprofit_yoy_asof", "netprofit_yoy_asof > 0"),
    ("flow", "capital_flow_available_flag", "capital_flow_available_flag", "derived_capital_flow", "has_moneyflow,has_margin,has_north_holding", "capital flow source available"),
    ("flow", "main_flow_20_positive_flag", "main_flow_20_positive_flag", "derived_capital_flow", "main_flow_sum_20", "main_flow_sum_20 > 0"),
    ("flow", "top_list_recent_flag", "top_list_recent_flag", "derived_capital_flow_event_cache", "top_list_days_20", "top_list_days_20 > 0"),
    ("sector", "sector_context_available_flag", "sector_context_available_flag", "derived_sector_concept_context", "sw_l1_code", "sw_l1_code is not null"),
    ("event", "corporate_action_available_flag", "corporate_action_available_flag", "derived_corporate_action", "corp_action_available_flag", "corporate action source available"),
    ("event", "repurchase_recent_flag", "repurchase_recent_flag", "derived_corporate_action", "repurchase_amount_365d", "repurchase_amount_365d > 0"),
    ("ownership", "ownership_available_flag", "ownership_available_flag", "derived_ownership_governance", "ownership_available_flag", "ownership source available"),
    ("ownership", "pledge_ratio_ge_10_flag", "pledge_ratio_state IN ('ge10','ge30','ge50')", "derived_ownership_governance", "pledge_ratio_ge_10_flag", "pledge ratio >= 10"),
    ("ownership", "pledge_ratio_ge_30_flag", "pledge_ratio_state IN ('ge30','ge50')", "derived_ownership_governance", "pledge_ratio_ge_30_flag", "pledge ratio >= 30"),
    ("ownership", "pledge_ratio_ge_50_flag", "pledge_ratio_state = 'ge50'", "derived_ownership_governance", "pledge_ratio_ge_50_flag", "pledge ratio >= 50"),
    ("exposure", "size_exposure_available", "size_exposure_state != 'unknown'", "derived_cross_sectional", "size_exposure_z", "size exposure available"),
    ("exposure", "value_exposure_available", "value_exposure_state != 'unknown'", "derived_cross_sectional", "value_exposure_z", "value exposure available"),
    ("exposure", "momentum_exposure_available", "momentum_flow_pair_state NOT LIKE 'unknown_%'", "derived_cross_sectional", "momentum_exposure_z", "momentum exposure available"),
    ("exposure", "quality_exposure_available", "quality_exposure_state != 'unknown'", "derived_cross_sectional", "quality_exposure_z", "quality exposure available"),
    ("exposure", "growth_exposure_available", "growth_exposure_state != 'unknown'", "derived_cross_sectional", "growth_exposure_z", "growth exposure available"),
    ("exposure", "flow_exposure_available", "flow_exposure_state != 'unknown'", "derived_cross_sectional", "flow_exposure_z", "flow exposure available"),
    ("exposure", "volatility_exposure_available", "risk_liquidity_pair_state NOT LIKE 'unknown_%'", "derived_cross_sectional", "volatility_exposure_z", "volatility exposure available"),
]


def build_condition_detail_sql() -> str:
    parts = []
    for group, name, expr, source_table, source_fields, formula in CONDITIONS:
        parts.append(
            f"""
            SELECT
                ts_code,
                trade_date,
                '{group}' AS condition_group,
                '{name}' AS condition_name,
                ({expr}) AS condition_value,
                ({expr}) IS NOT NULL AS condition_available_flag,
                '{source_table}' AS source_table,
                '{source_fields}' AS source_fields,
                '{formula}' AS formula_text,
                updated_at
            FROM derived_composite_state
            """
        )
    return "CREATE OR REPLACE VIEW composite_state_condition_detail_v AS\n" + "\nUNION ALL\n".join(parts)


def build_full_view_sql() -> str:
    return """
    CREATE OR REPLACE VIEW derived_composite_state_full_v AS
    SELECT
        c.* EXCLUDE (updated_at),
        ds.close_hfq,
        pt.ma_20_hfq,
        pt.ma_60_hfq,
        pt.ma_120_hfq,
        rm.ret_20_hfq,
        rm.ret_60_hfq,
        rm.ret_250_hfq,
        xs.amount_ma_20_pct_all_desc,
        xs.hv_60_pct_all_desc,
        xs.log_total_mv_pct_all_desc,
        xs.value_exposure_z,
        xs.quality_exposure_z,
        xs.momentum_exposure_z,
        xs.flow_exposure_z,
        xs.growth_exposure_z,
        xs.volatility_exposure_z,
        xs.liquidity_exposure_z,
        fa.latest_report_end_date,
        ca.latest_corp_action_date,
        og.latest_ownership_event_date,
        sc.concept_names_all,
        im.primary_index_name,
        cd.condition_names_true,
        c.updated_at
    FROM derived_composite_state c
    LEFT JOIN derived_daily_spine ds ON c.ts_code = ds.ts_code AND c.trade_date = ds.trade_date
    LEFT JOIN derived_price_technical pt ON c.ts_code = pt.ts_code AND c.trade_date = pt.trade_date
    LEFT JOIN derived_return_momentum rm ON c.ts_code = rm.ts_code AND c.trade_date = rm.trade_date
    LEFT JOIN derived_cross_sectional xs ON c.ts_code = xs.ts_code AND c.trade_date = xs.trade_date
    LEFT JOIN derived_financial_asof fa ON c.ts_code = fa.ts_code AND c.trade_date = fa.trade_date
    LEFT JOIN derived_corporate_action ca ON c.ts_code = ca.ts_code AND c.trade_date = ca.trade_date
    LEFT JOIN derived_ownership_governance og ON c.ts_code = og.ts_code AND c.trade_date = og.trade_date
    LEFT JOIN derived_sector_concept_context sc ON c.ts_code = sc.ts_code AND c.trade_date = sc.trade_date
    LEFT JOIN derived_index_market_context im ON c.ts_code = im.ts_code AND c.trade_date = im.trade_date
    LEFT JOIN (
        SELECT ts_code, trade_date, string_agg(condition_name, ';' ORDER BY condition_group, condition_name) AS condition_names_true
        FROM composite_state_condition_detail_v
        WHERE condition_value
        GROUP BY ts_code, trade_date
    ) cd ON c.ts_code = cd.ts_code AND c.trade_date = cd.trade_date
    """


def build_coverage_view_sql() -> str:
    modules = [
        ("price_technical", "price_above_ma20_flag IS NOT NULL"),
        ("volume_liquidity", "liquidity_available_flag"),
        ("return_momentum", "ret_20_positive_flag IS NOT NULL"),
        ("volatility_risk", "volatility_state != 'unknown'"),
        ("trading_constraint", "tradable_state != 'unknown'"),
        ("valuation_size", "pe_valid_flag IS NOT NULL OR pb_valid_flag IS NOT NULL"),
        ("financial_asof", "financial_available_flag"),
        ("financial_quality", "financial_statement_complete_flag IS NOT NULL"),
        ("financial_growth", "growth_revenue_positive_flag IS NOT NULL OR growth_profit_positive_flag IS NOT NULL"),
        ("capital_flow", "capital_flow_available_flag"),
        ("sector_concept", "sector_context_available_flag"),
        ("index_market", "market_context_state != 'unknown'"),
        ("cross_sectional", "exposure_available_count > 0"),
        ("corporate_action", "corporate_action_available_flag"),
        ("ownership_governance", "ownership_available_flag"),
    ]
    parts = []
    for module, expr in modules:
        parts.append(
            f"""
            SELECT
                trade_date,
                '{module}' AS module_name,
                count(*)::BIGINT AS expected_rows,
                count(CASE WHEN {expr} THEN 1 END)::BIGINT AS available_rows,
                count(CASE WHEN {expr} THEN 1 END)::DOUBLE / NULLIF(count(*), 0) AS available_ratio,
                count(CASE WHEN {expr} THEN 1 END)::DOUBLE / NULLIF(count(*), 0) AS key_non_null_ratio,
                max(updated_at) AS latest_source_update_at,
                NULL::VARCHAR AS quality_note
            FROM derived_composite_state
            GROUP BY trade_date
            """
        )
    return "CREATE OR REPLACE VIEW composite_state_module_coverage_v AS\n" + "\nUNION ALL\n".join(parts)


def main() -> None:
    with duckdb.connect(DB_PATH) as con:
        con.execute(build_condition_detail_sql())
        con.execute(build_full_view_sql())
        con.execute(build_coverage_view_sql())
        print(
            {
                "composite_state_condition_detail_v": con.execute(
                    "SELECT count(*) FROM pragma_table_info('composite_state_condition_detail_v')"
                ).fetchone()[0],
                "derived_composite_state_full_v": con.execute(
                    "SELECT count(*) FROM pragma_table_info('derived_composite_state_full_v')"
                ).fetchone()[0],
                "composite_state_module_coverage_v": con.execute(
                    "SELECT count(*) FROM pragma_table_info('composite_state_module_coverage_v')"
                ).fetchone()[0],
            }
        )


if __name__ == "__main__":
    main()
