# Fable 审计修复报告 Batch 23

生成时间：2026-06-12

## 修复范围

本批次处理 Fable 审计中的 L5：资金流缓存实际读取上下文为 520 个交易日，但 `docs/11_Phase4增量窗口与脚本分类.md` 写成 260 个交易日。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L5 资金流缓存文档与实现不一致 | 客观 | 文档改为“缓存读取窗口默认向前 520 个交易日；核心表 `capital_flow` 仍按 250 日读取窗口规划” |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/stock-maintain docs-check` | docs are up to date |

## 说明

该项属于文档漂移。代码中 `refresh_capital_flow_caches` 的 `context_days = 520` 保持不变，原因是缓存层要覆盖北向和事件类长窗口上下文。
