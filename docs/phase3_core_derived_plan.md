# Phase 3：衍生变量核心层重建设计

生成日期：2026-05-30

## 1. 重建原则

Phase 3 不再沿用原项目的 A-J 字母模块，也不再在旧框架上追加模块。新工程采用领域驱动的衍生变量体系：模块名直接表达数据来源、分析对象和维护责任，后续表名、注册表、计算代码、审计报告和文档都按这个体系组织。

本工程仍然只维护股票数据和变量数据，不建设未来收益、训练标签、回测目标、策略买卖信号或模型训练流程。

重建原则：

1. 从现有基础变量出发设计衍生变量，而不是从旧项目模块出发。
2. 日频变量统一落到 `(ts_code, trade_date)`，低频财务和事件保留原始粒度，并通过 point-in-time 映射进入日频视图。
3. 技术、收益、波动类变量默认使用后复权口径；估值、市值、股本、成交额、资金流使用源口径。
4. 每个变量必须进入注册表，记录口径、依赖、公式、窗口、缺失策略、质量规则和可用时点。
5. 变量先分为 `core`、`extended`、`experimental`，默认出口只包含 `core` 和审核通过的 `extended`。
6. 日常刷新默认只写最近 10 个交易日，超过 10 个交易日的历史重算需要显式确认。

## 2. 可用基础数据

Phase 3 可依赖 Phase 2 已建设的数据域：

| 基础域 | 主要表 | 可支撑的衍生方向 |
|---|---|---|
| 交易日历和证券主数据 | `trade_calendar`、`stock_basic_info`、`stock_status_history`、`stock_company_info` | 交易日主干、上市年龄、市场板块、ST、退市状态、公司属性 |
| 行情和复权 | `stock_daily`、`stock_adj_factor`、`stock_limit_price` | 复权价、收益、技术指标、波动、涨跌停、K 线结构 |
| 日度基础指标 | `stock_daily_basic` | 换手、量比、估值、市值、股本、股息率、规模风格 |
| 资金交易行为 | `stock_moneyflow_daily`、`margin_detail`、`northbound_daily`、`northbound_holding`、`top_list_daily`、`top_inst_detail` | 主力资金、大小单、两融、北向、龙虎榜、机构席位 |
| 财务报表和指标 | `financial_income_raw`、`financial_balance_raw`、`financial_cashflow_raw`、`financial_indicator_raw`、`financial_disclosure_schedule` | 财务 asof、盈利质量、成长、偿债、营运、杜邦、现金流质量 |
| 财务和公司事件 | `financial_dividend_raw`、`pledge_stat`、`financial_event_raw` | 分红、质押、业绩预告/快报、审计、主营构成、股东事件 |
| 指数、行业、概念 | `index_basic_info`、`index_daily`、`index_weight`、`sw_industry_classify`、`sw_industry_member`、`concept_basic`、`concept_member` | 指数成分、行业/概念暴露、市场宽度、相对收益、截面排名 |

变量可用性分为三类：

| 类型 | 含义 | 处理方式 |
|---|---|---|
| `available_now` | 当前基础表可直接计算 | 进入 `core` 或 `extended` |
| `requires_structured_split` | 数据在 `financial_event_raw` 或 JSON 中，需要先拆表 | 先设计结构表和变量，分批实现 |
| `reserved_source_extension` | 当前基础库未稳定维护，需要后续新增源 | 只保留设计，不进入验收 |

## 3. 新模块体系

新体系按维护责任分为 17 个模块。表名不使用字母序号，而使用领域名。

| 模块 | 物理表建议 | 主题 | 默认优先级 |
|---|---|---|---|
| 日频主干 | `derived_daily_spine` | 交易状态、股票状态、复权价、基础收益、基础连接键 | p0 |
| 价格技术 | `derived_price_technical` | 均线、趋势、摆动、通道、价格位置 | core |
| 成交流动性 | `derived_volume_liquidity` | 成交量、成交额、换手、VWAP、OBV、Amihud、交易稀疏 | core |
| 收益动量 | `derived_return_momentum` | 多周期收益、相对收益、动量质量、突破、反转 | core |
| 波动风险 | `derived_volatility_risk` | 历史波动、OHLC 波动、回撤、尾部风险、Beta、特质风险 | core |
| 交易约束 | `derived_trading_constraint` | 涨跌停、停牌、缺口、影线、振幅、可交易性 | core |
| 估值规模 | `derived_valuation_size` | 估值分位、市值规模、股本结构、股息率、估值成长组合 | core |
| 财务时点 | `derived_financial_asof` | 最新可得报告、TTM、单季、公告滞后、修订状态 | p0/core |
| 财务质量 | `derived_financial_quality` | 盈利能力、现金流质量、应计、资产质量、负债质量 | core |
| 财务趋势 | `derived_financial_growth` | 成长、环比、趋势、营运效率、偿债、杜邦、综合评分 | core |
| 公司行为 | `derived_corporate_action` | 分红送转、披露计划、预告快报、审计、主营构成 | extended |
| 持有人治理 | `derived_ownership_governance` | 质押、股东户数、十大股东、股权集中度、治理风险代理 | extended |
| 资金参与者 | `derived_capital_flow` | 主力资金、大小单、两融、北向、龙虎榜、机构席位 | core |
| 行业概念上下文 | `derived_sector_concept_context` | 行业暴露、概念暴露、行业/概念表现、热度、排名 | core |
| 指数市场上下文 | `derived_index_market_context` | 指数成分、指数权重、市场宽度、风格环境、风险偏好 | core |
| 截面变换 | `derived_cross_sectional` | 全市场/行业内排名、分位、z-score、中性残差、风格暴露 | core |
| 组合状态 | `derived_composite_state` | 量价确认、资金价格、估值质量、风险状态、共振计数 | extended |

统一出口：

| 视图 | 内容 |
|---|---|
| `stock_features_core` | 日频主干 + core 模块 |
| `stock_features_plus` | core + 审核通过的事件、治理、组合状态变量 |
| `stock_features_full` | core + extended + experimental，默认不供日常下游使用 |
| `stock_financial_asof_daily` | 财务 point-in-time 日频映射复核 |
| `feature_module_coverage` | 模块覆盖、key 对齐、非空率、刷新时间 |

## 4. 日频主干

日频主干是所有日频衍生变量的连接地基，必须优先实现。

| 子类 | core 变量 |
|---|---|
| 连接键 | `ts_code`、`trade_date`、`cal_date_index`、`trade_day_seq` |
| 股票状态 | `is_active_on_date`、`is_listed_on_date`、`is_delisted_on_date`、`list_age_days`、`delist_countdown_days` |
| 市场板块 | `exchange_board`、`market_board`、`is_sse_main`、`is_star`、`is_szse_main`、`is_chinext`、`is_bse` |
| ST 和名称状态 | `is_st`、`is_name_changed_recently` |
| 复权价格 | `open_hfq`、`high_hfq`、`low_hfq`、`close_hfq`、`pre_close_hfq` |
| 展示口径 | `open_qfq_current`、`high_qfq_current`、`low_qfq_current`、`close_qfq_current` |
| 基础收益 | `ret_1`、`log_ret_1`、`overnight_ret`、`intraday_ret` |
| 基础波幅 | `true_range`、`true_range_ratio`、`typical_price`、`median_price` |
| 交易状态 | `is_trading`、`suspend_flag`、`resume_flag`、`zero_volume_flag` |
| 涨跌停基础 | `limit_up_flag`、`limit_down_flag`、`one_price_limit_flag`、`dist_to_up_limit`、`dist_to_down_limit` |

## 5. 价格技术

价格技术模块维护传统技术分析中稳定、可解释、可审计的价格类变量。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 均线 | `sma_5/10/20/60/120/250`、`ema_12/26` | `wma_*`、`hma_*`、`tema_*` |
| 均线结构 | `ma_cross_5_20_up_sig`、`ma_cross_5_20_down_sig`、`ma_bull_align`、`ma_bear_align`、`ma_distance_20` | 交叉密度、均线带宽矩阵 |
| 趋势斜率 | `sma_slope_20`、`sma_slope_60`、`price_slope_20`、`trend_r2_60` | 多周期线性趋势 |
| MACD/PPO/TRIX | `macd_dif_12_26_9`、`macd_dea_12_26_9`、`macd_hist_12_26_9`、`ppo_12_26` | 多参数 MACD、TRIX |
| 摆动指标 | `rsi_6/14/24`、`kdj_k_9_3_3`、`kdj_d_9_3_3`、`kdj_j_9_3_3`、`wr_14`、`cci_20` | StochRSI、多周期 CCI/WR |
| 趋势强度 | `adx_14`、`plus_di_14`、`minus_di_14` | Vortex、Aroon |
| 通道 | `boll_mid_20_2`、`boll_upper_20_2`、`boll_lower_20_2`、`boll_width_20_2`、`donch_high_20`、`donch_low_20` | Keltner、Ichimoku |
| 价格位置 | `hhv_20/60/250`、`llv_20/60/250`、`price_pos_20/60/250` | 52 周位置、历史分位 |

## 6. 成交流动性

该模块使用原始成交量、成交额、换手率和自由流通换手率。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 成交量趋势 | `volume_ma_5/20/60`、`volume_std_20`、`volume_zscore_20` | 多周期成交量斜率 |
| 成交额趋势 | `amount_ma_5/20/60`、`amount_zscore_20`、`amount_stability_20` | 成交额分位 |
| 换手结构 | `turnover_ma_5/20/60`、`turnover_free_ma_20`、`turnover_accum_20` | 换手半衰期 |
| 量能异常 | `volume_surge_20_2_sig`、`volume_shrink_20_05_sig`、`amount_surge_20_2_sig` | 多阈值异常 |
| 价量指标 | `obv`、`obv_ma_20`、`pvt`、`vwap_20`、`vwap_deviation_20` | ADL、ADOSC、EMV |
| 成交压力 | `mfi_14`、`cmf_20`、`force_index_13` | 多周期 MFI/CMF |
| 流动性 | `amihud_20`、`amihud_60`、`turnover_to_mv_20`、`amount_to_circ_mv_20` | 冲击成本 |
| 交易稀疏 | `zero_volume_days_20`、`low_amount_days_20`、`low_turnover_days_20` | 北交所、退市股票复核 |

## 7. 收益动量

收益动量模块只使用历史可得收益，不产生未来收益或标签。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 多周期收益 | `ret_5/20/60/120/250`、`log_ret_5/20/60` | `ret_2/3/10/30/90` |
| 相对收益 | `excess_ret_20_hs300`、`excess_ret_60_hs300`、`excess_ret_20_sector` | 多基准相对收益 |
| 动量强度 | `roc_20/60`、`momentum_strength_60`、`momentum_hit_rate_60` | 斜率动量、残差动量 |
| 动量质量 | `momentum_consistency_60`、`momentum_decay_120`、`up_day_ratio_20` | 收益路径平滑度 |
| 突破 | `break_high_20_sig`、`break_high_60_sig`、`break_low_20_sig` | 放量突破确认 |
| 新高新低 | `new_high_days_120`、`new_low_days_120`、`dist_to_250d_high` | 全历史新高状态 |
| 反转 | `short_reversal_5`、`medium_reversal_20`、`ret_reversal_count_60` | 跳空反转、超跌反弹 |
| 连续涨跌 | `consecutive_up_days`、`consecutive_down_days`、`gain_loss_ratio_20` | 连续创新高/新低 |

## 8. 波动风险

波动风险模块维护收益分布、波动期限结构、回撤、基准风险和尾部风险。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 历史波动 | `hv_20/60/120/250`、`ewma_vol_60` | `hv_5/10/30` |
| OHLC 波动 | `parkinson_vol_20`、`garman_klass_vol_20`、`atr_14`、`natr_14` | Rogers-Satchell 波动 |
| 下行风险 | `dsv_20/60/120`、`downside_hit_rate_60` | 半方差期限结构 |
| 回撤 | `max_drawdown_60/120/250`、`drawdown_current`、`drawdown_days` | 回撤修复天数 |
| 分布形态 | `ret_skew_60`、`ret_kurt_60`、`ret_iqr_60` | 尾部偏度稳定性 |
| VaR/CVaR | `var95_60`、`cvar95_60`、`var99_120` | 参数法和历史法并存 |
| 基准风险 | `beta_60_hs300`、`beta_120_hs300`、`alpha_60_hs300`、`tracking_error_60_hs300` | 中证500、中证1000、创业板指 |
| 特质风险 | `idio_vol_60_hs300`、`corr_hs300_60` | 行业残差波动 |

## 9. 交易约束

交易约束模块把 A 股涨跌停、停牌、缺口、影线、振幅和可交易性作为独立风险域维护。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 涨跌停滚动 | `limit_up_days_5/20`、`limit_down_days_5/20`、`consecutive_limit_up_days`、`consecutive_limit_down_days` | 开板、炸板需更细行情时暂缓 |
| 停牌和恢复 | `suspend_days_20`、`resume_days_since` | 长停牌风险 |
| 缺口 | `gap_up_flag`、`gap_down_flag`、`gap_size`、`gap_fill_days_20` | 多周期缺口回补 |
| K 线结构 | `upper_shadow_ratio`、`lower_shadow_ratio`、`body_ratio`、`doji_flag`、`long_upper_shadow_flag`、`long_lower_shadow_flag` | 组合形态 |
| 振幅 | `intraday_range_ratio`、`amplitude_ma_20`、`amplitude_zscore_20` | NR7、宽幅震荡 |
| 可交易性 | `tradable_amount_flag`、`low_liquidity_flag`、`st_or_recent_list_flag` | 只作为数据维护维度 |

## 10. 估值规模

估值规模模块连接 `stock_daily_basic`、财务 asof 和分红数据。估值、市值保留源口径，不用后复权价格重算。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 估值基础 | `pe_ttm`、`pb`、`ps_ttm`、`dv_ttm`、`earnings_yield`、`book_to_price`、`sales_to_price` | EV/EBITDA |
| 估值分位 | `pe_ttm_pct_3y/5y`、`pb_pct_3y/5y`、`ps_ttm_pct_3y/5y` | 10 年分位 |
| 行业相对估值 | `pe_ttm_rel_sector`、`pb_rel_sector`、`ps_ttm_rel_sector` | 行业中位数偏离 |
| 市值和规模 | `log_total_mv`、`log_circ_mv`、`free_float_mv`、`size_bucket` | 市值分层迁移 |
| 股本结构 | `float_share_ratio`、`free_share_ratio`、`share_change_20` | 股本变动事件 |
| 分红收益 | `dividend_yield_ttm`、`cash_dividend_ttm`、`cash_dividend_payout_ratio` | 分红稳定性 |
| 估值成长组合 | `peg_ttm`、`pb_roe_combo` | 依赖财务 asof 成长和 ROE |

## 11. 财务时点

财务时点模块是财务衍生变量的地基，负责把低频报告按可得时点映射到日频。

| 子类 | core 变量 |
|---|---|
| 最新报告 | `latest_report_end_date`、`latest_report_type`、`latest_report_comp_type` |
| 可得时点 | `latest_financial_effective_date`、`report_lag_days`、`report_staleness_days` |
| 报告版本 | `financial_revision_count`、`is_revised_report`、`update_flag_latest` |
| TTM 口径 | `revenue_ttm`、`net_profit_attr_parent_ttm`、`ocf_ttm`、`ebit_ttm`、`ebitda_ttm` |
| 单季口径 | `revenue_q`、`net_profit_attr_parent_q`、`ocf_q`、`gross_profit_q` |
| 可用性 | `financial_available_flag`、`financial_missing_reason` |

## 12. 财务质量

财务质量模块严格 point-in-time，评估企业盈利、现金流、资产和负债质量。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 盈利能力 | `roe_asof`、`roa_asof`、`gross_margin_asof`、`net_margin_asof`、`roic_asof` | 行业中性盈利能力 |
| 现金流质量 | `ocf_to_net_profit`、`ocf_to_revenue`、`free_cashflow_to_revenue`、`cash_conversion_ratio` | 多期现金流稳定性 |
| 应计和利润质量 | `accruals_ratio`、`working_capital_accruals`、`non_oper_profit_ratio` | Sloan accruals |
| 资产质量 | `goodwill_to_assets`、`inventory_to_assets`、`receivable_to_revenue`、`cash_to_assets` | 减值风险代理 |
| 负债质量 | `debt_to_assets_asof`、`net_debt_to_equity`、`interest_bearing_debt_ratio` | 有息负债口径 |
| 每股质量 | `eps_asof`、`bps_asof`、`ocfps_asof`、`fcff_ps_asof` | TTM 和单季口径 |

## 13. 财务趋势

财务趋势模块关注低频财务变量的变化方向、速度和结构。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 成长 | `revenue_yoy_asof`、`netprofit_yoy_asof`、`profit_yoy_asof`、`ocf_yoy_asof` | 3 年 CAGR |
| 单季变化 | `q_revenue_yoy_asof`、`q_netprofit_yoy_asof`、`q_profit_qoq_asof` | 单季环比修复 |
| 趋势 | `roe_trend_8q`、`margin_trend_8q`、`revenue_growth_accel_4q` | 财务动量 |
| 营运效率 | `asset_turnover_asof`、`inventory_turnover_asof`、`ar_turnover_asof` | 周转天数 |
| 偿债流动性 | `current_ratio_asof`、`quick_ratio_asof`、`cash_ratio_asof`、`ocf_to_debt_asof` | 短债覆盖 |
| 杜邦 | `dupont_roe`、`dupont_margin`、`dupont_asset_turnover`、`dupont_equity_multiplier` | 税负、利息负担 |
| 综合财务评分 | `piotroski_f_score`、`altman_z_score` | 分项必须保留 |

## 14. 公司行为

公司行为模块把分红、披露、预告、快报、审计和主营构成拆成可审计变量。`financial_event_raw` 中的数据必须先结构化再进入此模块。

| 子类 | core/extended 变量 |
|---|---|
| 分红送转 | `cash_dividend_per_share`、`stock_dividend_ratio`、`days_since_ex_date`、`cash_dividend_ttm` |
| 披露节奏 | `disclosure_delay_days`、`pre_disclosure_change_count`、`report_lag_rank_sector` |
| 业绩预告 | `forecast_type_code`、`forecast_net_profit_mid`、`forecast_net_profit_range_width` |
| 业绩快报 | `express_revenue_yoy`、`express_net_profit_yoy`、`express_roe` |
| 审计意见 | `audit_opinion_code`、`audit_fee_chg`、`non_standard_audit_flag` |
| 主营构成 | `mainbz_top1_revenue_ratio`、`mainbz_segment_count`、`mainbz_gross_margin` |

## 15. 持有人治理

持有人治理模块关注质押、股东结构和治理风险代理。

| 子类 | core/extended 变量 |
|---|---|
| 质押 | `pledge_ratio_asof`、`pledge_ratio_chg`、`pledge_count_asof`、`high_pledge_flag` |
| 股东户数 | `holder_num_asof`、`holder_num_chg`、`holder_num_chg_rate` |
| 股东集中度 | `top10_holder_ratio`、`top10_float_holder_ratio`、`holder_concentration_chg` |
| 解禁和回购 | `unlock_ratio_30d`、`repurchase_amount_ttm`、`repurchase_progress_rate` |

## 16. 资金参与者

资金参与者模块连接主力资金、大小单、融资融券、北向和龙虎榜。事件稀疏变量使用 `event_sparse` 缺失策略。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 主力资金 | `main_net_inflow`、`main_net_inflow_rate`、`main_flow_ma_5/20`、`main_flow_persist_5/20` | 主力流入分位 |
| 大小单结构 | `super_large_net_ratio`、`large_net_ratio`、`medium_net_ratio`、`retail_net_ratio` | 大小单背离 |
| 融资融券 | `margin_balance_chg_5/20`、`margin_buy_ratio`、`short_balance_chg_20`、`margin_short_ratio` | 多空拥挤度 |
| 北向持股 | `north_hold_ratio`、`north_hold_chg_5/20`、`north_hold_shares_chg_20` | 北向持股分位 |
| 北向市场流 | `north_money`、`north_money_ma_20`、`north_money_zscore_60` | 市场风险偏好 |
| 龙虎榜 | `top_list_net_amount`、`top_inst_net_buy`、`top_inst_buy_sell_ratio` | 机构席位持续性 |

## 17. 行业概念上下文

行业概念上下文模块描述股票所属板块及其相对表现。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 行业暴露 | `sw_l1_code`、`sw_l2_code`、`sw_l3_code`、`sector_member_flag` | 多分类体系 |
| 行业表现 | `sector_ret_5/20/60`、`sector_amount_chg_20`、`sector_turnover_20` | 行业波动和资金 |
| 行业内排名 | `sector_ret_rank_20`、`sector_turnover_rank_20`、`sector_valuation_rank` | 行业内分位 |
| 概念暴露 | `concept_count`、`concept_hot_score`、`concept_ret_top1_20` | 概念贡献拆分 |
| 概念拥挤 | `concept_overlap_count`、`concept_member_weight_proxy` | 概念重复暴露 |

## 18. 指数市场上下文

指数市场上下文模块描述股票与宽基指数、市场宽度和风格环境的关系。

| 子类 | core 变量 | extended 变量 |
|---|---|---|
| 指数成分 | `is_hs300_member`、`is_zz500_member`、`is_zz1000_member`、`hs300_weight` | 上证50、科创50、创业板指 |
| 指数相对 | `ret_20_rel_hs300`、`ret_60_rel_zz500`、`corr_hs300_60` | 多基准 |
| 市场宽度 | `market_up_ratio`、`market_limit_up_count`、`market_ret_equal_weight`、`market_amount_total` | 全市场和分板块宽度 |
| 风格环境 | `size_style_ret_20`、`value_style_ret_20`、`growth_style_ret_20` | 由截面组合本地聚合 |
| 风险偏好 | `risk_appetite_proxy`、`market_vol_regime`、`market_liquidity_regime` | 市场状态 |

## 19. 截面变换

截面变换模块是面向股票分析模型的核心工程层。它不创造未来信息，只对当日可得变量做排名、分位、标准化和中性化。

| 子类 | core 变量 |
|---|---|
| 全市场排名 | `{base_var}_rank_all`、`{base_var}_pct_all` |
| 行业内排名 | `{base_var}_rank_sector`、`{base_var}_pct_sector` |
| 标准化 | `{base_var}_z_all`、`{base_var}_z_sector` |
| 中性化残差 | `{base_var}_resid_size_sector` |
| 风格暴露 | `size_exposure`、`value_exposure`、`quality_exposure`、`momentum_exposure`、`volatility_exposure`、`liquidity_exposure` |
| 缺失状态 | `feature_missing_count_core`、`feature_available_ratio_core`、`new_stock_feature_flag` |

截面变换必须保存样本范围、行业分组口径、winsorize 参数、排名方向和缺失处理策略。

## 20. 组合状态

组合状态模块只组合已有变量，不隐藏底层公式，不做买卖建议。

| 子类 | core/extended 变量 |
|---|---|
| 量价确认 | `volume_price_confirm_20`、`volume_breakout_confirm_20`、`obv_price_divergence_20` |
| 资金价格 | `flow_price_corr_20`、`flow_confirm_up_20`、`north_flow_price_confirm_20` |
| 动量风险 | `ret_to_risk_60`、`momentum_risk_adjusted_60`、`momentum_volatility_divergence_60` |
| 估值质量 | `value_quality_score`、`low_value_high_quality_flag`、`peg_quality_score` |
| 估值资金 | `value_flow_score`、`low_value_inflow_flag`、`crowded_value_flag` |
| 行业资金 | `sector_flow_lead_20`、`sector_price_flow_divergence_20` |
| 跨周期结构 | `macd_hist_chg_5`、`sma_slope_diff_20_60`、`hv_term_20_60`、`volume_term_5_20`、`turnover_term_5_60` |
| 信号共振 | `bull_signal_count_10`、`bear_signal_count_10`、`net_signal_count_10` |
| 市场状态 | `market_regime_trend`、`market_regime_volatility`、`market_regime_liquidity` |

## 21. 财务 point-in-time 规则

1. `effective_date = coalesce(first_ann_date, ann_date)`。
2. `first_ann_date` 和 `ann_date` 都缺失时，不得用 `end_date` 映射到日频。
3. 同一 `ts_code + end_date` 多版本披露时，按 `effective_date` 保留版本历史。
4. 日频 asof 取当日可得的最新版本。
5. TTM、单季、同比、环比变量必须使用后缀区分：`_ttm`、`_q`、`_yoy`、`_qoq`、`_asof`。
6. 财务缺失策略为 `financial_not_disclosed`，不得用未来报告回填。

## 22. 注册表要求

衍生变量必须全部进入 `config/variables/derived_variables.json`。每个变量至少包含：

| 字段 | 说明 |
|---|---|
| `name` | snake_case 标准变量名 |
| `label_zh` | 中文名 |
| `table` | 目标物理表或视图 |
| `module` | 领域模块名，如 `price_technical`、`financial_quality` |
| `category` | 子类，如 `moving_average`、`cashflow_quality` |
| `tier` | `p0`、`core`、`extended`、`experimental` |
| `dependencies` | 依赖基础变量或衍生变量 |
| `formula_ref` | 公式或算子引用 |
| `params` | 窗口、阈值、基准指数、截面口径 |
| `min_history` | 最小历史长度 |
| `read_window` | 增量读取窗口 |
| `write_window` | 增量写入窗口 |
| `price_basis` | `hfq`、`raw`、`financial_asof`、`not_price` |
| `point_in_time` | 是否严格可得时点 |
| `missing_policy` | 缺失策略 |
| `validation` | 非空率、范围、常量率、分布漂移 |

## 23. 刷新和性能机制

| 模块类型 | 默认 read window | 默认 write window |
|---|---:|---:|
| 日频主干 | 20 交易日 | 最近 10 交易日 |
| 价格、成交、收益、约束、资金 | 最大窗口 + 20 | 最近 10 交易日 |
| 波动风险、组合状态 | 最大窗口 + 60 | 最近 10 交易日 |
| 财务时点、质量、趋势 | 受影响报告期至今，日批限制 260 交易日 | 最近 10 交易日，财务刷新可扩大 |
| 公司行为、持有人治理 | 受影响事件 effective_date 至今 | 最近 10 交易日，事件修复可扩大 |
| 行业、概念、指数、市场 | 成分变化窗口 + 指标窗口 | 最近 10 交易日 |
| 截面变换 | 依赖模块写入窗口 | 最近 10 交易日 |

默认依赖顺序：

```text
daily_spine
  -> price_technical / volume_liquidity / return_momentum / volatility_risk / trading_constraint
  -> valuation_size / financial_asof / financial_quality / financial_growth
  -> corporate_action / ownership_governance / capital_flow
  -> sector_concept_context / index_market_context
  -> cross_sectional
  -> composite_state
```

## 24. 质量审计

Phase 3 质量审计至少包含：

| 检查 | 说明 |
|---|---|
| key 对齐 | `(ts_code, trade_date)` 与 `stock_daily` 写入窗口对齐 |
| 重复 key | 每个模块表无重复主键 |
| 非空率 | 按变量和缺失策略计算 |
| 初始窗口豁免 | rolling 初始窗口缺失不误报 |
| 常量率 | 信号、排名和组合变量不得全常量 |
| 范围检查 | RSI、分位、比例、flag 等合法范围 |
| point-in-time | 财务和事件变量不得提前使用 |
| 截面样本 | 记录当日样本数、行业覆盖、winsorize 参数 |
| 依赖版本 | 组合状态记录依赖模块刷新时间 |
| 分布漂移 | 与上一稳定批次对比 |

## 25. 实施步骤

1. 重写 `config/variables/derived_variables.json`，使用领域模块名，不再使用旧 A-J 模块名。
2. 将 `derived_daily_spine` 等领域物理表写入 `config/schema_registry.json`。
3. 建设 Feature Planner：按领域模块、日期范围和依赖窗口生成读取和写入计划。
4. 建设计算模块：优先 DuckDB SQL，递归和复杂状态指标再使用 pandas。
5. 先实现日频主干，再实现价格、成交、收益、波动、交易约束。
6. 实现估值、财务时点、财务质量、财务趋势。
7. 实现资金参与者、行业概念上下文、指数市场上下文。
8. 实现截面变换和组合状态。
9. 生成衍生变量 Excel/Markdown 数据字典、公式说明和依赖图。
10. 生成 `reports/feature_quality_report.md` 和 Phase 3 完成确认文档。

## 26. Phase 3 验收标准

Phase 3 完成时应满足：

1. 衍生变量注册表有效，无重复变量名。
2. 变量注册表、schema、实际表字段、数据字典一致。
3. core 领域模块已落库：日频主干、价格技术、成交流动性、收益动量、波动风险、交易约束、估值规模、财务时点、财务质量、财务趋势、资金参与者、行业概念上下文、指数市场上下文、截面变换。
4. 公司行为、持有人治理、组合状态完成当前基础表可支撑的稳定子集，未实现项列入延期清单。
5. `stock_features_core` 可按 `(ts_code, trade_date)` 稳定查询。
6. 最近 10 个交易日增量刷新可运行。
7. 全量初建可按模块断点运行。
8. 财务变量通过 point-in-time 检查。
9. 截面排名和标准化变量记录样本范围、winsorize 和行业口径。
10. 生成衍生变量 Excel 数据字典和质量审计报告。

