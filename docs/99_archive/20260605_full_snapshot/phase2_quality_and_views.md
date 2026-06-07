# Phase 2 质量审计与视图建设记录

生成日期：2026-05-29

## 1. 已完成

本次完成 Phase 2 后半段的第一轮建设：

1. 生成基础变量 Excel 数据字典。
2. 核对基础变量注册覆盖情况。
3. 建设复权行情视图。
4. 建设基础日频宽表视图。
5. 建设财务标准化视图。
6. 拆分 `financial_event_raw` 中的高价值事件结构化视图。
7. 生成质量审计和覆盖率报告。

## 2. 新增视图

行情与日频：

- `stock_price_adjusted`
- `stock_base_daily`

财务标准化：

- `financial_income`
- `financial_balance`
- `financial_cashflow`
- `financial_indicator`

财务事件结构化：

- `financial_event_forecast`
- `financial_event_audit`
- `financial_event_mainbz`
- `financial_event_holdernumber`
- `financial_event_top10_holders`
- `financial_event_pledge_detail`
- `financial_event_repurchase`
- `financial_event_share_float`

## 3. 质量报告

报告文件：

- `reports/quality_audit_report.md`
- `reports/quality_table_counts.csv`
- `reports/quality_year_coverage.csv`
- `reports/quality_null_checks.csv`
- `reports/quality_duplicate_checks.csv`
- `reports/quality_view_counts.csv`

关键结论：

1. 2006-2025 年 `stock_daily` 和 `stock_daily_basic` 的交易日覆盖率为 100%。
2. 2026 年当前覆盖至 2026-05-26，对应 92 个交易日。
3. `stock_limit_price` 在 2006 年无返回，属于源端早期接口覆盖缺失，需要在变量使用层标记为源端不可用区间。
4. 当前核心空值/非正值检查未发现问题。
5. 当前主键重复检查未发现问题。

## 4. 视图行数

| 视图 | 行数 |
|---|---:|
| `stock_price_adjusted` | 15295776 |
| `stock_base_daily` | 15295776 |
| `financial_income` | 294351 |
| `financial_balance` | 272771 |
| `financial_cashflow` | 297550 |
| `financial_indicator` | 253004 |
| `financial_event_forecast` | 139145 |
| `financial_event_audit` | 86452 |
| `financial_event_mainbz` | 828236 |
| `financial_event_holdernumber` | 492451 |
| `financial_event_top10_holders` | 4242597 |
| `financial_event_pledge_detail` | 216610 |
| `financial_event_repurchase` | 68573 |
| `financial_event_share_float` | 10288758 |

## 5. 后续建议

1. 基于 Excel 的 `Coverage_Gaps` 审阅并批量补齐 `base_variables.json`。
2. 为复权行情视图补充变量注册项：`open_hfq`、`close_hfq`、`open_qfq_current`、`close_qfq_current` 等。
3. 为标准财务视图补充变量注册项。
4. 对事件结构化视图继续增加高价值字段和字段中文说明。
5. 将质量审计加入日常更新后的固定检查步骤。
