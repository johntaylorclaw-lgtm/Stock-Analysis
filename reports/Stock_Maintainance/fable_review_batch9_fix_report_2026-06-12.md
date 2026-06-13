# Fable 审计修复报告 Batch 9

生成时间：2026-06-12

## 修复范围

本批次处理 M18：weekly-full 使用当前数据创建快照后立即自比，导致验证恒为通过。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| M18 `--create-snapshot-from-current` 自建快照后自比恒 pass | 客观 | 快照刷新与字段级比较拆分：创建快照时报告状态为 `snapshot_created`，不再执行同源 compare |
| M18 CLI 需要区分操作成功与验证通过 | 客观 | CLI 对 `snapshot_created` 返回 0 表示快照刷新操作成功；`WeeklyFullResult.passed` 仍只在独立 compare 通过时为 true |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_weekly_full.py` | 5 passed |
| `.venv-wsl/bin/pytest -q` | 71 passed |

## 运行语义

推荐流程：

1. 刷新参照快照：`.venv-wsl/bin/stock-maintain weekly-full --create-snapshot-from-current ...`
2. 独立比较：`.venv-wsl/bin/stock-maintain weekly-full ...`

第一步的 `snapshot_created` 只代表快照刷新成功，不代表数据一致性验证通过。

