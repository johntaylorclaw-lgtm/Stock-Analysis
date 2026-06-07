# Hermes Agent

Hermes Agent is responsible for post-run checking and handoff summaries.

Hermes runs after the operational command has completed:

1. After daily-light:

```bash
.venv-wsl/bin/stock-maintain summarize-run --mode daily --run-id <daily_run_id>
```

2. After weekly-full:

```bash
.venv-wsl/bin/stock-maintain summarize-run --mode weekly --run-id <weekly_run_id>
```

3. For current status:

```bash
.venv-wsl/bin/stock-maintain summarize-run --mode status --as-of-date <YYYY-MM-DD>
```

Hermes output should be Markdown-first and factual:

- status
- date window
- incremental trade days
- pass/fail counts
- blocker if any
- summary report path
- source report path

Hermes must not:

- make investment recommendations;
- generate subjective scores;
- silently run history windows over 10 trade days;
- overwrite full-reference snapshots without explicit instruction.
