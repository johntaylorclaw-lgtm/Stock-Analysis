# Fable 审计修复报告 Batch 20

生成时间：2026-06-12

## 修复范围

本批次处理 Fable 审计中的 L21：`validate-daily` 在首跑空库时可能把缺失锚点解释为“当前已到最新交易日”，从而形成误导性的通过或弱告警。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L21 空库首跑可能静默通过 | 客观 | 当 `stock_daily`/`derived_daily_spine` 均没有可用锚点，且目标验证表也没有任何日期数据时，报告状态改为 `blocked` 并输出 `blocked_reason` |
| L21 事件表单独验证误阻塞边界 | 客观 | 若锚点表为空但目标表自身已有日期数据，则不触发空库阻断，允许单表质量检查继续运行 |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_daily_validate.py` | 10 passed |
| `.venv-wsl/bin/pytest -q` | 89 passed |

## 说明

该修复用于首跑引导和空库防误判；正常日批仍以 `derived_daily_spine` 优先、`stock_daily` 兜底作为锚点。
