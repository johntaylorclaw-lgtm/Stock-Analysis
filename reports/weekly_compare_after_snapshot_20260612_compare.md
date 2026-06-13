# 增量窗口一致性对照报告

生成时间：2026-06-13T09:56:38
窗口：`2026-06-01` 至 `2026-06-12`
快照前缀：`audit_tmp_phase4_full_`
结果：pass

## 汇总

- 表数量：25
- 通过表：25
- 失败表：0
- 键缺失/额外行：0
- 差异字段数：0
- 差异单元格数：0

## 表级结果

| 表 | 当前行数 | 快照行数 | 比较字段数 | 键差异 | 差异字段数 | 差异单元格 | 结果 |
|---|---:|---:|---:|---:|---:|---:|---|
| `derived_daily_spine` | 55116 | 55116 | 46 | 0 | 0 | 0 | pass |
| `derived_price_technical` | 55116 | 55116 | 13 | 0 | 0 | 0 | pass |
| `derived_volume_liquidity` | 55116 | 55116 | 11 | 0 | 0 | 0 | pass |
| `derived_return_momentum` | 55116 | 55116 | 13 | 0 | 0 | 0 | pass |
| `derived_volatility_risk` | 55116 | 55116 | 10 | 0 | 0 | 0 | pass |
| `derived_trading_constraint` | 55116 | 55116 | 11 | 0 | 0 | 0 | pass |
| `derived_valuation_size` | 55116 | 55116 | 31 | 0 | 0 | 0 | pass |
| `derived_valuation_percentile_cache` | 55116 | 55116 | 40 | 0 | 0 | 0 | pass |
| `derived_financial_asof` | 55116 | 55116 | 27 | 0 | 0 | 0 | pass |
| `derived_financial_quality` | 55116 | 55116 | 114 | 0 | 0 | 0 | pass |
| `derived_financial_growth` | 55116 | 55116 | 252 | 0 | 0 | 0 | pass |
| `derived_capital_flow` | 55116 | 55116 | 61 | 0 | 0 | 0 | pass |
| `derived_northbound_flow_cache` | 55116 | 55116 | 38 | 0 | 0 | 0 | pass |
| `derived_capital_flow_event_cache` | 55116 | 55116 | 29 | 0 | 0 | 0 | pass |
| `derived_sector_daily_cache` | 1620 | 1620 | 93 | 0 | 0 | 0 | pass |
| `derived_concept_daily_cache` | 8730 | 8730 | 86 | 0 | 0 | 0 | pass |
| `derived_sector_concept_context` | 55116 | 55116 | 101 | 0 | 0 | 0 | pass |
| `derived_concept_stock_context_cache` | 55116 | 55116 | 221 | 0 | 0 | 0 | pass |
| `derived_index_daily_cache` | 140 | 140 | 26 | 0 | 0 | 0 | pass |
| `derived_index_membership_cache` | 55116 | 55116 | 16 | 0 | 0 | 0 | pass |
| `derived_index_market_context` | 55116 | 55116 | 102 | 0 | 0 | 0 | pass |
| `derived_cross_sectional` | 55116 | 55116 | 350 | 0 | 0 | 0 | pass |
| `derived_corporate_action` | 55116 | 55116 | 101 | 0 | 0 | 0 | pass |
| `derived_ownership_governance` | 55116 | 55116 | 60 | 0 | 0 | 0 | pass |
| `derived_composite_state` | 55116 | 55116 | 89 | 0 | 0 | 0 | pass |
