# Phase 4 增量性能优化验收报告

生成日期：2026-06-06

## 1. 验收结论

Phase 4 已达到当前阶段可验收状态。

本阶段完成了日批 read-context/write-window 机制、核心缓存脚本编排、daily-core/full 分层、耗时审计、Parquet 分区出口和文档同步机制。当前日批默认窗口为最近 10 个日历日；超过默认窗口的历史修复仍需显式确认。

## 2. 主要完成项

1. `build-features` 已统一输出 `plan`、`results`、`cache_results` 和耗时字段。
2. 核心缓存脚本已接入 pre/post-step，并支持 `--skip-cache-steps`。
3. `valuation_percentile_cache` 已拆分为 `daily-core/full`，日批只刷新 4 个 5 年兼容字段。
4. `concept_stock_context_cache` 已拆分为 `daily-core/full`，日批只刷新静态概念字段和 20 日字段。
5. `sector_index_caches` 已拆分为 `daily-core/full`，日批只刷新上下文核心依赖周期。
6. 列级 upsert 已加入“仅变化行更新”，显著降低重复日批 commit 成本。
7. `price_technical` 和 `return_momentum` 读取窗口从 750 日历日降至 420 日历日。
8. 新增 `stock-maintain phase4-audit`，统一生成窗口计划、脚本分类和最近构建耗时审计。
9. 新增 `stock-maintain export-parquet`，支持按日期分区和列裁剪导出。
10. 全局 Excel 数据字典已重建：`outputs/variable_dictionary/global_variable_dictionary.xlsx`。

## 3. 关键性能记录

| 分组 | 默认窗口 | 结果 | 主要耗时 |
|---|---:|---|---|
| 技术核心组：`price_technical`、`return_momentum`、`volatility_risk` | 10 日 | 21.299 秒 | `price_technical` 7.538 秒 |
| 交易补充组：`volume_liquidity`、`trading_constraint` | 10 日 | 12.051 秒 | `volume_liquidity` 5.948 秒 |
| 财务组：`financial_asof`、`financial_quality`、`financial_growth` | 10 日 | 48.549 秒 | `financial_quality` 28.010 秒 |
| 估值资金组：`valuation_size`、`capital_flow` | 10 日 | 55.034 秒 | `capital_flow_caches` 21.876 秒 |
| 板块指数组：`sector_concept_context`、`index_market_context` | 10 日 | 34.301 秒 | `sector_index_caches` 5.073 秒 |
| 全核心依赖组：`composite_state` 及全部依赖，不含缓存 | 10 日 | 174.748 秒 | `corporate_action` 54.534 秒 |

## 4. 优化前后摘要

| 对象 | 优化前 | 优化后 | 说明 |
|---|---:|---:|---|
| `valuation_percentile_cache` 10 日 | 约 57 秒 | 约 10 秒 | pandas 全上下文 rolling 改为 DuckDB 目标窗口精算 |
| `concept_stock_context_cache` 单日 | 约 14.5 秒 | 约 0.6 秒 | daily-core 列级更新，full 字段保留 |
| `sector_index_caches` 单日 | 约 7.3 秒 | 约 3.9 秒 | daily-core 核心周期列级更新 |
| `sector_index_caches` 10 日 | 约 14.3 秒 | 约 5.1 秒 | 仅变化行更新，降低 commit 成本 |
| `price_technical` 10 日 | 约 9.3 秒 | 约 7.5 秒 | 读取窗口 750 日历日降至 420 日历日 |

## 5. 数据质量与口径核对

1. `valuation_percentile_cache daily-core` 更新后，5 年核心字段非空正常，full 字段不被清空。
2. `concept_stock_context_cache daily-core` 更新后，`concept_ids_top_60`、`concept_best_ret_120`、`concept_best_ret_250` 仍保留非空值。
3. `sector_index_caches daily-core` 更新后，`industry_ret_250`、`concept_ret_250`、`index_ret_250` 等 full 字段仍保留非空值。
4. 技术模块降窗后，`ma_250_hfq`、`ret_250_hfq`、`hv_120` 等最长周期字段非空正常。
5. `docs-check` 通过，说明注册表、主文档和字典生成机制保持同步。

## 6. Parquet 出口

新增命令：

```bash
stock-maintain export-parquet \
  --source stock_features_core \
  --start-date 2026-05-26 \
  --end-date 2026-05-26 \
  --column close_hfq \
  --column ret_1_hfq
```

出口路径：`data/parquet/{dataset}/trade_date=YYYY-MM-DD/part.parquet`。

已完成实测：`stock_features_core` 在 `2026-05-26` 分区写出 5504 行，支持列裁剪并自动补充 `ts_code`、`trade_date`。

## 7. 遗留事项

1. `corporate_action` 已在 Phase 4.x 专项中优化，目标窗口单模块耗时由约 467 秒下降至约 53 秒，并通过字段级一致性验证。详见 `reports/phase4x_corporate_action_performance.md`。
2. `capital_flow_caches` 10 日仍约 21.9 秒，其中 `derived_capital_flow_event_cache` commit 成本较高；建议后续拆分 daily-core/full 或降低日批刷新频率。
3. `financial_quality` 10 日约 28.0 秒，属于财务宽表计算成本；当前可接受，但可在 Phase 5 增加抽样质量审计。
4. 完整全模块带缓存日批尚未一次性串行跑完；已通过分组验收覆盖所有模块和缓存路径。

## 8. 验证记录

1. `stock-maintain validate-config`：通过。
2. `stock-maintain docs-check`：通过。
3. `pytest`：27 项全部通过。
4. `stock-maintain phase4-audit --end-date 2026-05-26`：已生成最新审计报告。
5. 2026-05-27 至 2026-06-05 真实增量窗口对照：24 张衍生表与近期全量参照全部一致，详见 `reports/phase4_incremental_case_20260606.md`。
6. Phase 4.x `corporate_action` 性能专项：一致性通过，性能优化通过。
7. Phase 5 首个验收命令 `compare-incremental-window` 已完成，并复验 2026-05-27 至 2026-06-05 窗口 24 张表全部通过。

## 9. 下一阶段建议

Phase 5 建议聚焦验证、文档和交付闭环：

1. 建立 light/full 验证任务，区分日批轻验收和周批完整验收。
2. 增加样本 Excel 和抽样复核材料。
3. 将 `phase4-audit`、`docs-check`、`validate-config`、Parquet 出口纳入交付清单。
4. 编写迁移指南，说明从旧工程切换到本工程的运行步骤和验收口径。
