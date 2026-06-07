# Phase 3 Ownership Governance 审计报告

- 生成时间：2026-06-05 22:08:53
- 数据库：`/mnt/d/Opencode Workspace/Stock_Maintainance/data/duckdb/stock_data.duckdb`

## 1. 表规模

| 项目 | 结果 |
|---|---:|
| 核心物理表列数 | 63 |
| 完整视图列数 | 98 |
| 持有人集中度视图列数 | 10 |
| 事件时间线视图列数 | 12 |
| 核心表行数 | 15,295,776 |
| 覆盖股票数 | 5,809 |
| 覆盖交易日数 | 4,951 |
| 日期范围 | 2006-01-04 至 2026-05-26 |

## 2. 来源对象行数

| 对象 | 行数 |
|---|---:|
| `financial_pledge_stat` | 2,204,384 |
| `financial_pledge_detail` | 216,610 |
| `financial_holder_number` | 492,451 |
| `financial_top10_holders` | 1,651,109 |
| `financial_top10_float_holders` | 2,591,488 |
| `derived_ownership_governance` | 15,295,776 |
| `derived_ownership_governance_full_v` | 15,295,776 |
| `ownership_holder_concentration_v` | 477,251 |
| `ownership_governance_event_timeline_v` | 7,156,042 |

## 3. 核心字段覆盖率

| 字段 | 非空行数 | 全历史覆盖率 | 最新交易日非空数 |
|---|---:|---:|---:|
| `pledge_ratio_asof` | 10,118,669 | 66.1534% | 4,180 |
| `pledge_ratio_ge_10_flag` | 10,118,669 | 66.1534% | 4,180 |
| `pledge_ratio_ge_30_flag` | 10,118,669 | 66.1534% | 4,180 |
| `pledge_ratio_ge_50_flag` | 10,118,669 | 66.1534% | 4,180 |
| `holder_num_asof` | 14,954,262 | 97.7673% | 5,448 |
| `holder_num_to_total_share` | 14,942,579 | 97.6909% | 5,448 |
| `holder_num_to_free_share` | 14,937,545 | 97.6580% | 5,448 |
| `top10_holder_ratio_latest` | 14,640,211 | 95.7141% | 5,476 |
| `top10_float_holder_ratio_latest` | 14,436,933 | 94.3851% | 5,456 |
| `ownership_concentration_ratio_latest` | 14,806,178 | 96.7991% | 5,496 |
| `ownership_data_completeness_ratio` | 15,295,776 | 100.0000% | 5,504 |

## 4. Point-in-time 与唯一性检查

| 检查项 | 结果 |
|---|---:|
| 主键重复组数 | 0 |
| 股东户数公告日晚于交易日行数 | 0 |
| 十大股东公告日晚于交易日行数 | 0 |
| 质押统计有效日晚于交易日行数 | 0 |
| 质押阈值三档非单调行数 | 0 |
| 名单变动字段非0/1行数 | 0 |

## 5. 完整视图运行检查

| 字段 | 最新交易日非空数 |
|---|---:|
| `top1_holder_name_latest` | 5,476 |
| `top10_institution_holder_ratio_latest` | 5,476 |
| `top1_float_holder_name_latest` | 5,456 |
| `pledge_detail_active_count_asof` | 5,504 |

## 6. 结论

- `derived_ownership_governance` 已按 ownership/governance 第一阶段边界落库：质押、股东户数、十大股东、十大流通股东。
- 质押统计使用 `pledge_stat.end_date` 作为 as-of 有效日；股东户数和十大股东使用公告日进行 point-in-time 广播。
- 高质押阈值采用 10/30/50 三档事实标识，不引入评价分。
- Tushare 百分比/比例字段在核心表中保留来源口径；HHI 内部按百分数除以 100 后计算。
