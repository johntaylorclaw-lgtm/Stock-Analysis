# 11 Phase 4 增量窗口与脚本分类

更新日期：2026-06-06

本文定义 Phase 4 的模块级 read-context/write-window 规格，并对 Phase 3 独立脚本进行迁移分类。

关联产物：

1. `reports/phase4_feature_plan_20260526.json`
2. `reports/phase4_module_window_spec.csv`
3. `reports/phase4_phase3_script_classification.csv`
4. `reports/phase4_audit_report.md`
5. `reports/phase4_audit_report.json`
6. `reports/phase4_acceptance_report.md`

## 1. 设计目标

Phase 4 的性能优化不能只靠局部 SQL 调整，需要先明确每个模块在日批中的读取上下文和写入窗口。

核心原则：

1. `write-window` 默认最近 10 个交易日。
2. `read-context` 只为滚动、as-of、历史分位和事件窗口提供必要上下文。
3. 超过 10 个交易日的远期历史修复仍需显式确认。
4. 独立 Phase 3 脚本需要迁移到统一 builder，或明确标记为 full-only、view-only、audit-only。

## 2. 模块窗口规格

以下规格由 `stock-maintain plan-features --end-date 2026-05-26 --format json` 生成。

| 模块 | 读取窗口 | 写入窗口 | 优先级 | 风险说明 |
|---|---:|---:|---|---|
| `daily_spine` | 20 | 10 | P2 | 正常近端窗口 |
| `price_technical` | 420 | 10 | P1 | 长均线、250 日技术指标；420 个日历日可覆盖 250 个交易日口径 |
| `volume_liquidity` | 180 | 10 | P2 | 成交量和流动性滚动窗口 |
| `return_momentum` | 420 | 10 | P1 | 250 日收益和动量；420 个日历日可覆盖 250 个交易日口径 |
| `volatility_risk` | 360 | 10 | P2 | 120 日波动和风险窗口 |
| `trading_constraint` | 60 | 10 | P2 | 连续涨跌停和交易约束 |
| `valuation_size` | 20 | 10 | P2 | 核心估值表近端窗口；历史分位由独立缓存窗口刷新 |
| `financial_asof` | 260 | 10 | P2 | 财务 as-of 基础窗口 |
| `financial_quality` | 260 | 10 | P2 | 依赖财务 as-of |
| `financial_growth` | 260 | 10 | P2 | 财务成长使用报告序列，不再依赖 1300 天日频上下文 |
| `capital_flow` | 250 | 10 | P2 | 资金流滚动窗口 |
| `sector_concept_context` | 520 | 10 | P1 | 行业概念多周期 |
| `index_market_context` | 520 | 10 | P1 | 指数市场多周期 |
| `cross_sectional` | 520 | 10 | P1 | 依赖上游多模块，按交易日截面计算 |
| `corporate_action` | 1260 | 10 | P0 | 公司行为 3 年/365 日事件窗口 |
| `ownership_governance` | 1260 | 10 | P0 | 股东、质押和治理低频事件窗口 |
| `composite_state` | 250 | 10 | P2 | 综合状态依赖上游模块 |

## 3. 优化优先级

P0 模块：

1. `valuation_size`
2. `financial_growth`
3. `corporate_action`
4. `ownership_governance`

原因：

1. `valuation_size` 与 `financial_growth` 已完成第一轮降窗优化，当前不再属于长日频上下文模块；保留在本节用于记录 Phase 4 优化来源。
2. `corporate_action`、`ownership_governance` 仍涉及低频事件窗口，但已接入统一 builder 后端。
3. 后续重点从“日频 read-window”转向受影响股票、受影响报告期和缓存脚本编排。

P1 模块：

1. `price_technical`
2. `return_momentum`
3. `sector_concept_context`
4. `index_market_context`
5. `cross_sectional`

原因：

1. 存在 520-750 天上下文。
2. 多为滚动窗口或跨模块截面计算。
3. 可通过最小上下文、交易日索引和按日期分区优化。

P2 模块：

1. `daily_spine`
2. `volume_liquidity`
3. `volatility_risk`
4. `trading_constraint`
5. `financial_asof`
6. `financial_quality`
7. `capital_flow`
8. `composite_state`

原因：窗口较短或已较适合日批窗口刷新。

## 4. Phase 3 独立脚本分类摘要

本次共分类 57 个 Phase 3/Phase 4 相关脚本。

| 分类 | 数量 | 处理策略 |
|---|---:|---|
| `unified_builder_backend` | 6 | 已接入统一 builder，脚本保留为完整 SQL 后端和全量重建参考 |
| `windowized_cache_script` | 5 | 已支持 `--start-date/--end-date` 窗口刷新，其中核心缓存已接入 `build-features` pre/post-step |
| `external_full_sync` | 1 | 外部数据源全量同步工具，必须显式确认，日批禁止调用 |
| `full_rebuild_only` | 6 | 仅结构变更或全量重建使用，日批禁止调用 |
| `view_rebuild_only` | 9 | 保留为视图刷新脚本，可由 `create-views` 或模块 post-step 调用 |
| `audit_report` | 13 | 保留为审计脚本，Phase 4 接入统一 audit 命令 |
| `registry_maintenance` | 10 | 保留为注册维护脚本，不进入日批 |
| `review_needed` | 7 | 人工复核用途和增量边界 |

## 5. 已迁移脚本

以下脚本已接入 `stock-maintain build-features` 统一 builder。

| 脚本 | 统一模块 | 当前状态 |
|---|---|---|
| `build_phase3_corporate_action_core.py` | `build_corporate_action` | 已迁移。统一 builder 负责 write-window 删除、完整 SQL 插入、流通股本后处理，并使用事务保护。 |
| `build_phase3_ownership_governance_core.py` | `build_ownership_governance` | 已迁移。统一 builder 负责 write-window 删除和完整 SQL 插入，并使用事务保护。 |
| `build_phase3_sector_concept_core.py` | `build_sector_concept_context` | 已迁移。统一 builder 负责 write-window 删除和完整 SQL 插入，并使用事务保护。 |
| `build_phase3_cross_sectional_core.py` | `build_cross_sectional` | 已迁移。统一 builder 负责 write-window 删除、元数据插入、变量截面更新、暴露更新和残差后处理，并使用事务保护。 |
| `build_phase3_composite_state_core.py` | `build_composite_state` | 已迁移。统一 builder 负责 write-window 删除和完整 SQL 插入，并使用事务保护；替代旧版评分字段逻辑。 |
| `build_phase3_index_market_core.py` | `build_index_market_context` | 已迁移。统一 builder 负责 write-window 删除和完整 SQL 插入，并使用事务保护；脚本本身也支持日期窗口。 |

以下缓存脚本已从全量删除重建改为支持窗口刷新，并开始接入 `stock-maintain build-features` 统一编排：

| 脚本 | 缓存对象 | 编排位置 | 当前状态 |
|---|---|---|---|
| `backfill_valuation_percentile_cache.py` | `derived_valuation_percentile_cache` | `valuation_size` post-step | `daily-core` 已用于日批回填 4 个 5 年兼容字段；`full` 保留为周批、月批或显式维护任务。 |
| `build_phase3_capital_flow_caches.py` | `derived_northbound_flow_cache`、`derived_capital_flow_event_cache` | `capital_flow` post-step | 窗口模式按写入窗口删除，读取窗口默认向前 260 个交易日。 |
| `build_phase3_sector_index_caches.py` | `derived_sector_daily_cache`、`derived_concept_daily_cache`、`derived_index_daily_cache`、`derived_index_membership_cache` | `sector_concept_context` / `index_market_context` pre-step | 日批使用 `daily-core`：行业和指数计算 5/20/60/120，概念计算 20，指数成分按写入窗口展开；`full` 保留完整多周期刷新。 |
| `build_phase3_concept_stock_context_cache.py` | `derived_concept_stock_context_cache` | `sector_concept_context` pre-step | 日批使用 `daily-core`，只更新静态概念字段和 20 日概念字段；`full` 保留完整多周期刷新。 |
| `build_phase3_index_membership_cache.py` | `derived_index_membership_cache` | 独立维护入口 | 作为指数成分缓存的单表快捷刷新入口；日批由 `build_phase3_sector_index_caches.py` 统一刷新，避免重复。 |

以下外部同步脚本不进入日批：

| 脚本 | 对象 | 当前状态 |
|---|---|---|
| `sync_phase3_sw_industry_enhanced.py` | `derived_sw_industry_member_enhanced` | 已加 `--confirm-full-refresh` 保护；不带确认参数会拒绝全量删除刷新，`--dry-run` 可检查 L2 行业数量。 |

验证记录：

1. `build-features --module corporate_action --module ownership_governance --dry-run` 可在不打开 DuckDB 的情况下生成计划。
2. 两个后端脚本的 `build_insert_sql('2026-05-26', '2026-05-26')` 已通过 DuckDB `EXPLAIN INSERT` 解析。
3. `build_phase3_capital_flow_caches.py --start-date 2026-05-26 --end-date 2026-05-26` 已完成单日真实窗口刷新。
4. `build_phase3_sector_index_caches.py --start-date 2026-05-26 --end-date 2026-05-26` 已完成单日真实窗口刷新。
5. `build_sector_concept_context` 已完成 `2026-05-26` 单日真实窗口刷新，写入 5504 行。
6. `build_cross_sectional` 已完成 `2026-05-26` 单日真实窗口刷新，写入 5504 行。
7. `build_composite_state` 已完成 `2026-05-26` 单日真实窗口刷新，写入 5504 行。
8. `build_phase3_concept_stock_context_cache.py --start-date 2026-05-26 --end-date 2026-05-26` 已完成单日真实窗口刷新，写入 5504 行。
9. `build_phase3_index_membership_cache.py --start-date 2026-05-26 --end-date 2026-05-26` 已完成单日真实窗口刷新，写入 5504 行，其中有指数权重 1806 行。
10. `build_index_market_context` 已完成 `2026-05-26` 单日真实窗口刷新，写入 5504 行。
11. `sync_phase3_sw_industry_enhanced.py --dry-run` 已完成范围检查，L2 行业数量 134。
12. `build-features --module valuation_size --start-date 2026-05-26 --end-date 2026-05-26` 已完成真实单日构建：`derived_daily_spine` 5504 行、`derived_valuation_size` 5504 行，post-step `valuation_percentile_cache` 更新 5504 行。
13. `build-features --module sector_concept_context --end-date 2026-05-26 --dry-run` 已确认会触发 `sector_index_caches` 和 `concept_stock_context_cache` 两个 pre-step，且 dry-run 不打开 DuckDB。
14. `build-features --module valuation_size --end-date 2026-05-26 --dry-run` 已确认会触发 `valuation_percentile_cache` post-step。
15. `build-features --module sector_concept_context --module index_market_context --start-date 2026-05-26 --end-date 2026-05-26` 已完成真实单日端到端验收：优化前总构建耗时 35.590 秒；`sector_index_caches` 7.414 秒写入 6553 行，`concept_stock_context_cache` 14.542 秒写入 5504 行；`derived_sector_concept_context` 和 `derived_index_market_context` 各写入 5504 行。
16. `concept_stock_context_cache` 已拆分为 `daily-core/full`：日批只列级更新静态概念字段和 20 日概念字段，完整多周期字段由 `full` 维护。`2026-05-26` 单日端到端复验总构建耗时 28.340 秒，`concept_stock_context_cache` 降至 0.587 秒；非核心周期字段 `concept_ids_top_60`、`concept_best_ret_120`、`concept_best_ret_250` 核对后仍保留非空值。
17. `sector_index_caches` 已补充分表耗时审计。`2026-05-26` 单日复验中该步骤总耗时 7.289 秒，主要耗时为 `derived_sector_daily_cache.insert=3.723` 秒、`derived_concept_daily_cache.insert=1.976` 秒、`derived_index_membership_cache.insert=0.603` 秒、`derived_index_daily_cache.insert=0.078` 秒。
18. `sector_index_caches` 已拆分为 `daily-core/full`：日批列级更新核心周期，完整周期字段由 `full` 维护。`2026-05-26` 单日端到端复验总构建耗时 23.663 秒，`sector_index_caches` 降至 3.852 秒；`industry_ret_250`、`concept_ret_250`、`index_ret_250` 等 full 字段核对后仍保留非空值。
19. `sector_index_caches daily-core` 已完成 10 日默认窗口复验：`build-features --module sector_concept_context --module index_market_context --end-date 2026-05-26` 总耗时 46.661 秒；`sector_index_caches` 14.271 秒写入/更新 45847 行，`concept_stock_context_cache` 6.491 秒写入/更新 38504 行；新主要耗时集中在多日列级 upsert 的 commit 阶段，尤其 `derived_index_membership_cache.commit=5.667` 秒。
20. 列级 upsert 已加入“仅变化行更新”条件，避免重复日批对未变化行执行 UPDATE。10 日默认窗口复验总耗时降至 34.301 秒；`sector_index_caches` 降至 5.073 秒，`concept_stock_context_cache` 降至 1.781 秒；`derived_index_membership_cache.commit` 从 5.667 秒降至 0.181 秒。
21. `price_technical` 和 `return_momentum` 读取窗口已从 750 个日历日降至 420 个日历日，以覆盖 250 个交易日最长口径并减少过度读取。技术组 10 日窗口复验总耗时 21.299 秒；`price_technical` 从约 9.269 秒降至 7.538 秒，`return_momentum` 为 2.034 秒。最长周期字段核对正常：`ma_250_hfq` 非空 37499/38504，`ret_250_hfq` 非空 37495/38504。
22. Parquet 出口已新增 `stock-maintain export-parquet`：支持按 `trade_date=YYYY-MM-DD/part.parquet` 分区导出，支持 `--column` 列裁剪和 `--dry-run`。已完成 `stock_features_core` 单日列裁剪实测，`2026-05-26` 分区写出 5504 行。

## 6. 可窗口化脚本

可窗口化脚本已全部完成迁移或窗口化。当前没有剩余 `window_capable_script`。

## 7. 需要重构的全量删除脚本

需要重构的全量删除脚本已清零。当前不存在剩余 `full_delete_needs_refactor`。

## 8. Full-only 脚本

以下脚本仅用于结构重置或全量重建：

1. `reset_phase3_composite_state_table.py`
2. `reset_phase3_corporate_action_table.py`
3. `reset_phase3_cross_sectional_table.py`
4. `reset_phase3_financial_growth_core_table.py`
5. `reset_phase3_ownership_governance_table.py`
6. `reset_phase3_trading_technical_tables.py`

规则：

1. 日批禁止调用。
2. 只能在结构变更、全量重建或显式确认的历史修复中调用。
3. 调用前必须备份或确认 DuckDB 快照策略。

## 9. View-only、Audit-only、Registry-only

View-only 脚本：

1. `create_phase3_*_full_view.py`
2. `create_phase3_*_views.py`

建议保留，但 Phase 4 应逐步统一到 `stock-maintain create-views` 或模块 post-step。

Audit-only 脚本：

1. `generate_phase3_*_audit.py`
2. `generate_phase3_full_audit_report.py`

建议保留，并在 Phase 4 接入统一 audit 命令。

Registry-only 脚本：

1. `register_phase3_*`

建议保留为 schema/variable registry 维护工具，不进入日批。

## 10. 下一步执行建议

建议 Phase 4 下一步按以下顺序做：

1. 对完整日批组合做一次 dry-run/分组验收，确认 Phase 4 剩余瓶颈和是否达到当前阶段可验收标准。
2. 如需继续压缩技术模块耗时，下一步应从状态缓存或按股票批处理入手，而不是继续缩短 420 日历日读取窗口。
3. 将 `phase4_last_build_features_run.json` 纳入固定验收材料，用于比较后续优化前后的耗时变化。

统一审计命令：

```bash
stock-maintain phase4-audit --end-date 2026-05-26
```

该命令当前会生成 `reports/phase4_audit_report.md` 和 `reports/phase4_audit_report.json`，并刷新 `reports/phase4_module_window_spec.csv`。审计内容包括模块窗口计划、配置注册表校验、文档同步状态和 Phase 3 脚本分类摘要；当前版本不连接 DuckDB 主库，适合日批前后快速运行。

从本轮开始，非 dry-run 的 `build-features` 会额外生成 `reports/phase4_last_build_features_run.json`，记录模块核心构建和缓存 pre/post-step 的行数与耗时。`phase4-audit` 会读取该文件并在报告中展示最近一次构建耗时。

统一编排缓存策略：

1. `valuation_size`：核心表写入后执行 `valuation_percentile_cache` post-step，日批默认 `daily-core`，只刷新核心兼容字段并回填 `derived_valuation_size`。
2. `capital_flow`：核心表写入后执行 `capital_flow_caches` post-step，刷新北向资金和龙虎榜/机构席位事件缓存。
3. `sector_concept_context`：核心表写入前执行 `sector_index_caches` 和 `concept_stock_context_cache` pre-step；其中 `concept_stock_context_cache` 日批默认 `daily-core`。
4. `index_market_context`：核心表写入前执行 `sector_index_caches` pre-step；若同一轮构建中已由 `sector_concept_context` 触发，则不会重复执行。日批默认 `daily-core`。
5. `--skip-cache-steps` 可显式跳过缓存编排，用于调试核心 SQL 或排查缓存问题。

Parquet 出口命令：

```bash
stock-maintain export-parquet \
  --source stock_features_core \
  --start-date 2026-05-26 \
  --end-date 2026-05-26 \
  --column close_hfq \
  --column ret_1_hfq
```

导出路径采用 `data/parquet/{dataset}/trade_date=YYYY-MM-DD/part.parquet`，默认 `dataset` 等于 `source`。如不传 `--column`，导出源对象全部字段；如传 `--column`，系统会自动补充 `ts_code` 和 `trade_date` 作为稳定键。

## 11. 长窗口降窗记录

本轮已完成两个 P0 长窗口模块的降窗：

| 模块 | 原读取窗口 | 新读取窗口 | 处理方式 | 验证 |
|---|---:|---:|---|---|
| `valuation_size` | 2510 | 20 | 核心估值表只维护近端字段；5 年历史分位兼容字段由 `derived_valuation_percentile_cache` 窗口刷新后回填。 | `2026-05-26` 核心表 5504 行，分位缓存 5504 行。 |
| `financial_growth` | 1300 | 260 | 日频计划窗口降至财务 as-of 同级；SQL 内部按写入窗口涉及股票构造报告序列。 | `2026-05-26` 写入 5504 行。 |

估值分位缓存说明：

1. `backfill_valuation_percentile_cache.py` 已支持 `--start-date/--end-date`。
2. `--profile daily-core` 用于日批，只计算 `pe_ttm_pct_5y`、`pb_pct_5y`、`ps_ttm_pct_5y`、`total_mv_pct_5y` 四个核心兼容字段，默认读取 1250 个交易日上下文。
3. `--profile full` 用于周批、月批或显式维护任务，计算全部 40 个估值/规模历史分位字段，默认读取 2500 个交易日上下文，以保持 10 年历史分位字段口径。
4. `daily-core` 模式对已有缓存行执行列级更新，不删除完整缓存行，因此不会清空 `full` 模式生成的长周期字段；若写入窗口缺失缓存行，则插入该日期股票的核心字段，其他完整字段保持为空等待完整刷新。
5. 本轮 `full` 单日窗口 `2026-05-26` 读取起点为 `2016-02-02`，写入缓存 5504 行，并回填核心表兼容字段。
6. 本轮 `daily-core` 单日窗口 `2026-05-26` 读取起点为 `2021-03-25`，写入/更新缓存 5504 行；核心字段非空计数分别为 `pe_ttm_pct_5y=3962`、`pb_pct_5y=5463`、`ps_ttm_pct_5y=5497`、`total_mv_pct_5y=5504`，运行耗时约 33 秒。

## 12. 验收标准

1. `stock-maintain plan-features` 能输出所有模块窗口规格。
2. `reports/phase4_module_window_spec.csv` 已生成。
3. `reports/phase4_phase3_script_classification.csv` 已生成。
4. 日批禁止脚本清单明确。
5. 可迁移脚本清单明确。
6. 后续每完成一个脚本迁移，需更新本文和相关报告。
