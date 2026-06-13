# Fable 审计修复报告 Batch 17

生成时间：2026-06-12

## 修复范围

本批次处理 Fable 审计中的 L4、L14、L18 三项低风险但确定客观的问题：

1. `cache_steps.py` 存在未使用的 `_update_from_temp_sql` 死代码，且其内部 `information_schema` 判断方式不可靠。
2. `incremental_compare.py` 的窗口日期用 SQL 字符串拼接，和项目参数绑定风格不一致。
3. `daily_validate.py`、`weekly_full.py` 的交易日历读取在多交易所日历入库时可能重复计数。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L4 `_update_from_temp_sql` 死代码 | 客观 | 删除未使用函数，保留实际使用的 temp upsert 路径 |
| L14 增量对照日期 SQL 拼接 | 客观 | 当前表/快照表窗口改为参数绑定生成临时表，再进行后续比较 |
| L18 多交易所交易日历重复计数 | 客观 | 日常验证和周验证的交易日列表均改为按 `cal_date` 去重，兼容全 A 市场而非硬过滤单一交易所 |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_incremental_compare.py tests/test_daily_validate.py tests/test_weekly_full.py` | 18 passed |
| `.venv-wsl/bin/pytest -q` | 83 passed |

## 说明

交易日历采用 `DISTINCT cal_date` 而不是限定 `exchange='SSE'`，原因是本工程维护全 A 市场和北交所，同一日期多交易所重复应去重，但不应在工程层面预设只有上交所日历才是有效日历。
