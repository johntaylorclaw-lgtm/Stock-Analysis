# Operations

## Daily Operation

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

## Weekly Operation

1. Run `weekly-full --dry-run`.
2. Run `weekly-full`.
3. Run `summarize-run --mode weekly --run-id <weekly_run_id>`.
4. Report the Markdown summary path.

Weekly acceptance:

- 24 tables checked.
- 24 tables pass.
- key differences are 0.
- field differences are 0.
- If requested and actual compare windows differ, mention snapshot window alignment.

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
