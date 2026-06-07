# Phase 4 增量加载真实案例测试报告

- 生成时间：2026-06-06T23:10:00
- 增量窗口：2026-05-27 至 2026-06-05
- 缺口交易日：2026-05-27、2026-05-28、2026-05-29、2026-06-01、2026-06-02、2026-06-03、2026-06-04、2026-06-05
- 对照方式：先重算 2026-05-01 至 2026-06-05 作为近期全量参照并快照，再重建 2026-05-27 至 2026-06-05 增量窗口，比较重叠窗口。
- 数值字段容差：`max(1e-6, 1e-12 * 字段量级)`；SQL NULL 与 NaN 均视为缺失值。
- 对照报告：`reports/phase4_incremental_vs_full_overlap_tmp.json`

## 1. 结论

本轮基础变量与衍生变量增量加载测试通过。

最终对照 24 张表全部通过，目标窗口内无键缺失、无字段差异。比较对象覆盖个股日核心表、财务衍生表、资金流缓存、行业/概念缓存、指数缓存、横截面表、公司行动表与综合状态表。

## 2. 基础表补数覆盖

| 表 | 近期窗口行数 | 最大交易日 |
|---|---:|---|
| stock_daily | 44069 | 2026-06-05 |
| stock_daily_basic | 44069 | 2026-06-05 |
| stock_adj_factor | 44199 | 2026-06-05 |
| stock_limit_price | 61030 | 2026-06-05 |
| stock_moneyflow_daily | 41542 | 2026-06-05 |
| margin_detail | 32541 | 2026-06-05 |
| northbound_daily | 8 | 2026-06-05 |
| northbound_holding | 7485 | 2026-06-05 |
| top_list_daily | 721 | 2026-06-05 |
| top_inst_detail | 6771 | 2026-06-05 |
| index_daily | 112 | 2026-06-05 |
| index_weight | 300 | 2026-06-01 |

## 3. 衍生表增量与近期全量一致性

| 表 | 当前行数 | 快照行数 | 比较字段数 | 结果 |
|---|---:|---:|---:|---|
| derived_daily_spine | 44069 | 44069 | 46 | pass |
| derived_price_technical | 44069 | 44069 | 13 | pass |
| derived_volume_liquidity | 44069 | 44069 | 11 | pass |
| derived_return_momentum | 44069 | 44069 | 13 | pass |
| derived_volatility_risk | 44069 | 44069 | 10 | pass |
| derived_trading_constraint | 44069 | 44069 | 11 | pass |
| derived_valuation_size | 44069 | 44069 | 31 | pass |
| derived_valuation_percentile_cache | 44069 | 44069 | 40 | pass |
| derived_financial_asof | 44069 | 44069 | 27 | pass |
| derived_financial_quality | 44069 | 44069 | 114 | pass |
| derived_financial_growth | 44069 | 44069 | 252 | pass |
| derived_capital_flow | 44069 | 44069 | 61 | pass |
| derived_northbound_flow_cache | 44069 | 44069 | 38 | pass |
| derived_capital_flow_event_cache | 44069 | 44069 | 29 | pass |
| derived_sector_daily_cache | 1296 | 1296 | 93 | pass |
| derived_concept_daily_cache | 6984 | 6984 | 86 | pass |
| derived_sector_concept_context | 44069 | 44069 | 101 | pass |
| derived_concept_stock_context_cache | 44069 | 44069 | 221 | pass |
| derived_index_daily_cache | 112 | 112 | 26 | pass |
| derived_index_membership_cache | 44069 | 44069 | 16 | pass |
| derived_index_market_context | 44069 | 44069 | 102 | pass |
| derived_cross_sectional | 44069 | 44069 | 350 | pass |
| derived_corporate_action | 44069 | 44069 | 101 | pass |
| derived_composite_state | 44069 | 44069 | 89 | pass |

## 4. 本轮修复项

1. 新增并运行 `sync-financial-incremental-range`：按公告披露日期识别候选股票，再逐股补拉 `income`、`balancesheet`、`cashflow`、`fina_indicator`。本次 2026-05-27 至 2026-06-05 窗口候选为 0，详见 `reports/phase4_financial_incremental_run.json`。
2. 修复 `derived_daily_spine.limit_up_gap/limit_down_gap`：涨跌停价必须大于 0 才计算 gap，避免 0 跌停价产生 `inf`。
3. 修复 `derived_index_daily_cache.index_amount_chg_*`：指数成交额变化率在最终写窗口过滤前计算，保留 read-context 中的 lag 上下文。
4. 修复概念列表确定性：`derived_concept_stock_context_cache` 和 `derived_sector_concept_context` 的 top、lagging、active、best、worst 概念均增加稳定排序和空值过滤。
5. 修复 `top_list_reason` 聚合顺序：按 reason 字符串稳定排序。
6. 修复 `derived_corporate_action` 的股本变动 as-of：`financial_share_float` 读取完整历史事件，不再受 read_start 截断影响。
7. 修复横截面排名稳定性：rank/pct 排序前将输入 round 到 10 位小数，避免不同窗口下浮点尾差交换排名。
8. 修复综合状态边界：MA 比较和 MA alignment 使用 10 位小数量化，避免等值边界被浮点尾差扰动。
9. 调整 daily-core 缓存上下文：`sector_index_caches` 使用 260 个交易日上下文，满足指数成交额变化率的双窗口需求；`valuation_percentile_cache` 和 `capital_flow_caches` 保持扩展上下文策略。

## 5. 性能观察

本轮不含 `corporate_action` 的近期全量参照窗口耗时约 209 秒，目标增量窗口耗时约 142 秒。

上一轮包含 `corporate_action` 的目标增量窗口中，`corporate_action` 单模块耗时约 467 秒，是当前 Phase 4 最大性能瓶颈。它已通过一致性测试，但仍建议作为后续专项优化：将事件 ASOF 从全历史扫描进一步改为“受影响股票 + 受影响日期”的事件窗口更新。

## 6. 验证记录

1. `pytest -q`：27 项全部通过。
2. `build-features` 近期全量参照窗口：2026-05-01 至 2026-06-05，通过。
3. `build-features` 目标增量窗口：2026-05-27 至 2026-06-05，通过。
4. 增量与全量重叠窗口字段级比较：24 张表全部 pass。

## 7. 后续建议

1. 将本次对照脚本沉淀为正式命令，例如 `stock-maintain compare-incremental-window`。
2. 将 `corporate_action` 作为 Phase 4 后续性能专项，优先优化公司行动事件 ASOF 与 pandas 股本变动更新。
3. 将基础表补数、衍生构建、全量参照、增量对照、报告生成串成可复用 light/full 验收流程。
