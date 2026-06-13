# Fable 审计修复报告 Batch 14

生成时间：2026-06-12

## 修复范围

本批次处理 M4 的元数据部分：`latest_adj_factor_asof` 名称含 `asof`，但实际是当前样本库最新复权因子，用于前复权当前尺度展示，不是点时安全变量。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| M4 `latest_adj_factor_asof` 元数据误标 PIT | 客观 | 变量注册表中 `point_in_time` 改为 `false` |
| M4 字段含义容易误导 | 客观 | 中文名、公式和 schema 描述改为“当前样本最新复权因子 / 前复权当前尺度锚点” |

## 未改动说明

本批次不改字段名和落库数值，避免破坏既有视图与导出字段。字段继续服务于 `*_qfq` 当前尺度展示；连续历史统计仍使用 `*_hfq`。

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/stock-maintain docs-generate` | regenerated |
| `.venv-wsl/bin/stock-maintain refresh-dictionary --output-prefix fable_fix_adj_factor_dictionary` | pass |
| `.venv-wsl/bin/pytest -q tests/test_docs.py` | 4 passed |
| `.venv-wsl/bin/pytest -q` | 78 passed |

