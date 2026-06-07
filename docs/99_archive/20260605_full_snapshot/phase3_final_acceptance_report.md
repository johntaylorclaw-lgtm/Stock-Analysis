# Phase 3 总验收报告

生成日期：2026-06-05  
工程定位：A 股股票数据维护工程  
数据库：`data/duckdb/stock_data.duckdb`  
全局 Excel 数据字典：`outputs/variable_dictionary/global_variable_dictionary.xlsx`

## 1. 验收结论

Phase 3 主体衍生变量层已完成。

本阶段完成了日频主干、交易技术、估值规模、财务 as-of/质量/成长、资金流、行业概念与指数市场上下文、截面转换、公司行为、持有人治理、综合事实状态等模块的历史全量构建。

验收结论：

| 项目 | 结论 |
|---|---|
| 核心物理表 | 已完成 |
| 完整视图 | 已完成 |
| 审计报告 | 已生成 |
| Excel 数据字典 | 已刷新并更名为主文件 |
| 自动测试 | 11 项通过 |
| 旧评分字段 | 已从 `composite_state` 移除 |
| 统一出口视图 | 后置，不计入 Phase 3 主体完成条件 |

测试结果：

```text
python -m pytest
11 passed
```

## 2. 核心覆盖范围

Phase 3 全部日频核心物理表覆盖：

| 项目 | 结果 |
|---|---:|
| 核心日频行数 | 15,295,776 |
| 覆盖股票数 | 5,809 |
| 覆盖交易日数 | 4,951 |
| 日期范围 | 2006-01-04 至 2026-05-26 |

## 3. 模块验收清单

| 模块 | 核心对象 | 核心行数 | 核心列数 | 完整/辅助对象 | 审计报告 | 状态 |
|---|---|---:|---:|---|---|---|
| 日频主干 | `derived_daily_spine` | 15,295,776 | 49 | - | `reports/phase3_daily_spine_rebuild_report.md` | 完成 |
| 价格技术分析 | `derived_price_technical` | 15,295,776 | 16 | `derived_price_technical_full_v` 74列 | `reports/phase3_trading_technical_audit.md` | 完成 |
| 成交流动性 | `derived_volume_liquidity` | 15,295,776 | 14 | `derived_volume_liquidity_full_v` 69列 | `reports/phase3_trading_technical_audit.md` | 完成 |
| 收益动量 | `derived_return_momentum` | 15,295,776 | 16 | `derived_return_momentum_full_v` 77列 | `reports/phase3_trading_technical_audit.md` | 完成 |
| 波动风险 | `derived_volatility_risk` | 15,295,776 | 13 | `derived_volatility_risk_full_v` 50列 | `reports/phase3_trading_technical_audit.md` | 完成 |
| 交易约束 | `derived_trading_constraint` | 15,295,776 | 14 | `derived_trading_constraint_full_v` 69列 | `reports/phase3_trading_technical_audit.md` | 完成 |
| 估值规模 | `derived_valuation_size` | 15,295,776 | 34 | `derived_valuation_size_full_v` 165列 | `reports/phase3_valuation_size_audit.md` | 完成 |
| 财务 as-of | `derived_financial_asof` | 15,295,776 | 30 | - | `reports/phase3_financial_stage1_quality_audit.md` | 完成 |
| 财务质量 | `derived_financial_quality` | 15,295,776 | 117 | - | `reports/phase3_financial_stage1_quality_audit.md` | 完成 |
| 财务成长 | `derived_financial_growth` | 15,295,776 | 255 | `derived_financial_growth_full_v` 1196列 | `reports/phase3_financial_growth_hybrid_audit.md` | 完成 |
| 资金流 | `derived_capital_flow` | 15,295,776 | 64 | `derived_capital_flow_full_v` 246列 | `reports/phase3_capital_flow_audit.md` | 完成 |
| 北向资金缓存 | `derived_northbound_flow_cache` | 15,295,776 | 41 | - | `reports/phase3_capital_flow_audit.md` | 完成 |
| 资金事件缓存 | `derived_capital_flow_event_cache` | 15,295,776 | 32 | - | `reports/phase3_capital_flow_audit.md` | 完成 |
| 行业概念上下文 | `derived_sector_concept_context` | 15,295,776 | 104 | `derived_sector_concept_context_full_v` 356列 | `reports/phase3_sector_index_context_audit.md` | 完成 |
| 指数市场上下文 | `derived_index_market_context` | 15,295,776 | 105 | `derived_index_market_context_full_v` 260列 | `reports/phase3_sector_index_context_audit.md` | 完成 |
| 截面转换 | `derived_cross_sectional` | 15,295,776 | 353 | `derived_cross_sectional_full_v` 1063列 | `reports/phase3_cross_sectional_audit.md` | 完成 |
| 公司行为 | `derived_corporate_action` | 15,295,776 | 104 | `derived_corporate_action_full_v` 144列；`corporate_action_event_timeline_v` 10列 | `reports/phase3_corporate_action_audit.md` | 完成 |
| 持有人治理 | `derived_ownership_governance` | 15,295,776 | 63 | `derived_ownership_governance_full_v` 98列；`ownership_holder_concentration_v` 10列；`ownership_governance_event_timeline_v` 12列 | `reports/phase3_ownership_governance_audit.md` | 完成 |
| 综合事实状态 | `derived_composite_state` | 15,295,776 | 92 | `derived_composite_state_full_v` 115列；`composite_state_condition_detail_v` 10列；`composite_state_module_coverage_v` 8列 | `reports/phase3_composite_state_audit.md` | 完成 |

## 4. 审计结果摘要

| 审计项 | 结果 |
|---|---|
| 交易技术模块 | 已生成审计报告，核心表/视图存在 |
| 估值规模模块 | 已生成审计报告，核心表/视图存在 |
| 财务模块 | stage1、growth batch/full/hybrid 审计报告均已生成 |
| 资金流模块 | 核心表、北向缓存、事件缓存、完整视图均完成 |
| 行业概念与指数模块 | 核心对象、缓存和完整视图均完成 |
| 截面转换模块 | 核心表 353 列，完整视图 1063 列 |
| 公司行为模块 | PIT 检查通过，未来解禁窗口只使用已公告事件 |
| 持有人治理模块 | 主键重复 0；PIT 违规 0；质押阈值三档检查通过 |
| 综合事实状态模块 | 主键重复 0；`score` 字段数量 0；枚举非法值 0；条件明细一致 |

## 5. 文档整理结果

主文档区保留当前真实状态的设计和执行文档：

| 文档 | 用途 |
|---|---|
| `docs/phase3_daily_spine_design.md` | 日频主干设计 |
| `docs/phase3_trading_technical_core_design.md` | 交易技术模块设计 |
| `docs/phase3_valuation_size_design.md` | 估值规模模块设计 |
| `docs/phase3_financial_derived_variable_design.md` | 财务衍生变量主设计 |
| `docs/phase3_financial_growth_hybrid_design.md` | 财务成长混合存储方案 |
| `docs/phase3_financial_stage1_execution_log.md` | 财务一阶段执行记录 |
| `docs/phase3_financial_growth_stage2_execution_log.md` | 财务成长执行记录 |
| `docs/phase3_capital_flow_design.md` | 资金流模块设计 |
| `docs/phase3_sector_index_context_design.md` | 行业概念与指数市场上下文设计 |
| `docs/phase3_cross_sectional_design.md` | 截面转换模块设计与实施记录 |
| `docs/phase3_corporate_action_design.md` | 公司行为模块设计 |
| `docs/phase3_ownership_governance_design.md` | 持有人治理模块设计 |
| `docs/phase3_ownership_governance_execution_log.md` | 持有人治理执行记录 |
| `docs/phase3_composite_state_design.md` | 综合事实状态模块设计 |
| `docs/phase3_composite_state_execution_log.md` | 综合事实状态执行记录 |
| `docs/phase3_final_acceptance_report.md` | 本总验收报告 |

以下早期草案、过时计划或不再作为主入口的 Markdown 字典快照已归档：

| 归档目录 | 内容 |
|---|---|
| `docs/archive/phase3_legacy_20260605/` | 早期 Phase 3 计划、旧草案、旧 Markdown 字典快照 |
| `reports/archive/phase3_legacy_20260605/` | 早期计划报告和阶段性质量报告 |

说明：

1. Markdown 版 `generated_*dictionary.md` 是旧快照，已不再作为主字典入口。
2. 当前全局变量查看入口统一为 Excel：`outputs/variable_dictionary/global_variable_dictionary.xlsx`。
3. 归档采用移动而非删除，保留历史追溯能力。

## 6. 数据字典状态

当前主数据字典：

`outputs/variable_dictionary/global_variable_dictionary.xlsx`

该文件由用户从 `global_variable_dictionary_20260605144818.xlsx` 更名而来，已作为当前主字典入口。

数据字典原则：

1. 每个基础变量表、衍生变量表各有 sheet。
2. `Table_Index` 提供全局索引和跳转。
3. 中文字段说明、衍生逻辑以 `schema_registry.json` 和变量注册文件为来源。
4. 后续模块更新后仍应重新生成该 Excel。

## 7. 遗留事项

| 遗留事项 | 影响 | 建议 |
|---|---|---|
| 统一出口视图 `stock_features_core/plus/full` 尚未实施 | 不影响 Phase 3 主体模块使用，但下游统一读取入口仍需建设 | 作为下一阶段第一项 |
| 增量刷新统一调度尚未完全产品化 | 当前已完成全量历史构建，日增量机制需统一封装 | 下一阶段建设任务编排和依赖图 |
| `docs/data_contract.md` 存在历史编码乱码 | 不影响数据库和变量字典，但不适合作为当前契约入口 | 单独重建 UTF-8 版 data contract |
| 部分旧报告仍在 reports 中保留为审计资料 | 不影响使用，但报告区较重 | 后续可按“审计/运行日志/归档”再分层 |
| 北交所、退市股等边缘样本覆盖需持续监控 | 已纳入数据范围，但持续更新中仍需质量审计 | 加入周期性覆盖率监控 |

## 8. 下一阶段建议

建议进入 Phase 4：工程化运行与统一出口。

优先顺序：

1. 建设 `stock_features_core`、`stock_features_plus`、`stock_features_full` 统一出口视图。
2. 建立统一增量刷新编排：基础库刷新、衍生核心表刷新、缓存刷新、视图重建、审计、数据字典刷新。
3. 重建 UTF-8 版 `docs/data_contract.md`，让工程契约与现状一致。
4. 建立每日质量报告：行数、覆盖率、缺失率、PIT 检查、异常枚举、最新交易日完整性。
5. 设计长期维护策略：超过 10 个交易日历史修复显式确认；近 10 个交易日默认修复。
6. 将 Phase 3 的运行脚本整合为统一 CLI，例如 `python -m stock_maintainance phase3 audit`、`phase3 rebuild --module composite_state`。

## 9. 最终结论

Phase 3 主体模块已完成，可以进入收尾后的下一阶段。

本阶段产出的变量库已经具备以下能力：

1. 全 A 股日频主干对齐。
2. 交易、估值、财务、资金、行业、指数、公司行为、治理、综合状态等主要股票分析事实维度覆盖。
3. 核心物理表与完整视图分层。
4. 审计报告和数据字典同步机制。
5. 事实层原则：不生成选股评分、不生成买卖信号、不生成未来收益标签。
