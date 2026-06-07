# Phase 4 增量性能审计报告

生成时间：2026-06-06T17:44:46

## 1. 总览

- 写入窗口：`2026-05-17` 至 `2026-05-26`
- 模块数量：17
- 配置校验：passed
- 文档同步：up_to_date

## 2. 模块窗口

| 模块 | 变量数 | 读取窗口 | 写入窗口 | 表 |
|---|---:|---:|---:|---|
| `daily_spine` | 43 | 20 | 10 | derived_daily_spine |
| `price_technical` | 13 | 420 | 10 | derived_price_technical |
| `volume_liquidity` | 11 | 180 | 10 | derived_volume_liquidity |
| `return_momentum` | 13 | 420 | 10 | derived_return_momentum |
| `volatility_risk` | 10 | 360 | 10 | derived_volatility_risk |
| `trading_constraint` | 11 | 60 | 10 | derived_trading_constraint |
| `valuation_size` | 20 | 20 | 10 | derived_valuation_size |
| `financial_asof` | 27 | 260 | 10 | derived_financial_asof |
| `financial_quality` | 114 | 260 | 10 | derived_financial_quality |
| `financial_growth` | 252 | 260 | 10 | derived_financial_growth |
| `capital_flow` | 53 | 250 | 10 | derived_capital_flow |
| `sector_concept_context` | 101 | 520 | 10 | derived_sector_concept_context |
| `index_market_context` | 102 | 520 | 10 | derived_index_market_context |
| `cross_sectional` | 1060 | 520 | 10 | derived_cross_sectional, derived_cross_sectional_full_v |
| `corporate_action` | 150 | 1260 | 10 | corporate_action_event_timeline_v, derived_corporate_action, derived_corporate_action_full_v |
| `ownership_governance` | 106 | 1260 | 10 | derived_ownership_governance, derived_ownership_governance_full_v, ownership_governance_event_timeline_v |
| `composite_state` | 128 | 250 | 10 | composite_state_condition_detail_v, composite_state_module_coverage_v, derived_composite_state, derived_composite_state_full_v |

## 3. Phase 3 脚本分类

| 分类 | 数量 |
|---|---:|
| `audit_report` | 13 |
| `external_full_sync` | 1 |
| `full_rebuild_only` | 6 |
| `registry_maintenance` | 10 |
| `review_needed` | 7 |
| `unified_builder_backend` | 6 |
| `view_rebuild_only` | 9 |
| `windowized_cache_script` | 5 |

## 4. 最近构建耗时

- 最近运行时间：2026-06-06T17:33:51 至 2026-06-06T17:36:43
- 总耗时：174.748 秒

| 类型 | 名称 | 阶段 | 状态 | 行数 | 耗时秒 |
|---|---|---|---|---:|---:|
| module | `daily_spine` | core | success | 38504 | 2.095 |
| module | `price_technical` | core | success | 38504 | 8.496 |
| module | `volume_liquidity` | core | success | 38504 | 1.995 |
| module | `return_momentum` | core | success | 38504 | 1.955 |
| module | `volatility_risk` | core | success | 38504 | 3.026 |
| module | `trading_constraint` | core | success | 38504 | 5.956 |
| module | `valuation_size` | core | built | 38504 | 1.428 |
| module | `financial_asof` | core | success | 38504 | 6.634 |
| module | `financial_quality` | core | success | 38504 | 16.255 |
| module | `financial_growth` | core | success | 38504 | 8.824 |
| module | `capital_flow` | core | success | 38504 | 12.035 |
| module | `sector_concept_context` | core | success | 38504 | 7.584 |
| module | `index_market_context` | core | success | 38504 | 4.608 |
| module | `cross_sectional` | core | success | 38504 | 15.049 |
| module | `corporate_action` | core | success | 38504 | 54.534 |
| module | `ownership_governance` | core | success | 38504 | 18.194 |
| module | `composite_state` | core | success | 38504 | 3.935 |

## 5. 风险与遗留

当前未发现配置、文档或脚本分类层面的阻断问题。

## 6. 建议

1. 将 `phase4-audit` 纳入日批前后固定检查。
2. 分析 `return_momentum`、`price_technical` 等仍保留 750 天上下文的技术模块，评估状态缓存或按股票批处理。
3. 对完整日批组合做分组验收，确认 Phase 4 剩余瓶颈和可验收标准。
