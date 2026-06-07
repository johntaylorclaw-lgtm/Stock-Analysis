# Phase 5 统一出口视图覆盖率审计

生成时间：2026-06-07T11:56:32

## 当前规模

| 视图 | 当前列数 |
|---|---:|
| `stock_features_core` | 318 |
| `stock_features_plus` | 1198 |
| `stock_features_full` | 1602 |

## 模块覆盖

| 模块 | 模块有效字段 | core覆盖 | core缺口 | plus覆盖 | plus缺口 | full覆盖 | full缺口 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `derived_daily_spine` | 46 | 46 | 0 | 46 | 0 | 46 | 0 |
| `derived_price_technical` | 13 | 13 | 0 | 13 | 0 | 13 | 0 |
| `derived_volume_liquidity` | 11 | 11 | 0 | 11 | 0 | 11 | 0 |
| `derived_return_momentum` | 13 | 13 | 0 | 13 | 0 | 13 | 0 |
| `derived_volatility_risk` | 10 | 10 | 0 | 10 | 0 | 10 | 0 |
| `derived_trading_constraint` | 11 | 11 | 0 | 11 | 0 | 11 | 0 |
| `derived_valuation_size` | 31 | 31 | 0 | 31 | 0 | 31 | 0 |
| `derived_financial_asof` | 27 | 27 | 0 | 27 | 0 | 27 | 0 |
| `derived_financial_quality` | 114 | 22 | 92 | 114 | 0 | 114 | 0 |
| `derived_financial_growth` | 252 | 22 | 230 | 252 | 0 | 252 | 0 |
| `derived_capital_flow` | 61 | 31 | 30 | 61 | 0 | 61 | 0 |
| `derived_sector_concept_context` | 101 | 28 | 73 | 101 | 0 | 101 | 0 |
| `derived_index_market_context` | 102 | 29 | 73 | 102 | 0 | 102 | 0 |
| `derived_cross_sectional` | 350 | 21 | 329 | 21 | 329 | 349 | 1 |
| `derived_corporate_action` | 101 | 4 | 97 | 101 | 0 | 101 | 0 |
| `derived_ownership_governance` | 60 | 0 | 60 | 60 | 0 | 60 | 0 |
| `derived_composite_state` | 89 | 6 | 83 | 89 | 0 | 89 | 0 |

## 审计结论

1. Phase 3 股票级模块有效字段约 1392 个，`stock_features_full` 精确字段名缺口为 1 个。
2. 交易行情与技术分析相关模块有效字段约 104 个，`stock_features_core` 当前缺口为 1067 个，定位为日常核心出口而非全量字段出口。
3. `stock_features_plus` 当前精确字段名缺口为 329 个，主要来自横截面全量字段；其定位为研究增强出口。
4. `stock_features_full` 用于全量事实研究和审计；对重名字段会使用模块前缀，因此表格中的精确字段名覆盖口径可能低估带前缀字段的实际可用覆盖。

## 当前边界

| 视图 | 定位 | 当前处理 |
|---|---|---|
| `stock_features_core` | 日常高频稳定出口 | 扩充核心交易、估值、财务、资金、行业市场和截面字段 |
| `stock_features_plus` | 研究增强出口 | 在 core 基础上纳入财务质量/成长、资金、行业概念、指数市场、公司行为、股权治理、综合事实状态全量字段 |
| `stock_features_full` | 审计和全量研究出口 | 在 plus 基础上纳入横截面全量字段和基础 enriched 字段；对重复字段使用模块前缀 |
