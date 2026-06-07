# Phase 3 行业概念与指数市场上下文审计报告

生成时间：2026-06-03T22:00:00

## 1. 表与视图覆盖

| 对象 | 行数 | 实体数 | 起始日期 | 截止日期 | 字段数 |
|---|---:|---:|---|---|---:|
| `derived_sw_industry_member_enhanced` | 5,847 | 5847 | 1989-11-01 | 2026-04-22 | 12 |
| `derived_sector_daily_cache` | 762,770 | 162 | 2006-01-04 | 2026-05-26 | 97 |
| `derived_concept_daily_cache` | 4,265,393 | 873 | 2006-01-04 | 2026-05-26 | 89 |
| `derived_concept_stock_context_cache` | 15,295,776 | 5809 | 2006-01-04 | 2026-05-26 | 224 |
| `derived_sector_concept_context` | 15,295,776 | 5809 | 2006-01-04 | 2026-05-26 | 104 |
| `derived_sector_concept_context_full_v` | 15,295,776 | 5809 | 2006-01-04 | 2026-05-26 | 356 |
| `derived_index_daily_cache` | 63,767 | 14 | 2006-01-04 | 2026-05-26 | 29 |
| `derived_index_membership_cache` | 15,295,776 | 5809 | 2006-01-04 | 2026-05-26 | 19 |
| `derived_index_market_context` | 15,295,776 | 5809 | 2006-01-04 | 2026-05-26 | 105 |
| `derived_index_market_context_full_v` | 15,295,776 | 5809 | 2006-01-04 | 2026-05-26 | 260 |

## 2. 关键字段非空率

### derived_concept_stock_context_cache

| 字段 | 非空行数 | 非空率 |
|---|---:|---:|
| `concept_count` | 13,692,290 | 89.52% |
| `concept_ids_all` | 13,692,290 | 89.52% |
| `concept_ids_top_2` | 13,691,173 | 89.51% |
| `concept_ids_top_20` | 13,670,550 | 89.37% |
| `concept_active_ids_120` | 13,692,290 | 89.52% |

### derived_sector_concept_context

| 字段 | 非空行数 | 非空率 |
|---|---:|---:|
| `sw_l1_code` | 12,196,783 | 79.74% |
| `sw_l2_code` | 12,196,783 | 79.74% |
| `concept_count` | 15,295,776 | 100.00% |
| `concept_ids_top_20` | 13,692,290 | 89.52% |
| `sw_l2_ret_20` | 12,183,127 | 79.65% |
| `stock_ret_rank_industry_20` | 15,295,776 | 100.00% |

### derived_sector_concept_context_full_v

| 字段 | 非空行数 | 非空率 |
|---|---:|---:|
| `concept_ids_top_2` | 13,691,173 | 89.51% |
| `concept_lagging_ids_30` | 13,659,068 | 89.30% |
| `concept_active_ids_60` | 13,692,290 | 89.52% |
| `concept_narrow_leading_ids_250` | 13,308,526 | 87.01% |

### derived_index_market_context

| 字段 | 非空行数 | 非空率 |
|---|---:|---:|
| `market_up_ratio` | 15,295,776 | 100.00% |
| `hs300_ret_20` | 15,271,865 | 99.84% |
| `stock_excess_hs300_20` | 14,796,205 | 96.73% |
| `index_member_count` | 15,295,776 | 100.00% |
| `primary_index_code` | 5,974,223 | 39.06% |

## 3. 口径说明

- 申万行业一、二级成员已通过 `index_member_all(l2_code=...)` 实证并同步，增强成员表包含 L1/L2/L3 字段；三级字段暂不进入核心上下文。
- 概念成员缺少可靠进出日期，第一阶段按静态暴露处理。
- 概念多周期列表已通过 `derived_concept_stock_context_cache` 物理缓存实现，完整视图扩展 2/3/5/10/20/30/60/120/250 日领涨、领跌、活跃、窄口径领涨和统计字段。
- 指数权重按最近月度 asof 展开，最长回看 90 天。

## 4. 最近交易日视图抽检

- `derived_sector_concept_context_full_v` 最新交易日行数：5,504
- `derived_index_market_context_full_v` 最新交易日行数：5,504
