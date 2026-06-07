# Phase 3 Feature Plan

- Mode: `daily`
- Write window: `2026-05-20` to `2026-05-29`
- Requires confirmation: `false`

## Execution Order

`daily_spine` -> `price_technical` -> `volume_liquidity` -> `return_momentum` -> `volatility_risk` -> `trading_constraint` -> `valuation_size` -> `financial_asof` -> `financial_quality` -> `financial_growth` -> `capital_flow` -> `sector_concept_context` -> `index_market_context` -> `cross_sectional` -> `corporate_action` -> `ownership_governance` -> `composite_state`

## Module Plan

| module | variables | tables | read_start | write_start | write_end | read_window | write_window | dependencies |
|---|---:|---|---|---|---|---:|---:|---|
| daily_spine | 2 | derived_daily_spine | 2026-04-30 | 2026-05-20 | 2026-05-29 | 20 | 10 |  |
| price_technical | 1 | derived_price_technical | 2026-03-01 | 2026-05-20 | 2026-05-29 | 80 | 10 | daily_spine |
| volume_liquidity | 1 | derived_volume_liquidity | 2026-03-01 | 2026-05-20 | 2026-05-29 | 80 | 10 | daily_spine |
| return_momentum | 1 | derived_return_momentum | 2026-03-01 | 2026-05-20 | 2026-05-29 | 80 | 10 | daily_spine |
| volatility_risk | 1 | derived_volatility_risk | 2025-12-11 | 2026-05-20 | 2026-05-29 | 160 | 10 | daily_spine, return_momentum |
| trading_constraint | 1 | derived_trading_constraint | 2026-04-20 | 2026-05-20 | 2026-05-29 | 30 | 10 | daily_spine |
| valuation_size | 1 | derived_valuation_size | 2022-10-28 | 2026-05-20 | 2026-05-29 | 1300 | 10 | daily_spine, financial_asof |
| financial_asof | 1 | derived_financial_asof | 2025-09-02 | 2026-05-20 | 2026-05-29 | 260 | 10 |  |
| financial_quality | 1 | derived_financial_quality | 2025-09-02 | 2026-05-20 | 2026-05-29 | 260 | 10 | financial_asof |
| financial_growth | 1 | derived_financial_growth | 2025-09-02 | 2026-05-20 | 2026-05-29 | 260 | 10 | financial_asof |
| capital_flow | 1 | derived_capital_flow | 2026-03-01 | 2026-05-20 | 2026-05-29 | 80 | 10 | daily_spine |
| sector_concept_context | 1 | derived_sector_concept_context | 2026-03-01 | 2026-05-20 | 2026-05-29 | 80 | 10 | daily_spine, return_momentum |
| index_market_context | 1 | derived_index_market_context | 2026-04-30 | 2026-05-20 | 2026-05-29 | 20 | 10 | daily_spine, return_momentum |
| cross_sectional | 1 | derived_cross_sectional | 2026-05-10 | 2026-05-20 | 2026-05-29 | 10 | 10 | daily_spine, price_technical, volume_liquidity, return_momentum, volatility_risk, trading_constraint, valuation_size, financial_quality, financial_growth, capital_flow, sector_concept_context, index_market_context |
| corporate_action | 1 | derived_corporate_action | 2025-09-02 | 2026-05-20 | 2026-05-29 | 260 | 10 | financial_asof |
| ownership_governance | 1 | derived_ownership_governance | 2025-09-02 | 2026-05-20 | 2026-05-29 | 260 | 10 | financial_asof |
| composite_state | 1 | derived_composite_state | 2026-04-30 | 2026-05-20 | 2026-05-29 | 20 | 10 | price_technical, volume_liquidity, return_momentum, volatility_risk, valuation_size, financial_quality, capital_flow, sector_concept_context, index_market_context, cross_sectional |
