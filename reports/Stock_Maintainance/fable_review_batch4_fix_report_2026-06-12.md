# Fable Review Batch 4 Fix Report - 2026-06-12

## Scope

This batch continued Fable audit remediation after H11/M1 fixes.

Covered items:

- H2 tail hardening: `daily_spine` transaction rollback protection.
- BJ moneyflow coverage feasibility check.
- M2: short-history observation guards for price and volume derived ratios.
- M3: strict in-window max drawdown calculation.

## Fixes

### 1. `daily_spine` Transaction Guard

`build_daily_spine` previously used explicit `BEGIN TRANSACTION` and `COMMIT` without the shared rollback wrapper.

It now uses `write_transaction`, matching the rest of the core feature rebuild path. If insert/count fails after delete, the transaction rolls back rather than leaving a partially deleted write window.

### 2. BJ Moneyflow Feasibility

Empirical Tushare checks were run with the project token.

Results:

- `moneyflow(trade_date=20260611)` returned 5,193 rows and 0 `.BJ` rows.
- `moneyflow(trade_date=20260610)` returned 5,195 rows and 0 `.BJ` rows.
- `moneyflow(trade_date=20240611)` returned 5,094 rows and 0 `.BJ` rows.
- Single-stock checks for `920221.BJ`, `920455.BJ`, `920651.BJ`, `430047.BJ`, and `835185.BJ` returned 0 rows.

Conclusion:

The current Tushare `moneyflow` API does not appear to provide BJ-market stock moneyflow rows through either date-level or stock-level calls. The remaining `stock_moneyflow_daily` BJ coverage issue is a real source limitation, not a local ingestion miss.

### 3. Price/Volume Observation Guards

The following fields now require the matching rolling window to have enough observations before output:

- `close_to_ma_20_hfq`
- `close_to_ma_60_hfq`
- `ma_20_slope_20_hfq`
- `ma_60_slope_60_hfq`
- `price_position_20_hfq`
- `price_position_60_hfq`
- `volume_ratio_20`
- `amount_ratio_20`
- turnover, free-turnover, amount, and amihud rolling fields use their own observation counts rather than a broad volume count.

This prevents newly listed or sparse-history stocks from receiving short-window proxy values in fields whose names imply complete 20/60 day windows.

### 4. Max Drawdown Window Definition

`max_drawdown_20_hfq` and `max_drawdown_60_hfq` now compute the worst peak-to-trough drawdown strictly inside the current 20/60-row window.

The prior implementation used a rolling peak and then a second rolling minimum, which could effectively include up to `2N-1` rows and pull a peak from before the current window.

## Tests

Added:

- `tests/test_technical_windows.py`

Coverage:

- short-history price ratios remain `NULL`
- short-history volume ratios remain `NULL`
- max drawdown ignores a peak that is outside the current drawdown window

Full test suite:

```text
58 passed
```

Gates:

```text
stock-maintain validate-config
stock-maintain docs-check
```

Both passed.

## Real Database Rebuild

Rebuilt the recent operational window `2026-06-01` to `2026-06-11` through the `composite_state` dependency chain.

Rows written per main module:

- `derived_daily_spine`: 49,604
- `derived_price_technical`: 49,604
- `derived_volume_liquidity`: 49,604
- `derived_return_momentum`: 49,604
- `derived_volatility_risk`: 49,604
- `derived_trading_constraint`: 49,604
- `derived_valuation_size`: 49,604
- `derived_financial_asof`: 49,604
- `derived_financial_quality`: 49,604
- `derived_financial_growth`: 49,604
- `derived_capital_flow`: 49,604
- `derived_sector_concept_context`: 49,604
- `derived_index_market_context`: 49,604
- `derived_cross_sectional`: 49,604
- `derived_composite_state`: 49,604

Views were refreshed with:

```text
stock-maintain create-views
```

Daily validation:

```text
stock-maintain validate-daily --as-of-date 2026-06-11 --output-prefix fable_fix_batch4_validate_20260611
```

Result: `warning`.

Known remaining warnings:

- `margin_detail` expected T+1/source lag.
- `northbound_holding` expected T+1/source lag.
- `stock_moneyflow_daily` lacks BJ-market coverage for 121 stocks due to current Tushare source limitation.

## Remaining Notes

The BJ moneyflow limitation should be handled as a source-strategy task rather than a local backfill task unless a different Tushare endpoint or alternate vendor source is approved.
