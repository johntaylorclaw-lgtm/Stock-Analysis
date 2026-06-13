# Operations

## Daily Operation

Default schedule: 20:00 Asia/Shanghai local time.

1. Run `daily-light --dry-run`.
2. If status is `blocked`, stop and report the reason.
3. Run `daily-light` only when the dry-run window is acceptable.
4. Run `summarize-run --mode daily --run-id <daily_run_id>`.
5. Report the Markdown summary path.

Daily acceptance:

- `daily-light` status is `pass`.
- precheck and postcheck are `pass`.
- If incremental trade days are 0, confirm `sync-master` still ran.
- New stock and delisting updates are handled by `sync-master`.
- `margin_detail` and `northbound_holding` latest-date gaps are expected T+1 source delays when validation marks them as expected delay.

## Daily Full Repair

Use `daily-full` when a date should be force reloaded even if it already exists in the database. Common triggers:

- Tushare T+0 data arrived after the daily-light run.
- A prior daily-light run skipped because incremental trade days were 0.
- Recent daily source tables or derived features need a one-to-ten day repair window.

Run:

```bash
.venv-wsl/bin/stock-maintain daily-full \
  --as-of-date <YYYY-MM-DD> \
  --reload-trade-days 1 \
  --output-prefix <run_id>
```

Use `--refresh-weekly-snapshot` after a repair if the weekly reference snapshot should be rebuilt from the repaired current data.

## Weekly Operation

1. Run `weekly-full --dry-run`.
2. Run `weekly-full --auto-create-missing-snapshot`.
3. Run `summarize-run --mode weekly --run-id <weekly_run_id>`.
4. Report the Markdown summary path.

Weekly acceptance:

- 25 tables checked.
- 25 tables pass.
- key differences are 0.
- field differences are 0.
- If requested and actual compare windows differ, mention snapshot window alignment.
- If the result is `snapshot_created`, rerun weekly-full once more without snapshot creation to complete the independent compare.

## Dictionary Operation

Run:

```bash
.venv-wsl/bin/stock-maintain refresh-dictionary --output-prefix <run_id>
```

Acceptance:

- feature view schemas are synced.
- generated docs are refreshed.
- `global_variable_dictionary.xlsx` exists.
- `docs-check` passes.

## Repair Operation

If the requested repair exceeds 10 trade days:

1. Do not run automatically.
2. Produce a plan.
3. Ask for explicit confirmation.
4. After repair, run targeted validation and weekly/full comparison when applicable.

## Sample Operation

Use `sample-stock` for human review. Keep sample output in `outputs/phase5/` or the current phase output directory.
