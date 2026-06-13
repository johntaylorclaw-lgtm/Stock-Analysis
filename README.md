# Stock_Maintainance

A-share stock data maintenance project for base data, derived feature maintenance, daily incremental operation, weekly validation, and audit reporting.

This project does not implement stock selection, backtesting, model training, or future-return target labels.

## Current Status

- Phase 0-3: project rebuild, base warehouse, derived feature layers, documentation archive, and variable dictionary completed.
- Phase 4: incremental performance and guardrail work completed with remaining source-limitation warnings documented.
- Phase 5: daily/weekly operation, report summaries, Agent Skill wrapper, and audit repair loop are active.
- Runtime preference: use WSL from `/mnt/d/Opencode Workspace/Stock_Maintainance`.

## Common Commands

```bash
cd "/mnt/d/Opencode Workspace/Stock_Maintainance"

.venv-wsl/bin/stock-maintain validate-config
.venv-wsl/bin/stock-maintain docs-check
.venv-wsl/bin/stock-maintain create-views
.venv-wsl/bin/stock-maintain validate-daily --as-of-date 2026-06-11
```

Daily incremental run:

```bash
.venv-wsl/bin/stock-maintain daily-light --as-of-date 2026-06-11 --output-prefix daily_2026-06-11
.venv-wsl/bin/stock-maintain summarize-run --mode daily --run-id daily_2026-06-11
```

Weekly validation:

```bash
.venv-wsl/bin/stock-maintain weekly-full --as-of-date 2026-06-11
.venv-wsl/bin/stock-maintain summarize-run --mode weekly
```

Tests:

```bash
.venv-wsl/bin/pytest -q
```

Current verified result: 67 passed.

## Key Documents

- `docs/00_文档索引.md`
- `docs/01_项目设计总览.md`
- `docs/02_数据契约与基础变量.md`
- `docs/03_衍生变量设计.md`
- `docs/04_数据库结构与存储.md`
- `docs/05_Phase2基础库验收.md`
- `docs/06_Phase3衍生变量验收.md`
- `docs/07_运行维护与数据字典.md`
- `docs/08_审计验收与遗留事项.md`
- `docs/09_Phase4增量性能优化设计.md`
- `docs/10_Phase4执行记录与验收.md`
- `docs/11_Phase5验证文档交付闭环设计.md`
- `docs/12_Phase5执行记录与验收.md`
- `docs/13_AgentSkill运行手册与自动报告设计.md`
- `docs/14_运行手册.md`

## Main Outputs

- DuckDB database: `data/duckdb/stock_data.duckdb`
- Global variable dictionary: `outputs/global_variable_dictionary.xlsx`
- Reports: `reports/`
- Agent Skill: `Skill/stock-maintenance-ops/`

