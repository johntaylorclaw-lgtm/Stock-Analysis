# Phase 3 Feature Plan

- Mode: `daily`
- Write window: `2026-05-20` to `2026-05-29`
- Requires confirmation: `false`

## Execution Order

`daily_spine` -> `price_technical`

## Module Plan

| module | variables | tables | read_start | write_start | write_end | read_window | write_window | dependencies |
|---|---:|---|---|---|---|---:|---:|---|
| daily_spine | 2 | derived_daily_spine | 2026-04-30 | 2026-05-20 | 2026-05-29 | 20 | 10 |  |
| price_technical | 1 | derived_price_technical | 2026-03-01 | 2026-05-20 | 2026-05-29 | 80 | 10 | daily_spine |
