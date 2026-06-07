# 05 衍生变量 Phase 3 总览

更新日期：2026-06-05

## 1. Phase 3 目标

Phase 3 负责建设股票分析模型可用的衍生事实变量层。

本阶段坚持：

1. 事实变量优先。
2. 不生成评分。
3. 不生成买卖信号。
4. 不生成未来收益标签。
5. 不沿用原项目旧 A-J 框架。
6. 基于可得基础变量重新设计领域驱动模块体系。
7. 核心物理表与完整视图分层。

## 2. 设计框架

Phase 3 采用以下模块体系：

| 模块组 | 模块 | 核心目标 |
|---|---|---|
| 日频基准 | 日频主干 | 对齐股票、交易日、价格口径、上市状态和质量标记 |
| 市场行为 | 价格技术、成交流动性、收益动量、波动风险、交易约束 | 覆盖技术分析和 A 股交易制度事实 |
| 基本面 | 估值规模、财务 as-of、财务质量、财务成长 | 覆盖估值、市值、财务状态和多周期变化 |
| 资金参与者 | 资金流、北向、两融、龙虎榜事件 | 覆盖交易参与者和资金结构 |
| 上下文 | 行业概念、指数市场 | 覆盖板块、概念、指数、市场宽度和市场环境 |
| 截面工程 | 截面转换 | rank、percentile、z-score、中性化残差 |
| 事件治理 | 公司行为、持有人治理 | 分红、预告、快报、审计、主营、回购、解禁、质押、股东 |
| 综合事实 | 综合事实状态 | 多域状态、条件计数和可解释暴露 |

## 3. 模块清单

| 模块 | 核心对象 | 状态 |
|---|---|---|
| 日频主干 | `derived_daily_spine` | 完成 |
| 价格技术分析 | `derived_price_technical` | 完成 |
| 成交流动性 | `derived_volume_liquidity` | 完成 |
| 收益动量 | `derived_return_momentum` | 完成 |
| 波动风险 | `derived_volatility_risk` | 完成 |
| 交易约束 | `derived_trading_constraint` | 完成 |
| 估值规模 | `derived_valuation_size` | 完成 |
| 财务 as-of | `derived_financial_asof` | 完成 |
| 财务质量 | `derived_financial_quality` | 完成 |
| 财务成长 | `derived_financial_growth` | 完成 |
| 资金流 | `derived_capital_flow` | 完成 |
| 北向资金缓存 | `derived_northbound_flow_cache` | 完成 |
| 资金事件缓存 | `derived_capital_flow_event_cache` | 完成 |
| 行业概念上下文 | `derived_sector_concept_context` | 完成 |
| 指数市场上下文 | `derived_index_market_context` | 完成 |
| 截面转换 | `derived_cross_sectional` | 完成 |
| 公司行为 | `derived_corporate_action` | 完成 |
| 持有人治理 | `derived_ownership_governance` | 完成 |
| 综合事实状态 | `derived_composite_state` | 完成 |

## 4. 核心物理表规模

| 核心对象 | 行数 | 列数 |
|---|---:|---:|
| `derived_daily_spine` | 15,295,776 | 49 |
| `derived_price_technical` | 15,295,776 | 16 |
| `derived_volume_liquidity` | 15,295,776 | 14 |
| `derived_return_momentum` | 15,295,776 | 16 |
| `derived_volatility_risk` | 15,295,776 | 13 |
| `derived_trading_constraint` | 15,295,776 | 14 |
| `derived_valuation_size` | 15,295,776 | 34 |
| `derived_financial_asof` | 15,295,776 | 30 |
| `derived_financial_quality` | 15,295,776 | 117 |
| `derived_financial_growth` | 15,295,776 | 255 |
| `derived_capital_flow` | 15,295,776 | 64 |
| `derived_northbound_flow_cache` | 15,295,776 | 41 |
| `derived_capital_flow_event_cache` | 15,295,776 | 32 |
| `derived_sector_concept_context` | 15,295,776 | 104 |
| `derived_index_market_context` | 15,295,776 | 105 |
| `derived_cross_sectional` | 15,295,776 | 353 |
| `derived_corporate_action` | 15,295,776 | 104 |
| `derived_ownership_governance` | 15,295,776 | 63 |
| `derived_composite_state` | 15,295,776 | 92 |

## 5. 完整视图与辅助对象

| 对象 | 列数 | 说明 |
|---|---:|---|
| `derived_price_technical_full_v` | 74 | 技术分析完整视图 |
| `derived_volume_liquidity_full_v` | 69 | 成交流动性完整视图 |
| `derived_return_momentum_full_v` | 77 | 收益动量完整视图 |
| `derived_volatility_risk_full_v` | 50 | 波动风险完整视图 |
| `derived_trading_constraint_full_v` | 69 | 交易约束完整视图 |
| `derived_valuation_size_full_v` | 165 | 估值规模完整视图 |
| `derived_financial_growth_full_v` | 1196 | 财务成长完整视图 |
| `derived_capital_flow_full_v` | 246 | 资金流完整视图 |
| `derived_sector_concept_context_full_v` | 356 | 行业概念完整视图 |
| `derived_index_market_context_full_v` | 260 | 指数市场完整视图 |
| `derived_cross_sectional_full_v` | 1063 | 截面转换完整视图 |
| `derived_corporate_action_full_v` | 144 | 公司行为完整视图 |
| `derived_ownership_governance_full_v` | 98 | 持有人治理完整视图 |
| `derived_composite_state_full_v` | 115 | 综合事实状态完整视图 |
| `corporate_action_event_timeline_v` | 10 | 公司行为事件时间线 |
| `ownership_holder_concentration_v` | 10 | 股东集中度辅助视图 |
| `ownership_governance_event_timeline_v` | 12 | 持有人治理事件时间线 |
| `composite_state_condition_detail_v` | 10 | 综合状态条件明细 |
| `composite_state_module_coverage_v` | 8 | 综合状态模块覆盖 |

## 6. 变量丰富度原则

用户明确要求基础变量和衍生变量尽量完整、数据尽量丰富。Phase 3 的实现原则为：

1. 核心物理表保留高频使用和增量必须写入字段。
2. 完整视图展开更丰富周期，例如 2、3、5、10、20、30、60、90、120、180、250 等。
3. 财务成长使用物理核心表 + 完整视图，避免把 1000+ 列全部物化造成空间压力。
4. 概念上下文保留多概念列表和多周期列表，不只保留单一概念。
5. 截面转换提供全市场、市场板块、交易所、行业等多个分组口径。
6. 事实层不生成综合评分，但可以生成条件计数、状态枚举和透明暴露。

## 7. 验收入口

Phase 3 总验收和遗留事项见：

`docs/08_审计验收与遗留事项.md`

模块设计细节见：

`docs/06_Phase3模块设计合订本.md`
