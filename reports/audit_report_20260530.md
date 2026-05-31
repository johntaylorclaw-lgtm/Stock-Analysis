# Audit Report: Stock_Maintainance

**Audit Date**: 2026-05-30
**Target**: /mnt/d/Opencode Workspace/Stock_Maintainance
**Scope**: Phase 1 and Phase 2 completed portions (code, data, config, docs)

---

## 1. Summary

### Verdict Statement
The project has a clean code architecture, complete data processing pipeline, and acceptable security posture, but **4 blocking issues** (1 security config defect + 1 date normalization gap + 1 Tushare null-value handling gap + zero test coverage) must be resolved before Phase 2 expansion.

### Project Context
Stock_Maintainance is an A-share data maintenance project. Its mandate is raw data warehousing only — no stock selection, factor engineering, or labeling. The project spans two phases:
- **Phase 1**: P0/P1 core data (daily prices, financial statements, valuation, indices, concepts, margin, northbound, top-list, dividends, forecasts, financial events) — 36 Tushare APIs, 32 raw tables + 20 application views
- **Phase 2**: P2 extended data + variable registry system (only JSON definitions and validation framework completed; no P2 ingestion logic written)

### Audit Actions
This audit executed the full 5-step workflow:
1. **Step 1 — Understand**: Read 17 documents (Phase docs, data contract, variable registry design, quality_and_views, etc.)
2. **Step 2 — Code Analysis**: Reviewed 13 Python source modules + 5 JSON config files
3. **Step 3 — Data Analysis**: Connected to DuckDB and executed 38 SQL queries covering table structure, row counts, yearly coverage, PK uniqueness, null distribution, stock status, metadata status, and task failure root-cause analysis
4. **Step 4 — Cross-Validation**: Compared 3 data sources (sources.json 36 APIs == metadata_source_api 36 entries == generated_source_dictionary.md 36 entries), schema_registry.json 32 tables vs DB actual columns, views.py 20 views vs DB actual views
5. **Step 5 — Report**: Generated this audit report

Key metrics:
- Database size: 9.6 GB
- Tables: 32 raw tables + 20 application views
- Year coverage: 2006–2026 (2026 at 38%, in progress; all other years at 100% daily coverage)
- Stocks: 5,850 (5,525 Listed + 325 Delisted)
- Task failures: 4, all retryable, root causes traced
- Test files: 0

---

## 2. Issues

### Issue #1 — .env File Permissions Overly Permissive

| Attribute | Value |
|-----------|-------|
| **Severity** | BLOCKING |
| **Category** | security |
| **Evidence** | .env file permissions 777 (rwxrwxrwx), contains real Tushare token |
| **Description** | The .env file containing the production Tushare API token is world-readable and world-writable. Any user on the host can steal or tamper with the token. While .gitignore correctly prevents git commit exposure, local file permissions are uncontrolled. Additionally, sources.json defines token_file_fallback pointing to ../stock_data_maintainance/.env, expanding the token exposure surface across projects. |

### Issue #2 — Incomplete Date Normalization Logic

| Attribute | Value |
|-----------|-------|
| **Severity** | BLOCKING |
| **Category** | correctness |
| **Evidence** | src/stock_maintainance/transform.py date normalization only handles 8-digit YYYYMMDD format; metadata_task_failure records 3 failures due to end_date format errors |
| **Description** | Tushare financial event APIs (forecast, express, dividend, etc.) return end_date values in non-uniform formats: "2014" (4-digit year), "201409" (6-digit year-month), "201602" (6-digit year-month). The transform.py normalize function only supports YYYYMMDD to YYYY-MM-DD conversion, causing sync_financial_events_batch failures for 3 stocks: 000420.SZ, 000587.SZ, 000718.SZ. |

### Issue #3 — Tushare Returns null Violating NOT NULL Constraint

| Attribute | Value |
|-----------|-------|
| **Severity** | BLOCKING |
| **Category** | correctness |
| **Evidence** | metadata_task_failure records sync_financial_batch failure for 002204.SZ; error: NOT NULL constraint failed: financial_indicator_raw.ann_date |
| **Description** | Tushare's fina_indicator API returns ann_date=null for stock 002204.SZ on a certain reporting period, but the table defines NOT NULL on ann_date. The ingestion code does a direct INSERT without defensive handling, causing the entire financial indicator batch sync to fail for this stock. |

### Issue #4 — Zero Test Coverage

| Attribute | Value |
|-----------|-------|
| **Severity** | BLOCKING |
| **Category** | test-effectiveness |
| **Evidence** | Global search for test*.py and *test*.py returned 0 files; no pytest/nose/unittest configuration found |
| **Description** | The project has no automated tests whatsoever. Core modules including data ingestion (ingest.py), format transformation (transform.py), schema management (schema.py), and view generation (views.py) lack any unit or integration tests. With 4 production task failures already present, the absence of regression testing means bug fixes cannot be verified and similar issues cannot be prevented from recurring. |

### Issue #5 — metadata_source_api Status Not Updated in Real-time

| Attribute | Value |
|-----------|-------|
| **Severity** | MAJOR |
| **Category** | data-integrity |
| **Evidence** | SELECT DISTINCT status FROM metadata_source_api returns only 'planned'; all 36 records have status='planned' |
| **Description** | The metadata_source_api table has a status field (presumably planned/success/failure), but ingest.py never updates it after API calls. All 36 APIs remain permanently in 'planned' status. Actual execution tracking is done only through metadata_task_state and metadata_task_failure, leaving the status column non-functional. |

### Issue #6 — schema_registry.json Field Mismatch with Actual Database

| Attribute | Value |
|-----------|-------|
| **Severity** | MAJOR |
| **Category** | data-integrity |
| **Evidence** | schema_registry.json defines sw_industry_classify with field sw_code (VARCHAR, "Shenwan numeric industry code"), but the actual DB table has only 6 columns without sw_code, using industry_code as the industry code column |
| **Description** | The schema registry defines a sw_code field that does not exist in the database. Either the registry contains a redundant field definition that was never ingested, or the ingestion code failed to write sw_code. This undermines schema_registry.json's authority as the "database source of truth" — any future tool relying on it for automated validation would find a missing field. |

### Issue #7 — .env World-writable Permissions Enable Local Exploitation

| Attribute | Value |
|-----------|-------|
| **Severity** | MAJOR |
| **Category** | security |
| **Evidence** | .env file permissions are 777 (world-writable) |
| **Description** | As a supplement to Issue #1: 777 permissions not only allow other users to read the token, but also allow any local user to modify the file. A malicious user could replace the token with a fake value or inject arbitrary environment variables (e.g., modify PATH, set LD_PRELOAD), creating a code execution risk. |

### Issue #8 — Key Fields Have Unmonitored null Ratios

| Attribute | Value |
|-----------|-------|
| **Severity** | MINOR |
| **Category** | data-integrity |
| **Evidence** | financial_income_raw.total_revenue nulls: 0.2% (673/294,351); financial_indicator_raw.roe nulls: 1.7% (4,328/253,004) |
| **Description** | Core financial indicator fields have small but non-zero null ratios. These could be from Tushare source data gaps (companies not disclosing certain metrics) or from ingestion/transformation losses. No null-ratio alerting threshold is configured in the ingestion pipeline. |

### Issue #9 — Empty Placeholder Directories

| Attribute | Value |
|-----------|-------|
| **Severity** | INFO |
| **Category** | documentation |
| **Evidence** | ls data/parquet/ and ls data/snapshots/ return empty |
| **Description** | Two directories exist but contain no files. They appear to be placeholders for future Parquet export functionality and periodic database snapshots, but are not referenced by any module in code (paths.py defines no corresponding paths). If intended for Phase 2, this should be documented. |

---

## 3. Impact

| Issue | Potential Impact |
|-------|------------------|
| **#1** | Token can be stolen by other host users, exhausting Tushare quota; token can be tampered with, causing silent ingestion failures |
| **#2** | All financial event data (dividends, forecasts, audits, top-10 holders, pledges, etc. — 13 event types) permanently missing for 3 stocks; broader impact if Tushare returns more YYYY/YYYYMM format dates |
| **#3** | All financial indicator data (eps, roe, roa, gross margin, etc. — 153 columns) permanently missing for 002204.SZ |
| **#4** | No way to verify code changes; bug fixes may introduce new issues undetected; project quality cannot be quantified |
| **#5** | metadata_source_api status field loses monitoring value; external tools relying on this field for freshness checks would misreport all APIs as unexecuted |
| **#6** | If Phase 2 relies on schema_registry.json for automated table creation, it would create a redundant sw_code column or cause schema inconsistency |
| **#7** | Local privilege escalation surface: malicious users can hijack environment variables for arbitrary code execution |
| **#8** | Unmonitored null accumulation could cause critical field quality degradation over time |
| **#9** | No operational impact |

---

## 4. Recommendations

### Issue #1 — Harden Token File Permissions

Change .env permissions to owner read/write only (600). Also audit the token_file_fallback path (../stock_data_maintainance/.env) to ensure it is equally protected, or consider removing cross-project fallback and using environment variable injection consistently.

### Issue #2 — Fix Date Normalization
In transform.py, add support for 4-digit year (YYYY) and 6-digit year-month (YYYYMM) formats:

Also update any direct date casting logic in tushare_source.py.

### Issue #3 — Defensive Handling of null ann_date
Add defensive processing in the financial_indicator_raw INSERT logic:
- **Option A**: Use end_date as ann_date fallback
- **Option B (Recommended)**: Pre-process with COALESCE(ann_date, end_date) in ingest.py before INSERT
- **Option C**: Relax NOT NULL constraint on ann_date (requires downstream view impact assessment)

Option B is recommended — preserves table structure while providing a reasonable fallback. Log WARNING when fallback is applied.

### Issue #4 — Establish Test Suite
At minimum, implement:

Use pytest framework with DuckDB :memory: connections and mock Tushare responses.

### Issue #5 — Update metadata_source_api Status
In ingest.py, after each successful API call:

Update to 'failure' on error.

### Issue #6 — Fix schema_registry.json
Determine the intended behavior of sw_industry_classify.sw_code:
- If Tushare index_classify API actually returns this field: fix ingest.py to correctly write sw_code column
- If the field is deprecated/not returned: remove sw_code from the schema_registry.json sw_industry_classify table definition

### Issue #7 — Harden File Permissions

Ensure umask 077 is effective when writing log/config files.

### Issue #8 — Add null Ratio Alerting
In audit.py or cli.py audit command, add key field null ratio checks with a threshold (e.g., 5%) triggering WARNING-level audit reports.

### Issue #9 — Clean Up or Document Empty Directories
- If intended for Phase 2: document in docs/phase2.md
- If unused: remove to maintain project cleanliness

---

## 5. Verdict

**REVISIONS REQUIRED**

4 BLOCKING issues identified:
1. .env token file permissions at 777 — must tighten to 600
2. Incomplete date normalization — must support YYYY and YYYYMM formats
3. ann_date null handling missing — must add COALESCE fallback
4. Zero test coverage — must establish test suite

Resolve all BLOCKING issues before proceeding to Phase 2 extension.
