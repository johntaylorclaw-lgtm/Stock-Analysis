# Fable Review Batch 2 Fix Report - 2026-06-11

## Scope

This batch continued the Fable audit remediation after the first batch of runtime, transaction, corporate action, optional API, and compare-window fixes.

The focus was the financial derived layer:

- H3/M21: point-in-time version selection for `derived_financial_quality` and `derived_financial_growth`
- H7: special ratio sentinel values must not be treated as real negative growth in same-direction flags
- H8: ROE percentage vs decimal unit mismatch in DuPont ROE gap

## Fixes

### 1. Financial PIT Version Selection

`derived_financial_quality` previously selected the final latest raw statement version by `(ts_code, end_date)` and joined it to all as-of trade dates. This could leak later-announced revisions into earlier trade dates.

Now the module builds `indicator_asof`, `income_asof`, `balance_asof`, and `cashflow_asof` by `(ts_code, trade_date, latest_report_end_date)` and keeps only raw records whose effective/announcement date is not later than the target `trade_date`.

`derived_financial_growth` now applies the same rule not only to the current report period, but also to previous, lagged, and same-period comparison reports. The report-value context is keyed by `asof_trade_date`, so every growth comparison uses the report versions visible on that trade date.

### 2. Growth Same-Direction Flags

The ratio special value convention uses negative `-9xxxxxx` sentinel values. These values are diagnostic categories, not real negative growth.

The following flags now require both inputs to be valid (`x > -9000000`) before evaluating same-sign direction:

- `revenue_profit_same_direction_flag`
- `profit_ocf_same_direction_flag`

### 3. ROE Unit Alignment

Tushare `roe` is stored in percentage units, while the internally calculated DuPont ROE is a decimal ratio.

`roe_calc_gap_asof` now uses:

```text
roe_asof / 100 - dupont_roe_calc_asof
```

This keeps both sides in decimal units before subtraction.

### 4. Dictionary Synchronization

Updated `config/variables/derived_variables.json` so the variable dictionary records:

- `roe_calc_gap_asof = roe_asof / 100 - dupont_roe_calc_asof`
- same-direction flags exclude `-9` ratio special codes before sign comparison

Then refreshed the global dictionary:

```text
stock-maintain refresh-dictionary --output-prefix global_variable_dictionary
```

Result: pass.

## Tests And Validation

### Unit Tests

Added `tests/test_financial_pit.py`.

Coverage:

- two raw versions for the same report period
- early trade date sees only early announced version
- later trade date sees later revision
- ROE gap uses decimal-compatible units
- growth PIT selection follows trade-date visibility
- same-direction flag excludes `-9` sentinel values

Full test suite:

```text
52 passed
```

### Real Database Rebuild

Rebuilt real database window `2026-06-01` to `2026-06-11`.

`financial_quality`:

- `financial_asof`: 49,604 rows
- `financial_quality`: 49,604 rows
- elapsed: 21.970 seconds

`financial_growth`:

- `financial_asof`: 49,604 rows
- `financial_growth`: 49,604 rows
- elapsed: 23.784 seconds

### Gates

```text
stock-maintain validate-config
stock-maintain docs-check
```

Both passed.

Daily validation:

```text
stock-maintain validate-daily --as-of-date 2026-06-11 --output-prefix fable_fix_batch2_validate_20260611
```

Result: pass.

Expected delayed tables:

- `margin_detail`
- `northbound_holding`

## Remaining Notes

This batch fixes the main physical financial derived layer. Any standalone legacy scripts or archived historical drafts that describe pre-fix formulas should be treated as archived context unless they are explicitly reactivated in a future phase.
