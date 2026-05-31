# Phase 3 Feature Plan

- Mode: `history`
- Write window: `2006-01-04` to `2026-05-26`
- Requires confirmation: `true`
- Confirmation reason: write range spans 7448 calendar days; Phase 3 daily mode defaults to 10 recent trading days

## Execution Order

`daily_spine` -> `price_technical` -> `volume_liquidity` -> `return_momentum` -> `volatility_risk` -> `trading_constraint` -> `valuation_size` -> `financial_asof` -> `financial_quality` -> `financial_growth` -> `capital_flow` -> `sector_concept_context` -> `index_market_context` -> `cross_sectional` -> `corporate_action` -> `ownership_governance` -> `composite_state`

## Module Plan

| module | variables | tables | read_start | write_start | write_end | read_window | write_window | dependencies |
|---|---:|---|---|---|---|---:|---:|---|
| daily_spine | 2 | derived_daily_spine | 2005-12-15 | 2006-01-04 | 2026-05-26 | 20 | 10 |  |
| price_technical | 1 | derived_price_technical | 2005-10-16 | 2006-01-04 | 2026-05-26 | 80 | 10 | daily_spine |
| volume_liquidity | 1 | derived_volume_liquidity | 2005-10-16 | 2006-01-04 | 2026-05-26 | 80 | 10 | daily_spine |
| return_momentum | 1 | derived_return_momentum | 2005-10-16 | 2006-01-04 | 2026-05-26 | 80 | 10 | daily_spine |
| volatility_risk | 1 | derived_volatility_risk | 2005-07-28 | 2006-01-04 | 2026-05-26 | 160 | 10 | daily_spine, return_momentum |
| trading_constraint | 1 | derived_trading_constraint | 2005-12-05 | 2006-01-04 | 2026-05-26 | 30 | 10 | daily_spine |
| valuation_size | 1 | derived_valuation_size | 2002-06-14 | 2006-01-04 | 2026-05-26 | 1300 | 10 | daily_spine, financial_asof |
| financial_asof | 1 | derived_financial_asof | 2005-04-19 | 2006-01-04 | 2026-05-26 | 260 | 10 |  |
| financial_quality | 1 | derived_financial_quality | 2005-04-19 | 2006-01-04 | 2026-05-26 | 260 | 10 | financial_asof |
| financial_growth | 1 | derived_financial_growth | 2005-04-19 | 2006-01-04 | 2026-05-26 | 260 | 10 | financial_asof |
| capital_flow | 1 | derived_capital_flow | 2005-10-16 | 2006-01-04 | 2026-05-26 | 80 | 10 | daily_spine |
| sector_concept_context | 1 | derived_sector_concept_context | 2005-10-16 | 2006-01-04 | 2026-05-26 | 80 | 10 | daily_spine, return_momentum |
| index_market_context | 1 | derived_index_market_context | 2005-12-15 | 2006-01-04 | 2026-05-26 | 20 | 10 | daily_spine, return_momentum |
| cross_sectional | 1 | derived_cross_sectional | 2005-12-25 | 2006-01-04 | 2026-05-26 | 10 | 10 | daily_spine, price_technical, volume_liquidity, return_momentum, volatility_risk, trading_constraint, valuation_size, financial_quality, financial_growth, capital_flow, sector_concept_context, index_market_context |
| corporate_action | 1 | derived_corporate_action | 2005-04-19 | 2006-01-04 | 2026-05-26 | 260 | 10 | financial_asof |
| ownership_governance | 1 | derived_ownership_governance | 2005-04-19 | 2006-01-04 | 2026-05-26 | 260 | 10 | financial_asof |
| composite_state | 1 | derived_composite_state | 2005-12-15 | 2006-01-04 | 2026-05-26 | 20 | 10 | price_technical, volume_liquidity, return_momentum, volatility_risk, valuation_size, financial_quality, capital_flow, sector_concept_context, index_market_context, cross_sectional |
