# Phase 3 综合状态模块设计

生成日期：2026-06-05  
状态：已实施并审计通过。

实施日期：2026-06-05  
审计报告：`reports/phase3_composite_state_audit.md`  
执行记录：`docs/phase3_composite_state_execution_log.md`

## 0. 实施摘要

本模块已按确认边界完成全量历史构建：

| 对象 | 类型 | 实际列数 | 行数/状态 |
|---|---|---:|---:|
| `derived_composite_state` | 物理表 | 92 | 15,295,776 |
| `derived_composite_state_full_v` | 视图 | 115 | 15,295,776 |
| `composite_state_condition_detail_v` | 视图 | 10 | 长表视图 |
| `composite_state_module_coverage_v` | 视图 | 8 | 按交易日和模块统计 |

确认并实施的边界：

1. 删除旧占位字段 `value_quality_score`，本模块禁止 `score` 后缀字段。
2. 保留 `*_condition_count` 条件计数字段；它们只统计明确布尔事实成立数量，不加权、不表达好坏。
3. 暴露状态使用 z 值三档，分位状态使用 20%/80% 三档。
4. 状态枚举使用英文编码。
5. 核心物理表宽度控制在设计范围内。
6. 统一出口视图 `stock_features_plus/full` 后置。
7. 公司行为和治理状态只做事实状态，不做风险/机会判断。

## 1. 模块定位

`composite_state` 是 Phase 3 衍生变量库的“事实状态汇总层”。它把已经完成的日频主干、交易技术、估值规模、财务、资金流、行业/概念/指数、截面转换、公司行为、持有人治理等模块连接起来，形成便于下游读取的状态字段。

本模块不生成选股分数，不生成买卖信号，不生成未来收益标签，不输出“好/坏/强/弱”的主观评价。所有字段必须满足以下条件之一：

1. 可由上游事实变量直接映射。
2. 可由上游事实变量通过明确公式得到布尔状态。
3. 可由上游事实变量通过透明阈值得到枚举状态。
4. 可由若干明确布尔状态做数量统计，但字段命名为 `condition_count`，不命名为 `score`。

旧版占位字段 `value_quality_score` 与本工程事实层原则冲突，建议在本模块实施时删除并替换为事实状态和暴露共现字段。

## 2. 与其他模块边界

| 上游模块 | 本模块使用方式 | 不在本模块重复实现 |
|---|---|---|
| `derived_daily_spine` | 股票身份、交易日、上市状态、价格基础状态 | 复权价格、日频主干构建 |
| `derived_price_technical` | 均线、趋势、技术形态状态 | 技术指标本体计算 |
| `derived_volume_liquidity` | 成交活跃度、流动性状态 | 成交量/成交额滚动指标本体 |
| `derived_return_momentum` | 收益方向、动量/反转状态 | 收益和动量指标本体 |
| `derived_volatility_risk` | 波动、回撤、风险状态 | 波动率、回撤、Beta 本体 |
| `derived_trading_constraint` | 可交易性、涨跌停、停牌、约束状态 | 交易约束指标本体 |
| `derived_valuation_size` | 规模、估值位置状态 | 估值和市值指标本体 |
| `derived_financial_asof` | 财报可得性、披露时点状态 | 财报 as-of 映射 |
| `derived_financial_quality` | 盈利、现金流、资产负债状态 | 财务质量指标本体 |
| `derived_financial_growth` | 收入/利润/现金流增长状态 | 成长指标本体 |
| `derived_capital_flow` | 主力、两融、北向、龙虎榜状态 | 资金流滚动指标本体 |
| `derived_sector_concept_context` | 行业/概念相对状态 | 行业/概念上下文计算 |
| `derived_index_market_context` | 指数、市场环境、宽度状态 | 市场上下文计算 |
| `derived_cross_sectional` | 横截面暴露和分位状态 | rank/z-score/中性化本体 |
| `derived_corporate_action` | 分红、业绩预告、审计、解禁、回购状态 | 公司行为事件本体 |
| `derived_ownership_governance` | 质押、股东户数、持有人集中度状态 | 持有人治理指标本体 |

## 3. 表结构方案

| 对象 | 类型 | 粒度 | 用途 |
|---|---|---|---|
| `derived_composite_state` | 物理表 | `ts_code + trade_date` | 高频读取的核心状态事实 |
| `derived_composite_state_full_v` | 视图 | `ts_code + trade_date` | 更宽的状态、阈值、共现和文本字段 |
| `composite_state_condition_detail_v` | 视图 | `ts_code + trade_date + condition_name` | 条件明细长表，便于审计和解释 |
| `composite_state_module_coverage_v` | 视图 | `trade_date + module_name` | 模块覆盖率、缺失率、最新更新时间审计 |

建议规模：

| 对象 | 建议字段数 |
|---|---:|
| `derived_composite_state` | 92 |
| `derived_composite_state_full_v` | 115 |
| `composite_state_condition_detail_v` | 10 |
| `composite_state_module_coverage_v` | 8 |

## 4. 核心物理表字段设计

主键：`ts_code + trade_date`

### 4.1 元数据与覆盖状态

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `ts_code` | 股票代码 | VARCHAR | `derived_daily_spine.ts_code` |
| `trade_date` | 交易日期 | DATE | `derived_daily_spine.trade_date` |
| `composite_available_flag` | 综合状态可用标记 | BOOLEAN | 任一核心上游模块可用 |
| `module_available_count` | 上游模块可用数量 | INTEGER | 核心模块可用标记求和 |
| `module_available_ratio` | 上游模块可用率 | DOUBLE | `module_available_count / module_count` |
| `missing_module_names` | 缺失模块名称列表 | VARCHAR | 缺失核心模块用 `;` 拼接 |
| `state_condition_count` | 核心状态条件总数 | INTEGER | 核心布尔状态为 true 的数量 |
| `state_condition_available_count` | 核心状态条件可判断数量 | INTEGER | 核心布尔状态非空数量 |
| `state_condition_available_ratio` | 核心状态条件可判断率 | DOUBLE | `available_count / total_condition_count` |
| `latest_low_freq_event_date` | 最近低频事件日期 | DATE | 财报/公司行为/治理事件日期最大值 |
| `days_since_latest_low_freq_event` | 距最近低频事件天数 | INTEGER | `trade_date - latest_low_freq_event_date` |
| `updated_at` | 本地更新时间 | TIMESTAMP | `CURRENT_TIMESTAMP` |

### 4.2 股票身份与可交易状态

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `is_listed_asof` | 当日是否上市 | BOOLEAN | `derived_daily_spine.is_listed_asof` |
| `is_st_asof` | 当日是否 ST | BOOLEAN | `derived_daily_spine.is_st` 或同义字段 |
| `market_board_state` | 市场板块状态 | VARCHAR | `derived_daily_spine.market/exchange/board` 组合 |
| `list_age_bucket` | 上市年限分层 | VARCHAR | `list_age_days`: `<1y/1-3y/3-5y/5-10y/>=10y` |
| `tradable_state` | 交易可达状态 | VARCHAR | `derived_trading_constraint.tradable_state` |
| `price_valid_state` | 价格有效状态 | VARCHAR | `has_price/price_valid_flag/is_trading` 组合 |
| `limit_lock_state` | 涨跌停锁定状态 | VARCHAR | `none/limit_up/limit_down/one_price_limit/unknown` |
| `recent_suspend_state` | 近期停牌状态 | VARCHAR | 按 `suspend_days_20` 分层 |

### 4.3 趋势与收益状态

这些字段只描述价格与收益事实，连续收益沿用上游后复权口径。

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `price_above_ma20_flag` | 收盘价高于20日均线 | BOOLEAN | `close_hfq > sma_20_hfq` |
| `price_above_ma60_flag` | 收盘价高于60日均线 | BOOLEAN | `close_hfq > sma_60_hfq` |
| `ma20_above_ma60_flag` | 20日均线高于60日均线 | BOOLEAN | `sma_20_hfq > sma_60_hfq` |
| `ma60_above_ma120_flag` | 60日均线高于120日均线 | BOOLEAN | `sma_60_hfq > sma_120_hfq` |
| `ma_alignment_state` | 均线排列状态 | VARCHAR | `bull/partial_bull/mixed/partial_bear/bear/unknown` |
| `ret_20_positive_flag` | 20日收益为正 | BOOLEAN | `derived_return_momentum.ret_20_hfq > 0` |
| `ret_60_positive_flag` | 60日收益为正 | BOOLEAN | `ret_60_hfq > 0` |
| `ret_250_positive_flag` | 250日收益为正 | BOOLEAN | `ret_250_hfq > 0` |
| `momentum_spread_positive_flag` | 中期动量差为正 | BOOLEAN | `momentum_60_20_hfq > 0` |
| `trend_condition_count` | 趋势条件满足数 | INTEGER | 上述趋势布尔字段 true 数量 |
| `trend_state` | 趋势枚举状态 | VARCHAR | 基于趋势条件数与均线排列，见边界问题 |

### 4.4 流动性与波动状态

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `liquidity_available_flag` | 流动性状态可判断 | BOOLEAN | 成交额、换手、Amihud 至少一项可用 |
| `amount_activity_state` | 成交额活跃度状态 | VARCHAR | 基于 `amount_ma_20_pct_all_desc` 或 `amount_ma_20_z_all` 分层 |
| `turnover_activity_state` | 换手活跃度状态 | VARCHAR | 基于 `turnover_rate_ma_20` 的截面位置分层 |
| `liquidity_cost_state` | 流动性成本状态 | VARCHAR | 基于 `amihud_20` 截面位置分层 |
| `volatility_state` | 波动状态 | VARCHAR | 基于 `hv_60` 截面位置分层 |
| `drawdown_state` | 回撤状态 | VARCHAR | 基于 `max_drawdown_60_hfq` 分层 |
| `liquidity_condition_count` | 流动性条件满足数 | INTEGER | 明确布尔条件 true 数量 |
| `risk_condition_count` | 风险状态条件数 | INTEGER | 波动/回撤/约束状态条件 true 数量 |

### 4.5 估值与规模状态

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `size_bucket_all` | 全市场规模分层 | VARCHAR | `log_total_mv_pct_all_desc` 或 `total_mv_pct_all_desc` 分层 |
| `size_bucket_sw_l2` | 申万二级内规模分层 | VARCHAR | `log_total_mv_pct_sw_l2_desc` 分层 |
| `pe_valid_flag` | PE 可解释标记 | BOOLEAN | `pe_ttm > 0` |
| `pb_valid_flag` | PB 可解释标记 | BOOLEAN | `pb > 0` |
| `valuation_percentile_state` | 历史估值位置状态 | VARCHAR | `pe_ttm_pct_5y/pb_pct_5y/ps_ttm_pct_5y` 分层，不判断贵贱好坏 |
| `value_exposure_state` | 价值暴露状态 | VARCHAR | `derived_cross_sectional.value_exposure_z` 分层 |
| `size_exposure_state` | 规模暴露状态 | VARCHAR | `derived_cross_sectional.size_exposure_z` 分层 |
| `valuation_condition_count` | 估值状态条件数 | INTEGER | 可解释估值条件 true 数量 |

### 4.6 财务披露、质量与成长状态

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `financial_available_flag` | 财务状态可用标记 | BOOLEAN | `derived_financial_asof.latest_report_end_date IS NOT NULL` |
| `financial_statement_complete_flag` | 当前报告期三表/指标完整 | BOOLEAN | `derived_financial_quality.has_complete_statement_set_asof` |
| `financial_staleness_state` | 财务数据滞后状态 | VARCHAR | `days_since_latest_financial_effective_date` 分层 |
| `profitability_positive_flag` | 盈利能力为正 | BOOLEAN | `roe_asof > 0 OR roa_asof > 0`，具体口径待确认 |
| `cashflow_profit_match_flag` | 经营现金流与利润同向 | BOOLEAN | `ocf_to_profit_asof > 0` |
| `leverage_state` | 资产负债状态 | VARCHAR | `debt_to_assets_asof` 分层 |
| `growth_revenue_positive_flag` | 收入同比为正 | BOOLEAN | `revenue_yoy_asof > 0` |
| `growth_profit_positive_flag` | 净利润同比为正 | BOOLEAN | `netprofit_yoy_asof > 0` |
| `quality_exposure_state` | 财务质量暴露状态 | VARCHAR | `derived_cross_sectional.quality_exposure_z` 分层 |
| `growth_exposure_state` | 成长暴露状态 | VARCHAR | `derived_cross_sectional.growth_exposure_z` 分层 |
| `financial_condition_count` | 财务条件满足数 | INTEGER | 财务布尔条件 true 数量 |

### 4.7 资金流与参与者状态

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `capital_flow_available_flag` | 资金流状态可用标记 | BOOLEAN | `derived_capital_flow.has_moneyflow OR has_margin OR has_north_holding` |
| `main_flow_20_positive_flag` | 20日主力净流入为正 | BOOLEAN | `main_flow_sum_20 > 0` |
| `main_flow_persist_state` | 主力净流入持续状态 | VARCHAR | `main_flow_persist_ratio_20` 分层 |
| `margin_balance_change_state` | 融资余额变化状态 | VARCHAR | `margin_balance_chg_20` 分层 |
| `north_holding_change_state` | 北向持股变化状态 | VARCHAR | `north_hold_ratio_chg_20` 分层 |
| `top_list_recent_flag` | 近期龙虎榜事件标记 | BOOLEAN | `top_list_count_20 > 0` 或完整视图字段 |
| `flow_exposure_state` | 资金流暴露状态 | VARCHAR | `derived_cross_sectional.flow_exposure_z` 分层 |
| `capital_flow_condition_count` | 资金流条件满足数 | INTEGER | 资金流布尔条件 true 数量 |

### 4.8 行业、概念与市场上下文状态

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `sector_context_available_flag` | 行业上下文可用标记 | BOOLEAN | `derived_sector_concept_context.sw_l1_code IS NOT NULL` |
| `sw_l1_code` | 申万一级行业代码 | VARCHAR | `derived_sector_concept_context.sw_l1_code` |
| `sw_l2_code` | 申万二级行业代码 | VARCHAR | `derived_sector_concept_context.sw_l2_code` |
| `sector_relative_return_state` | 行业内相对收益状态 | VARCHAR | `stock_excess_sw_l2_20` 分层 |
| `concept_membership_state` | 概念归属状态 | VARCHAR | `none/single/multiple/unknown` |
| `concept_heat_state` | 概念热度状态 | VARCHAR | `concept_hot_count_20` 或概念列表增强字段分层 |
| `index_membership_state` | 主要指数成员状态 | VARCHAR | HS300/ZZ500/ZZ1000/STAR/CHINEXT 等组合 |
| `market_context_state` | 市场环境状态 | VARCHAR | 基于市场宽度/指数收益/涨跌停分布枚举 |
| `sector_market_condition_count` | 板块市场条件数 | INTEGER | 行业/概念/市场上下文布尔条件 true 数量 |

### 4.9 公司行为与持有人治理状态

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `corporate_action_available_flag` | 公司行为状态可用标记 | BOOLEAN | `derived_corporate_action` 核心事件任一可用 |
| `dividend_recent_state` | 近期分红状态 | VARCHAR | `cash_dividend_ttm`、最近分红日期分层 |
| `forecast_recent_state` | 业绩预告状态 | VARCHAR | `has_forecast_asof` 与预告类型代码 |
| `audit_opinion_state` | 审计意见状态 | VARCHAR | `audit_opinion_code_latest` 映射 |
| `repurchase_recent_flag` | 近期回购事件标记 | BOOLEAN | `repurchase_amount_365d > 0` |
| `unlock_future_state` | 未来解禁状态 | VARCHAR | `next_share_float_share_30d/90d` 分层，限已公告 |
| `ownership_available_flag` | 持有人治理状态可用标记 | BOOLEAN | `derived_ownership_governance.ownership_available_flag` |
| `pledge_ratio_state` | 质押比例状态 | VARCHAR | `none/ge10/ge30/ge50/unknown` |
| `holder_number_change_state` | 股东户数变化状态 | VARCHAR | `holder_num_chg_rate_1report/4report` 分层 |
| `holder_concentration_state` | 股权集中度状态 | VARCHAR | `top10_holder_ratio_latest` 分层 |
| `event_condition_count` | 事件治理条件数 | INTEGER | 公司行为/治理布尔条件 true 数量 |

### 4.10 截面暴露共现状态

| 字段 | 中文名 | 类型 | 衍生逻辑 |
|---|---|---|---|
| `exposure_available_count` | 横截面暴露可用数量 | INTEGER | size/value/momentum/volatility/liquidity/quality/growth/flow 非空数 |
| `value_quality_pair_state` | 价值与质量暴露共现状态 | VARCHAR | `value_exposure_z` 与 `quality_exposure_z` 分层组合 |
| `momentum_flow_pair_state` | 动量与资金流暴露共现状态 | VARCHAR | `momentum_exposure_z` 与 `flow_exposure_z` 分层组合 |
| `growth_quality_pair_state` | 成长与质量暴露共现状态 | VARCHAR | `growth_exposure_z` 与 `quality_exposure_z` 分层组合 |
| `risk_liquidity_pair_state` | 波动与流动性暴露共现状态 | VARCHAR | `volatility_exposure_z` 与 `liquidity_exposure_z` 分层组合 |
| `multi_domain_condition_count` | 多域条件满足数 | INTEGER | 趋势/流动性/财务/资金/事件条件数汇总 |

## 5. 完整视图扩展

`derived_composite_state_full_v` 继承核心表，并扩展以下内容：

1. 每个状态字段的原始依赖值，例如 `trend_state` 对应的 `close_hfq/sma_20_hfq/sma_60_hfq`。
2. 更丰富的阈值版本，例如 5/20/60/120/250 周期的收益方向和成交活跃状态。
3. 横截面暴露的原始 z 值和分位值。
4. 行业、概念、指数成员文本字段。
5. 公司行为和治理的最近事件文本字段。
6. 条件明细 JSON 或长表入口字段，例如 `condition_names_true`、`condition_names_available`。

完整视图不新增主观评分，只提供解释材料。

## 6. 条件明细视图

`composite_state_condition_detail_v` 建议用长表表达每个条件的来源与结果：

| 字段 | 中文名 | 类型 | 逻辑 |
|---|---|---|---|
| `ts_code` | 股票代码 | VARCHAR | 股票代码 |
| `trade_date` | 交易日期 | DATE | 交易日期 |
| `condition_group` | 条件组 | VARCHAR | `trend/liquidity/risk/valuation/financial/flow/sector/event/exposure` |
| `condition_name` | 条件名称 | VARCHAR | 条件字段名 |
| `condition_value` | 条件是否成立 | BOOLEAN | 条件结果 |
| `condition_available_flag` | 条件是否可判断 | BOOLEAN | 依赖字段是否可用 |
| `source_table` | 来源表 | VARCHAR | 上游来源 |
| `source_fields` | 来源字段 | VARCHAR | 依赖字段列表 |
| `formula_text` | 公式文本 | VARCHAR | 可读公式 |
| `updated_at` | 本地更新时间 | TIMESTAMP | `CURRENT_TIMESTAMP` |

该视图用于解释 `*_condition_count`，避免计数字段变成黑箱。

## 7. 模块覆盖审计视图

`composite_state_module_coverage_v` 建议按交易日和模块统计覆盖情况：

| 字段 | 中文名 | 类型 | 逻辑 |
|---|---|---|---|
| `trade_date` | 交易日期 | DATE | 交易日 |
| `module_name` | 模块名称 | VARCHAR | 上游模块 |
| `expected_rows` | 应覆盖行数 | BIGINT | 当日 `derived_daily_spine` 行数 |
| `available_rows` | 可用行数 | BIGINT | 模块可用标记为 true 的行数 |
| `available_ratio` | 可用率 | DOUBLE | `available_rows / expected_rows` |
| `key_non_null_ratio` | 关键字段非空率 | DOUBLE | 模块关键字段非空统计 |
| `latest_source_update_at` | 来源最新更新时间 | TIMESTAMP | 来源表最大 `updated_at` |
| `quality_note` | 质量备注 | VARCHAR | 异常说明 |

## 8. 阈值与枚举建议

建议采用统一、可审计的阈值体系：

| 场景 | 建议阈值 |
|---|---|
| 暴露 z 值状态 | `<= -1`, `(-1,1)`, `>= 1` 三档 |
| 截面分位状态 | `<20%`, `20%-80%`, `>80%` 三档 |
| 历史估值位置 | `<20%`, `20%-80%`, `>80%` 三档 |
| 收益方向 | `>0`, `=0`, `<0` |
| 质押比例 | 沿用 ownership：`<10`, `>=10`, `>=30`, `>=50` |
| 财务滞后 | `<=120d`, `121-240d`, `>240d` |
| 上市年限 | `<1y`, `1-3y`, `3-5y`, `5-10y`, `>=10y` |
| 未来解禁 | `none`, `30d`, `90d`, `unknown`，仅统计已公告 |

所有阈值都应写入变量字典和设计文档，不隐藏在 SQL 中。

## 9. 复权口径

| 变量类型 | 口径 |
|---|---|
| 价格趋势、收益、动量、回撤 | 使用上游后复权口径字段 |
| 成交额、换手、资金流、市值、估值 | 原始交易事实口径，不复权 |
| 财务、公司行为、治理事件 | point-in-time asof 口径，不复权 |
| 横截面暴露 | 继承 `derived_cross_sectional` 已定义口径 |

## 10. 实施步骤

1. 废弃旧 `value_quality_score` 占位字段，注册新的 `derived_composite_state`、`derived_composite_state_full_v`、`composite_state_condition_detail_v`、`composite_state_module_coverage_v`。
2. 编写 `scripts/register_phase3_composite_state.py`，同步 schema 和变量字典。
3. 编写 `scripts/reset_phase3_composite_state_table.py`。
4. 编写 `scripts/build_phase3_composite_state_core.py`，按年份全量构建核心表。
5. 编写 `scripts/create_phase3_composite_state_views.py`。
6. 编写 `scripts/generate_phase3_composite_state_audit.py`。
7. 刷新 `outputs/variable_dictionary/global_variable_dictionary.xlsx`。
8. 增加专项测试：旧 score 字段不存在、核心字段注册一致、状态枚举值合法、PIT 检查通过。

## 11. 审计要求

实施完成后生成 `reports/phase3_composite_state_audit.md`，至少包含：

1. 核心表行数、列数、股票数、日期范围。
2. 上游模块覆盖率。
3. 各状态组非空率。
4. 枚举字段非法值检查。
5. `*_condition_count` 与条件明细视图一致性检查。
6. point-in-time 检查：财务、公司行为、治理事件不得使用未来公告。
7. 旧字段 `value_quality_score` 不存在检查。

## 12. 待确认边界问题

1. 是否确认删除旧占位字段 `value_quality_score`，并禁止本模块出现任何 `score` 后缀字段？
2. 是否接受 `*_condition_count` 这类“条件计数”字段？它们不做加权、不表达好坏，只统计明确布尔事实成立数量。若你认为仍接近评分，我会只保留布尔字段和枚举字段。
3. 暴露状态分层是否采用统一 z 值三档：`<=-1`、`-1~1`、`>=1`？截面分位和历史分位是否采用 `<20%`、`20%-80%`、`>80%`？
4. `trend_state` 是否可以采用 `bull/partial_bull/mixed/partial_bear/bear/unknown` 这类英文枚举？还是你希望统一使用中文枚举或数字编码？
5. 核心物理表是否接受约 90-130 列的宽度？更宽的解释字段进入 `derived_composite_state_full_v`。
6. 是否把 `stock_features_plus/full` 统一出口视图放到本模块实施之后另开一步做？我的建议是先完成 composite_state，再做统一出口视图，避免出口视图与模块建设互相牵制。
7. 公司行为和治理状态中，分红、回购、质押、解禁等事件只做事实状态，不做风险/机会判断，是否确认？
