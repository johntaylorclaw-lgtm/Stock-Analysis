# Phase 3：衍生变量核心层实施计划

生成日期：2026-05-30  
适用范围：领域驱动衍生变量体系  
前置状态：Phase 2 基础数据层已完成，Phase 3 设计已重建为领域模块体系。

## 1. 实施目标

Phase 3 的目标是把设计中的领域驱动衍生变量体系落成可运行、可审计、可增量刷新、可导出的工程层。

本阶段不建设未来收益、训练标签、回测目标、策略信号收益归因或模型训练流程。

Phase 3 完成后，应具备：

1. 完整衍生变量注册表。
2. 领域物理表 schema。
3. 可规划 read window / write window 的 Feature Planner。
4. 可分模块全量初建和最近 10 个交易日增量刷新。
5. `stock_features_core`、`stock_features_plus`、`stock_features_full` 统一出口。
6. 衍生变量 Excel/Markdown 数据字典。
7. 衍生变量质量审计报告。
8. Phase 3 完成确认报告。

## 2. 实施边界

### 2.1 纳入范围

| 范围 | 说明 |
|---|---|
| 日频主干 | 复权价、基础收益、交易状态、股票状态、涨跌停基础 |
| 市场行为 | 价格技术、成交流动性、收益动量、波动风险、交易约束 |
| 基本面 | 估值规模、财务时点、财务质量、财务趋势 |
| 资金参与者 | 主力资金、大小单、两融、北向、龙虎榜 |
| 上下文 | 行业、概念、指数、市场宽度、风格环境 |
| 截面变换 | 排名、分位、标准化、中性化、风格暴露 |
| 事件和治理稳定子集 | 分红、质押、披露、预告快报、审计、主营构成中当前基础表可支撑部分 |
| 组合状态稳定子集 | 量价、资金价格、估值质量、风险状态等解释性强的组合变量 |

### 2.2 不纳入范围

| 不纳入项 | 说明 |
|---|---|
| 未来收益标签 | 由其他工程生成 |
| 训练集构造 | 由其他工程完成 |
| 回测引擎 | 由其他工程完成 |
| 交易信号生产 | 本工程只维护变量，不给买卖建议 |
| 盘口/分钟级变量 | Phase 3 仅基于当前日频和低频基础库 |
| 当前基础库未稳定覆盖的数据源扩展 | 只保留设计，不作为 Phase 3 阻断验收 |

## 3. 目标模块和表

| 顺序 | 模块 | 物理表 | Phase 3 要求 |
|---:|---|---|---|
| 1 | `daily_spine` | `derived_daily_spine` | 必须完成 |
| 2 | `price_technical` | `derived_price_technical` | core 完成 |
| 3 | `volume_liquidity` | `derived_volume_liquidity` | core 完成 |
| 4 | `return_momentum` | `derived_return_momentum` | core 完成 |
| 5 | `volatility_risk` | `derived_volatility_risk` | core 完成 |
| 6 | `trading_constraint` | `derived_trading_constraint` | core 完成 |
| 7 | `valuation_size` | `derived_valuation_size` | core 完成 |
| 8 | `financial_asof` | `derived_financial_asof` | 必须完成 |
| 9 | `financial_quality` | `derived_financial_quality` | core 完成 |
| 10 | `financial_growth` | `derived_financial_growth` | core 完成 |
| 11 | `capital_flow` | `derived_capital_flow` | core 完成 |
| 12 | `sector_concept_context` | `derived_sector_concept_context` | core 完成 |
| 13 | `index_market_context` | `derived_index_market_context` | core 完成 |
| 14 | `cross_sectional` | `derived_cross_sectional` | core 完成 |
| 15 | `corporate_action` | `derived_corporate_action` | 稳定子集完成 |
| 16 | `ownership_governance` | `derived_ownership_governance` | 稳定子集完成 |
| 17 | `composite_state` | `derived_composite_state` | 稳定子集完成 |

## 4. 总体依赖顺序

```text
Phase 3 contract and registry
  -> schema and migration
  -> feature planner
  -> daily_spine
  -> market behavior modules
       price_technical
       volume_liquidity
       return_momentum
       volatility_risk
       trading_constraint
  -> fundamentals modules
       valuation_size
       financial_asof
       financial_quality
       financial_growth
  -> participants and context
       capital_flow
       sector_concept_context
       index_market_context
  -> cross_sectional
  -> corporate_action / ownership_governance / composite_state
  -> views, export, audit, docs
```

实现原则：

1. `daily_spine` 是所有日频变量的强依赖。
2. `financial_asof` 是所有财务变量的强依赖。
3. `cross_sectional` 必须在上游 core 模块完成后计算。
4. `composite_state` 只组合已有变量，不重复计算底层指标。
5. 事件和治理变量允许分批，但已注册变量必须能说明可用性和缺失策略。

## 5. 里程碑计划

### Milestone 0：Phase 3 契约冻结

目标：把领域模块、表名、变量注册字段、质量规则和刷新规则冻结。

任务：

1. 确认领域模块体系。
2. 明确所有目标物理表名。
3. 明确默认价格口径。
4. 明确财务 point-in-time 映射规则。
5. 明确最近 10 个交易日增量刷新规则。
6. 明确 `core`、`extended`、`experimental` 出口边界。

产出：

| 产出 | 文件 |
|---|---|
| Phase 3 设计 | `docs/phase3_core_derived_plan.md` |
| 变量体系设计 | `docs/variable_registry_design.md` |
| Phase 3 实施计划 | `docs/phase3_implementation_plan.md` |

验收：

1. 文档中不再把旧 A-J 作为新工程主框架。
2. `validate-config` 通过。
3. `docs-check` 通过。

当前状态：已基本完成。

### Milestone 1：衍生变量注册表扩展

目标：将 seed registry 扩展为 Phase 3 可实现的完整注册表。

任务：

1. 按 17 个领域模块生成变量清单。
2. 为每个变量补齐 `dependencies`、`formula_ref`、`params`、`min_history`、`read_window`、`write_window`。
3. 补齐 `price_basis`、`point_in_time`、`missing_policy`、`validation`。
4. 标记变量可用性：`available_now`、`requires_structured_split`、`reserved_source_extension`。
5. 对事件和治理变量列出稳定子集和延期清单。
6. 生成衍生变量 Markdown 和 Excel 数据字典。

产出：

| 产出 | 文件 |
|---|---|
| 完整衍生变量注册表 | `config/variables/derived_variables.json` |
| 衍生变量 Markdown 字典 | `docs/generated_variable_dictionary.md` |
| 衍生变量 Excel 字典 | `outputs/phase3/derived_variable_dictionary.xlsx` |
| 变量覆盖报告 | `docs/phase3_variable_coverage_review.md` |

验收：

1. 注册表 JSON 合法。
2. 无重复变量名。
3. 每个变量有模块、表、层级、依赖、公式、口径和缺失策略。
4. `validate-config` 通过。
5. 数据字典可人工审阅。

建议优先级：

1. 先注册 `daily_spine`、市场行为、财务时点、估值规模。
2. 再注册财务质量、财务趋势、资金参与者、上下文。
3. 最后注册截面、事件治理、组合状态。

### Milestone 2：Schema 和迁移机制

目标：将领域物理表写入 schema registry，并支持创建和补列迁移。

任务：

1. 在 `config/schema_registry.json` 增加所有 `derived_*` 领域表。
2. 每张表统一主键 `(ts_code, trade_date)`。
3. 每张表增加 `updated_at`。
4. 对低频事件拆表保留原始粒度，日频衍生表只保存 asof 结果。
5. 确认 schema 字段与变量注册表一致。
6. 跑 `init-db` 或 schema reconcile。

产出：

| 产出 | 文件/对象 |
|---|---|
| schema registry 更新 | `config/schema_registry.json` |
| 领域物理表 | DuckDB `derived_*` tables |
| schema gap review | `docs/phase3_schema_gap_review.md` |

验收：

1. 所有注册表目标表存在。
2. 所有注册变量字段在 schema 中存在，或被明确标记为视图字段。
3. `validate-config` 通过。
4. `init-db` / schema reconcile 可重复运行。

### Milestone 3：Feature Planner

目标：建立按模块、日期范围、依赖窗口生成执行计划的规划器。

任务：

1. 读取变量注册表。
2. 解析模块依赖关系。
3. 根据 `min_history`、`read_window`、`write_window` 计算读取窗口和写入窗口。
4. 支持日常模式：默认最近 10 个交易日写入。
5. 支持历史模式：超过 10 个交易日时输出确认提示。
6. 输出模块执行顺序、影响表、预计行数和风险提示。

产出：

| 产出 | 文件/命令 |
|---|---|
| planner 模块 | `src/stock_maintainance/features/planner.py` |
| CLI | `plan-features` |
| 计划报告 | `reports/phase3_feature_plan.md` |

验收：

1. 能对指定日期范围生成计划。
2. 能对指定模块生成计划。
3. 能识别超 10 日历史重算。
4. 能输出 read/write window。
5. 不实际写数据时可 dry-run。

### Milestone 4：计算引擎骨架

目标：建立可复用的模块执行框架。

任务：

1. 建立 `src/stock_maintainance/features/` 包。
2. 建立模块统一接口：`plan`、`build`、`delete_window`、`insert_window`、`audit_window`。
3. 建立 DuckDB SQL 执行工具。
4. 建立 pandas 辅助算子位置，仅用于递归或复杂状态变量。
5. 建立统一写入策略：按写入窗口删除重写。
6. 建立模块运行日志和行数统计。

建议文件：

```text
src/stock_maintainance/features/
  __init__.py
  planner.py
  registry.py
  context.py
  writer.py
  audit.py
  modules/
    daily_spine.py
    price_technical.py
    volume_liquidity.py
    return_momentum.py
    volatility_risk.py
    trading_constraint.py
    valuation_size.py
    financial_asof.py
    financial_quality.py
    financial_growth.py
    capital_flow.py
    sector_concept_context.py
    index_market_context.py
    cross_sectional.py
    corporate_action.py
    ownership_governance.py
    composite_state.py
```

CLI：

| 命令 | 用途 |
|---|---|
| `plan-features` | 输出刷新计划 |
| `build-features` | 构建指定模块或全部模块 |
| `audit-features` | 审计衍生变量质量 |
| `export-feature-dictionary` | 导出衍生变量字典 |

验收：

1. 空模块可 dry-run。
2. 指定模块可单独运行。
3. 写入窗口删除重写逻辑可测试。
4. 运行日志记录模块、日期、输入行数、输出行数、耗时。

### Milestone 5：日频主干实现

目标：完成所有日频变量的共同地基。

任务：

1. 计算复权 OHLC。
2. 计算 `ret_1`、`log_ret_1`、`overnight_ret`、`intraday_ret`。
3. 计算 `true_range`、`true_range_ratio`、`typical_price`。
4. 计算涨跌停标记和距离。
5. 计算交易状态、停牌/零成交状态。
6. 计算股票状态、上市年龄、退市状态、市场板块。

产出：

| 产出 | 对象 |
|---|---|
| 主干表 | `derived_daily_spine` |
| 主干质量报告 | `reports/phase3_daily_spine_quality.md` |

验收：

1. key 与 `stock_daily` 写入窗口对齐。
2. 复权价非空率符合预期。
3. OHLC 合法。
4. 涨跌停 flag 范围为 0/1。
5. 无重复 `(ts_code, trade_date)`。

### Milestone 6：市场行为模块实现

目标：实现市场行为核心变量。

模块：

1. `price_technical`
2. `volume_liquidity`
3. `return_momentum`
4. `volatility_risk`
5. `trading_constraint`

任务：

1. 实现均线、MACD、RSI、KDJ、WR、CCI、BOLL、通道、价格位置。
2. 实现成交量/成交额/换手均线、VWAP、OBV、PVT、MFI、CMF、Amihud。
3. 实现多周期收益、相对收益、动量强度、突破、新高新低、反转。
4. 实现历史波动、回撤、下行波动、VaR/CVaR、Beta、特质风险。
5. 实现涨跌停滚动、缺口、影线、实体、振幅、可交易性。

验收：

1. 每个模块可单独运行。
2. 每个模块 key 与 `derived_daily_spine` 对齐。
3. 初始窗口缺失被正确豁免。
4. RSI 等范围变量通过范围检查。
5. 信号变量常量率不过高。

### Milestone 7：基本面模块实现

目标：实现估值和财务相关核心变量。

模块：

1. `valuation_size`
2. `financial_asof`
3. `financial_quality`
4. `financial_growth`

任务：

1. 实现估值基础、估值分位、行业相对估值、市值规模、分红收益。
2. 建立 `financial_asof` 日频映射。
3. 实现 TTM 和单季口径。
4. 实现盈利能力、现金流质量、应计、资产质量、负债质量。
5. 实现成长、环比、趋势、营运效率、偿债、杜邦、综合评分。

关键约束：

1. 不允许用 `end_date` 提前映射。
2. 必须使用 `effective_date = coalesce(first_ann_date, ann_date)`。
3. 多版本披露保留可得时点版本。

验收：

1. 财务 point-in-time 检查通过。
2. 财务变量对未披露区间不做未来回填。
3. TTM/单季/同比/环比口径明确。
4. 财务缺失原因可解释。

### Milestone 8：资金、上下文和截面模块实现

目标：实现资金参与者、行业概念、指数市场和截面变换。

模块：

1. `capital_flow`
2. `sector_concept_context`
3. `index_market_context`
4. `cross_sectional`

任务：

1. 实现主力资金、大小单、两融、北向、龙虎榜核心变量。
2. 实现行业暴露、行业表现、行业内排名。
3. 实现概念暴露、概念热度、概念表现。
4. 实现指数成分、指数权重、指数相对收益、市场宽度。
5. 实现全市场和行业内排名、分位、z-score、中性残差、风格暴露。

验收：

1. 资金源缺失使用 `source_optional` 或 `event_sparse`，不阻塞主流程。
2. 行业/概念/指数映射遵守可得时点。
3. 截面变量记录样本范围、行业口径、winsorize 参数和排名方向。
4. 截面变量无异常全常量。

### Milestone 9：事件治理和组合状态稳定子集

目标：实现当前基础库可支撑的事件、治理和组合状态变量。

模块：

1. `corporate_action`
2. `ownership_governance`
3. `composite_state`

任务：

1. 从 `financial_event_raw` 中优先拆出高价值事件结构表。
2. 实现分红、披露节奏、预告快报、审计、主营构成稳定子集。
3. 实现质押、股东户数、股东集中度稳定子集。
4. 实现量价确认、资金价格、估值质量、动量风险、共振计数。
5. 对暂不可稳定实现的变量列入延期清单。

验收：

1. 事件变量全部有 `event_sparse` 或明确缺失策略。
2. 组合变量记录依赖变量和公式。
3. 组合变量非零率和常量率通过审计。
4. 延期清单说明原因和前置数据需求。

### Milestone 10：统一视图和导出

目标：建立下游稳定使用的统一出口。

任务：

1. 建立 `stock_features_core`。
2. 建立 `stock_features_plus`。
3. 建立 `stock_features_full`。
4. 建立 `stock_financial_asof_daily`。
5. 建立 `feature_module_coverage`。
6. 可选建立 Parquet 导出接口。

验收：

1. 视图无重复 key。
2. `stock_features_core` 不包含未来标签。
3. `stock_features_core` 查询稳定。
4. 字段来自注册表。
5. 视图字段与数据字典一致。

### Milestone 11：质量审计和验收报告

目标：建立 Phase 3 的强制质量闸门。

任务：

1. 表行数和日期覆盖检查。
2. key 对齐检查。
3. 非空率检查。
4. 常量率检查。
5. 合法范围检查。
6. point-in-time 检查。
7. 截面样本检查。
8. 分布漂移检查。
9. 输出 Markdown 和 CSV 报告。

产出：

| 产出 | 文件 |
|---|---|
| 表计数 | `reports/feature_quality_table_counts.csv` |
| 非空率 | `reports/feature_quality_null_ratios.csv` |
| 常量率 | `reports/feature_quality_constant_checks.csv` |
| key 对齐 | `reports/feature_quality_key_alignment.csv` |
| 审计报告 | `reports/feature_quality_report.md` |
| Phase 3 完成报告 | `docs/phase3_completion_report.md` |

验收：

1. 阻断级问题为 0。
2. 非阻断问题有解释和后续动作。
3. 审计报告可复现生成。

## 6. 实施顺序建议

建议按四个批次推进。

### Batch 1：工程骨架和主干

包含：

1. 完整注册表第一版。
2. schema registry。
3. Feature Planner。
4. 计算引擎骨架。
5. `derived_daily_spine`。

完成后即可验证增量机制、key 对齐和最小主视图。

### Batch 2：日频市场行为

包含：

1. `price_technical`
2. `volume_liquidity`
3. `return_momentum`
4. `volatility_risk`
5. `trading_constraint`

完成后可以形成第一版日频技术与风险特征库。

### Batch 3：基本面、资金和上下文

包含：

1. `valuation_size`
2. `financial_asof`
3. `financial_quality`
4. `financial_growth`
5. `capital_flow`
6. `sector_concept_context`
7. `index_market_context`

完成后可以形成默认 `stock_features_core`。

### Batch 4：截面、事件治理、组合状态和审计

包含：

1. `cross_sectional`
2. `corporate_action`
3. `ownership_governance`
4. `composite_state`
5. 统一视图。
6. 完整审计报告。
7. Excel 数据字典。
8. Phase 3 完成报告。

## 7. 风险和处理策略

| 风险 | 影响 | 处理 |
|---|---|---|
| 注册表变量过多导致一次实现失控 | 工期和质量风险 | 先 core，extended 分批 |
| 财务字段口径复杂 | point-in-time 和公式风险 | 先 `financial_asof`，再质量和趋势 |
| 事件数据在 JSON 中 | 结构不稳定 | 高价值事件先拆表，其他延期 |
| 长窗口变量增量慢 | 日批性能风险 | read window / write window 分离 |
| 截面变量样本口径不清 | 下游误用 | 记录 universe、行业口径、winsorize 参数 |
| 组合状态变量黑箱化 | 审计困难 | 只组合已有变量，公式注册化 |
| 北向、龙虎榜等源缺失 | 日批阻塞 | 使用 optional/event_sparse 缺失策略 |

## 8. 已确认事项

2026-05-30 已确认：

1. Phase 3 按 `core first` 推进，先完成 `daily_spine`、市场行为、财务时点、资金、上下文和截面，再补 extended。
2. 衍生变量 Excel 字典按实际落库字段生成，不以未落库注册表草案作为最终字典。
3. 事件治理模块先做分红、质押、披露、预告快报、审计和主营构成；股东户数/十大股东若结构化不足，则列为延期项。

下一步执行 Batch 1。
