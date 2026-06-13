# Fable 审计修复报告 Batch 22

生成时间：2026-06-12

## 修复范围

本批次处理 Fable 审计中的 L26：`north_money_zscore_{n}` 只有标准差非零守门，序列起点可能用短窗口计算 z-score。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L26 北向资金 z-score 无最小样本数守门 | 客观 | `north_money_zscore_{20,60,120,250}` 增加 `count(north_money) >= n` 完整窗口守门 |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_capital_flow_cache_script.py` | 1 passed |
| `.venv-wsl/bin/stock-maintain build-features --module capital_flow --start-date 2026-06-01 --end-date 2026-06-11 --mode daily --allow-confirmed-history` | 成功；`derived_capital_flow` 49,604 行，缓存合计 99,208 行 |
| `.venv-wsl/bin/pytest -q` | 91 passed |

## 说明

该口径会使每个 z-score 周期的前 `n-1` 个有效观测输出为空，更符合完整周期变量的语义。
