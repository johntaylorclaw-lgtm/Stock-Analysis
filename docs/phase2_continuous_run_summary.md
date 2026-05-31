# Phase 2 连续执行记录

生成日期：2026-05-28

## 1. 执行口径

本轮在用户确认“无需进一步确认则继续执行 Phase2”后，持续推进基础库和财务增强数据建设。执行过程中未遇到 token 额度耗尽；遇到的数据格式问题均已定位并修正。

历史行情口径：

- 股票范围：全 A 股，含上市、退市、暂停上市状态主数据。
- 历史起点：2006-01-01。
- 行情批次：按交易日调用 `daily`、`daily_basic`、`stk_limit`。
- 复权因子：按股票调用 `adj_factor`。
- 财务报表：按股票调用 `income`、`balancesheet`、`cashflow`、`fina_indicator`。
- 财务增强事件：按股票调用稀疏事件接口，统一进入 `financial_event_raw` 并保留完整 `payload_json`。

## 2. 已完成的主要全量任务

1. 2006-01-01 至 2026-05-26 全市场日行情主干。
2. 2006-01-01 至 2026-05-26 全股票复权因子。
3. 默认指数池 2006-01-01 至 2026-05-26 指数日线。
4. 默认指数池 2006-01 至 2026-05 月度指数成分权重。
5. Tushare 概念基础表和概念成分全量。
6. 申万 2021 行业分类和行业成分全量。
7. 2006-01-01 至 2026-05-26 全股票四大财务表：
   - 利润表
   - 资产负债表
   - 现金流量表
   - 财务指标
8. 2006-01-01 至 2026-05-26 全股票财务增强事件 raw 表。

## 3. 当前核心表规模

| 表 | 行数 |
|---|---:|
| `stock_basic_info` | 5849 |
| `trade_calendar` | 7670 |
| `stock_daily` | 15295776 |
| `stock_daily_basic` | 15204489 |
| `stock_limit_price` | 17533118 |
| `stock_adj_factor` | 15653891 |
| `index_basic_info` | 7696 |
| `index_daily` | 63767 |
| `index_weight` | 2899016 |
| `concept_basic` | 879 |
| `concept_member` | 34444 |
| `sw_industry_classify` | 511 |
| `sw_industry_member` | 5847 |
| `financial_income_raw` | 294351 |
| `financial_balance_raw` | 272771 |
| `financial_cashflow_raw` | 297550 |
| `financial_indicator_raw` | 253004 |
| `financial_event_raw` | 16390985 |
| `metadata_task_state` | 135527 |
| `metadata_task_failure` | 4 |

当前 `metadata_task_state` 中未处理失败状态数量为 0。`metadata_task_failure` 保留 4 条历史失败记录，均为执行中已修复并补跑成功的数据格式问题。

## 4. 财务增强事件分布

| API | 行数 |
|---|---:|
| `express` | 28163 |
| `fina_audit` | 86452 |
| `fina_mainbz` | 828236 |
| `forecast` | 139145 |
| `pledge_detail` | 216610 |
| `repurchase` | 68573 |
| `share_float` | 10288758 |
| `stk_holdernumber` | 492451 |
| `top10_floatholders` | 2591488 |
| `top10_holders` | 1651109 |

`dividend`、`disclosure_date`、`pledge_stat` 在本轮按当前调用参数未写入记录，后续需要单独验证这些接口是否需要不同参数口径，或是否受权限/源端覆盖限制影响。

## 5. 执行中修正的问题

1. DuckDB 单文件写入不能并行执行多个写库进程。后续调度采用单写进程，读和质量检查可并行。
2. `fina_indicator` 个别历史记录 `ann_date` 为空。结构化表用 `end_date` 补充缺失公告日作为主键占位，原始空值保留在 `payload_json`。
3. `fina_mainbz` 等事件接口的 `end_date` 可能返回 `YYYY` 或 `YYYYMM`，已统一归一化为年末或月末日期，原始值保留在 `payload_json`。
4. 指数权重月度维护不能只查月初日期，已改为查询整月区间并保存源端实际返回的权重日期。

## 6. 下一步建议

Phase 2 下一步应进入质量审计和结构化视图建设：

1. 对 2006 至今的行情、估值、涨跌停做按年覆盖率报告。
2. 对财务 raw 表做空值率、重复主键、公告日/报告期完整性审计。
3. 将 `financial_event_raw` 中高价值事件拆成稳定结构化视图。
4. 对 `dividend`、`disclosure_date`、`pledge_stat` 做参数口径复核。
5. 建设前复权/后复权行情视图和基础日频宽表。
