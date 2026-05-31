# Stock_Maintainance

A-share stock data maintenance project.

This rebuilt project focuses on maintaining rich, auditable stock data. It does not implement stock selection, backtesting, model training, or target-label generation.

## Phase Status

- Phase 0: scope confirmed in `docs/phase0_confirmation.md`
- Phase 1: project skeleton, data contract, schema registry, variable registry, and documentation checks
- Phase 2: started base data warehouse construction; see `docs/phase2_start_summary.md`
- Phase 2 continuous run: see `docs/phase2_continuous_run_summary.md`
- Phase 2 quality/views: see `docs/phase2_quality_and_views.md`
- Phase 2 contract gap review: see `docs/phase2_contract_gap_review.md`

## Initial Commands

```bash
python -m stock_maintainance.cli plan
python -m stock_maintainance.cli docs-generate
python -m stock_maintainance.cli docs-check
python -m stock_maintainance.cli schema-summary
```

## Phase 2 Commands

```powershell
$env:PYTHONPATH='src'
python -m stock_maintainance.cli init-db
python -m stock_maintainance.cli smoke-tushare
python -m stock_maintainance.cli sync-master
python -m stock_maintainance.cli sync-daily-date 20260526
python -m stock_maintainance.cli sync-financial-sample 600519.SH --start-date 20240101 --end-date 20260526
python -m stock_maintainance.cli sync-financial-batch --start-date 20060101 --end-date 20260526
python -m stock_maintainance.cli sync-financial-events-batch --start-date 20060101 --end-date 20260526
python -m stock_maintainance.cli sync-daily-range 20260525 20260526 --limit 2
python -m stock_maintainance.cli sync-adj-factor 600519.SH --start-date 20260501 --end-date 20260526
python -m stock_maintainance.cli sync-index-daily 20260501 20260526 --index-code 000300.SH
python -m stock_maintainance.cli sync-index-weight-month 202605 --index-code 000300.SH
python -m stock_maintainance.cli sync-index-weight-range 200601 202605
python -m stock_maintainance.cli sync-sw-industry --limit-members 2
python -m stock_maintainance.cli sync-concepts --limit-concepts 3
python -m stock_maintainance.cli sync-market-behavior-date 20260526
python -m stock_maintainance.cli sync-market-behavior-range 20260513 20260526
python -m stock_maintainance.cli create-views
python -m stock_maintainance.cli audit-quality
```

## Key Documents

- `docs/data_contract.md`
- `docs/variable_registry_design.md`
- `docs/tushare_api_feasibility_20260527.md`
- `docs/phase2_confirmation_checklist.md`
- `docs/phase2_start_summary.md`
- `docs/phase2_batch_progress.md`
- `docs/phase2_continuous_run_summary.md`
- `docs/base_variable_coverage_review.md`
- `docs/phase2_quality_and_views.md`
- `docs/phase2_contract_gap_review.md`
