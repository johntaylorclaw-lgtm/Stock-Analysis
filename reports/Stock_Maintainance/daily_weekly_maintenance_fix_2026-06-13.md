# 日常维护场景修复报告

生成时间：2026-06-13

## 根因判断

1. `daily-light` 的设计是“缺几天补几天”。当某个交易日已经有记录但源端后续补发、更正或早先接口返回空表时，后续日批可能因为没有新增缺口而跳过重拉，无法主动修复迟到数据。
2. 2026-06-08 的日批在 16:05 执行，`daily_basic`、市场行为和指数日行情等晚间 T+0 接口尚未完整发布，因此出现 warning。20:00 以后运行可显著缓解，但仅靠 daily-light 仍不能处理“已存在日期需要强制重拉”的场景。
3. 2026-06-12 的 `weekly-full` blocked 原因是 `audit_tmp_phase4_full_*` 参照快照表缺失；这不是字段对照失败，而是 weekly compare 没有可用参照基准。

## 已完成修复

| 项目 | 修复 |
|---|---|
| daily-full 模块 | 新增 `stock-maintain daily-full`，对指定最近交易日窗口强制重拉日频基础表、复权因子、市场行为、指数日行情，并重算衍生变量和刷新视图 |
| daily-full dry-run | dry-run 改为轻量计划，不再执行重型 feature dry-run，避免长时间持有 DuckDB 锁 |
| weekly-full 缺快照恢复 | 新增 `--auto-create-missing-snapshot`，缺少参照快照时自动创建快照并返回 `snapshot_created`，不伪装成 compare pass |
| Hermes/文档 | 更新 `config/hermes_agent.json`、Skill 命令手册和运行手册，加入 daily-full 和 weekly snapshot bootstrap 流程 |

## 实证验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_daily_full.py tests/test_weekly_full.py` | 9 passed |
| `.venv-wsl/bin/pytest -q tests/test_daily_full.py tests/test_daily_light.py tests/test_weekly_full.py` | 14 passed |
| `.venv-wsl/bin/pytest -q tests/test_daily_full.py tests/test_daily_light.py tests/test_weekly_full.py` | 16 passed，补充 daily-light/daily-full postcheck 收口规则后复测 |
| `.venv-wsl/bin/pytest -q` | 108 passed |
| `.venv-wsl/bin/stock-maintain daily-full --as-of-date 2026-06-12 --reload-trade-days 1 --dry-run --output-prefix daily_full_dry_run_20260612_v2` | 生成报告，status=`warning`，目标交易日为 2026-06-12 |
| `.venv-wsl/bin/stock-maintain weekly-full --as-of-date 2026-06-12 --auto-create-missing-snapshot --output-prefix weekly_auto_snapshot_20260612` | status=`snapshot_created`，创建 25 张参照快照 |
| `.venv-wsl/bin/stock-maintain weekly-full --as-of-date 2026-06-12 --output-prefix weekly_compare_after_snapshot_20260612` | status=`pass`，25 张表通过 |

## 后续建议

1. 日常 20:00 继续运行 `daily-light`。
2. 如果日批 warning 来自已存在日期的迟到源数据，使用 `daily-full --reload-trade-days 1` 强制修复。
3. 每周首次缺快照时运行 `weekly-full --auto-create-missing-snapshot`，随后再运行一次 `weekly-full` 完成独立 compare。
4. 后续可继续优化 `validate-daily` 的运行耗时，使 daily-full dry-run 更轻。
