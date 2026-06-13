# Daily-Light 验证报告

生成时间：2026-06-08T15:58:53
截至日期：`2026-06-08`
最新交易日：`2026-06-08`
当前锚点日期：`2026-06-05`
结果：`warning`

## 窗口判断

- 自动补数上限：10 个交易日
- 校验日期：2026-06-05
- 待增量日期：2026-06-08
- 待增量交易日数：1
- 是否需要显式确认：否

## 汇总

- 表数量：39
- 缺失表：0
- 有目标日期缺口的表：38
- 有重复键的表：0
- 股票级衍生行数低于 spine 的表：0

## 表级结果

| 表 | 分组 | 最大日期 | 目标日期缺口 | 重复键 | 空 ts_code | 最新/目标行数 | 结果 |
|---|---|---|---:|---:|---:|---:|---|
| `stock_daily` | base_daily | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `stock_daily_basic` | base_daily | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `stock_adj_factor` | base_daily | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `stock_limit_price` | base_daily | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `stock_moneyflow_daily` | base_daily | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `margin_detail` | base_daily | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `northbound_daily` | base_daily | 2026-06-05 | 1 | 0 | None | 0 | fail |
| `northbound_holding` | base_daily | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `top_list_daily` | base_daily | 2026-06-05 | 1 | None | 0 | 0 | fail |
| `top_inst_detail` | base_daily | 2026-06-05 | 1 | None | 0 | 0 | fail |
| `index_daily` | base_daily | 2026-06-05 | 1 | 0 | None | 0 | fail |
| `index_weight` | base_periodic | 2026-06-01 | 0 | 0 | None |  | pass |
| `derived_daily_spine` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_price_technical` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_volume_liquidity` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_return_momentum` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_volatility_risk` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_trading_constraint` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_valuation_size` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_valuation_percentile_cache` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_financial_asof` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_financial_quality` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_financial_growth` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_capital_flow` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_northbound_flow_cache` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_capital_flow_event_cache` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_sector_daily_cache` | derived | 2026-06-05 | 1 | 0 | None | 0 | fail |
| `derived_concept_daily_cache` | derived | 2026-06-05 | 1 | 0 | None | 0 | fail |
| `derived_sector_concept_context` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_concept_stock_context_cache` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_index_daily_cache` | derived | 2026-06-05 | 1 | 0 | None | 0 | fail |
| `derived_index_membership_cache` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_index_market_context` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_cross_sectional` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_corporate_action` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `derived_composite_state` | derived | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `stock_features_core` | feature_view | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `stock_features_plus` | feature_view | 2026-06-05 | 1 | 0 | 0 | 0 | fail |
| `stock_features_full` | feature_view | 2026-06-05 | 1 | 0 | 0 | 0 | fail |

## 问题明细

### stock_daily
- 目标日期无数据：2026-06-08
### stock_daily_basic
- 目标日期无数据：2026-06-08
### stock_adj_factor
- 目标日期无数据：2026-06-08
### stock_limit_price
- 目标日期无数据：2026-06-08
### stock_moneyflow_daily
- 目标日期无数据：2026-06-08
### margin_detail
- 目标日期无数据：2026-06-08
### northbound_daily
- 目标日期无数据：2026-06-08
### northbound_holding
- 目标日期无数据：2026-06-08
### top_list_daily
- 目标日期无数据：2026-06-08
### top_inst_detail
- 目标日期无数据：2026-06-08
### index_daily
- 目标日期无数据：2026-06-08
### derived_daily_spine
- 目标日期无数据：2026-06-08
### derived_price_technical
- 目标日期无数据：2026-06-08
### derived_volume_liquidity
- 目标日期无数据：2026-06-08
### derived_return_momentum
- 目标日期无数据：2026-06-08
### derived_volatility_risk
- 目标日期无数据：2026-06-08
### derived_trading_constraint
- 目标日期无数据：2026-06-08
### derived_valuation_size
- 目标日期无数据：2026-06-08
### derived_valuation_percentile_cache
- 目标日期无数据：2026-06-08
### derived_financial_asof
- 目标日期无数据：2026-06-08
### derived_financial_quality
- 目标日期无数据：2026-06-08
### derived_financial_growth
- 目标日期无数据：2026-06-08
### derived_capital_flow
- 目标日期无数据：2026-06-08
### derived_northbound_flow_cache
- 目标日期无数据：2026-06-08
### derived_capital_flow_event_cache
- 目标日期无数据：2026-06-08
### derived_sector_daily_cache
- 目标日期无数据：2026-06-08
### derived_concept_daily_cache
- 目标日期无数据：2026-06-08
### derived_sector_concept_context
- 目标日期无数据：2026-06-08
### derived_concept_stock_context_cache
- 目标日期无数据：2026-06-08
### derived_index_daily_cache
- 目标日期无数据：2026-06-08
### derived_index_membership_cache
- 目标日期无数据：2026-06-08
### derived_index_market_context
- 目标日期无数据：2026-06-08
### derived_cross_sectional
- 目标日期无数据：2026-06-08
### derived_corporate_action
- 目标日期无数据：2026-06-08
### derived_composite_state
- 目标日期无数据：2026-06-08
### stock_features_core
- 目标日期无数据：2026-06-08
### stock_features_plus
- 目标日期无数据：2026-06-08
### stock_features_full
- 目标日期无数据：2026-06-08
