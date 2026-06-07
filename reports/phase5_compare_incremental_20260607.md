# 增量窗口一致性对照报告

生成时间：2026-06-07T10:07:12
窗口：`2026-05-27` 至 `2026-06-05`
快照前缀：`audit_tmp_phase4_full_`
结果：pass

## 汇总

- 表数量：24
- 通过表：24
- 失败表：0
- 键缺失/额外行：0
- 差异字段数：0
- 差异单元格数：0

## 表级结果

| 表 | 当前行数 | 快照行数 | 比较字段数 | 键差异 | 差异字段数 | 差异单元格 | 结果 |
|---|---:|---:|---:|---:|---:|---:|---|
| `derived_daily_spine` | 44069 | 44069 | 46 | 0 | 0 | 0 | pass |
| `derived_price_technical` | 44069 | 44069 | 13 | 0 | 0 | 0 | pass |
| `derived_volume_liquidity` | 44069 | 44069 | 11 | 0 | 0 | 0 | pass |
| `derived_return_momentum` | 44069 | 44069 | 13 | 0 | 0 | 0 | pass |
| `derived_volatility_risk` | 44069 | 44069 | 10 | 0 | 0 | 0 | pass |
| `derived_trading_constraint` | 44069 | 44069 | 11 | 0 | 0 | 0 | pass |
| `derived_valuation_size` | 44069 | 44069 | 31 | 0 | 0 | 0 | pass |
| `derived_valuation_percentile_cache` | 44069 | 44069 | 40 | 0 | 0 | 0 | pass |
| `derived_financial_asof` | 44069 | 44069 | 27 | 0 | 0 | 0 | pass |
| `derived_financial_quality` | 44069 | 44069 | 114 | 0 | 0 | 0 | pass |
| `derived_financial_growth` | 44069 | 44069 | 252 | 0 | 0 | 0 | pass |
| `derived_capital_flow` | 44069 | 44069 | 61 | 0 | 0 | 0 | pass |
| `derived_northbound_flow_cache` | 44069 | 44069 | 38 | 0 | 0 | 0 | pass |
| `derived_capital_flow_event_cache` | 44069 | 44069 | 29 | 0 | 0 | 0 | pass |
| `derived_sector_daily_cache` | 1296 | 1296 | 93 | 0 | 0 | 0 | pass |
| `derived_concept_daily_cache` | 6984 | 6984 | 86 | 0 | 0 | 0 | pass |
| `derived_sector_concept_context` | 44069 | 44069 | 101 | 0 | 0 | 0 | pass |
| `derived_concept_stock_context_cache` | 44069 | 44069 | 221 | 0 | 0 | 0 | pass |
| `derived_index_daily_cache` | 112 | 112 | 26 | 0 | 0 | 0 | pass |
| `derived_index_membership_cache` | 44069 | 44069 | 16 | 0 | 0 | 0 | pass |
| `derived_index_market_context` | 44069 | 44069 | 102 | 0 | 0 | 0 | pass |
| `derived_cross_sectional` | 44069 | 44069 | 350 | 0 | 0 | 0 | pass |
| `derived_corporate_action` | 44069 | 44069 | 101 | 0 | 0 | 0 | pass |
| `derived_composite_state` | 44069 | 44069 | 89 | 0 | 0 | 0 | pass |
