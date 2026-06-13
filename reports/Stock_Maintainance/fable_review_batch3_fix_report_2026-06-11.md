# Fable Review Batch 3 Fix Report - 2026-06-11

## Scope

This batch continued the Fable audit remediation after the financial PIT fixes.

Fixed items:

- H11: daily validation only planned gaps from one anchor table and did not expose per-table lag or new-stock coverage gaps.
- M1: feature build write-window planning used calendar days while documents and operation rules say recent trading days.
- M19 follow-up hardening: `validation_days=0` remains explicitly empty and is covered by the new tests.

## Fixes

### 1. Per-Table Lag Audit

`validate-daily` now records each table's lag from its own `max(trade_date/cal_date)` to the latest open trading date.

The report includes:

- `lag_dates_to_latest`
- `hidden_lag_dates`
- `expected_delay_lag`
- `table_lag_issue_count`

This catches cases where `derived_daily_spine` is current but another base or derived table is stale.

Expected T+1 tables remain non-blocking, but hidden lag is visible in the report.

### 2. New-Stock Coverage Audit

`validate-daily` now checks whether A-share stocks in `stock_basic_info` that listed before the current gap window have any coverage records from listing date to latest trade date.

The audit is limited to full-coverage A-share daily tables:

- `stock_daily`
- `stock_daily_basic`
- `stock_adj_factor`
- `stock_limit_price`
- `stock_moneyflow_daily`

B-share codes are excluded from this check:

- `900xxx.SH`
- `20xxxx.SZ`

Sparse or eligibility-limited domains such as margin, northbound holding, top list, and institutional list are not treated as full-market new-stock coverage tables.

### 3. Trading-Day Feature Planning

`build_feature_plan` now accepts optional trading dates.

When a trading calendar is available:

- default write start is computed from the latest N trading days, not N calendar days
- confirmation uses trading-day count
- confirmation message reports trading days

When a calendar is unavailable, planning falls back to the previous calendar-day behavior so isolated dry-run and minimal test environments still work.

`build-features` and `plan-features` both load the trade calendar before planning, so manual planning and actual execution now align.

## Tests

Added:

- `tests/test_feature_planner.py`
- additional cases in `tests/test_daily_validate.py`

Coverage:

- hidden table lag when anchor table is current
- new-stock coverage issue
- default feature write window based on trading days
- confirmation count based on trading days

Full suite:

```text
56 passed
```

Gates:

```text
stock-maintain validate-config
stock-maintain docs-check
```

Both passed.

## Real Database Validation

Command:

```text
stock-maintain validate-daily --as-of-date 2026-06-11 --output-prefix fable_fix_batch3_validate3_20260611
```

Result: `warning`.

Summary:

- table count: 40
- missing tables: 0
- target-date coverage issue tables: 0
- hidden lag issue tables: 2
- new-stock coverage issue count: 1
- duplicate issue tables: 0
- stock-level derived row-count issues: 0
- expected delayed tables: 2

Expected delayed/lagged tables:

- `margin_detail`
- `northbound_holding`

Remaining new-stock coverage issue:

- `stock_moneyflow_daily`: 121 BJ-market stocks have no coverage records in the current database.

Sample:

- `920221.BJ`, list date `2023-06-08`
- `920455.BJ`, list date `2023-06-21`
- `920651.BJ`, list date `2023-06-27`

This appears to be a real coverage gap for North Exchange moneyflow data, not a validation false positive. It should be handled as a follow-up data-source feasibility/backfill task.

## Remaining Notes

This batch improves detection and planning. It does not automatically widen daily-light incremental dates per stale table, because each source has different fetch strategy and cost. The correct next step is a targeted BJ moneyflow feasibility check and, if supported by Tushare, a batched historical backfill for missing BJ moneyflow coverage.
