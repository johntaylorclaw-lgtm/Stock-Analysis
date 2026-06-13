# Fable 审计修复报告 Batch 24

生成时间：2026-06-12

## 修复范围

本批次处理 Fable 审计中的 L2 剩余问题：`next_disclosure_pre_date` 与 `days_to_next_disclosure` 在 `derived_financial_asof` 中为硬编码 `NULL` 占位。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L2 下一次披露计划字段硬编码为空 | 客观 | 使用 `financial_disclosure_schedule` 映射不早于交易日的下一次计划披露日期 |
| L2 披露字段字典未说明真实口径 | 客观 | 更新 `derived_variables.json`、生成版 Markdown 字典和全局 Excel/JSON 字典 |

## 口径

`next_disclosure_pre_date = min(coalesce(pre_date, actual_date, modify_date, ann_date))`，条件为同一 `ts_code` 且披露计划日不早于 `trade_date`。

`days_to_next_disclosure = date_diff('day', trade_date, next_disclosure_pre_date)`。

当前真实库 2026-06-01 至 2026-06-11 窗口该字段仍为空，原因是现有 `financial_disclosure_schedule` 未覆盖这些交易日之后的未来披露计划；这属于基础数据覆盖现状，不是衍生 SQL 失败。

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_financial_pit.py tests/test_docs.py` | 9 passed |
| `.venv-wsl/bin/stock-maintain build-features --module financial_asof --start-date 2026-06-01 --end-date 2026-06-11 --mode daily --allow-confirmed-history` | 成功，写入 49,604 行 |
| `.venv-wsl/bin/stock-maintain docs-generate` | passed |
| `.venv-wsl/bin/stock-maintain refresh-dictionary --output-prefix global_variable_dictionary` | pass，`docs_diff_count=0` |
| `.venv-wsl/bin/pytest -q` | 92 passed |

## 说明

本批次采用可获取的披露计划基础表实现，不引入预测或评分逻辑；无未来计划时保留空值，符合事实层原则。
