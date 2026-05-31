# Stock_Maintainance 重建方案审阅稿

生成日期：2026-05-27  
新项目路径：`D:\Opencode Workspace\Stock_Maintainance`  
原项目路径：`D:\Opencode Workspace\stock_data_maintainance`  
当前阶段：设计审阅，不进入代码实现

## 0. 本文目标

本文先完成你要求的三件事：

1. 理解原项目，并列出原项目已实现或计划实现的功能，供你逐一审查。
2. 在原项目基础上重新设计基础变量和衍生变量架构，使变量体系更完整、更可维护。
3. 设计新的项目实施步骤、运行机制、效率方案和文档同步机制，作为后续重建工作的蓝图。

本文不会假设原项目一切都正确。它的定位是：继承原项目已经验证过的优点，修正原项目在变量设计、代码结构、日增量效率和文档一致性上的问题。

## 0.1 Phase 0 确认结论

根据 2026-05-27 第一轮审阅反馈，Phase 0 已确认如下：

| 事项 | 确认结论 |
|---|---|
| 原项目数据范围 | 原项目功能清单中的数据都需要保留，新项目目标是更丰富、更详实，而不是缩减范围 |
| 财务明细 | 当前方案不够充分，后续需重点展开分红、股东、股本结构、主营构成、业绩预告/快报等细分设计 |
| 概念板块 | 当前方案不够充分，后续需展开概念定义、成分映射历史、概念行情、概念资金流和概念热度 |
| 衍生变量 | 不再沿用旧 A-J 框架，改为领域驱动模块体系，覆盖日频主干、市场行为、基本面、事件持有人、资金参与者、上下文、截面和组合状态 |
| 核心/扩展变量 | 不做二选一；基础变量、核心衍生变量和扩展衍生变量都要建设，通过模块表、视图和变量注册表连接 |
| 标签/目标变量 | 不纳入本工程 |
| 日常修复窗口 | 最近 10 个交易日的历史修复可以默认触发 |
| 远期历史刷新 | 超过 10 个交易日的源数据修复或衍生变量刷新需要显式确认，基础库初建阶段除外 |
| 工程定位 | 本工程专注股票数据维护，不负责量化选股、回测训练、策略标签和模型目标 |

详细确认记录见 `docs/phase0_confirmation.md`。

## 1. 原项目功能清单，请先审查

下面按功能域列出原项目已经具备的能力。后续新项目应至少覆盖这些功能；你可在每项后标注保留、调整、删除或新增。

### 1.1 数据源与数据范围

| 功能 | 原项目状态 | 新项目处理建议 |
|---|---|---|
| A 股全市场股票池 | 覆盖沪深京，约 5,500 只股票 | 保留，增加退市/暂停上市状态管理 |
| 历史日线数据 | 覆盖约 2006 至当前，`stock_daily` 约 1,525 万行 | 保留，作为核心事实表 |
| 复权因子 | `stock_adj_factor`，支持前复权、后复权因子 | 保留，复权口径必须纳入变量元数据 |
| 日度基础指标 | `stock_daily_basic`，含换手率、估值、市值、股本 | 保留，提升为一等源表，不作为临时表 |
| 指数日线 | `index_daily`，含沪深 300 等核心指数 | 保留，扩展指数池配置 |
| 交易日历 | `trade_calendar` | 保留，作为所有增量任务的日期基准 |
| 个股基础信息 | `stock_basic_info`、`stock_list` | 保留，增加证券状态变更历史 |
| 行业/概念板块 | `board_industry`、`board_concept`、`stock_concept_mapping` | 保留，建议增加行业归属历史表 |
| 个股资金流 | `stock_fund_flow_daily` | 保留，明确金额单位和缺失策略 |
| 行业资金流 | `stock_fund_flow_industry`，由个股聚合修复 | 保留，建议作为可复现聚合表 |
| 北向资金 | `north_bound_daily`、`north_bound_stock`，当前默认不补全 | 保留为可选数据域，默认不阻塞主流程 |
| 融资融券 | `margin_trading` | 保留，按交易所可用性处理缺失 |
| 财务报表 | `financial_income`、`financial_balance`、`financial_cashflow` | 保留，增加公告日可用性约束 |
| 财务指标 | `financial_indicator` | 保留，明确源字段、推导字段和 ASOF 映射 |
| 财务补充明细 | `financial_detail` | 保留，但需拆分分红、股东、分部收入等子表 |
| 备用数据源 | akshare/Sina/THS/SSE/SZSE 等曾作为补充 | 保留为 fallback，不作为无记录的隐式逻辑 |

### 1.2 数据库与存储功能

| 功能 | 原项目状态 | 新项目处理建议 |
|---|---|---|
| DuckDB 单文件数据库 | `data/stock_data.duckdb`，约 60GB 级 | 保留，增加分层数据目录和版本标识 |
| 自然复合主键 | 多数表使用 `(ts_code, trade_date)` 或等价主键 | 保留，统一写入冲突策略 |
| 物理衍生表 | `derived_a` 至 `derived_j` 物理表 | 只保留“模块化物理表”的经验，新项目改为领域表，如 `derived_price_technical`、`derived_financial_quality` |
| 汇总视图 | `stock_derived` 视图连接旧模块 | 保留统一出口思想，新项目改为 `stock_features_core`、`stock_features_plus`、`stock_features_full` |
| Parquet 导出 | `tools/export_feature_parquet.py` | 保留，作为下游训练/分析推荐出口 |
| 样例工作簿导出 | 单只股票基础+衍生 Excel 样例 | 保留，作为人工验收工具 |
| 变量标签表 | `metadata_variable_labels` 和 CSV/JSON/XLSX/MD 导出 | 保留，改为由变量注册表自动生成 |
| 空间分析报告 | DuckDB 存储占用、表大小报告 | 保留，纳入定期审计 |

### 1.3 增量更新与调度功能

| 功能 | 原项目状态 | 新项目处理建议 |
|---|---|---|
| 老式并发更新入口 | `src/updater.py`，8 线程并发 | 不作为主入口，保留为参考 |
| 有序增量流水线 | `src/incremental_update_pipeline.py` | 作为新项目主流程原型 |
| 动态缺口检测 | 按各表 `MAX(date)` 和交易日历计算缺口 | 保留，升级为统一 gap planner |
| 18:00 前不追当天 | 防止盘中/早晨误追未收盘交易日 | 保留，配置化 |
| 日常轻量模式 | 默认最近 10 个交易日源修复和衍生刷新 | 保留，但优化窗口计算效率 |
| 历史修复模式 | `--run-tier history --derived-mode full` | 保留，作为显式人工任务 |
| 北向资金开关 | 默认跳过，`--update-north` 显式开启 | 保留 |
| 财务近期刷新开关 | 默认只补缺失季度，显式刷新近 6 季度 | 保留，增加公告修订检测 |
| CHECKPOINT | 更新后清理 WAL | 保留 |
| Agent Skill 入口 | `StockDataUpdater.incremental_update()` | 保留，重建为轻薄接口层 |

### 1.4 衍生变量功能

原项目当前核心资产是旧 A-J 衍生变量物理表，实际宽视图约 772 列，其中衍生变量约 770 个。新项目不继承旧字母框架，只继承其中已经证明有价值的变量思想，并重新归入领域模块。

| 原项目功能域 | 原项目位置 | 新项目领域模块 | 新项目处理建议 |
|---|---|---|---|
| 复权、收益、基础状态 | 散落在旧视图和多模块中 | `daily_spine` | 提升为所有日频变量的共同地基 |
| 均线、趋势、摆动、通道 | `derived_a` | `price_technical` | 保留稳定指标，周期分 core/extended |
| 成交量、成交额、换手、VWAP、Amihud | `derived_b` | `volume_liquidity` | 补充流动性稳定性、交易稀疏和冲击成本 |
| 多周期收益、突破、新高新低、反转 | `derived_d` | `return_momentum` | 明确只做历史收益特征，不做未来标签 |
| 波动、回撤、Beta、VaR、特质风险 | `derived_c` | `volatility_risk` | 明确基准指数、年化参数和尾部风险口径 |
| K 线、缺口、涨跌停、停牌 | `derived_e` | `trading_constraint` | A 股交易约束独立成域 |
| 估值、市值、分红、规模 | `derived_f` 的一部分 | `valuation_size` | 与财务质量拆开，保留源口径 |
| 财务 asof、盈利质量、成长、杜邦 | `derived_f` 的一部分 | `financial_asof`、`financial_quality`、`financial_growth` | 全部按公告日 point-in-time 映射 |
| 分红、预告、审计、主营构成 | 旧财务明细和事件表 | `corporate_action` | 从 `financial_event_raw` 拆成结构化表后计算 |
| 质押、股东户数、股东集中度 | 旧财务明细和质押表 | `ownership_governance` | 独立维护治理和持有人结构变量 |
| 资金流、两融、北向、龙虎榜 | `derived_g` | `capital_flow` | 缺失来源显式标注，事件稀疏不阻塞主流程 |
| 行业、概念、指数、市场宽度 | `derived_h` 和基础映射 | `sector_concept_context`、`index_market_context` | 扩展行业历史、概念热度、指数和市场状态 |
| 截面排名、分位、标准化 | 部分散落在旧模块 | `cross_sectional` | 新增为模型友好的工程层 |
| 跨域组合、共振、状态变量 | `derived_i`、`derived_j` | `composite_state` | 只组合已有变量，保留公式和依赖审计 |

### 1.5 验证、审计与修复功能

| 功能 | 原项目状态 | 新项目处理建议 |
|---|---|---|
| 衍生变量统计报告 | `tools/derived_stats_report.py`，检查空列、低填充、常量列、分布 | 保留，作为强制验收门 |
| 全表逐列完整性审计 | `tools/audit_all_table_column_completeness.py` | 保留，纳入定期任务 |
| 三方交叉验证 | `tests/verify_data.py` | 保留，改为抽样验证套件 |
| 常量信号审查 | 发现并修复常量背离信号、突破确认信号 | 保留，加入信号有效性规则 |
| daily_basic 修复 | 修复换手率、估值、市值、财务 ASOF 字段 | 保留，重构为可测试的 repair job |
| 审计 5 修复 | 修复复权缺口、OHLC 异常、估值分位常量等 | 作为新项目迁移验收用例 |
| 白名单机制 | 低填充字段可配置白名单 | 保留，但必须记录原因和过期时间 |

### 1.6 文档与报告功能

| 功能 | 原项目状态 | 新项目处理建议 |
|---|---|---|
| README 总览 | 有，但与实际演进存在偏差 | 新项目 README 自动引用生成文档 |
| 设计文档 | 有 DDL、数据字典、索引计划、经验总结、增量方案 | 保留文档类型，但改为 schema/registry 生成 |
| 实施文档 | 旧字母模块实现说明 | 只作为迁移参考，新项目拆成领域变量注册表和公式说明 |
| 审计报告 | 多个 dated report | 保留，统一 `reports/YYYYMMDD/` |
| 变量标签报告 | CSV/JSON/XLSX/MD | 保留，由 metadata 生成 |
| 文档同步机制 | 原项目主要靠人工维护，出现漂移 | 新项目必须引入文档漂移检测 |

## 2. 原项目优点，应在新项目中继承

1. DuckDB 作为本地 OLAP 引擎是合适的。A 股日频数据和宽特征扫描适合列式存储，单文件也便于备份和迁移。
2. `stock_daily` 与 `stock_adj_factor` 分离是正确的。原始价格和复权口径分开，能避免把不可逆的价格处理固化到源表。
3. `stock_daily_basic` 从临时修复表升级为一等源表是正确演进。估值、市值、股本、自由流通股、换手率必须可复现。
4. 旧项目证明“模块化物理表”比单个巨型宽表更可维护。新项目继承模块化思想，但模块边界改为领域驱动。
5. 统一出口视图是好设计。下游用户看到统一宽表，内部保留领域表和分模块刷新。
6. 有序增量流水线优于纯并发更新。结构、行情、日度基础、资金、财务、修复、衍生、验证有明确依赖顺序。
7. 日常轻量模式与历史修复模式分离是正确方向。日常任务不应默认全量重算 60GB 级宽特征。
8. 变量标签、价格口径、完整性审计、常量列审查这些元数据工作很有价值，应转为制度化机制。
9. Parquet 导出是必要的下游加速层。模型训练和跨日期/跨列筛选不应反复扫描 DuckDB 宽视图。
10. Agent Skill 包装思路可保留，但新项目中应只做薄封装，不承载业务逻辑。

## 3. 原项目主要问题与新项目约束

| 问题 | 原项目表现 | 新项目约束 |
|---|---|---|
| 变量体系先实现后整理 | 多轮演进后出现 315 列、770 列、772 列等口径混杂 | 先建立变量注册表，再生成 DDL、文档、标签、验证规则 |
| 基础变量不完整 | 有些字段靠修复脚本回填，字段来源和可靠性不统一 | 每个基础变量记录 source、unit、frequency、availability、quality |
| 衍生变量重复和冗余 | A 模块大量周期展开，部分信号曾为常量 | 变量分为 core、extended、experimental 三档，实验变量默认不进主宽表 |
| 日增量慢 | 2026-05-26 日批约 7,197 秒，主要耗时在源修复和衍生刷新 | 所有日批计算必须支持 read_context_window + write_window |
| 代码结构混杂 | src、tools、backups、repair 脚本职责交叉 | 采用 ingestion、storage、features、validation、ops 五层架构 |
| 文档漂移 | README 和实际旧模块、表数、列数存在不一致 | 文档由注册表和数据库 introspection 生成，CI 检查漂移 |
| 修复脚本散落 | 多个 repair 工具体现真实逻辑，但没有沉淀为稳定模块 | repair job 纳入正式 pipeline，带测试和审计输出 |
| 数据可用时点不足 | 财务变量 ASOF 映射已有，但需强化公告日/可得日约束 | 所有财务和公司行为变量必须 point-in-time |

## 4. 新项目总体架构

### 4.1 推荐目录结构

```text
Stock_Maintainance/
  README.md
  pyproject.toml
  config/
    sources.yaml
    pipeline.yaml
    variables/
      base.yaml
      derived_daily_spine.yaml
      derived_price_technical.yaml
      derived_volume_liquidity.yaml
      derived_financial_quality.yaml
      ...
    validation.yaml
  docs/
    rebuild_plan.md
    data_contract.md
    variable_dictionary.md
    runbook.md
    changelog.md
    adr/
  src/
    stock_maintainance/
      cli.py
      config/
      db/
      ingest/
      storage/
      features/
      validation/
      export/
      ops/
  tests/
    unit/
    integration/
    data_quality/
  reports/
  data/
    duckdb/
    parquet/
    snapshots/
  logs/
```

### 4.2 分层原则

| 层 | 职责 | 说明 |
|---|---|---|
| source layer | API 拉取、源字段标准化、限流、重试 | 不做复杂业务推导 |
| raw/staging layer | 保存源返回快照或标准化临时表 | 便于复盘源数据变化 |
| base layer | 清洗后的基础事实表和维表 | 所有主键、单位、日期口径稳定 |
| repair layer | 可复现修复和 ASOF 映射 | 从散落脚本升级为正式 job |
| feature layer | 领域驱动衍生变量模块 | 由变量注册表驱动；标签/目标变量不纳入本工程 |
| metadata layer | 变量标签、口径、依赖、质量规则 | 生成文档和验证 |
| export layer | DuckDB 视图、Parquet、样例工作簿 | 服务下游使用 |
| validation layer | 完整性、分布、漂移、常量、样本复核 | 每次 pipeline 产出报告 |

## 5. 新基础变量架构

基础变量不等于全部源字段。新项目建议把基础变量分为 8 个域，每个字段在注册表中记录：字段名、中文名、单位、频率、主键、来源、是否 point-in-time、缺失策略、是否进入默认训练集。

### 5.1 S0 证券主数据

| 类别 | 推荐变量 |
|---|---|
| 身份标识 | `ts_code`、`symbol`、`name`、`exchange`、`market`、`list_status` |
| 上市状态 | `list_date`、`delist_date`、`is_active`、`is_st`、`is_suspended` |
| 地域行业 | `area`、`industry_l1`、`industry_l2`、`industry_l3`、`concept_tags` |
| 股本结构 | `total_share`、`float_share`、`free_share`、`restricted_share` |
| 公司事件 | 分红、送转、配股、拆并股、退市整理、名称变更 |

改进点：原项目只有当前行业和当前股票信息，新项目应增加历史行业归属和证券状态历史，避免回测中使用未来行业分类。

### 5.2 S1 交易日历与市场状态

| 类别 | 推荐变量 |
|---|---|
| 交易日历 | `cal_date`、`is_open`、`pretrade_date`、`next_trade_date` |
| 市场阶段 | 年、季、月、周、月末、季末、年末、节前节后 |
| 日内状态 | 盘后可用时间、数据源可用时间、是否半日交易，若源支持 |

改进点：日批以“最新已完成交易日”为基准，继续保留 18:00 前不追当天的规则。

### 5.3 S2 个股行情基础

| 类别 | 推荐变量 |
|---|---|
| OHLC | `open`、`high`、`low`、`close`、`pre_close` |
| 收益与幅度源字段 | `change`、`pct_chg`、`amplitude` |
| 成交 | `volume`、`amount` |
| 换手与量比 | `turnover_rate`、`turnover_rate_f`、`volume_ratio` |
| 涨跌停状态 | `limit_up_price`、`limit_down_price`、`is_limit_up`、`is_limit_down`、`is_one_price_limit` |
| 停复牌 | `is_trading`、`suspend_reason`，若源可得 |

改进点：涨跌停、停牌、一字板是 A 股特有且对策略很重要，应进入基础变量或基础衍生的核心层。

### 5.4 S3 价格口径与复权基础

| 类别 | 推荐变量 |
|---|---|
| 复权因子 | `qfq_factor`、`hfq_factor` |
| 后复权 OHLC | `open_hfq`、`high_hfq`、`low_hfq`、`close_hfq` |
| 前复权 OHLC | 可选，用于与券商/行情软件校验 |
| 原始价格口径 | raw close，用于估值、市值、成交约束 |

约束：技术、收益、波动变量使用连续复权价格；估值、市值、股本、成交金额变量使用原始口径。该规则必须写入变量元数据。

### 5.5 S4 估值、市值和股本日度基础

| 类别 | 推荐变量 |
|---|---|
| 估值 | `pe`、`pe_ttm`、`pb`、`ps`、`ps_ttm`、`dv_ratio`、`dv_ttm` |
| 市值 | `total_mv`、`circ_mv`、`free_float_mv` |
| 股本 | `total_share`、`float_share`、`free_share` |
| 衍生基础 | 市值分组、流通市值分组、估值有效性标记 |

改进点：`stock_daily_basic` 不再叫 staging，不允许随意删除；它是估值、股本、换手、行业权重的基础来源。

### 5.6 S5 资金与交易行为

| 类别 | 推荐变量 |
|---|---|
| 个股资金流 | 主力、超大单、大单、中单、小单流入流出和净额 |
| 资金占比 | 主力净流入率、各档资金占成交额比例 |
| 两融 | 融资买入、融资偿还、融资余额、融券卖出、融券余额、两融余额 |
| 北向 | 北向净流入、持股数量、持股市值、持股比例、变化量 |
| 龙虎榜 | 可选扩展：买卖金额、机构席位、上榜原因 |

改进点：北向和龙虎榜可作为 optional domain，不能因为缺失拖垮主日批。

### 5.7 S6 财务与公告时点

| 类别 | 推荐变量 |
|---|---|
| 报表身份 | `ann_date`、`end_date`、`report_type`、`comp_type` |
| 利润表 | 营收、成本、费用、利润、归母净利、EPS |
| 资产负债表 | 资产、负债、权益、现金、应收、存货、商誉、有息负债 |
| 现金流量表 | 经营、投资、筹资现金流、现金净增加、OCFPS |
| 财务指标 | ROE、ROA、毛利率、净利率、负债率、周转率、成长率 |
| 财务可用性 | `effective_date` = 可用于日频特征的公告日或延迟可用日 |

改进点：财务日频映射必须用公告日，不允许简单用报告期末向后填充造成未来函数。

### 5.8 S7 板块、指数和市场环境

| 类别 | 推荐变量 |
|---|---|
| 指数行情 | 宽基指数、风格指数、行业指数 OHLCV |
| 行业归属 | 个股行业历史、概念历史、成分变化 |
| 市场宽度 | 上涨家数、下跌家数、涨停/跌停家数、成交额分布 |
| 风格环境 | 大小盘、价值成长、波动、流动性风格指数 |

改进点：原项目 H 模块已做相对强度，新项目应增加市场宽度和风格基准，支持更完整的横截面环境变量。

### 5.9 S8 元数据与审计基础

| 类别 | 推荐变量 |
|---|---|
| 源数据血缘 | `source_name`、`source_endpoint`、`fetch_time`、`source_version` |
| 数据质量 | `null_rate`、`duplicate_count`、`outlier_count`、`last_valid_date` |
| 任务状态 | 每个 job 的输入范围、输出行数、耗时、错误 |
| 变量元数据 | 标签、单位、口径、依赖、填充规则、测试规则 |

改进点：这是新项目文档同步和质量治理的基础。

## 6. 新衍生变量架构

### 6.1 重建版分层

新项目不再使用旧 A-J 或任何字母模块作为主框架。衍生变量按真实维护责任分层：

| 层 | 名称 | 定义 | 默认出口 |
|---|---|---|---|
| D0 | Daily Spine | `ts_code`、`trade_date`、交易状态、股票状态、复权价、基础收益 | 是 |
| D1 | Market Behavior | 价格技术、成交流动性、收益动量、波动风险、交易约束 | 是 |
| D2 | Fundamentals | 估值规模、财务时点、财务质量、财务趋势 | 是 |
| D3 | Events and Ownership | 公司行为、披露、分红、质押、股东结构 | 分批 |
| D4 | Participants | 主力资金、大小单、两融、北向、龙虎榜、机构席位 | 是 |
| D5 | Context | 行业、概念、指数、市场宽度、风格环境 | 是 |
| D6 | Cross Section | 排名、分位、标准化、中性化、风格暴露 | 是 |
| D7 | Composite State | 跨域组合、共振、风险状态、市场状态 | 分批 |
| D8 | Experimental | 未稳定验证的研究变量 | 否 |

### 6.2 领域模块设计

| 模块 | 物理表建议 | 主要内容 | 关键改进 |
|---|---|---|---|
| `daily_spine` | `derived_daily_spine` | 交易状态、股票状态、复权价、基础收益、连接键 | 统一所有日频变量的地基 |
| `price_technical` | `derived_price_technical` | 均线、趋势、摆动、通道、价格位置 | 稳定指标进 core，长尾周期进 extended |
| `volume_liquidity` | `derived_volume_liquidity` | 成交量、成交额、换手、VWAP、OBV、Amihud | 补充交易稀疏、流动性稳定和冲击成本 |
| `return_momentum` | `derived_return_momentum` | 多周期收益、相对收益、动量质量、突破、反转 | 只做历史收益特征，不做未来标签 |
| `volatility_risk` | `derived_volatility_risk` | 历史波动、OHLC 波动、回撤、尾部风险、Beta、特质风险 | 明确基准、年化参数和尾部口径 |
| `trading_constraint` | `derived_trading_constraint` | 涨跌停、停牌、缺口、影线、振幅、可交易性 | A 股交易约束独立成域 |
| `valuation_size` | `derived_valuation_size` | 估值分位、市值规模、股本结构、股息率、PEG | 估值源口径和技术复权口径分离 |
| `financial_asof` | `derived_financial_asof` | 最新可得报告、TTM、单季、公告滞后、修订状态 | 财务变量的 point-in-time 地基 |
| `financial_quality` | `derived_financial_quality` | 盈利能力、现金流质量、应计、资产质量、负债质量 | 深化财务质量分析 |
| `financial_growth` | `derived_financial_growth` | 成长、环比、趋势、营运效率、偿债、杜邦、综合评分 | 区分单季、TTM、同比、环比 |
| `corporate_action` | `derived_corporate_action` | 分红送转、披露计划、预告快报、审计、主营构成 | 从原始事件拆成结构化变量 |
| `ownership_governance` | `derived_ownership_governance` | 质押、股东户数、十大股东、股权集中度 | 独立维护持有人和治理风险代理 |
| `capital_flow` | `derived_capital_flow` | 主力资金、大小单、两融、北向、龙虎榜、机构席位 | 可用性分级，事件稀疏不阻塞 |
| `sector_concept_context` | `derived_sector_concept_context` | 行业暴露、概念暴露、板块表现、热度、排名 | 支持行业/概念上下文 |
| `index_market_context` | `derived_index_market_context` | 指数成分、指数权重、市场宽度、风格环境 | 支持市场状态和基准上下文 |
| `cross_sectional` | `derived_cross_sectional` | 全市场/行业内排名、分位、z-score、中性残差 | 面向分析模型的横截面工程层 |
| `composite_state` | `derived_composite_state` | 量价确认、资金价格、估值质量、风险状态、共振计数 | 只组合已有变量，保留公式和依赖审计 |

### 6.3 变量注册表示例

```yaml
- name: rsi_14
  label_zh: 14日相对强弱指标
  table: derived_price_technical
  module: price_technical
  category: oscillator
  tier: core
  frequency: daily
  dtype: double
  unit: ratio
  price_basis: hfq
  dependencies: [derived_daily_spine.close_hfq]
  formula_ref: indicators.rsi
  params: {window: 14}
  min_history: 14
  read_window: 80
  write_window: 10
  point_in_time: true
  missing_policy: initial_window_null
  validation:
    min_non_null_rate: 0.95
    constant_allowed: false
    range: [0, 100]
```

### 6.4 推荐核心变量优先级

| 优先级 | 变量类型 | 说明 |
|---|---|---|
| P0 | 日频主干、复权价格、基础收益、交易状态、财务 asof | 没有这些不进入衍生计算 |
| P1 | 价格、成交、收益、波动、交易约束、估值、财务质量、资金、上下文、截面 core | 股票分析模型最常用，必须稳定快速 |
| P2 | 公司行为、持有人治理、组合状态稳定子集 | 依赖事件拆表和有效性验证 |
| P3 | 扩展周期、复杂事件、实验信号 | 先进入研究出口，通过验证后升 core |
| P4 | 标签/目标变量 | 不纳入本工程 |

## 7. 高效运行机制设计

### 7.1 日常增量目标

原项目 2026-05-26 日批约 7,197 秒，正确但偏慢。新项目目标：

| 场景 | 目标 |
|---|---|
| 普通日批，无财务刷新 | 15 至 30 分钟内完成 |
| 普通日批，含少量源缺口 | 30 至 45 分钟内完成 |
| 财务近期刷新 | 明确标记为较重任务，可独立运行 |
| 全量历史重建 | 不伪装成日批，允许小时级 |

### 7.2 核心效率原则

1. 所有日批任务都必须使用 `read_context_window` 和 `write_window`。例如计算最近 10 日写入窗口时，可读取 500 日历史上下文，但只删除并写入最近 10 日。
2. 每个变量声明 `min_history` 和 `dependency_modules`，由 planner 自动计算最小读取窗口。
3. 数据源拉取按 API endpoint 分组限流，并发只发生在不会争抢同一写表的任务之间。
4. DuckDB 写入采用批量 DataFrame、临时表、`INSERT OR REPLACE BY NAME` 或 `MERGE`，禁止逐行写入。
5. 领域模块分模块刷新，模块内部再按 SQL-friendly、pandas-recursive、repair 三类算子分段。
6. 财务 ASOF 映射按变更股票和变更报告期限制范围，不每日全市场大范围扫描。
7. 宽视图只作为查询出口，训练和批量加载优先读分区 Parquet。
8. 验证分 light/full 两级，日批默认 light，周度或变更后 full。

### 7.3 Pipeline 顺序

```text
plan
  -> structure update
  -> trading/date source update
  -> daily_basic update
  -> capital/flow update
  -> financial update or revision check
  -> source repair
  -> feature planner computes dirty windows
  -> daily spine refresh
  -> market behavior / fundamentals / participants / context refresh
  -> cross sectional refresh
  -> event ownership / composite state refresh
  -> light/full validation
  -> parquet export, optional
  -> docs/metadata/report generation
```

### 7.4 运行模式

| 模式 | 命令设想 | 用途 |
|---|---|---|
| plan | `stock-maintain plan` | 只检查缺口和将执行的任务 |
| daily | `stock-maintain update --tier daily` | 默认日批 |
| daily-fast | `stock-maintain update --tier daily --features core` | 只刷新核心变量 |
| finance-refresh | `stock-maintain update --refresh-financial --quarters 6` | 财报披露季或修订检查 |
| history-repair | `stock-maintain repair --tier history --full-features` | 复权、DDL、公式变更后 |
| validate | `stock-maintain validate --mode full` | 全量审计 |
| export | `stock-maintain export parquet --start-date 2020-01-01` | 下游训练出口 |
| sample | `stock-maintain export sample --ts-code 600016.SH` | 人工审阅样本 |

### 7.5 增量刷新算法

1. 对每张源表计算缺失日期或缺失报告期。
2. 对每个数据域生成 `dirty_range`，例如行情变化影响日频主干、市场行为、上下文、截面和组合状态；财务变化影响财务时点、财务质量、财务趋势、截面和组合状态；资金变化影响资金参与者、截面和组合状态。
3. 对每个衍生模块读取 `dirty_range - max(min_history)` 到 `dirty_range.end` 的上下文。
4. 只删除并重写 `dirty_range` 内的目标表记录。
5. 对递归指标保存必要状态，或用足够上下文窗口重算。
6. 模块刷新完成后运行 row-key 对齐检查：每个模块必须与 `stock_daily` 在写入窗口内 key 一致。

## 8. 数据质量与验收机制

### 8.1 每次日批必须通过的 light 检查

| 检查 | 规则 |
|---|---|
| 源表最新日期 | 核心源表最新日期应达到最新已完成交易日，允许源端延迟白名单 |
| 复权完整性 | 写入窗口内 `stock_daily` 不得因缺复权因子导致衍生 key 丢失 |
| 领域模块 key 对齐 | 写入窗口内所有核心日频模块 key 与行情 key 一致 |
| 关键列非空 | P0/P1 关键列不得整列空 |
| 常量列 | signal 类变量非白名单不得全常量 |
| OHLC 合法性 | high/low/open/close 包络合法 |
| 日志与报告 | 每次生成 pipeline JSON、Markdown 摘要、错误列表 |

### 8.2 full 检查

| 检查 | 规则 |
|---|---|
| 全库逐列完整性 | 每列非空率、低填充、全空列 |
| 分布漂移 | 与前一稳定版本对比均值、分位、非零率 |
| 常量/低基数审查 | 对信号列特别检查 |
| 抽样外部复核 | 抽样股票与第三方数据源比对 |
| point-in-time 检查 | 财务、行业、公司事件不得穿越公告日 |
| Parquet 出口检查 | 行数、分区、列数和 DuckDB 一致 |

### 8.3 白名单规则

白名单不能只是“跳过”。每条白名单必须记录：

| 字段 | 说明 |
|---|---|
| table/column | 表和字段 |
| reason | 为什么允许低填充或缺失 |
| owner | 谁批准 |
| created_at | 何时加入 |
| expires_at | 何时复审 |
| fallback | 下游如何处理 |

## 9. 文档同步机制

新项目必须建立“文档跟着代码和数据契约走”的机制，避免原项目中的文档漂移。

### 9.1 单一事实来源

| 内容 | 单一来源 | 自动生成 |
|---|---|---|
| 表结构 | schema/migration 代码 | DDL 文档、数据字典 |
| 变量定义 | `config/variables/*.yaml` | 变量字典、中文标签、价格口径表 |
| 数据源 | `config/sources.yaml` | 数据源文档、限流说明 |
| pipeline | `config/pipeline.yaml` 和 CLI | runbook |
| 验证规则 | `config/validation.yaml` | 验收文档 |
| 变更历史 | `docs/changelog.md` 和 ADR | 发布说明 |

### 9.2 每次变更的同步要求

任何涉及数据契约的改动，必须同时包含：

1. schema 或 migration。
2. 变量注册表或数据源注册表更新。
3. 对应单元测试或数据质量测试。
4. 自动生成文档刷新。
5. changelog 条目。
6. 如果改变历史数据口径，增加 ADR 并标记是否需要 full rebuild。

### 9.3 文档漂移检测

建议提供命令：

```bash
stock-maintain docs generate
stock-maintain docs check
```

`docs check` 对比当前文档和自动生成结果；若存在差异，任务失败。这样 README、数据字典、变量清单不会再落后于代码。

## 10. 实施步骤

### Phase 0：审阅和冻结范围

| 任务 | 产出 |
|---|---|
| 你审查本文第 1 节功能清单 | 明确保留、调整、删除、新增 |
| 确定数据范围 | 历史起点、指数池、可选数据域 |
| 确定变量默认出口 | core/extended/experimental 边界 |
| 确定性能目标 | 日批目标耗时和机器资源 |

### Phase 1：项目骨架和契约

| 任务 | 产出 |
|---|---|
| 建立 Python 包结构和 CLI | `stock-maintain` 命令 |
| 建立配置系统 | sources、pipeline、variables、validation |
| 建立 schema/migration | 初始 DuckDB 表结构 |
| 建立文档生成器 | 数据字典、变量字典自动生成 |
| 建立日志/报告规范 | pipeline JSON 和 MD 摘要 |

### Phase 2：基础数据层重建

| 任务 | 产出 |
|---|---|
| 迁移或重抓交易日历、股票池、指数池 | S0/S1 基础表 |
| 重建行情、复权、daily_basic | S2/S3/S4 |
| 重建资金、两融、北向 optional | S5 |
| 重建财务和公告日映射 | S6 |
| 建立行业/概念历史机制 | S7 |
| 完成基础表质量审计 | baseline report |

### Phase 3：衍生变量核心层

| 任务 | 产出 |
|---|---|
| 建立 feature planner | dirty window 和依赖图 |
| 实现日频主干、市场行为、基本面、资金参与者、上下文、截面 core 模块 | 核心变量物理表 |
| 实现事件持有人和组合状态稳定子集 | 公司行为、治理、跨域组合和状态变量 |
| 明确排除标签/目标变量 | 本工程不维护未来收益、训练标签或回测目标 |
| 建立 `stock_features_core`、`stock_features_plus` 和 `stock_features_full` | 瘦/宽两类出口 |

### Phase 4：增量性能优化

| 任务 | 产出 |
|---|---|
| 将所有模块改为 read-context/write-window | 日批不全量扫描 |
| 优化财务 ASOF 映射 | 按变更范围计算 |
| 优化 pandas 递归指标 | 分股票批处理，状态缓存或最小上下文 |
| 优化 Parquet 出口 | 按日期分区和列裁剪 |
| 建立性能基准 | 与原项目日批对比 |

### Phase 5：验证、文档和交付闭环

| 任务 | 产出 |
|---|---|
| light/full 验证稳定 | 日批和周批验收 |
| 文档自动生成和漂移检测 | docs check 通过 |
| 样本 Excel 和抽样复核 | 人工审查材料 |
| Agent Skill 薄封装 | 状态、计划、更新、修复 |
| 迁移指南 | 如何从老项目切换 |

## 11. Phase 0 已确认与待展开项

### 11.1 已确认

1. 原项目功能清单中的数据域全部保留，新项目以丰富、详实、可维护为目标。
2. 基础变量、核心衍生变量和扩展衍生变量都需要建设，通过模块表、统一视图和变量注册表进行映射连接。
3. 标签/目标变量不纳入本工程。
4. 最近 10 个交易日的历史修复可以默认触发；超过 10 个交易日的远期源数据修复或衍生变量刷新需要显式确认，基础库初建阶段除外。
5. 本工程专注股票数据维护，不负责量化选股、回测训练、策略标签和模型目标。

### 11.2 待展开

1. 财务明细设计需要单独展开，覆盖分红、股东、股本结构、主营构成、业绩预告/快报、审计意见、商誉和减值等细分数据。
2. 概念板块设计需要单独展开，覆盖概念定义、股票-概念映射历史、概念成分变化、概念行情、概念资金流和概念热度。
3. 衍生变量设计已经抛弃旧 A-J 框架，后续按领域驱动框架落地注册表、刷新机制、依赖关系和验证规则。

## 12. Phase 1 前置文档状态

Phase 1 前置文档已补充：

1. `docs/data_contract.md`：基础表、财务明细、概念板块、数据源、主键约束和 Tushare 可获取性基线。
2. `docs/variable_registry_design.md`：基础变量与领域驱动衍生变量注册表设计、命名规范、变量分层、刷新窗口和验证规则。
3. `docs/tushare_api_feasibility_20260527.md`：使用老项目 Tushare token 做小样本 API 实证验证，确认 A 股全市场、主要指数、指数成分、申万行业、概念、财务详细报表和财务增强接口的可引入性。

进入 Phase 1 实现前，下一步应继续细化并冻结 P0/P1 表结构与变量注册表第一版。
