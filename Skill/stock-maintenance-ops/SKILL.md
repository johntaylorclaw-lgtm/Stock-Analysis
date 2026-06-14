---
name: stock-maintenance-ops
description: Use this skill in the Stock_Maintainance project for Hermes Agent operations: daily-light follow-up checks, daily-full repair summaries, weekly-full follow-up checks, status summaries, dictionary refreshes, sample review, and maintenance handoff reports.
---

# Stock Maintenance Ops

Use this skill only inside:

```bash
cd "/mnt/d/Opencode Workspace/Stock_Maintainance"
```

Always use WSL project commands:

```bash
.venv-wsl/bin/stock-maintain <command>
```

## Hermes Agent Role

Hermes Agent is the reporting and handoff agent for this project. Hermes does not design investment strategy and does not create subjective scores. Hermes runs after maintenance commands and produces factual Markdown summaries.

Default daily schedule: 20:00 Asia/Shanghai local time. This timing is intentional because several T+0 Tushare APIs publish in the evening window.

Default follow-up rules:

1. After `daily-light`, run:

```bash
.venv-wsl/bin/stock-maintain summarize-run --mode daily --run-id <daily_run_id>
```

2. After `weekly-full`, run:

```bash
.venv-wsl/bin/stock-maintain summarize-run --mode weekly --run-id <weekly_run_id>
```

3. After `daily-full`, run:

```bash
.venv-wsl/bin/stock-maintain summarize-run --mode daily-full --run-id <daily_full_run_id>
```

4. For current status, run:

```bash
.venv-wsl/bin/stock-maintain summarize-run --mode status --as-of-date <YYYY-MM-DD>
```

## Command Map

| Intent | Command |
|---|---|
| Current status | `summarize-run --mode status` |
| Daily preflight | `daily-light --dry-run` |
| Daily execution | `daily-light` at 20:00 local time |
| Daily report | `summarize-run --mode daily --run-id <run_id>` |
| Daily forced reload | `daily-full` |
| Daily forced reload report | `summarize-run --mode daily-full --run-id <run_id>` |
| Weekly validation | `weekly-full` |
| Weekly report | `summarize-run --mode weekly --run-id <run_id>` |
| Refresh dictionary | `refresh-dictionary` |
| Sample one stock | `sample-stock --ts-code <ts_code>` |

## Safety Rules

1. Do not auto-run history windows over 10 trade days unless the user explicitly confirms.
2. Do not auto-trigger independent full rebuild snapshots; shadow rebuild is a separate design task.
3. Do not handwrite Excel dictionary commands; use `refresh-dictionary`.
4. Do not generate investment recommendations, labels, rankings as advice, or subjective scoring.
5. If a report status is `blocked` or `fail`, stop and summarize the blocker.
6. If only `margin_detail` or `northbound_holding` is missing for the latest trade date, treat it as expected T+1 source delay and cite the validation report.

## References

Read only as needed:

- `references/commands.md` for CLI parameters.
- `references/operations.md` for daily, weekly, repair, dictionary, and sample workflows.
- `references/reports.md` for report paths and acceptance criteria.
- `references/hermes_agent.md` for Hermes-specific handoff behavior.
