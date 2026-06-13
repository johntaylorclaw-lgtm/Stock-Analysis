# Fable 审计修复报告 Batch 18

生成时间：2026-06-12

## 修复范围

本批次处理 Fable 审计中的 L16、L17：

1. `daily-light` 未显式传入 `as_of_date` 时默认使用自然日今天，盘中或数据发布前可能把尚不可得的当日算入缺口。
2. Parquet 分区出口先删除旧文件再写新文件，进程中断时可能留下缺失分区；同时 `ORDER BY ts_code` 对无 `ts_code` 的来源表不稳。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L16 daily-light 默认日期可能过早 | 客观 | 无显式 `as_of_date` 时，先按请求自然日刷新/读取交易日历，再解析为不晚于该日的最新开市日；显式传参仍原样尊重 |
| L17 Parquet 非原子覆盖 | 客观 | 分区写入改为 `part.parquet.tmp` 临时文件成功后 `replace` 原子替换；写前不再删除旧分区文件 |
| L17 导出日期/排序边界 | 客观 | 增加 `YYYY-MM-DD` 日期格式校验；导出排序按 `trade_date`，有 `ts_code` 时追加 `ts_code` |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_daily_light.py tests/test_phase4_export.py` | 7 passed |
| `.venv-wsl/bin/stock-maintain validate-config` | passed |
| `.venv-wsl/bin/pytest -q` | 86 passed |

## 说明

`daily-light` 的默认日期解析选择“最新开市日”而不是“昨天”，可以覆盖周末、节假日和临时休市等情况；用户显式指定历史或当日日期时，系统不额外改写用户意图。
