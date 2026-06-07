# Phase 5 总验收报告

生成日期：2026-06-07

## 1. 阶段定位

Phase 5 目标是把 Phase 4 已验证的增量能力固化为日常运行、周度复核、文档同步、样本审查和统一出口交付闭环。

本阶段已完成首版闭环，重点包括：

1. daily-light 日批编排；
2. weekly-full 周度复核；
3. validate-daily 日批质量门禁；
4. compare-incremental-window 字段级一致性对照；
5. sample-stock 抽样 Excel；
6. refresh-dictionary 文档和 Excel 数据字典同步；
7. stock_features_core/plus/full 统一出口扩充。

## 2. 当前数据事实

| 指标 | 当前值 |
|---|---:|
| 证券主数据股票数 | 5,851 |
| 当前上市股票数 | 5,525 |
| 已退市股票数 | 326 |
| 日行情覆盖股票数 | 5,813 |
| 日频核心行数 | 15,339,845 |
| 覆盖交易日数 | 4,959 |
| 日期范围 | 2006-01-04 至 2026-06-05 |

## 3. 命令验收

| 命令 | 状态 | 关键报告 |
|---|---|---|
| `daily-light` | pass | `reports/phase5_daily_light_execute_20260607.md` |
| `weekly-full` | pass | `reports/phase5_weekly_full_compare_20260607.md` |
| `validate-daily` | pass | `reports/phase5_validate_daily_light_feature_views_20260607.md` |
| `compare-incremental-window` | pass | `reports/phase5_compare_incremental_20260607.md` |
| `sample-stock` | pass | `outputs/phase5/phase5_sample_stock_expanded_20260607_000001_SZ.xlsx` |
| `refresh-dictionary` | pass | `reports/phase5_refresh_dictionary_20260607.json` |

## 4. 统一出口视图

| 视图 | 列数 | 定位 |
|---|---:|---|
| `stock_features_core` | 318 | 日常高频稳定出口 |
| `stock_features_plus` | 1,198 | 研究增强事实出口 |
| `stock_features_full` | 1,602 | 审计和全量研究出口 |

三档视图均已同步至 `config/schema_registry.json` 和 `outputs/variable_dictionary/global_variable_dictionary.xlsx`。

## 5. 样本与字典

| 对象 | 路径 |
|---|---|
| 全局 Excel 数据字典 | `outputs/variable_dictionary/global_variable_dictionary.xlsx` |
| 扩充后单股样本 Excel | `outputs/phase5/phase5_sample_stock_expanded_20260607_000001_SZ.xlsx` |
| generated schema dictionary | `docs/generated/generated_schema_dictionary.md` |
| generated variable dictionary | `docs/generated/generated_variable_dictionary.md` |
| generated source dictionary | `docs/generated/generated_source_dictionary.md` |

## 6. 日批与新股机制

`daily-light` 已将 `sync-master` 作为正式补数前置步骤，用于刷新：

1. `stock_basic_info`
2. `stock_company_info`
3. `stock_status_history`
4. `trade_calendar`
5. `index_basic_info`

因此新股上市、退市状态变化和公司基础信息变化会在日批前先进入主库，再由基础日频补数和衍生构建自然补齐。

## 7. 周度复核机制

`weekly-full` 已完成首版：

1. 默认最近 40 个开放交易日作为参照窗口；
2. 默认最近 10 个开放交易日作为请求比较窗口；
3. 复用已有全量参照快照；
4. 自动将请求比较窗口与快照共同窗口取交集；
5. 字段级对照通过 `compare-incremental-window` 完成。

2026-06-07 实测：

| 项目 | 值 |
|---|---|
| 请求比较窗口 | 2026-05-25 至 2026-06-05 |
| 快照共同窗口 | 2026-05-27 至 2026-06-05 |
| 实际比较窗口 | 2026-05-27 至 2026-06-05 |
| 表数 | 24 |
| 通过表 | 24 |
| 键差异 | 0 |
| 字段差异 | 0 |

## 8. 门禁结果

| 门禁 | 结果 |
|---|---|
| `pytest -q` | 38 passed |
| `stock-maintain validate-config` | pass |
| `stock-maintain docs-check` | pass |

## 9. 遗留事项

1. weekly-full 当前复用已有快照；真正独立的影子全量重建参照尚未实现。
2. `stock_features_full` 为千列级视图，daily-light 已采用轻量键覆盖检查；如需更快，可继续优化 validate-daily 的视图检查策略。
3. `sample-module` 尚未单独封装；当前 `sample-stock` 已满足单股抽检需求。
4. 迁移指南和 Agent Skill 薄封装尚可作为下一阶段交付增强。

## 10. 下一阶段建议

建议进入 Phase 6：交付固化与迁移。

优先事项：

1. 建立影子全量重建参照，强化 weekly-full 独立性；
2. 编写从旧项目切换到新项目的迁移指南；
3. 封装 Agent Skill 或轻量运行手册，支持状态、计划、日批、周检、修复、抽样；
4. 增加自动化运行日志汇总，形成每日/每周固定报告。
