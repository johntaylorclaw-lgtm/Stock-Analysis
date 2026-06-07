# Daily-Light 验证报告

生成时间：2026-06-07T15:38:20
截至日期：`2026-06-07`
最新交易日：`2026-06-05`
当前锚点日期：`2026-06-05`
结果：`pass`

## 窗口判断

- 自动补数上限：10 个交易日
- 校验日期：2026-06-05
- 待增量日期：无
- 待增量交易日数：0
- 是否需要显式确认：否

## 汇总

- 表数量：39
- 缺失表：0
- 有目标日期缺口的表：0
- 有重复键的表：0
- 股票级衍生行数低于 spine 的表：0

## 表级结果

| 表 | 分组 | 最大日期 | 目标日期缺口 | 重复键 | 空 ts_code | 最新/目标行数 | 结果 |
|---|---|---|---:|---:|---:|---:|---|
| `stock_daily` | base_daily | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `stock_daily_basic` | base_daily | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `stock_adj_factor` | base_daily | 2026-06-05 | 0 | 0 | 0 | 5526 | pass |
| `stock_limit_price` | base_daily | 2026-06-05 | 0 | 0 | 0 | 7634 | pass |
| `stock_moneyflow_daily` | base_daily | 2026-06-05 | 0 | 0 | 0 | 5197 | pass |
| `margin_detail` | base_daily | 2026-06-05 | 0 | 0 | 0 | 1981 | pass |
| `northbound_daily` | base_daily | 2026-06-05 | 0 | 0 | None | 1 | pass |
| `northbound_holding` | base_daily | 2026-06-05 | 0 | 0 | 0 | 936 | pass |
| `top_list_daily` | base_daily | 2026-06-05 | 0 | None | 0 | 83 | pass |
| `top_inst_detail` | base_daily | 2026-06-05 | 0 | None | 0 | 786 | pass |
| `index_daily` | base_daily | 2026-06-05 | 0 | 0 | None | 14 | pass |
| `index_weight` | base_periodic | 2026-06-01 | 0 | 0 | None | 0 | pass |
| `derived_daily_spine` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_price_technical` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_volume_liquidity` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_return_momentum` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_volatility_risk` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_trading_constraint` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_valuation_size` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_valuation_percentile_cache` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_financial_asof` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_financial_quality` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_financial_growth` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_capital_flow` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_northbound_flow_cache` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_capital_flow_event_cache` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_sector_daily_cache` | derived | 2026-06-05 | 0 | 0 | None | 162 | pass |
| `derived_concept_daily_cache` | derived | 2026-06-05 | 0 | 0 | None | 873 | pass |
| `derived_sector_concept_context` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_concept_stock_context_cache` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_index_daily_cache` | derived | 2026-06-05 | 0 | 0 | None | 14 | pass |
| `derived_index_membership_cache` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_index_market_context` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_cross_sectional` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_corporate_action` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `derived_composite_state` | derived | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `stock_features_core` | feature_view | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `stock_features_plus` | feature_view | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
| `stock_features_full` | feature_view | 2026-06-05 | 0 | 0 | 0 | 5514 | pass |
