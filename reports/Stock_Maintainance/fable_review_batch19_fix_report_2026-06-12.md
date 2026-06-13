# Fable 审计修复报告 Batch 19

生成时间：2026-06-12

## 修复范围

本批次处理 Fable 审计中的 L19：基础入库转换函数 `add_updated_at` 使用 naive UTC，而运行报告使用本地时间，导致时间戳口径混用。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L19 `updated_at` 使用 naive UTC | 客观 | `add_updated_at` 改为 Asia/Shanghai 本地时间，并保持数据库字段为无时区 `TIMESTAMP`，避免引入迁移 |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_transform.py tests/test_daily_light.py tests/test_phase4_export.py` | 11 passed |
| `.venv-wsl/bin/stock-maintain docs-check` | passed |
| `.venv-wsl/bin/pytest -q` | 88 passed |

## 说明

本次只修正 Python 入库转换层的时间戳。衍生 SQL 中的 `CURRENT_TIMESTAMP` 属 DuckDB 执行时间，未在本批次做结构迁移；如后续需要严格统一所有 SQL 生成时间，可作为时间戳专项处理。
