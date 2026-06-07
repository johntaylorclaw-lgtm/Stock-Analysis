# 09 Phase 4 启动审计与实施计划

更新日期：2026-06-06

本文记录 Phase 4.0 启动审计结论，并据此调整 Phase 4 和 Phase 5 的实施边界。

详细审计报告见：

`reports/phase4_0_startup_audit.md`

## 1. 总体结论

用户提出的后续计划方向合适，但 Phase 4 建议从“增量性能优化”扩展为“工程化增量与统一出口”。

原因：

1. 当前 Phase 3 核心表已完成全量历史构建，下一步核心矛盾已经从“变量是否存在”转向“能否稳定、高效、可审计地日更”。
2. 项目已有 `stock-maintain plan-features` 和 `build-features` 的增量骨架，适合继续强化。
3. 当前已有 `stock_features_core/plus/full` 视图，但列数较轻且尚未进入 schema registry，需要在 Phase 4 正式定义为下游出口。
4. Phase 4.0 已修正 `docs-check` 和 `validate-config` 两个门禁项，后续可以把它们纳入常规验收。

## 2. Phase 4.0 审计发现

| 审计项 | 发现 | 影响 | Phase 4 建议 |
|---|---|---|---|
| Phase 3 核心表 | 19 个核心物理表均存在，行数均为 15,295,776，日期 2006-01-04 至 2026-05-26 | 主体底表可作为 Phase 4 增量基础 | 保持表结构，优先改刷新机制 |
| 统一出口视图 | `stock_features_core` 62 列、`plus` 65 列、`full` 90 列，已存在但偏轻 | 已有雏形，但不等同于最终下游宽出口 | Phase 4 正式设计列集和注册 |
| schema registry | 78 个注册表在数据库中均存在 | 表注册基础可靠 | 补充视图注册和出口说明 |
| 未注册视图 | 数据库中有 40 个视图未注册，包括财务标准化视图和 `stock_features_*` | docs/check/dictionary 漂移风险 | 增加 view registry 或扩展 schema registry |
| 变量注册 | `derived_variables.json` 2,214 个变量，base 543 个变量 | 变量覆盖丰富 | 解决重复变量名校验口径 |
| `validate-config` | 已修复，变量唯一性按 `table + name` 判断，允许跨表同名字段 | 可作为配置门禁 | 后续继续扩展 view registry 校验 |
| `docs-check` | 已修复，检查 00-09 主文档、归档目录和 Excel 主字典，不再要求旧 Markdown 字典位于 docs 根目录 | 可作为文档门禁 | 后续增加视图注册和字典漂移检查 |
| `build-features --dry-run` | 可输出增量计划；曾因并行只读连接导致写锁失败，重试后通过 | dry-run 仍使用写连接，不够轻 | dry-run/plan 使用只读连接或延迟连接 |
| 旧 Phase3 脚本 | 部分脚本支持日期窗口，部分 cache/reset 脚本仍全量删除或重建 | 日批性能风险 | 逐模块迁移到统一 builder |

## 3. 当前对象规模

| 对象 | 类型 | 列数 | 行数/说明 |
|---|---|---:|---:|
| `derived_daily_spine` | 物理表 | 49 | 15,295,776 |
| `derived_price_technical` | 物理表 | 16 | 15,295,776 |
| `derived_volume_liquidity` | 物理表 | 14 | 15,295,776 |
| `derived_return_momentum` | 物理表 | 16 | 15,295,776 |
| `derived_volatility_risk` | 物理表 | 13 | 15,295,776 |
| `derived_trading_constraint` | 物理表 | 14 | 15,295,776 |
| `derived_valuation_size` | 物理表 | 34 | 15,295,776 |
| `derived_financial_asof` | 物理表 | 30 | 15,295,776 |
| `derived_financial_quality` | 物理表 | 117 | 15,295,776 |
| `derived_financial_growth` | 物理表 | 255 | 15,295,776 |
| `derived_capital_flow` | 物理表 | 64 | 15,295,776 |
| `derived_sector_concept_context` | 物理表 | 104 | 15,295,776 |
| `derived_index_market_context` | 物理表 | 105 | 15,295,776 |
| `derived_cross_sectional` | 物理表 | 353 | 15,295,776 |
| `derived_corporate_action` | 物理表 | 104 | 15,295,776 |
| `derived_ownership_governance` | 物理表 | 63 | 15,295,776 |
| `derived_composite_state` | 物理表 | 92 | 15,295,776 |
| `stock_features_core` | 视图 | 62 | 已存在 |
| `stock_features_plus` | 视图 | 65 | 已存在 |
| `stock_features_full` | 视图 | 90 | 已存在 |

## 4. Phase 4 调整后计划

建议 Phase 4 命名为：

**Phase 4：工程化增量与统一出口**

| 顺序 | 任务 | 产出 | 优先级 |
|---:|---|---|---|
| 1 | 修正 `docs-check` 和 `validate-config` 规则 | 配置和文档检查可作为 Phase 4 门禁 | P0，已完成 |
| 2 | 注册并正式设计 `stock_features_core/plus/full` | 统一出口视图设计文档、schema/view registry、数据字典入口 | P0，已完成 |
| 3 | 建立 Phase 4 增量运行计划 | module dependency graph、read-context/write-window 表、确认机制 | P0，已完成初版窗口规格和脚本分类 |
| 4 | 将所有核心模块迁移到统一 builder | 日批通过 `stock-maintain build-features` 执行 | P0，待按脚本分类迁移 |
| 5 | 优化财务 ASOF 映射 | 按新增公告、修订报告和受影响交易日重算 | P0 |
| 6 | 优化长窗口和递归指标 | 估值、财务成长、行业指数、技术长周期的最小上下文策略 | P1 |
| 7 | 优化 Parquet 出口 | 按日期/模块分区，支持列裁剪和增量导出 | P1 |
| 8 | 建立性能基准 | 与原项目日批、Phase 3 全量和 Phase 4 日批对比 | P1 |

## 5. Phase 5 调整后计划

Phase 5 保持“验证、文档和交付闭环”，但应承接 Phase 4 的工程化产物。

| 任务 | 产出 |
|---|---|
| light/full 验证稳定 | 日批 light、周批 full、月度深度审计 |
| 文档自动生成和漂移检测 | `docs-check`、`validate-config`、Excel 字典检查通过 |
| 样本 Excel 和抽样复核 | 单股票、多股票、多模块抽样材料 |
| Agent Skill 薄封装 | 状态、计划、更新、修复、审计、字典刷新 |
| 迁移指南 | 如何从老项目切换到新项目 |
| 交付验收包 | 数据库、字典、主文档、审计报告、运行手册、迁移说明 |

## 6. Phase 4 启动前建议先做的 P0 修复

1. `stock-maintain docs-check` 已修正：当前主字典是 Excel，不再强制要求旧 Markdown 字典留在主 docs 目录。
2. `stock-maintain validate-config` 已修正：变量唯一性按 `table + name` 判断，允许不同表中存在同名字段。
3. `stock_features_core/plus/full` 已建立正式定义，已注册到 schema registry，并纳入 Excel 数据字典生成范围。
4. `build-features --dry-run` 已改为不打开 DuckDB 写连接，便于并行审计和计划查看。
5. Phase 3 独立脚本已完成初版分类，详见 `11_Phase4增量窗口与脚本分类.md`。

## 7. 结论

可以进入 Phase 4，但建议先完成上述 P0 修复，再开始大规模性能优化。

Phase 4 的第一步不应直接改所有模块，而应先把“检查门禁、统一出口、增量调度骨架”稳住。这样后续每个模块的优化都能被同一套计划、审计和数据字典机制吸收。
