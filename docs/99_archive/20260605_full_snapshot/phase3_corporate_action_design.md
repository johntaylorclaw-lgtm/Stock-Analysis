# Phase 3 公司行为模块设计

生成日期：2026-06-04  
状态：第一阶段核心物理表、第二阶段完整视图和统一事件时间线已完成。

## 1. 模块定位

`corporate_action` 维护上市公司已经披露或已经发生的公司行为与公告事件事实，重点覆盖分红送转、业绩预告、业绩快报、审计意见、主营构成、回购、限售解禁和股本事件。

本模块不做主观评分，不生成买卖信号，不引入未来信息。它的职责是把低频、稀疏、事件型数据转换成可审计、point-in-time 安全的日频变量入口。

## 2. 与其他模块的边界

| 模块 | 是否纳入本模块 | 边界说明 |
|---|---|---|
| 分红送转 | 是 | 现金分红、送股、转增、除权除息、派息节奏进入 `corporate_action` |
| 业绩预告/快报 | 是 | 作为公告事件事实进入本模块；财务正式报表仍由 `financial_asof/quality/growth` 维护 |
| 审计意见 | 是 | 审计结果、审计费用、审计机构作为公告事件事实进入本模块 |
| 主营构成 | 是 | 按报告期披露的收入/利润/成本结构进入本模块 |
| 回购 | 是 | 回购公告与进度属于公司行为，进入本模块 |
| 限售解禁/流通股本变化 | 是 | 解禁日期、解禁规模、股本变化进入本模块 |
| 质押 | 否 | 进入 `ownership_governance`，因为其本质是股东治理和风险代理 |
| 股东户数、十大股东 | 否 | 进入 `ownership_governance`，避免公司行为模块过宽 |
| 估值中的股息率 | 间接 | `valuation_size` 可继续使用股息率，本模块提供更完整的分红事件和 TTM 现金分红事实 |

## 3. 可用基础数据

| 数据入口 | 当前状态 | 主要用途 |
|---|---|---|
| `financial_dividend` / `financial_dividend_raw` | 已结构化，约 16 万行 | 分红、送股、转增、股权登记日、除权除息日、派息日 |
| `financial_forecast` | 已从 `financial_event_raw` 拆出，约 13.9 万行 | 业绩预告类型、净利润区间、变动幅度区间 |
| `financial_express` | 已从 `financial_event_raw` 拆出 | 业绩快报收入、利润、资产、ROE 等 |
| `financial_audit_opinion` | 已从 `financial_event_raw` 拆出，约 8.6 万行 | 审计意见、审计费用、审计机构 |
| `financial_main_business` | 已从 `financial_event_raw` 拆出，约 82.8 万行 | 主营业务分部收入、利润、成本、币种 |
| `financial_repurchase` | 已从 `financial_event_raw` 拆出，约 6.9 万行 | 回购进度、回购数量、金额、价格上下限 |
| `financial_share_float` | 已从 `financial_event_raw` 拆出，约 1,028 万行 | 限售解禁日期、解禁股数、解禁比例、持有人 |
| `stock_daily_basic` | 已落库 | 总股本、流通股本、自由流通股本、市值、股息率 |
| `stock_adj_factor` | 已落库 | 复权因子变化，用于识别除权除息影响和复权事件 |
| `derived_daily_spine` | 已落库 | 日频主干、上市状态、交易状态、价格有效性 |
| `derived_financial_asof` / `derived_financial_quality` | 已落库 | 分红支付率、预告/快报与正式财报对照的后续扩展依赖 |

## 4. 表结构方案

本模块采用“一张核心物理表 + 一张完整视图 + 若干低频事件辅助视图”的结构。

| 对象 | 类型 | 粒度 | 用途 |
|---|---|---|---|
| `derived_corporate_action` | 物理表 | `ts_code + trade_date` | 高频使用的日频公司行为事实 |
| `derived_corporate_action_full_v` | 视图 | `ts_code + trade_date` | 更宽的低频事件 asof 与前瞻窗口变量 |
| `corporate_action_event_timeline_v` | 视图 | `ts_code + event_type + event_date + record_key` | 统一事件时间线，便于审计和抽查 |
| `corporate_action_dividend_event_v` | 视图 | `ts_code + record_key` | 分红送转事件规范化 |
| `corporate_action_main_business_summary_v` | 视图 | `ts_code + end_date` | 主营构成按报告期聚合 |

实施结果：

| 对象 | 类型 | 实际规模 |
|---|---|---:|
| `derived_corporate_action` | 物理表 | 15,295,776 行，104 列 |
| `derived_corporate_action_full_v` | 视图 | 15,295,776 行，144 列 |
| `corporate_action_event_timeline_v` | 视图 | 11,602,540 行，10 列 |

审计报告：`reports/phase3_corporate_action_audit.md`

## 5. 核心物理表：`derived_corporate_action`

定位：日频核心事实入口，控制列宽，优先服务下游宽表、截面转换和人工抽检。

预计字段数：约 90-120 列。  
主键：`ts_code + trade_date`

### 5.1 元数据字段

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `ts_code` | 股票代码 | VARCHAR | `derived_daily_spine.ts_code` |
| `trade_date` | 交易日期 | DATE | `derived_daily_spine.trade_date` |
| `corp_action_available_flag` | 公司行为数据可用标记 | BOOLEAN | 任一核心事件 asof 字段非空 |
| `latest_corp_action_date` | 最近公司行为事件日期 | DATE | `max(event_date <= trade_date)` |
| `days_since_latest_corp_action` | 距最近公司行为事件天数 | INTEGER | `trade_date - latest_corp_action_date` |
| `corp_action_event_count_365d` | 近一年公司行为事件数 | INTEGER | `count(event_date between trade_date-365 and trade_date)` |
| `updated_at` | 本地更新时间 | TIMESTAMP | `CURRENT_TIMESTAMP` |

## 6. 分红送转核心字段

口径说明：

1. 分红送转事件的可得日使用 `effective_date = coalesce(ann_date, record_date, ex_date)`。
2. 事件发生日优先使用 `ex_date`；若缺失，用 `record_date`，再用 `ann_date`。
3. 现金分红字段保持 Tushare 原始口径，不做复权。
4. 对 TTM 现金分红，按事件发生日滚动 365 天汇总。
5. 对“下一次已公告未实施分红”，必须要求 `ann_date <= trade_date < ex_date`，避免未来信息。

### 6.1 核心字段

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `latest_dividend_ann_date` | 最近分红公告日 | DATE | `asof(max(financial_dividend.ann_date <= trade_date))` |
| `latest_dividend_end_date` | 最近分红所属报告期 | DATE | 最近可得分红记录的 `end_date` |
| `latest_dividend_ex_date` | 最近除权除息日 | DATE | 最近可得分红记录的 `ex_date` |
| `latest_dividend_record_date` | 最近股权登记日 | DATE | 最近可得分红记录的 `record_date` |
| `latest_dividend_pay_date` | 最近派息日 | DATE | 最近可得分红记录的 `pay_date` |
| `latest_dividend_proc` | 最近分红实施进度 | VARCHAR | `financial_dividend.div_proc` |
| `cash_dividend_per_share_latest` | 最近每股现金分红 | DOUBLE | `financial_dividend.cash_div` |
| `cash_dividend_after_tax_latest` | 最近税后每股现金分红 | DOUBLE | `financial_dividend.cash_div_tax` |
| `bonus_share_ratio_latest` | 最近送股比例 | DOUBLE | `financial_dividend.stk_bo_rate` |
| `transfer_share_ratio_latest` | 最近转增比例 | DOUBLE | `financial_dividend.stk_co_rate` |
| `stock_dividend_ratio_latest` | 最近送转合计比例 | DOUBLE | `coalesce(stk_bo_rate,0)+coalesce(stk_co_rate,0)` |
| `cash_dividend_ttm` | 近一年每股现金分红合计 | DOUBLE | `sum(cash_div) where event_date in [trade_date-365, trade_date]` |
| `cash_dividend_after_tax_ttm` | 近一年税后每股现金分红合计 | DOUBLE | `sum(cash_div_tax)` 同上 |
| `stock_dividend_ratio_ttm` | 近一年送转比例合计 | DOUBLE | `sum(stk_bo_rate+stk_co_rate)` 同上 |
| `dividend_event_count_365d` | 近一年分红事件数 | INTEGER | `count(dividend events)` |
| `days_since_dividend_ann` | 距最近分红公告天数 | INTEGER | `trade_date-latest_dividend_ann_date` |
| `days_since_ex_dividend` | 距最近除权除息天数 | INTEGER | `trade_date-latest_dividend_ex_date` |
| `has_dividend_announced_not_executed` | 是否有已公告未除权分红 | BOOLEAN | `exists(ann_date<=trade_date AND ex_date>trade_date)` |
| `next_announced_ex_date` | 下一次已公告除权除息日 | DATE | `min(ex_date) where ann_date<=trade_date AND ex_date>trade_date` |
| `next_announced_cash_dividend` | 下一次已公告每股现金分红 | DOUBLE | 对应 `next_announced_ex_date` 的 `cash_div` |

### 6.2 扩展字段进入完整视图

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `cash_dividend_3y_sum` | 三年每股现金分红合计 | `sum(cash_div)` over 3 年 |
| `cash_dividend_5y_sum` | 五年每股现金分红合计 | `sum(cash_div)` over 5 年 |
| `dividend_year_count_3y` | 三年有分红年份数 | `count(distinct year(ex_date))` |
| `dividend_year_count_5y` | 五年有分红年份数 | 同上 |
| `dividend_interval_days_latest` | 最近两次分红间隔 | `latest_ex_date - previous_ex_date` |
| `cash_dividend_ttm_to_close` | 近一年现金分红/收盘价 | `cash_dividend_ttm / stock_daily.close`，不使用复权价 |
| `cash_dividend_ttm_to_total_mv` | 近一年现金分红估算/总市值 | `cash_dividend_ttm * total_share / total_mv` |
| `cash_dividend_payout_ratio_ttm` | 现金分红支付率 | `cash_dividend_ttm * total_share / net_profit_attr_parent_ttm`，依赖财务 asof |

## 7. 业绩预告字段

口径说明：

1. 可得日为 `financial_forecast.ann_date`。
2. 同一日多条记录时，优先取 `end_date` 最新、`record_key` 最新。
3. 预告类型只保留事实分类，不转换成好坏评分。
4. 净利润区间中位数仅作为区间事实的中心值，不代表预测评价。

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `has_forecast_asof` | 是否已有业绩预告 | BOOLEAN | `exists(financial_forecast.ann_date <= trade_date)` |
| `latest_forecast_ann_date` | 最近预告公告日 | DATE | `asof(max(ann_date))` |
| `latest_forecast_end_date` | 最近预告报告期 | DATE | 最近预告 `end_date` |
| `forecast_type_latest` | 最近预告类型 | VARCHAR | `financial_forecast.forecast_type` |
| `forecast_type_code_latest` | 最近预告类型编码 | INTEGER | 见第 13 节枚举 |
| `forecast_p_change_min_latest` | 预告净利变动下限 | DOUBLE | `financial_forecast.p_change_min` |
| `forecast_p_change_max_latest` | 预告净利变动上限 | DOUBLE | `financial_forecast.p_change_max` |
| `forecast_p_change_mid_latest` | 预告净利变动中位 | DOUBLE | `(p_change_min+p_change_max)/2` |
| `forecast_net_profit_min_latest` | 预告净利润下限 | DOUBLE | `financial_forecast.net_profit_min` |
| `forecast_net_profit_max_latest` | 预告净利润上限 | DOUBLE | `financial_forecast.net_profit_max` |
| `forecast_net_profit_mid_latest` | 预告净利润中位 | DOUBLE | `(net_profit_min+net_profit_max)/2` |
| `forecast_range_width_latest` | 预告净利润区间宽度 | DOUBLE | `net_profit_max-net_profit_min` |
| `forecast_change_range_width_latest` | 预告变动幅度区间宽度 | DOUBLE | `p_change_max-p_change_min` |
| `days_since_forecast_ann` | 距最近预告公告天数 | INTEGER | `trade_date-latest_forecast_ann_date` |

完整视图扩展：

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `forecast_count_365d` | 近一年预告次数 | `count(ann_date in 365d)` |
| `forecast_revision_count_same_end_date` | 同一报告期预告修正次数 | `count(distinct ann_date)` by `ts_code,end_date` asof |
| `forecast_latest_summary` | 最近预告摘要 | `financial_forecast.summary` |
| `forecast_latest_change_reason` | 最近预告原因 | `financial_forecast.change_reason` |

## 8. 业绩快报字段

口径说明：

1. 可得日为 `financial_express.ann_date`。
2. 快报数值属于披露事实，正式财报仍以财务模块为准。
3. 快报字段保留 Tushare 原始单位和百分比口径。

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `has_express_asof` | 是否已有业绩快报 | BOOLEAN | `exists(financial_express.ann_date <= trade_date)` |
| `latest_express_ann_date` | 最近快报公告日 | DATE | `asof(max(ann_date))` |
| `latest_express_end_date` | 最近快报报告期 | DATE | 最近快报 `end_date` |
| `express_revenue_latest` | 最近快报营业收入 | DOUBLE | `financial_express.revenue` |
| `express_operating_profit_latest` | 最近快报营业利润 | DOUBLE | `financial_express.operating_profit` |
| `express_total_profit_latest` | 最近快报利润总额 | DOUBLE | `financial_express.total_profit` |
| `express_net_profit_latest` | 最近快报净利润 | DOUBLE | `financial_express.net_profit` |
| `express_total_assets_latest` | 最近快报总资产 | DOUBLE | `financial_express.total_assets` |
| `express_equity_attr_parent_latest` | 最近快报归母权益 | DOUBLE | `financial_express.equity_attr_parent` |
| `express_diluted_eps_latest` | 最近快报摊薄 EPS | DOUBLE | `financial_express.diluted_eps` |
| `express_diluted_roe_latest` | 最近快报摊薄 ROE | DOUBLE | `financial_express.diluted_roe` |
| `express_yoy_net_profit_latest` | 最近快报净利润同比 | DOUBLE | `financial_express.yoy_net_profit` |
| `days_since_express_ann` | 距最近快报公告天数 | INTEGER | `trade_date-latest_express_ann_date` |

完整视图扩展：

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `express_count_365d` | 近一年快报次数 | `count(ann_date in 365d)` |
| `express_latest_performance_summary` | 最近快报摘要 | `financial_express.performance_summary` |
| `express_to_formal_net_profit_gap` | 快报与正式财报净利润差异 | `express_net_profit_latest - derived_financial_asof.net_profit_attr_parent_ttm_or_period`，待财务期口径确认 |

## 9. 审计意见字段

口径说明：

1. 可得日为 `financial_audit_opinion.ann_date`。
2. 审计意见编码只做事实分类，非评价分。
3. 审计费用保持原始货币金额，不做通胀调整。

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `latest_audit_ann_date` | 最近审计公告日 | DATE | `asof(max(ann_date))` |
| `latest_audit_end_date` | 最近审计报告期 | DATE | 最近审计 `end_date` |
| `audit_opinion_latest` | 最近审计意见 | VARCHAR | `financial_audit_opinion.audit_result` |
| `audit_opinion_code_latest` | 最近审计意见编码 | INTEGER | 见第 13 节枚举 |
| `non_standard_audit_flag_latest` | 最近是否非标审计意见 | BOOLEAN | 编码不属于标准无保留意见 |
| `audit_fees_latest` | 最近审计费用 | DOUBLE | `financial_audit_opinion.audit_fees` |
| `audit_agency_latest` | 最近审计机构 | VARCHAR | `financial_audit_opinion.audit_agency` |
| `days_since_audit_ann` | 距最近审计公告天数 | INTEGER | `trade_date-latest_audit_ann_date` |

完整视图扩展：

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `audit_fees_change_1y` | 审计费用一年变化 | `audit_fees_latest - lag_1y_audit_fees` |
| `audit_fees_change_rate_1y` | 审计费用一年变化率 | 安全比率：`audit_fees_change_1y / lag_1y_audit_fees` |
| `audit_agency_changed_flag` | 审计机构是否变更 | `audit_agency_latest != previous_audit_agency` |
| `non_standard_audit_count_5y` | 五年非标审计次数 | `sum(non_standard_audit_flag)` over 5 年 |

## 10. 主营构成字段

口径说明：

1. 粒度为报告期披露的业务分部，日频 asof 时优先使用 `financial_event_raw.ann_date`；若源记录缺失公告日，则保守使用 `end_date + 120 天` 作为可得日兜底。
2. 主营构成是事实层结构变量，不判断业务好坏。
3. 分部收入、利润、成本原始单位保持 Tushare 口径。

核心表只放聚合后的业务集中度字段：

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `latest_mainbz_end_date` | 最近主营构成报告期 | DATE | `asof(max(financial_main_business.end_date))` |
| `mainbz_segment_count_latest` | 最近主营分部数量 | INTEGER | `count(bz_item)` by `ts_code,end_date` |
| `mainbz_revenue_total_latest` | 最近主营分部收入合计 | DOUBLE | `sum(bz_sales)` |
| `mainbz_profit_total_latest` | 最近主营分部利润合计 | DOUBLE | `sum(bz_profit)` |
| `mainbz_cost_total_latest` | 最近主营分部成本合计 | DOUBLE | `sum(bz_cost)` |
| `mainbz_top1_revenue_ratio_latest` | 第一大业务收入占比 | DOUBLE | `max(bz_sales)/sum(bz_sales)` |
| `mainbz_top3_revenue_ratio_latest` | 前三大业务收入占比 | DOUBLE | `sum(top3 bz_sales)/sum(bz_sales)` |
| `mainbz_top1_profit_ratio_latest` | 第一大业务利润占比 | DOUBLE | `max(bz_profit)/sum(bz_profit)` |
| `mainbz_gross_margin_latest` | 主营分部毛利率 | DOUBLE | `(sum(bz_sales)-sum(bz_cost))/sum(bz_sales)` |
| `days_since_mainbz_end_date` | 距主营构成报告期天数 | INTEGER | `trade_date-latest_mainbz_end_date` |

完整视图扩展：

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `mainbz_top1_item_latest` | 第一大业务名称 | `arg_max(bz_item,bz_sales)` |
| `mainbz_top1_code_latest` | 第一大业务代码 | `arg_max(bz_code,bz_sales)` |
| `mainbz_hhi_revenue_latest` | 主营收入 HHI | `sum((bz_sales/sum_sales)^2)` |
| `mainbz_hhi_profit_latest` | 主营利润 HHI | `sum((bz_profit/sum_profit)^2)` |
| `mainbz_segment_count_change_1y` | 主营分部数一年变化 | `current - lag_1y` |
| `mainbz_top1_revenue_ratio_change_1y` | 第一大业务收入占比一年变化 | `current - lag_1y` |

## 11. 回购字段

口径说明：

1. 可得日为 `financial_repurchase.ann_date`。
2. 回购金额和数量用事件滚动窗口统计，不判断利好利空。
3. 若回购进度文本存在多种写法，只做规范化枚举，保留原始文本。

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `latest_repurchase_ann_date` | 最近回购公告日 | DATE | `asof(max(ann_date))` |
| `latest_repurchase_proc` | 最近回购进度 | VARCHAR | `financial_repurchase.proc` |
| `latest_repurchase_proc_code` | 最近回购进度编码 | INTEGER | 见第 13 节枚举 |
| `latest_repurchase_volume` | 最近回购数量 | DOUBLE | `financial_repurchase.volume` |
| `latest_repurchase_amount` | 最近回购金额 | DOUBLE | `financial_repurchase.amount` |
| `latest_repurchase_high_limit` | 最近回购价格上限 | DOUBLE | `financial_repurchase.high_limit` |
| `latest_repurchase_low_limit` | 最近回购价格下限 | DOUBLE | `financial_repurchase.low_limit` |
| `repurchase_amount_365d` | 近一年回购金额合计 | DOUBLE | `sum(amount)` over 365d |
| `repurchase_volume_365d` | 近一年回购数量合计 | DOUBLE | `sum(volume)` over 365d |
| `repurchase_count_365d` | 近一年回购事件数 | INTEGER | `count(repurchase events)` |
| `days_since_repurchase_ann` | 距最近回购公告天数 | INTEGER | `trade_date-latest_repurchase_ann_date` |

完整视图扩展：

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `repurchase_amount_to_total_mv_365d` | 近一年回购金额/总市值 | `repurchase_amount_365d / stock_daily_basic.total_mv` |
| `repurchase_volume_to_total_share_365d` | 近一年回购数量/总股本 | `repurchase_volume_365d / stock_daily_basic.total_share` |
| `repurchase_amount_3y` | 三年回购金额合计 | `sum(amount)` over 3 年 |
| `repurchase_count_3y` | 三年回购事件数 | `count(events)` over 3 年 |

## 12. 限售解禁与股本事件字段

口径说明：

1. `financial_share_float.float_date` 是解禁/流通事件发生日。
2. 对未来窗口变量，只允许使用 `ann_date <= trade_date` 且 `float_date > trade_date` 的已公告事件。
3. 已发生窗口使用 `float_date <= trade_date`。
4. 股本基础事实来自 `stock_daily_basic.total_share/float_share/free_share`，不做复权。

### 12.1 核心字段

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `latest_share_float_ann_date` | 最近解禁公告日 | DATE | `asof(max(ann_date))` |
| `latest_share_float_date` | 最近解禁日期 | DATE | `max(float_date <= trade_date)` |
| `latest_share_float_share` | 最近解禁股数 | DOUBLE | 对应最近解禁记录的 `float_share` |
| `latest_share_float_ratio` | 最近解禁比例 | DOUBLE | 对应最近解禁记录的 `float_ratio` |
| `share_float_event_count_365d` | 近一年解禁事件数 | INTEGER | `count(float_date in 365d)` |
| `share_float_share_365d` | 近一年解禁股数合计 | DOUBLE | `sum(float_share)` over 365d |
| `share_float_ratio_365d` | 近一年解禁比例合计 | DOUBLE | `sum(float_ratio)` over 365d |
| `days_since_share_float` | 距最近解禁天数 | INTEGER | `trade_date-latest_share_float_date` |
| `next_share_float_date_30d` | 未来30日最近已公告解禁日 | DATE | `min(float_date)` where `ann_date<=trade_date<float_date<=trade_date+30` |
| `next_share_float_share_30d` | 未来30日已公告解禁股数 | DOUBLE | `sum(float_share)` over future 30d |
| `next_share_float_ratio_30d` | 未来30日已公告解禁比例 | DOUBLE | `sum(float_ratio)` over future 30d |
| `next_share_float_share_90d` | 未来90日已公告解禁股数 | DOUBLE | 同上 90d |
| `next_share_float_ratio_90d` | 未来90日已公告解禁比例 | DOUBLE | 同上 90d |
| `total_share_asof` | 当日总股本 | DOUBLE | `stock_daily_basic.total_share` |
| `float_share_asof` | 当日流通股本 | DOUBLE | `stock_daily_basic.float_share` |
| `free_share_asof` | 当日自由流通股本 | DOUBLE | `stock_daily_basic.free_share` |
| `float_share_ratio_asof` | 流通股本占总股本 | DOUBLE | `float_share_asof/total_share_asof` |
| `free_share_ratio_asof` | 自由流通股本占总股本 | DOUBLE | `free_share_asof/total_share_asof` |
| `total_share_chg_20d` | 总股本20日变化 | DOUBLE | `total_share_asof - lag(total_share_asof,20 trade days)` |
| `float_share_chg_20d` | 流通股本20日变化 | DOUBLE | `float_share_asof - lag(float_share_asof,20 trade days)` |
| `free_share_chg_20d` | 自由流通股本20日变化 | DOUBLE | `free_share_asof - lag(free_share_asof,20 trade days)` |

### 12.2 完整视图扩展

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `next_share_float_share_180d` | 未来180日已公告解禁股数 | `sum(float_share)` over future 180d |
| `next_share_float_ratio_180d` | 未来180日已公告解禁比例 | 同上 |
| `share_float_share_3y` | 过去三年解禁股数合计 | `sum(float_share)` over 3 年 |
| `share_float_ratio_3y` | 过去三年解禁比例合计 | `sum(float_ratio)` over 3 年 |
| `total_share_chg_60d/120d/250d` | 总股本多周期变化 | 多周期交易日差分 |
| `float_share_chg_60d/120d/250d` | 流通股本多周期变化 | 多周期交易日差分 |
| `free_share_chg_60d/120d/250d` | 自由流通股本多周期变化 | 多周期交易日差分 |

## 13. 枚举编码建议

枚举字段必须保留原始文本字段，同时提供编码字段供模型或筛选使用。

### 13.1 业绩预告类型编码

| 编码 | 类型 |
|---:|---|
| 1 | 预增 |
| 2 | 略增 |
| 3 | 扭亏 |
| 4 | 续盈 |
| 5 | 预减 |
| 6 | 略减 |
| 7 | 首亏 |
| 8 | 续亏 |
| 9 | 不确定 |
| 99 | 其他/无法识别 |

说明：编码只表示类型，不表示好坏，不参与评分。

### 13.2 审计意见编码

| 编码 | 类型 |
|---:|---|
| 1 | 标准无保留意见 |
| 2 | 带强调事项段的无保留意见 |
| 3 | 保留意见 |
| 4 | 否定意见 |
| 5 | 无法表示意见 |
| 99 | 其他/无法识别 |

`non_standard_audit_flag_latest = audit_opinion_code_latest in (2,3,4,5,99)`。

### 13.3 回购进度编码

| 编码 | 类型 |
|---:|---|
| 1 | 董事会预案 |
| 2 | 股东大会通过 |
| 3 | 实施中 |
| 4 | 已完成 |
| 5 | 停止实施 |
| 99 | 其他/无法识别 |

## 14. 完整视图：`derived_corporate_action_full_v`

完整视图继承核心表全部字段，并补充：

1. 分红 3 年/5 年历史稳定性字段。
2. 预告摘要、变动原因、修正次数。
3. 快报摘要及与正式财报的差异字段。
4. 审计费用变化、审计机构变更、非标审计历史次数。
5. 主营构成 top1/top3、HHI、分部变化。
6. 回购 3 年窗口和相对市值/股本字段。
7. 解禁 180 日未来窗口和多周期股本变化字段。

完整视图不物理落库，除非后续审计显示查询性能无法接受，才迁移高频字段进入核心物理表。

## 15. 统一事件时间线：`corporate_action_event_timeline_v`

该视图用于审计和抽样，不作为下游宽表主入口。

| 字段 | 中文名 | 逻辑 |
|---|---|---|
| `ts_code` | 股票代码 | 来源事件股票代码 |
| `event_type` | 事件类型 | `dividend/forecast/express/audit/main_business/repurchase/share_float/share_capital` |
| `event_date` | 事件发生日 | 分红用 `ex_date`，预告/快报/审计/回购用 `ann_date`，解禁用 `float_date` |
| `effective_date` | 信息可得日 | 通常为 `ann_date`；未来解禁必须用 `ann_date` 控制可得性 |
| `end_date` | 报告期 | 如适用 |
| `record_key` | 原始记录键 | 源记录键 |
| `event_value_1` | 事件数值1 | 现金分红、净利润中位、审计费用、回购金额、解禁股数等 |
| `event_value_2` | 事件数值2 | 送转比例、变动幅度中位、回购数量、解禁比例等 |
| `event_text` | 事件文本 | 预告类型、审计意见、回购进度等 |
| `source_table` | 来源表 | 便于追溯 |

## 16. 缺失与特殊值策略

1. 事件未披露：数值字段为空，布尔存在字段为 `false`。
2. 已公告但实施日缺失：不生成未来实施窗口字段，只保留公告 asof 字段。
3. 分母为 0/空/负的比率字段：沿用 `docs/ratio_special_value_policy.md` 的特殊值编码规则。
4. 原始文本无法识别枚举：编码为 `99`，原始文本保留。
5. 低频事件不存在不视为数据质量失败；审计报告应区分“源端无事件”和“字段解析失败”。

## 17. 审计要求

实施后生成 `reports/phase3_corporate_action_audit.md`，至少包含：

1. 核心物理表行数、列数、日期范围、股票覆盖。
2. 各事件源表/视图行数和日期范围。
3. 分红、预告、快报、审计、主营、回购、解禁核心字段非空率。
4. point-in-time 检查：未来解禁字段必须满足 `ann_date <= trade_date < float_date`。
5. 分红 TTM 抽样复算。
6. 股本变化字段抽样复算。
7. 枚举无法识别比例。
8. 与 `derived_valuation_size.dividend_yield_ttm` 或 `stock_daily_basic.dv_ttm` 的口径差异说明。

## 18. 实施步骤

已完成：

1. 注册 schema 和变量字典：`derived_corporate_action`、`derived_corporate_action_full_v`、`corporate_action_event_timeline_v`。
2. 新增核心构建脚本：`scripts/build_phase3_corporate_action_core.py`。
3. 新增完整视图脚本：`scripts/create_phase3_corporate_action_views.py`。
4. 全量历史构建核心表，覆盖 2006-01-04 至 2026-05-26。
5. 生成审计报告：`reports/phase3_corporate_action_audit.md`。
6. 刷新全局 Excel 数据字典。
7. 运行测试和 schema registry 校验。

## 19. 已确认边界

1. 质押、股东户数、十大股东排除出 `corporate_action`，后续放入 `ownership_governance`。
2. 回购和限售解禁字段纳入核心物理表。
3. 分红现金字段按 Tushare 原始每股口径保留，不做复权调整。
4. 未来 30/90/180 日解禁窗口只统计“已公告事件”，即 `ann_date <= trade_date < float_date`。
5. 主营构成核心表只放聚合字段，具体 top1 名称、HHI、分部明细放入完整视图。
