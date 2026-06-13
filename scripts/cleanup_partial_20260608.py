import duckdb
db = duckdb.connect('data/duckdb/stock_data.duckdb')
target = '2026-06-08'
base_tables = [
    'stock_daily', 'stock_daily_basic', 'stock_adj_factor', 'stock_limit_price',
    'stock_moneyflow_daily', 'margin_detail', 'northbound_daily', 'northbound_holding',
    'top_list_daily', 'top_inst_detail', 'index_daily'
]
for t in base_tables:
    try:
        r = db.execute(f"DELETE FROM {t} WHERE trade_date = '{target}'").fetchone()
        print(f'{t}: deleted {r[0]} rows')
    except Exception as e:
        print(f'{t}: {e}')
derived_tables = [
    'derived_daily_spine', 'derived_price_technical', 'derived_volume_liquidity',
    'derived_return_momentum', 'derived_volatility_risk', 'derived_trading_constraint',
    'derived_valuation_size', 'derived_valuation_percentile_cache',
    'derived_financial_asof', 'derived_financial_quality', 'derived_financial_growth',
    'derived_capital_flow', 'derived_northbound_flow_cache', 'derived_capital_flow_event_cache',
    'derived_sector_daily_cache', 'derived_concept_daily_cache',
    'derived_sector_concept_context', 'derived_concept_stock_context_cache',
    'derived_index_daily_cache', 'derived_index_membership_cache', 'derived_index_market_context',
    'derived_cross_sectional', 'derived_corporate_action', 'derived_composite_state'
]
for t in derived_tables:
    try:
        r = db.execute(f"DELETE FROM {t} WHERE trade_date = '{target}'").fetchone()
        print(f'{t}: deleted {r[0]} rows')
    except Exception as e:
        print(f'{t}: {e}')
db.close()
print('Cleanup complete.')
