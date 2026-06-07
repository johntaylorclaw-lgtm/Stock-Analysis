# Phase 3 持有人治理模块设计

生成日期：2026-06-05  
状态：已实施并审计通过。

实施日期：2026-06-05  
审计报告：`reports/phase3_ownership_governance_audit.md`

## 0. 实施摘要

本模块已完成第一阶段边界内的全量历史构建：

| 对象 | 类型 | 实际列数 | 行数/状态 |
|---|---|---:|---:|
| `derived_ownership_governance` | 物理表 | 63 | 15,295,776 |
| `derived_ownership_governance_full_v` | 视图 | 98 | 15,295,776 |
| `ownership_holder_concentration_v` | 视图 | 10 | 477,251 |
| `ownership_governance_event_timeline_v` | 视图 | 12 | 7,156,042 |

关键口径：

1. 第一阶段只纳入质押、股东户数、十大股东、十大流通股东；实控人、董监高和管理层暂不纳入。
2. `financial_pledge_stat` 使用 `end_date` 作为 as-of 有效日。
3. 股东户数、十大股东、十大流通股东使用 `ann_date <= trade_date` 控制 point-in-time。
4. 高质押事实标记采用 10/30/50 三档：`pledge_ratio_ge_10_flag`、`pledge_ratio_ge_30_flag`、`pledge_ratio_ge_50_flag`。
5. Tushare 比例字段在核心表保留来源口径；HHI 内部按百分数除以 100 后计算。
6. 持有人分散度代理同时提供总股本和自由流通股本口径：`holder_num_to_total_share`、`holder_num_to_free_share`。
7. 股东类型归一化和名单变动进入完整视图，不进入核心物理表。

## 1. 模块定位

`ownership_governance` 维护股东结构、股权集中度、股东户数、股权质押和重要持有人事件等事实变量。它承接 `corporate_action` 明确排除的质押、股东户数、十大股东和十大流通股东数据，作为治理结构和持有人行为的独立模块。

本模块不生成主观评分，不输出买卖信号，不判断“好公司/坏公司”。字段只描述事实状态、变化幅度、集中度、活跃度和事件可得性。

## 2. 与其他模块的边界

| 模块 | 是否纳入本模块 | 边界说明 |
|---|---|---|
| 股权质押统计 | 是 | `pledge_stat` 和 `financial_pledge_stat` 进入核心物理表 |
| 股权质押明细 | 是 | `financial_pledge_detail` 进入完整视图和事件时间线 |
| 股东户数 | 是 | `financial_holder_number` 进入核心表，构造户数变化和集中度代理 |
| 十大股东 | 是 | `financial_top10_holders` 进入核心表/完整视图 |
| 十大流通股东 | 是 | `financial_top10_float_holders` 进入核心表/完整视图 |
| 回购、解禁、分红 | 否 | 已进入 `corporate_action` |
| 北向持股 | 否 | 已进入 `capital_flow`，属于资金参与者而非公司治理 |
| 实控人、董监高、管理层 | 暂不纳入 | 当前基础库未稳定维护；后续可作为治理源扩展 |
| 主营构成、审计意见 | 否 | 已进入 `corporate_action` |

## 3. 可用基础数据

| 数据入口 | 当前状态 | 主要用途 |
|---|---|---|
| `financial_pledge_stat` / `pledge_stat` | 已结构化，约 220 万行 | 股票级质押比例、质押笔数、未解押/已解押质押量 |
| `financial_pledge_detail` | 已从 `financial_event_raw` 拆出，约 21.7 万行 | 股东级质押、解押、质押起止日期和持有人信息 |
| `financial_holder_number` | 已从 `financial_event_raw` 拆出，约 49.2 万行 | 股东户数及报告期变化 |
| `financial_top10_holders` | 已从 `financial_event_raw` 拆出，约 165 万行 | 十大股东持股、占比、变化、股东类型 |
| `financial_top10_float_holders` | 已从 `financial_event_raw` 拆出，约 259 万行 | 十大流通股东持股、占比、变化、股东类型 |
| `stock_daily_basic` | 已落库 | 总股本、流通股本、自由流通股本、市值，辅助归一化 |
| `derived_daily_spine` | 已落库 | 日频主干、股票状态、市场板块、交易日对齐 |

## 4. 表结构方案

| 对象 | 类型 | 粒度 | 用途 |
|---|---|---|---|
| `derived_ownership_governance` | 物理表 | `ts_code + trade_date` | 高频日频治理事实和持有人结构变量 |
| `derived_ownership_governance_full_v` | 视图 | `ts_code + trade_date` | 更宽的明细聚合、长期窗口和文本字段 |
| `ownership_governance_event_timeline_v` | 视图 | `ts_code + event_type + event_date + record_key` | 统一质押、户数、股东结构事件时间线 |
| `ownership_holder_concentration_v` | 视图 | `ts_code + end_date + holder_scope` | 股东集中度低频聚合，便于审计 |

预计规模：

| 对象 | 预计列数 |
|---|---:|
| `derived_ownership_governance` | 63 |
| `derived_ownership_governance_full_v` | 98 |
| `ownership_holder_concentration_v` | 10 |
| `ownership_governance_event_timeline_v` | 12 |

## 5. 核心物理表：`derived_ownership_governance`

主键：`ts_code + trade_date`

### 5.1 元数据字段

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `ts_code` | 股票代码 | VARCHAR | `derived_daily_spine.ts_code` |
| `trade_date` | 交易日期 | DATE | `derived_daily_spine.trade_date` |
| `ownership_available_flag` | 持有人治理数据可用标记 | BOOLEAN | 任一质押/户数/股东结构字段非空 |
| `latest_ownership_event_date` | 最近持有人治理事件日期 | DATE | `max(event_date <= trade_date)` |
| `days_since_latest_ownership_event` | 距最近持有人治理事件天数 | INTEGER | `trade_date - latest_ownership_event_date` |
| `ownership_event_count_365d` | 近一年持有人治理事件数 | INTEGER | `count(event_date in 365d)` |
| `updated_at` | 本地更新时间 | TIMESTAMP | `CURRENT_TIMESTAMP` |

## 6. 质押统计字段

口径说明：

1. `pledge_stat.end_date` 作为统计报告期或统计日期；日频 asof 取 `end_date <= trade_date` 的最新记录。
2. `pledge_ratio` 保持 Tushare 原始百分比/比例口径，实施前需用抽样确认其单位。若原值为百分数，则保留源口径并在字段说明标明。
3. 质押本身不被编码为风险评分；只提供比例、变化、次数和结构事实。

### 6.1 核心字段

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `latest_pledge_end_date` | 最新质押统计日期 | DATE | `asof(max(financial_pledge_stat.end_date <= trade_date))` |
| `pledge_count_asof` | 最新质押笔数 | INTEGER | `financial_pledge_stat.pledge_count` |
| `pledge_unreleased_share_asof` | 最新未解押质押股数 | DOUBLE | `financial_pledge_stat.unrest_pledge` |
| `pledge_released_share_asof` | 最新已解押质押股数 | DOUBLE | `financial_pledge_stat.rest_pledge` |
| `pledge_total_share_base_asof` | 质押统计总股本 | DOUBLE | `financial_pledge_stat.total_share` |
| `pledge_ratio_asof` | 最新质押比例 | DOUBLE | `financial_pledge_stat.pledge_ratio` |
| `pledge_ratio_chg_1report` | 质押比例较上一统计期变化 | DOUBLE | `pledge_ratio_asof - lag(pledge_ratio_asof,1 pledge report)` |
| `pledge_ratio_chg_4report` | 质押比例较四个统计期前变化 | DOUBLE | `pledge_ratio_asof - lag(pledge_ratio_asof,4 pledge reports)` |
| `pledge_count_chg_1report` | 质押笔数较上一统计期变化 | DOUBLE | `pledge_count_asof - lag(pledge_count_asof,1 pledge report)` |
| `pledge_share_to_total_share_asof` | 未解押质押股数/总股本 | DOUBLE | `pledge_unreleased_share_asof / stock_daily_basic.total_share` |
| `pledge_stat_staleness_days` | 质押统计滞后天数 | INTEGER | `trade_date - latest_pledge_end_date` |
| `pledge_ratio_ge_10_flag` | 质押比例大于等于10%标记 | BOOLEAN | `pledge_ratio_asof >= 10` |
| `pledge_ratio_ge_30_flag` | 质押比例大于等于30%标记 | BOOLEAN | `pledge_ratio_asof >= 30` |
| `pledge_ratio_ge_50_flag` | 质押比例大于等于50%标记 | BOOLEAN | `pledge_ratio_asof >= 50` |
| `pledge_data_available_flag` | 质押统计可用标记 | BOOLEAN | `latest_pledge_end_date IS NOT NULL` |

### 6.2 完整视图扩展

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `pledge_ratio_chg_20d/60d/120d/250d` | 质押比例多周期日频变化 | `pledge_ratio_asof - lag(pledge_ratio_asof,n trade days)` |
| `pledge_count_chg_20d/60d/120d/250d` | 质押笔数多周期日频变化 | 同上 |
| `pledge_detail_active_count_asof` | asof 有效质押明细数 | `start_date <= trade_date AND (end_date IS NULL OR end_date >= trade_date)` |
| `pledge_detail_active_amount_asof` | asof 有效质押明细股数 | `sum(pledge_amount)` 有效明细 |
| `pledge_release_count_365d` | 近一年解押事件数 | `count(is_release)` over 365d |

## 7. 股东户数字段

口径说明：

1. 股东户数使用 `financial_holder_number.ann_date` 作为可得日；缺失时不使用 `end_date` 回填。
2. 户数下降/上升只作为事实变化，不表达筹码集中“好坏”。
3. 比率变化采用普通安全比率；分母异常时沿用 `docs/ratio_special_value_policy.md`。

### 7.1 核心字段

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `latest_holder_ann_date` | 最新股东户数公告日 | DATE | `asof(max(ann_date <= trade_date))` |
| `latest_holder_end_date` | 最新股东户数报告期 | DATE | `financial_holder_number.end_date` |
| `holder_num_asof` | 最新股东户数 | BIGINT | `financial_holder_number.holder_num` |
| `holder_num_chg_1report` | 股东户数较上一期变化 | DOUBLE | `holder_num_asof - lag(holder_num_asof,1 holder report)` |
| `holder_num_chg_rate_1report` | 股东户数较上一期变化率 | `holder_num_chg_1report / previous_holder_num` |
| `holder_num_chg_4report` | 股东户数较四期前变化 | DOUBLE | `holder_num_asof - lag(holder_num_asof,4 holder reports)` |
| `holder_num_chg_rate_4report` | 股东户数较四期前变化率 | DOUBLE | 安全比率 |
| `shares_per_holder_asof` | 户均持股数 | DOUBLE | `stock_daily_basic.total_share / holder_num_asof` |
| `free_shares_per_holder_asof` | 户均自由流通股数 | DOUBLE | `stock_daily_basic.free_share / holder_num_asof` |
| `holder_num_to_total_share` | 股东户数/总股本 | DOUBLE | `holder_num_asof / stock_daily_basic.total_share` |
| `holder_num_to_free_share` | 股东户数/自由流通股本 | DOUBLE | `holder_num_asof / stock_daily_basic.free_share` |
| `holder_num_staleness_days` | 股东户数数据滞后天数 | INTEGER | `trade_date - latest_holder_ann_date` |
| `holder_data_available_flag` | 股东户数可用标记 | BOOLEAN | `latest_holder_ann_date IS NOT NULL` |

### 7.2 完整视图扩展

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `holder_num_chg_20d/60d/120d/250d` | 股东户数多周期日频变化 | `holder_num_asof - lag(holder_num_asof,n trade days)` |
| `holder_num_chg_rate_20d/60d/120d/250d` | 股东户数多周期变化率 | 安全比率 |
| `holder_num_chg_20d/60d/120d/250d` | 股东户数多周期日频变化 | `holder_num_asof - lag(holder_num_asof,n trade days)` |
| `holder_num_chg_rate_20d/60d/120d/250d` | 股东户数多周期变化率 | 安全比率 |

## 8. 十大股东集中度字段

口径说明：

1. 十大股东以 `financial_top10_holders.ann_date` 为可得日；日频 asof 取最新公告版本。
2. 同一 `ts_code + end_date + ann_date` 内按股东明细聚合。
3. 集中度字段是事实结构变量，不表达治理好坏。
4. 股东类型保留原始文本；控股股东/机构/个人等类型归一化可进入完整视图。

### 8.1 核心字段

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `latest_top10_holder_ann_date` | 最新十大股东公告日 | DATE | `asof(max(ann_date <= trade_date))` |
| `latest_top10_holder_end_date` | 最新十大股东报告期 | DATE | 最新 `end_date` |
| `top10_holder_count_latest` | 十大股东明细数 | INTEGER | `count(holder_name)` |
| `top1_holder_ratio_latest` | 第一大股东持股比例 | DOUBLE | `max(hold_ratio)` |
| `top3_holder_ratio_latest` | 前三大股东持股比例 | DOUBLE | `sum(top3 hold_ratio)` |
| `top5_holder_ratio_latest` | 前五大股东持股比例 | DOUBLE | `sum(top5 hold_ratio)` |
| `top10_holder_ratio_latest` | 十大股东持股比例 | DOUBLE | `sum(hold_ratio)` |
| `top10_holder_hhi_latest` | 十大股东持股 HHI | DOUBLE | `sum((hold_ratio/100)^2)` 或按源比例口径调整 |
| `top10_holder_ratio_chg_1report` | 十大股东比例较上一期变化 | DOUBLE | `current - previous` |
| `top1_holder_ratio_chg_1report` | 第一大股东比例较上一期变化 | DOUBLE | `current - previous` |
| `top10_holder_staleness_days` | 十大股东数据滞后天数 | INTEGER | `trade_date - latest_top10_holder_ann_date` |

### 8.2 完整视图扩展

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `top1_holder_name_latest` | 第一大股东名称 | `arg_max(holder_name,hold_ratio)` |
| `top1_holder_type_latest` | 第一大股东类型 | `arg_max(holder_type,hold_ratio)` |
| `top10_institution_holder_ratio_latest` | 十大股东中机构持股比例 | `sum(hold_ratio where holder_type like institution)` |
| `top10_individual_holder_ratio_latest` | 十大股东中个人持股比例 | 同上 |
| `top10_holder_change_sum_latest` | 十大股东持股变动合计 | `sum(hold_change)` |
| `top10_holder_positive_change_count` | 十大股东增持人数 | `count(hold_change>0)` |
| `top10_holder_negative_change_count` | 十大股东减持人数 | `count(hold_change<0)` |
| `top10_holder_name_churn_1report` | 十大股东名单是否变动 | 与上一报告期 holder_name 集合对比；相同为 0，不同为 1 |

## 9. 十大流通股东集中度字段

口径说明：

1. 十大流通股东以 `financial_top10_float_holders.ann_date` 为可得日。
2. 流通股东字段优先使用 `hold_float_ratio`；若为空，可在完整视图中保留 `hold_ratio` 兜底字段，但核心表不建议混用。

### 9.1 核心字段

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `latest_top10_float_ann_date` | 最新十大流通股东公告日 | DATE | `asof(max(ann_date <= trade_date))` |
| `latest_top10_float_end_date` | 最新十大流通股东报告期 | DATE | 最新 `end_date` |
| `top10_float_holder_count_latest` | 十大流通股东明细数 | INTEGER | `count(holder_name)` |
| `top1_float_holder_ratio_latest` | 第一大流通股东持股比例 | DOUBLE | `max(hold_float_ratio)` |
| `top3_float_holder_ratio_latest` | 前三大流通股东持股比例 | DOUBLE | `sum(top3 hold_float_ratio)` |
| `top5_float_holder_ratio_latest` | 前五大流通股东持股比例 | DOUBLE | `sum(top5 hold_float_ratio)` |
| `top10_float_holder_ratio_latest` | 十大流通股东持股比例 | DOUBLE | `sum(hold_float_ratio)` |
| `top10_float_holder_hhi_latest` | 十大流通股东 HHI | DOUBLE | `sum((hold_float_ratio/100)^2)` |
| `top10_float_holder_ratio_chg_1report` | 十大流通股东比例较上一期变化 | DOUBLE | `current - previous` |
| `top1_float_holder_ratio_chg_1report` | 第一大流通股东比例较上一期变化 | DOUBLE | `current - previous` |
| `top10_float_staleness_days` | 十大流通股东数据滞后天数 | INTEGER | `trade_date - latest_top10_float_ann_date` |

### 9.2 完整视图扩展

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `top1_float_holder_name_latest` | 第一大流通股东名称 | `arg_max(holder_name,hold_float_ratio)` |
| `top1_float_holder_type_latest` | 第一大流通股东类型 | `arg_max(holder_type,hold_float_ratio)` |
| `top10_float_institution_ratio_latest` | 十大流通股东机构持股比例 | `sum(hold_float_ratio where holder_type like institution)` |
| `top10_float_individual_ratio_latest` | 十大流通股东个人持股比例 | `sum(hold_float_ratio where holder_type like individual)` |
| `top10_float_holder_change_sum_latest` | 十大流通股东持股变动合计 | `sum(hold_change)` |
| `top10_float_holder_positive_change_count` | 十大流通股东增持人数 | `count(hold_change>0)` |
| `top10_float_holder_negative_change_count` | 十大流通股东减持人数 | `count(hold_change<0)` |
| `top10_float_holder_name_churn_1report` | 十大流通股东名单是否变动 | 与上一报告期 holder_name 集合对比；相同为 0，不同为 1 |

## 10. 综合结构事实字段

这些字段仍是事实组合，不是评分。

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `ownership_concentration_ratio_latest` | 综合股权集中度 | DOUBLE | 优先 `top10_holder_ratio_latest`，缺失时用 `top10_float_holder_ratio_latest` |
| `ownership_concentration_chg_1report` | 综合集中度较上一期变化 | DOUBLE | `current - previous` |
| `float_concentration_premium_latest` | 流通集中度相对总股东集中度差 | DOUBLE | `top10_float_holder_ratio_latest - top10_holder_ratio_latest` |
| `holder_num_to_total_share` | 总股本口径持有人分散度代理 | DOUBLE | `holder_num_asof / stock_daily_basic.total_share` |
| `holder_num_to_free_share` | 自由流通股本口径持有人分散度代理 | DOUBLE | `holder_num_asof / stock_daily_basic.free_share` |
| `pledge_to_concentration_ratio` | 质押比例/集中度 | DOUBLE | `pledge_ratio_asof / top10_holder_ratio_latest`，安全比率 |
| `ownership_data_completeness_count` | 持有人治理核心字段可用数 | INTEGER | 核心字段非空计数 |
| `ownership_data_completeness_ratio` | 持有人治理核心字段可用率 | DOUBLE | `count / 核心字段数` |

## 11. 事件时间线：`ownership_governance_event_timeline_v`

用于审计和抽样，不作为日频宽表主入口。

| 字段 | 中文名 | 逻辑 |
|---|---|---|
| `ts_code` | 股票代码 | 来源事件股票代码 |
| `event_type` | 事件类型 | `pledge_stat/pledge_detail/holder_number/top10_holder/top10_float_holder` |
| `event_date` | 事件日期 | 质押统计用 `end_date`，明细用 `start_date/end_date`，股东数据用 `ann_date` |
| `effective_date` | 信息可得日 | 优先 `ann_date`；质押统计缺公告日时用 `end_date` |
| `end_date` | 报告期或截止日 | 如适用 |
| `record_key` | 原始记录键 | 源记录键 |
| `holder_name` | 持有人名称 | 明细或股东结构事件 |
| `holder_type` | 持有人类型 | 源文本 |
| `event_value_1` | 事件数值1 | 质押比例、股东户数、持股比例 |
| `event_value_2` | 事件数值2 | 质押股数、持股变动 |
| `event_text` | 事件文本 | 质押解除、股东类型等 |
| `source_table` | 来源表 | 便于追溯 |

## 12. 缺失与特殊值策略

1. 低频事件未披露：数值字段为空，布尔可用字段为 `false`。
2. 质押统计无公告日：允许用 `end_date` 作为 asof 日期，因为 `pledge_stat` 是统计型基础表；该口径需在数据字典标明。
3. 股东户数、十大股东、十大流通股东必须使用 `ann_date` 控制可得性；`ann_date` 缺失时不回填。
4. 比率字段分母异常时沿用 `docs/ratio_special_value_policy.md`。
5. 股东类型枚举无法识别时保留原文本，归一化字段为空或 `unknown`。
6. 名单变动字段在上一报告期缺失时置空，不用 0 代替。

## 13. 审计要求

实施后生成 `reports/phase3_ownership_governance_audit.md`，至少包含：

1. 核心物理表行数、列数、股票数、日期范围。
2. 来源对象行数和日期范围。
3. 质押、户数、十大股东、十大流通股东核心字段非空率。
4. 主键重复检查。
5. point-in-time 检查：股东户数和十大股东字段不得使用 `ann_date > trade_date` 的记录。
6. 质押统计 asof 抽样复算。
7. 十大股东/十大流通股东集中度抽样复算。
8. 股东名单变动字段抽样复算。
9. 与 `corporate_action` 的边界检查：回购、解禁、分红字段不得重复进入本模块。

## 14. 实施步骤

1. 注册 schema 和变量字典：`derived_ownership_governance`、`derived_ownership_governance_full_v`、`ownership_governance_event_timeline_v`。
2. 必要时增强 `financial_holder_number`、`financial_top10_holders`、`financial_top10_float_holders`、`financial_pledge_detail` 视图字段。
3. 新增核心构建脚本：`scripts/build_phase3_ownership_governance_core.py`。
4. 新增完整视图脚本：`scripts/create_phase3_ownership_governance_views.py`。
5. 全量历史构建核心表。
6. 生成审计报告。
7. 刷新全局 Excel 数据字典。
8. 运行测试和 schema registry 校验。

## 15. 待确认问题

1. 是否同意本模块只纳入质押、股东户数、十大股东、十大流通股东，暂不纳入实控人、董监高和管理层信息？
2. `pledge_stat` 缺公告日时，是否接受用 `end_date` 作为 asof 日期？我的建议是接受，但必须在数据字典标注这是统计截止日口径。
3. 高质押比例事实标记阈值是否采用 `pledge_ratio_asof >= 50`？如果你希望更敏感，可以用 30/50 两档字段。
4. 十大股东集中度字段是否保留源百分比口径，不统一除以 100？我的建议是保留源口径，HHI 内部计算时再标准化。
5. 股东类型归一化是否进入第一阶段？我的建议是第一阶段保留原始 `holder_type` 和简单机构/个人聚合，复杂股东类型映射后续再增强。
6. `holder_dispersion_proxy_latest` 的分母用总股本还是自由流通股本？我的建议是核心表给两个字段：`holder_num_to_total_share` 和 `holder_num_to_free_share`，避免口径争议。
7. 名单变动字段是否进入核心表？我的建议是只把集中度和比例变化放核心表，名单 churn 放完整视图，避免核心构建过重。
