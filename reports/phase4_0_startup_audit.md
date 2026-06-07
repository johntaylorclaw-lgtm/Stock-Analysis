# Phase 4.0 启动审计报告

生成日期：2026-06-06  
工程路径：`D:\Opencode Workspace\Stock_Maintainance`  
数据库：`data/duckdb/stock_data.duckdb`

## 1. 审计目的

本次审计用于判断 Phase 4/5 计划是否适合当前项目状态，并识别 Phase 4 开工前必须处理的工程化问题。

审计范围：

1. Phase 3 核心对象是否完整。
2. schema registry、数据库对象、数据字典和文档检查是否一致。
3. 当前增量调度骨架是否可复用。
4. 哪些脚本仍偏全量构建，需要迁移到 read-context/write-window。
5. Phase 4/5 计划是否需要调整。

## 2. 结论

用户提出的 Phase 4/5 方向总体合适，但建议调整为：

1. Phase 4：工程化增量与统一出口。
2. Phase 5：验证、文档和交付闭环。

Phase 4.0 已完成前两项 P0 门禁修复；后续 Phase 4 继续处理统一出口、dry-run 写锁和模块增量化：

1. `docs-check` 已适配当前主文档和 Excel 字典体系。
2. `validate-config` 已按 `table + name` 判断变量唯一性。
3. `stock_features_core/plus/full` 已正式注册和设计。
4. `build-features --dry-run` 已改为不打开 DuckDB 写连接，避免 DuckDB 写锁冲突。

## 3. 数据库对象审计

核心日频覆盖：

| 项目 | 结果 |
|---|---:|
| 核心日频行数 | 15,295,776 |
| 覆盖日期 | 2006-01-04 至 2026-05-26 |
| DuckDB 文件大小 | 约 118GB |
| Excel 数据字典 | `outputs/variable_dictionary/global_variable_dictionary.xlsx`，约 1.2MB |

Phase 3 核心表：

| 对象 | 类型 | 列数 | 行数 | 日期范围 |
|---|---|---:|---:|---|
| `derived_daily_spine` | 物理表 | 49 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_price_technical` | 物理表 | 16 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_volume_liquidity` | 物理表 | 14 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_return_momentum` | 物理表 | 16 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_volatility_risk` | 物理表 | 13 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_trading_constraint` | 物理表 | 14 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_valuation_size` | 物理表 | 34 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_financial_asof` | 物理表 | 30 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_financial_quality` | 物理表 | 117 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_financial_growth` | 物理表 | 255 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_capital_flow` | 物理表 | 64 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_northbound_flow_cache` | 物理表 | 41 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_capital_flow_event_cache` | 物理表 | 32 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_sector_concept_context` | 物理表 | 104 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_index_market_context` | 物理表 | 105 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_cross_sectional` | 物理表 | 353 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_corporate_action` | 物理表 | 104 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_ownership_governance` | 物理表 | 63 | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `derived_composite_state` | 物理表 | 92 | 15,295,776 | 2006-01-04 至 2026-05-26 |

统一出口视图：

| 对象 | 类型 | 列数 | 结论 |
|---|---|---:|---|
| `stock_features_core` | 视图 | 62 | 已存在，但列数偏轻 |
| `stock_features_plus` | 视图 | 65 | 已存在，但列数偏轻 |
| `stock_features_full` | 视图 | 90 | 已存在，但不等同于 Phase 3 全量宽变量出口 |

## 4. 基础表最新范围

| 表 | 行数 | 日期范围 |
|---|---:|---|
| `stock_daily` | 15,295,776 | 2006-01-04 至 2026-05-26 |
| `stock_daily_basic` | 15,204,489 | 2006-01-04 至 2026-05-26 |
| `stock_adj_factor` | 15,653,891 | 2006-01-04 至 2026-05-26 |
| `stock_limit_price` | 17,533,118 | 2007-01-04 至 2026-05-26 |
| `stock_moneyflow_daily` | 14,186,050 | 2007-01-04 至 2026-05-26 |
| `margin_detail` | 6,486,792 | 2010-03-31 至 2026-05-26 |
| `northbound_holding` | 5,669,689 | 2016-06-29 至 2026-05-26 |
| `index_daily` | 63,767 | 2006-01-04 至 2026-05-26 |

结论：主要基础表最新日期均到 2026-05-26，但不同数据域历史起点天然不同，质量报告需按数据域解释缺失。

## 5. Registry 与文档检查

| 检查 | 结果 | 说明 |
|---|---|---|
| schema registry 表数 | 78 | 注册表对象在数据库中均存在 |
| 数据库对象数 | 118 | 含未注册视图 |
| 未注册数据库对象 | 40 | 主要是财务标准化视图、市场视图和 `stock_features_*` |
| base variables | 543 | 覆盖基础变量域 |
| derived variables | 2,214 | 覆盖 Phase 3 变量 |
| `stock-maintain docs-check` | 通过 | 检查 00-09 主文档、归档目录和 Excel 主字典；生成型 Markdown 如存在则检查 `docs/generated/` |
| `stock-maintain validate-config` | 通过 | 变量唯一性按 `table + name` 判断，允许跨表同名字段 |
| `python -m pytest` | 通过 | 15 passed |

Phase 4.0 修复前，`validate-config` 重复字段示例：

```text
event_date
latest_report_end_date
is_listed_asof
close_hfq
ma_20_hfq
sw_l1_code
event_type
effective_date
end_date
source_table
ownership_available_flag
```

判断：这些重复多数是跨表同名事实字段，并不一定是数据设计错误。校验规则已改为 `table + name` 唯一。

## 6. 增量骨架审计

当前已有：

1. `stock-maintain plan-features`
2. `stock-maintain build-features`
3. `src/stock_maintainance/features/planner.py`
4. `src/stock_maintainance/features/modules.py`
5. `delete_write_window`
6. 模块依赖图 `MODULE_DEPENDENCIES`

`plan-features --end-date 2026-05-26` 可输出 10 日写入窗口：

| 模块 | 读取窗口 | 写入窗口 | 说明 |
|---|---:|---:|---|
| `daily_spine` | 20 | 10 | 近端价格和状态 |
| `price_technical` | 750 | 10 | 长均线和 250 日类指标 |
| `volume_liquidity` | 180 | 10 | 成交和流动性滚动窗口 |
| `return_momentum` | 750 | 10 | 250 日收益和动量 |
| `volatility_risk` | 360 | 10 | 120 日波动和风险 |
| `trading_constraint` | 60 | 10 | 连续涨跌停和近端约束 |
| `valuation_size` | 2510 | 10 | 历史估值分位，读取窗口最长 |
| `financial_asof` | 260 | 10 | 财务 as-of |
| `financial_quality` | 260 | 10 | 财务质量 |
| `financial_growth` | 1300 | 10 | 多周期财务成长 |
| `capital_flow` | 250 | 10 | 资金流滚动窗口 |
| `sector_concept_context` | 520 | 10 | 行业概念多周期 |
| `index_market_context` | 520 | 10 | 指数市场多周期 |

结论：

1. 增量骨架已经具备。
2. 估值、财务成长、行业/指数上下文读取窗口较长，是性能优化重点。
3. Phase 3 的部分独立脚本仍存在全量删除/重建逻辑，需要迁移到统一 builder 或明确为 full rebuild 专用。

## 7. Phase 4 风险清单

| 风险 | 严重性 | 建议 |
|---|---|---|
| docs-check 与当前文档归档策略冲突 | 已解除 | 已修正 |
| validate-config 对跨表同名变量过严 | 已解除 | 已修正 |
| `stock_features_*` 未正式注册 | 已解除 | 已注册为 P4 统一出口视图 |
| dry-run 仍可能触发写连接锁 | 已解除 | `build-features --dry-run` 不再打开 DuckDB 写连接 |
| 估值历史分位读取窗口过长 | 中 | 考虑缓存/分位状态表/受影响窗口 |
| 财务 ASOF 按日期窗口重算仍可能过宽 | 中 | 改按公告变更范围映射受影响交易日 |
| 部分 cache 脚本全量删除 | 中 | 标记 full-only 或改窗口刷新 |

## 8. 建议的 Phase 4 P0 顺序

1. 修 `validate-config`：变量唯一性改为 `table + name`。已完成。
2. 修 `docs-check`：适配当前主文档 + Excel 数据字典体系。已完成。
3. 注册 `stock_features_core/plus/full`，并设计列集。已完成。
4. 改 `build-features --dry-run` 连接策略。已完成。
5. 输出模块级 read-context/write-window 规格表。
6. 逐模块把独立 Phase 3 脚本迁移或归类为 full-only。

## 9. 最终判断

可以进入 Phase 4。

但 Phase 4 的第一步应是“门禁修复 + 统一出口正式化”，然后再做各模块性能优化。这样后续优化结果可以被 `docs-check`、`validate-config`、审计报告和 Excel 数据字典统一验收。
