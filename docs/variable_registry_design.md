# 变量注册表与变量体系设计

生成日期：2026-05-30  
项目定位：股票数据维护工程  
设计目标：以统一注册表维护基础变量和衍生变量，保证字段命名、口径、依赖、刷新窗口、质量规则和文档同步一致。

## 1. 设计结论

1. 新项目同时建设基础变量、核心衍生变量和扩展衍生变量。
2. 本工程不建设未来收益、训练标签、回测目标或策略信号收益归因。
3. 衍生变量体系不再沿用原项目 A-J 字母框架，改为领域驱动模块体系。
4. 注册表是 DDL、中文标签、数据字典、验证规则、刷新窗口和文档生成的单一事实来源。
5. 所有变量必须能追踪来源、依赖、价格口径、可得时点和缺失策略。

## 2. 注册表字段

每个变量必须记录以下元数据。

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 标准字段名，英文 snake_case |
| `label_zh` | 是 | 中文名 |
| `table` | 是 | 所属物理表或视图 |
| `module` | 是 | 领域模块，如 `price_technical`、`financial_quality` |
| `category` | 是 | 子类，如 `moving_average`、`cashflow_quality` |
| `tier` | 是 | `p0`、`core`、`extended`、`experimental` |
| `dtype` | 是 | DuckDB 类型 |
| `unit` | 是 | 单位，如 `yuan`、`percent`、`shares`、`ratio` |
| `frequency` | 是 | `daily`、`quarterly`、`event`、`snapshot` |
| `grain` | 是 | 主键粒度，如 `(ts_code, trade_date)` |
| `source_type` | 是 | `tushare`、`derived`、`local_aggregate`、`manual_config` |
| `source_api` | 否 | Tushare API 名称 |
| `source_field` | 否 | 源字段名 |
| `dependencies` | 否 | 依赖变量或表字段 |
| `formula_ref` | 否 | 公式实现引用 |
| `params` | 否 | 窗口、阈值、基准指数、截面口径 |
| `price_basis` | 是 | `raw`、`hfq`、`qfq`、`financial_asof`、`not_price` |
| `point_in_time` | 是 | 是否严格按可得时点 |
| `effective_date_rule` | 否 | 低频映射规则 |
| `min_history` | 否 | 计算所需最小历史长度 |
| `read_window` | 否 | 日批读取上下文窗口 |
| `write_window` | 否 | 日批写入窗口 |
| `missing_policy` | 是 | 缺失处理策略 |
| `validation` | 是 | 非空率、常量、范围、分布等规则 |
| `doc_note` | 否 | 文档说明 |

## 3. 命名规范

### 3.1 基础变量

基础变量优先使用 Tushare 常用字段名或行业通用字段名，但业务字段名必须稳定可读。

| 原始字段 | 标准变量名 | 说明 |
|---|---|---|
| `vol` | `volume` | 成交量 |
| `turnover_rate_f` | `turnover_rate_free` | 自由流通换手率 |
| `f_ann_date` | `first_ann_date` | 首次公告日或实际公告日 |
| `n_income_attr_p` | `net_profit_attr_parent` | 归母净利润 |
| `n_cashflow_act` | `cf_from_operating` | 经营活动现金流净额 |

### 3.2 衍生变量

| 类型 | 命名规则 | 示例 |
|---|---|---|
| 单窗口指标 | `{indicator}_{window}` | `sma_20`、`hv_60` |
| 多参数指标 | `{indicator}_{p1}_{p2}_{p3}` | `macd_hist_12_26_9` |
| 相对变量 | `{name}_rel_{benchmark}` | `ret_20_rel_hs300` |
| 截面排名 | `{name}_rank_all`、`{name}_pct_sector` | `ret_20_rank_all` |
| 标准化 | `{name}_z_all`、`{name}_z_sector` | `pb_z_sector` |
| asof 财务 | `{name}_asof` | `roe_asof` |
| TTM 财务 | `{name}_ttm` | `net_profit_ttm` |
| 单季财务 | `{name}_q` | `revenue_q` |
| 同比/环比 | `{name}_yoy`、`{name}_qoq` | `revenue_yoy_asof` |
| 信号 | `{name}_flag` 或 `{name}_sig` | `limit_up_flag` |

## 4. 变量分层

| 层 | 名称 | 说明 | 默认维护 |
|---|---|---|---|
| Base | 基础变量 | 源字段和可复现基础字段 | 是 |
| Daily Spine | 日频主干 | 交易状态、股票状态、复权价、基础收益、连接键 | 是 |
| Market Behavior | 市场行为 | 价格技术、成交流动性、收益动量、波动风险、交易约束 | 是 |
| Fundamentals | 基本面 | 估值规模、财务时点、财务质量、财务趋势 | 是 |
| Events and Ownership | 事件与持有人 | 公司行为、披露、分红、质押、股东结构 | 分批 |
| Participants | 资金参与者 | 主力资金、大小单、两融、北向、龙虎榜、机构席位 | 是 |
| Context | 上下文 | 行业、概念、指数、市场宽度、风格环境 | 是 |
| Cross Section | 截面变换 | 排名、分位、标准化、中性化、风格暴露 | 是 |
| Composite State | 组合状态 | 跨域组合、共振、风险状态、市场状态 | 分批 |
| Experimental | 实验扩展 | 尚未稳定验证的研究变量 | 可选 |

## 5. 基础变量注册范围

基础变量沿用 Phase 2 的 445 个注册变量，并按以下数据域维护：

| 数据域 | 代表表 | 关键变量方向 |
|---|---|---|
| 证券主数据 | `stock_basic_info`、`stock_status_history`、`stock_company_info` | 股票身份、上市状态、市场板块、公司属性 |
| 交易日历 | `trade_calendar` | 交易日、前后交易日、月末/季末交易日 |
| 行情和复权 | `stock_daily`、`stock_adj_factor`、`stock_limit_price` | OHLCV、复权因子、涨跌停价格 |
| 日度基础指标 | `stock_daily_basic` | 换手、量比、PE/PB/PS、股息率、股本、市值 |
| 资金交易行为 | `stock_moneyflow_daily`、`margin_detail`、`northbound_*`、`top_list_*` | 资金流、两融、北向、龙虎榜 |
| 财务报表和指标 | `financial_income_raw`、`financial_balance_raw`、`financial_cashflow_raw`、`financial_indicator_raw` | 三大报表、财务指标、公告可得日 |
| 财务事件 | `financial_dividend_raw`、`financial_event_raw`、`pledge_stat` | 分红、质押、预告、快报、审计、股东事件 |
| 行业概念指数 | `sw_industry_*`、`concept_*`、`index_*` | 行业、概念、指数成分、指数行情 |
| 元数据审计 | `metadata_*`、`audit_*` | 血缘、任务状态、质量状态 |

## 6. 衍生变量领域模块

后续注册表、schema、计算代码和质量报告统一使用以下领域模块名，不再使用 A-J 旧模块名。

| 模块 | 物理表建议 | 主题 | 优先级 |
|---|---|---|---|
| `daily_spine` | `derived_daily_spine` | 交易状态、股票状态、复权价、基础收益、连接键 | p0 |
| `price_technical` | `derived_price_technical` | 均线、趋势、摆动、通道、价格位置 | core |
| `volume_liquidity` | `derived_volume_liquidity` | 成交量、成交额、换手、VWAP、OBV、Amihud、交易稀疏 | core |
| `return_momentum` | `derived_return_momentum` | 多周期收益、相对收益、动量质量、突破、反转 | core |
| `volatility_risk` | `derived_volatility_risk` | 历史波动、OHLC 波动、回撤、尾部风险、Beta、特质风险 | core |
| `trading_constraint` | `derived_trading_constraint` | 涨跌停、停牌、缺口、影线、振幅、可交易性 | core |
| `valuation_size` | `derived_valuation_size` | 估值分位、市值规模、股本结构、股息率、估值成长组合 | core |
| `financial_asof` | `derived_financial_asof` | 最新可得报告、TTM、单季、公告滞后、修订状态 | p0/core |
| `financial_quality` | `derived_financial_quality` | 盈利能力、现金流质量、应计、资产质量、负债质量 | core |
| `financial_growth` | `derived_financial_growth` | 成长、环比、趋势、营运效率、偿债、杜邦、综合评分 | core |
| `corporate_action` | `derived_corporate_action` | 分红送转、披露计划、预告快报、审计、主营构成 | extended |
| `ownership_governance` | `derived_ownership_governance` | 质押、股东户数、十大股东、股权集中度、治理风险代理 | extended |
| `capital_flow` | `derived_capital_flow` | 主力资金、大小单、两融、北向、龙虎榜、机构席位 | core |
| `sector_concept_context` | `derived_sector_concept_context` | 行业暴露、概念暴露、行业/概念表现、热度、排名 | core |
| `index_market_context` | `derived_index_market_context` | 指数成分、指数权重、市场宽度、风格环境、风险偏好 | core |
| `cross_sectional` | `derived_cross_sectional` | 排名、分位、z-score、中性残差、风格暴露 | core |
| `composite_state` | `derived_composite_state` | 量价确认、资金价格、估值质量、风险状态、共振计数 | extended |

## 7. 模块变量范围

### 7.1 日频主干

`derived_daily_spine` 是全部日频变量的共同地基。

| 子类 | 变量示例 |
|---|---|
| 股票状态 | `is_active_on_date`、`is_listed_on_date`、`is_delisted_on_date`、`list_age_days` |
| 市场板块 | `exchange_board`、`market_board`、`is_star`、`is_chinext`、`is_bse` |
| 复权价格 | `open_hfq`、`high_hfq`、`low_hfq`、`close_hfq`、`pre_close_hfq` |
| 基础收益 | `ret_1`、`log_ret_1`、`overnight_ret`、`intraday_ret` |
| 基础波幅 | `true_range`、`true_range_ratio`、`typical_price` |
| 交易状态 | `is_trading`、`suspend_flag`、`resume_flag`、`zero_volume_flag` |
| 涨跌停基础 | `limit_up_flag`、`limit_down_flag`、`one_price_limit_flag` |

### 7.2 市场行为变量

| 模块 | 变量方向 |
|---|---|
| `price_technical` | `sma_*`、`ema_*`、`macd_*`、`rsi_*`、`kdj_*`、`wr_*`、`cci_*`、`adx_*`、`boll_*`、`donch_*`、`price_pos_*` |
| `volume_liquidity` | `volume_ma_*`、`amount_ma_*`、`turnover_ma_*`、`obv`、`pvt`、`vwap_*`、`mfi_*`、`cmf_*`、`amihud_*` |
| `return_momentum` | `ret_*`、`log_ret_*`、`excess_ret_*`、`roc_*`、`momentum_*`、`break_high_*`、`new_high_days_*` |
| `volatility_risk` | `hv_*`、`ewma_vol_*`、`parkinson_vol_*`、`max_drawdown_*`、`var95_*`、`beta_*`、`idio_vol_*` |
| `trading_constraint` | `limit_up_days_*`、`consecutive_limit_up_days`、`gap_*`、`upper_shadow_ratio`、`body_ratio`、`tradable_amount_flag` |

### 7.3 基本面变量

| 模块 | 变量方向 |
|---|---|
| `valuation_size` | `earnings_yield`、`book_to_price`、`pe_ttm_pct_*`、`pb_pct_*`、`log_total_mv`、`free_float_mv`、`dividend_yield_ttm` |
| `financial_asof` | `latest_report_end_date`、`latest_financial_effective_date`、`report_lag_days`、`revenue_ttm`、`net_profit_attr_parent_ttm`、`revenue_q` |
| `financial_quality` | `roe_asof`、`roa_asof`、`ocf_to_net_profit`、`accruals_ratio`、`goodwill_to_assets`、`net_debt_to_equity` |
| `financial_growth` | `revenue_yoy_asof`、`netprofit_yoy_asof`、`q_revenue_yoy_asof`、`roe_trend_8q`、`dupont_roe`、`piotroski_f_score` |

### 7.4 事件、持有人和资金参与者

| 模块 | 变量方向 |
|---|---|
| `corporate_action` | `cash_dividend_per_share`、`days_since_ex_date`、`forecast_type_code`、`express_net_profit_yoy`、`audit_opinion_code`、`mainbz_top1_revenue_ratio` |
| `ownership_governance` | `pledge_ratio_asof`、`pledge_ratio_chg`、`holder_num_asof`、`holder_num_chg`、`top10_holder_ratio` |
| `capital_flow` | `main_net_inflow_rate`、`main_flow_ma_*`、`super_large_net_ratio`、`margin_balance_chg_*`、`north_hold_chg_*`、`top_inst_net_buy` |

### 7.5 上下文、截面和组合状态

| 模块 | 变量方向 |
|---|---|
| `sector_concept_context` | `sw_l1_code`、`sector_ret_*`、`sector_ret_rank_*`、`concept_count`、`concept_hot_score` |
| `index_market_context` | `is_hs300_member`、`hs300_weight`、`ret_20_rel_hs300`、`market_up_ratio`、`market_limit_up_count`、`risk_appetite_proxy` |
| `cross_sectional` | `{base_var}_rank_all`、`{base_var}_pct_sector`、`{base_var}_z_all`、`{base_var}_resid_size_sector`、`style_exposure_*` |
| `composite_state` | `volume_price_confirm_20`、`flow_price_corr_20`、`value_quality_score`、`ret_to_risk_60`、`bull_signal_count_10` |

## 8. 财务 point-in-time 规则

1. `effective_date = coalesce(first_ann_date, ann_date)`。
2. 若 `first_ann_date` 和 `ann_date` 都缺失，不得使用 `end_date` 映射到日频。
3. 多版本披露必须保留版本历史，日频 asof 取当日可得的最新版本。
4. 财务变量必须区分 `_ttm`、`_q`、`_yoy`、`_qoq`、`_asof`。
5. 财务缺失策略为 `financial_not_disclosed`，不得用未来报告回填。

## 9. 视图和变量出口

| 出口 | 内容 | 用途 |
|---|---|---|
| `stock_base_daily` | 基础日频变量、复权价格、估值、市值、行业/概念映射 | 数据维护和通用查询 |
| `stock_features_core` | 日频主干 + core 衍生变量 | 默认下游出口 |
| `stock_features_plus` | core + 审核通过的事件、治理、组合变量 | 更丰富分析出口 |
| `stock_features_full` | core + extended + experimental | 研究和人工审查 |
| `stock_financial_asof_daily` | 财务 point-in-time 日频映射 | 财务变量复核 |
| `feature_module_coverage` | 模块覆盖、key 对齐、非空率 | 审计 |

所有出口都必须能通过 `(ts_code, trade_date)` 连接。

## 10. 刷新窗口规则

| 变量类型 | 默认 read window | 默认 write window |
|---|---:|---:|
| 日频主干 | 20 交易日 | 最近 10 交易日 |
| 价格、成交、收益、约束、资金 | 最大指标窗口 + 20 | 最近 10 交易日 |
| 波动风险、组合状态 | 最大指标窗口 + 60 | 最近 10 交易日 |
| 财务时点、质量、趋势 | 受影响报告期至今，日批限制 260 交易日 | 最近 10 交易日，财务刷新可扩大 |
| 公司行为、持有人治理 | 受影响事件 effective_date 至今 | 最近 10 交易日，事件修复可扩大 |
| 行业、概念、指数、市场 | 成分变化窗口 + 指标窗口 | 最近 10 交易日 |
| 截面变换 | 依赖模块写入窗口 | 最近 10 交易日 |

超过 10 个交易日的远期历史刷新必须显式确认，基础库初建阶段除外。

## 11. 验证规则

| 规则 | 说明 |
|---|---|
| `not_all_null` | 非白名单变量不得整列空 |
| `min_non_null_rate` | 按变量预期设置最低非空率 |
| `constant_allowed` | signal、排名、组合变量默认不允许全常量 |
| `range_check` | RSI、分位、比例、flag 等合法范围 |
| `key_alignment` | 模块表 key 与 `stock_daily` 对齐 |
| `point_in_time_check` | 财务、行业、概念、事件不得用未来可得数据 |
| `cross_section_sample_check` | 截面变量记录样本数、行业覆盖和 winsorize 参数 |
| `distribution_drift` | 与稳定版本分布对比 |

## 12. 缺失策略枚举

| 策略 | 含义 |
|---|---|
| `required` | 必须存在，缺失即失败 |
| `initial_window_null` | 初始窗口不足导致缺失，允许 |
| `source_optional` | 源端可选域，如北向、龙虎榜 |
| `event_sparse` | 事件稀疏变量，如分红、龙虎榜 |
| `financial_not_disclosed` | 财务尚未公告 |
| `suspended_or_not_trading` | 停牌或无交易 |
| `whitelisted_with_expiry` | 临时白名单，需复审 |

## 13. 注册表示例

```yaml
- name: rsi_14
  label_zh: 14日相对强弱指标
  table: derived_price_technical
  module: price_technical
  category: oscillator
  tier: core
  dtype: double
  unit: ratio
  frequency: daily
  grain: [ts_code, trade_date]
  source_type: derived
  dependencies: [derived_daily_spine.close_hfq]
  formula_ref: indicators.rsi
  params: {window: 14}
  price_basis: hfq
  point_in_time: true
  min_history: 14
  read_window: 80
  write_window: 10
  missing_policy: initial_window_null
  validation:
    min_non_null_rate: 0.95
    constant_allowed: false
    range: [0, 100]

- name: net_profit_attr_parent_ttm
  label_zh: TTM归母净利润
  table: derived_financial_asof
  module: financial_asof
  category: ttm
  tier: core
  dtype: double
  unit: yuan
  frequency: daily
  grain: [ts_code, trade_date]
  source_type: derived
  dependencies: [financial_income_raw.net_profit_attr_parent, financial_income_raw.effective_date]
  formula_ref: financial.ttm_asof
  price_basis: financial_asof
  point_in_time: true
  effective_date_rule: first_non_null(first_ann_date, ann_date)
  missing_policy: financial_not_disclosed
  validation:
    constant_allowed: false
```

## 14. Phase 3 交付判定

进入实现前，变量注册表设计需要完成：

1. P0 基础变量清单冻结。
2. 领域驱动衍生模块冻结。
3. core/extended/experimental 分级规则冻结。
4. Tushare 来源和字段映射完成第一版。
5. 财务明细、公司事件、持有人治理、行业概念和资金变量进入注册表。
6. 验证规则和缺失策略枚举可支撑自动生成数据字典。

