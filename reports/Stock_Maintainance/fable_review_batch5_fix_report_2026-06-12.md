# Fable Review Batch 5 Fix Report - 2026-06-12

## Scope

This batch addressed additional medium-risk Fable audit items after the technical-window fixes.

Covered items:

- M5: financial growth QoQ and single-quarter values should not use non-adjacent report periods.
- M8: cross-sectional sentinel filter threshold was too broad.
- M14: direct sync range commands bypassed the 10-trading-day confirmation rule.
- M15: `validate-daily` returned exit code 0 for blocked status unless `--fail-on-warning` was passed.

## Fixes

### 1. Financial Growth Adjacent-Quarter Guard

`derived_financial_growth` now only outputs QoQ report growth when:

```text
prev_report_end_date = current_report_end_date - 3 months
```

Flow-metric single-quarter values now also require the previous report in the same fiscal year to be the immediately preceding quarter. If Q2 is missing and Q3 is available, Q3 single-quarter value is `NULL` instead of `Q3 cumulative - Q1 cumulative`.

This avoids using the previous available report as if it were the previous adjacent quarter.

### 2. Cross-Sectional Sentinel Threshold

The sentinel filter in cross-sectional scripts changed from:

```text
value <= -900000
```

to:

```text
value <= -9000000
```

Affected scripts:

- `scripts/build_phase3_cross_sectional_core.py`
- `scripts/create_phase3_cross_sectional_full_view.py`

This keeps real large negative amount values, such as large capital outflows, from being incorrectly dropped as sentinel values.

### 3. Direct Sync Range Guardrails

The following direct range commands now require `--allow-confirmed-history` when the requested window exceeds the automatic threshold:

- `sync-daily-range`
- `sync-market-behavior-range`
- `sync-adj-factor-range`
- `sync-index-daily`
- `sync-financial-incremental-range`

Behavior:

- If trade calendar is available, the guard uses trading-day count.
- If the range extends beyond available calendar or a minimal environment lacks calendar data, it falls back to calendar-day count.
- Blocked commands print JSON and exit with code 2.

Example checked:

```text
stock-maintain sync-daily-range 20260601 20260620
```

Result:

```text
status = blocked
exit = 2
```

### 4. `validate-daily` Blocked Exit Code

`validate-daily` now returns exit code 2 whenever summary status is `blocked`, even if `--fail-on-warning` is not provided.

Example checked:

```text
stock-maintain validate-daily --as-of-date 2026-06-30 --max-auto-trade-days 1
```

Result:

```text
status = blocked
exit = 2
```

## Tests

Added:

- `tests/test_cli_guardrails.py`
- additional financial growth gap test in `tests/test_financial_pit.py`

Coverage:

- blocked `validate-daily` exit code
- direct sync range guard blocks large unconfirmed windows
- direct sync range guard allows explicit confirmation
- cross-sectional sentinel threshold is `-9000000`
- financial growth QoQ/single-quarter output is `NULL` when adjacent report is missing

Full suite:

```text
63 passed
```

Gates:

```text
stock-maintain validate-config
stock-maintain docs-check
```

Both passed.

## Real Database Rebuild

Rebuilt recent window `2026-06-01` to `2026-06-11` through `cross_sectional`.

Key row counts:

- `derived_daily_spine`: 49,604
- `derived_financial_growth`: 49,604
- `derived_cross_sectional`: 49,604

Views were refreshed.

Daily validation:

```text
stock-maintain validate-daily --as-of-date 2026-06-11 --output-prefix fable_fix_batch5_validate_20260611
```

Result: `warning`.

Known remaining warnings:

- `margin_detail` expected T+1/source lag.
- `northbound_holding` expected T+1/source lag.
- `stock_moneyflow_daily` BJ-market coverage limitation from current Tushare `moneyflow` API.
