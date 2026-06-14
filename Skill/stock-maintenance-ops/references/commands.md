# Commands

Run from:

```bash
cd "/mnt/d/Opencode Workspace/Stock_Maintainance"
```

Use:

```bash
.venv-wsl/bin/stock-maintain <command>
```

## daily-light

Preflight:

```bash
.venv-wsl/bin/stock-maintain daily-light \
  --as-of-date <YYYY-MM-DD> \
  --dry-run \
  --output-prefix <run_id>
```

Execute:

```bash
.venv-wsl/bin/stock-maintain daily-light \
  --as-of-date <YYYY-MM-DD> \
  --output-prefix <run_id>
```

Optional flags:

- `--include-financial`
- `--include-index-weight`
- `--allow-confirmed-history`

## daily-full

Use this when daily-light skipped an already-present date, source data arrived late, or a recent date needs a forced reload:

```bash
.venv-wsl/bin/stock-maintain daily-full \
  --as-of-date <YYYY-MM-DD> \
  --reload-trade-days 1 \
  --output-prefix <run_id>
```

For a recent repair window and weekly snapshot refresh:

```bash
.venv-wsl/bin/stock-maintain daily-full \
  --as-of-date <YYYY-MM-DD> \
  --reload-trade-days <N> \
  --refresh-weekly-snapshot \
  --output-prefix <run_id>
```

## weekly-full

```bash
.venv-wsl/bin/stock-maintain weekly-full \
  --as-of-date <YYYY-MM-DD> \
  --auto-create-missing-snapshot \
  --output-prefix <run_id>
```

Use `--dry-run` for preflight.

## summarize-run

```bash
.venv-wsl/bin/stock-maintain summarize-run --mode status --as-of-date <YYYY-MM-DD>
.venv-wsl/bin/stock-maintain summarize-run --mode daily --run-id <daily_run_id>
.venv-wsl/bin/stock-maintain summarize-run --mode daily-full --run-id <daily_full_run_id>
.venv-wsl/bin/stock-maintain summarize-run --mode weekly --run-id <weekly_run_id>
.venv-wsl/bin/stock-maintain summarize-run --mode phase --phase phase5
```

## refresh-dictionary

```bash
.venv-wsl/bin/stock-maintain refresh-dictionary --output-prefix <run_id>
```

## sample-stock

```bash
.venv-wsl/bin/stock-maintain sample-stock \
  --ts-code <ts_code> \
  --start-date <YYYY-MM-DD> \
  --end-date <YYYY-MM-DD> \
  --rows 5 \
  --output-prefix <run_id>
```
