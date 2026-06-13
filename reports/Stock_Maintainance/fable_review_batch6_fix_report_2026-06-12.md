# Fable 审计修复报告 Batch 6

生成时间：2026-06-12

## 修复范围

本批次继续处理 `D:\Opencode Workspace\audit\reports\15_独立项目Review报告.md` 中仍成立的中风险工程问题。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| M6 分红 TTM 存在重复计数和非交易日事件漏计风险 | 客观 | `derived_corporate_action` 构建改为使用去重后的 `dividend_latest`，并将非交易日分红事件映射到下一个可交易日 |
| M7 行业/概念上下文排名存在 NULL 行业分组和小样本误导 | 客观 | 行业内 rank/percentile 增加行业非空、值非空、有效样本数不低于 2 的保护 |
| M11 Tushare 客户端缺少分页能力 | 客观 | `TushareClient` 新增 `call_paged`，按 `limit/offset` 拉取并拼接结果 |
| M12 `sync_daily_range` 缺少逐日 resume/失败记录 | 客观 | 日区间同步新增逐交易日 `metadata_task_state` 与 `metadata_task_failure` 记录，并支持默认 resume |
| M13 `sync_dividend_batch` 在未提供 `end_date` 时不应用 `start_date` | 客观 | 分红批处理始终按 `ann_date >= start_date` 过滤；如提供 `end_date` 再追加上界 |
| M16 `reconcile_schema` 对 `derived_financial_growth` 大量缺列静默重建 | 客观 | 仅空表允许自动重建；非空表直接报错，要求显式迁移/重建 |

## 实际重建

| 对象 | 范围 | 行数 |
|---|---:|---:|
| `derived_corporate_action` | 2026-01-01 至 2026-06-11 | 570,165 |
| `derived_sector_concept_context` | 2026-01-01 至 2026-06-11 | 570,165 |

## 抽查结果

| 检查项 | 结果 |
|---|---:|
| `derived_corporate_action` 2026 窗口行数 | 570,165 |
| `2026-06-11` `cash_dividend_ttm` 非空/总行数 | 5,511 / 5,511 |
| `derived_sector_concept_context` 2026 窗口行数 | 570,165 |
| `sw_l2_code IS NULL` 但 `stock_mv_rank_industry IS NOT NULL` | 0 |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_cli_guardrails.py tests/test_corporate_action_script.py` | 9 passed |
| `.venv-wsl/bin/pytest -q` | 67 passed |
| `.venv-wsl/bin/stock-maintain validate-config` | passed |
| `.venv-wsl/bin/stock-maintain docs-check` | passed |
| `.venv-wsl/bin/stock-maintain create-views` | created analytical views |
| `.venv-wsl/bin/stock-maintain validate-daily --as-of-date 2026-06-11 --output-prefix fable_fix_batch6_validate_20260611` | warning |

## 剩余说明

`validate-daily` 的 warning 仍来自已识别的外部数据源限制或预期延迟：

| 项目 | 说明 |
|---|---|
| `margin_detail`、`northbound_holding` | 已纳入 expected-delay 口径 |
| 北交所 `stock_moneyflow_daily` 新股覆盖提醒 | 已实证 Tushare `moneyflow` 当前不返回 `.BJ` 数据，属于源限制 |

