# Third-party Audit Assessment

Assessment date: 2026-05-30

Target report: `reports/audit_report_20260530.md`

## Overall judgment

The report is partially useful but not fully objective. It correctly identified several operational hardening gaps, but it is stale on the current Phase 2 state and overstates some items as blocking.

The biggest non-objective statement is that "Phase 2 ingestion logic" was not written. Current project state already contains Phase 2 ingestion routines, full historical P2 tables, registered base variables, analytical views, and quality reports.

## Issue-by-issue review

| issue | judgment | action |
|---|---|---|
| #1 .env permissions | Objective. Windows ACL grants broad inherited access. | Removed cross-project token fallback in config; ACL tightening was attempted but blocked by OS permissions in the current sandbox. |
| #2 date normalization | Not objective for current code. | `parse_tushare_date` already supports `YYYYMMDD`, `YYYYMM`, and `YYYY`. Added regression tests. Stale failure records remain in DB until write access is available. |
| #3 null ann_date handling | Not objective for current code. | `financial_indicator_raw` already uses `ann_date = ann_date.fillna(end_date)`. Added regression coverage around the related date parser. Stale failure records remain in DB until write access is available. |
| #4 zero test coverage | Objective. | Added a minimal test suite and pytest configuration. |
| #5 metadata_source_api status | Objective. | Added source status preservation and a `refresh-source-status` CLI command; quality audit now refreshes statuses before reporting. Current DB update requires DuckDB write access. |
| #6 sw_industry_classify schema mismatch | Objective for the current DB file. | Added schema reconciliation during `init_database`, including nullable-column migration. Current DB migration requires DuckDB write access. |
| #7 .env world-writable risk | Same root as #1. | Same action as #1. |
| #8 unmonitored null ratios | Objective as a monitoring gap, but minor. | Added null-ratio checks and CSV/Markdown output to quality audit. |
| #9 empty placeholder directories | Mostly informational. | `database.ensure_runtime_dirs` intentionally creates `data/parquet` and `data/snapshots`; this is not a Phase 2 blocker. |

## Fixes implemented in code

1. `config/sources.json`: removed `../stock_data_maintainance/.env` fallback.
2. `src/stock_maintainance/env.py`: updated token error message to use project `.env` only.
3. `src/stock_maintainance/database.py`: added schema reconciliation for missing nullable/defaulted fields.
4. `src/stock_maintainance/database.py`: added source API status preservation and refresh logic.
5. `src/stock_maintainance/cli.py`: added `refresh-source-status`.
6. `src/stock_maintainance/audit.py`: refreshes source status and emits `quality_null_ratios.csv`.
7. `tests/test_transform.py`: added date-normalization regression tests.
8. `tests/test_schema_registry.py`: added field SQL regression tests.
9. `pyproject.toml`: added pytest configuration.

## Current environment blockers

The current sandbox user can read but cannot write the existing `.env` ACL or open the DuckDB file in write mode.

Blocked commands:

```powershell
icacls .env /inheritance:r /grant:r "<current-user>:(R,W)" "BUILTIN\Administrators:(F)" "NT AUTHORITY\SYSTEM:(F)"
python -m stock_maintainance.cli init-db
python -m stock_maintainance.cli refresh-source-status
```

These should be run from an Administrator shell or the normal project owner account.

## Verification completed

1. Python compile check passed for modified source and tests.
2. Unit smoke checks passed for date normalization and schema field SQL.
3. Config validation passed.
4. Docs check passed.

