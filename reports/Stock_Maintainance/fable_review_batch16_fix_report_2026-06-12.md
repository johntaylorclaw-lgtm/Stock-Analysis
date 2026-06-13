# Fable 审计修复报告 Batch 16

生成时间：2026-06-12

## 修复范围

本批次处理两个运行中发现的实际缺陷：

1. `derived_financial_asof` 的财务报表存在性标志在部分缺失场景下返回 `NULL`，不利于下游稳定消费。
2. `validate-daily --as-of-date` 在数据库已经有更新交易日数据时，验证锚点可能取到超过指定 `as_of_date` 的最新衍生日，导致验证对象偏离用户指定日期。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| 财务 asof 报表存在性标志可能为 `NULL` | 客观 | `has_income_statement`、`has_balance_sheet`、`has_cashflow_statement`、`has_indicator_statement` 统一 `coalesce(..., false)`，缺失时输出明确布尔值 |
| `validate-daily` 指定 `as_of_date` 时锚点未受截止日约束 | 客观 | 新增 `_table_max_date_on_or_before`，验证锚点限定为不晚于最新待验证交易日 |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/stock-maintain build-features --module financial_asof --start-date 2026-06-01 --end-date 2026-06-11 --mode daily --allow-confirmed-history` | 成功，写入 49,604 行 |
| `.venv-wsl/bin/pytest -q tests/test_financial_pit.py tests/test_daily_validate.py` | 11 passed |
| `.venv-wsl/bin/stock-maintain validate-daily --as-of-date 2026-06-11 --output-prefix fable_fix_batch16_validate_20260611_v2` | warning；覆盖率问题 0，重复问题 0，仅 `margin_detail`、`northbound_holding` 属于预期源延迟 |
| `.venv-wsl/bin/pytest -q` | 81 passed |

## 说明

本批次未改变财务 PIT 映射口径，只修正缺失标志的可消费性；`validate-daily` 的锚点修复后，指定历史日期的验证不会被之后已经落库的交易日污染。
