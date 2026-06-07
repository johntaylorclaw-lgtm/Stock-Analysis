# Phase 3 截面转换模块设计与实施记录

生成日期：2026-06-04  
状态：第一阶段核心物理表和第二阶段完整视图已完成；第三阶段增量机制暂缓，待全量底表稳定后再设计。

## 1. 模块定位

`cross_sectional` 面向股票分析模型提供“当日可得事实变量”的横截面转换，不生成买卖建议，不生成未来收益标签，不生成主观评分。它只回答一个问题：某只股票在某个交易日，相对于全市场、市场板块、交易所、申万一级/二级行业处在什么位置。

本模块继承以下原则：

1. 后复权收益、动量、回撤等连续历史变量使用上游 `*_hfq` 口径。
2. 成交额、换手、市值、估值、资金流、财务 asof 变量保持事实口径，不做复权。
3. 财务变量使用 point-in-time asof 口径，不引入未来公告信息。
4. 截面转换仅做 winsorize、rank、percentile、z-score、中性化残差和透明暴露合成。
5. 暴露字段命名为 `exposure`，不命名为 `score`，不表达好坏判断。

## 2. 已完成对象

| 阶段 | 对象 | 类型 | 状态 | 实际规模 |
|---|---|---|---|---:|
| 第一阶段 | `derived_cross_sectional` | 物理表 | 已完成 | 15,295,776 行，353 列 |
| 第二阶段 | `derived_cross_sectional_full_v` | 视图 | 已完成 | 1,063 列 |
| 第三阶段 | 增量刷新机制 | 机制设计 | 暂缓 | 待后续全量底表稳定后实施 |

全量覆盖范围：

| 项目 | 结果 |
|---|---:|
| 日期范围 | 2006-01-04 至 2026-05-26 |
| 覆盖交易日 | 4,951 |
| 覆盖股票数 | 5,809 |
| 截面有效股票行数 | 15,209,864 |

审计报告：`reports/phase3_cross_sectional_audit.md`

## 3. 核心物理表结构

主键：`ts_code + trade_date`

样本与参数字段：

| 字段 | 中文名 | 逻辑 |
|---|---|---|
| `xs_universe_flag` | 是否进入截面样本 | `derived_daily_spine.is_listed_asof AND has_price AND price_valid_flag`，包含停牌但有有效价格的股票 |
| `xs_market` | 市场分组 | `derived_daily_spine.market` |
| `xs_exchange` | 交易所分组 | `derived_daily_spine.exchange` |
| `xs_sw_l1_code` | 申万一级行业 | `derived_sector_concept_context.sw_l1_code` |
| `xs_sw_l2_code` | 申万二级行业 | `derived_sector_concept_context.sw_l2_code` |
| `xs_sample_all_count` | 全市场样本数 | 当日 `xs_universe_flag=true` 的股票数 |
| `xs_sample_market_count` | 市场分组样本数 | 当日、市场分组内有效样本数 |
| `xs_sample_sw_l1_count` | 申万一级样本数 | 当日、申万一级行业内有效样本数 |
| `xs_sample_sw_l2_count` | 申万二级样本数 | 当日、申万二级行业内有效样本数 |
| `xs_core_available_count` | 核心变量可用数 | 45 个核心变量中非空且非特殊值的数量 |
| `xs_core_available_ratio` | 核心变量可用率 | `xs_core_available_count / 45` |
| `xs_missing_fields` | 缺失核心字段列表 | 缺失核心变量名用 `;` 拼接 |
| `xs_winsor_lower_pct` | 缩尾下分位 | `0.01` |
| `xs_winsor_upper_pct` | 缩尾上分位 | `0.99` |
| `xs_min_group_zscore_n` | z-score 最小分组样本数 | `20` |
| `xs_min_group_rank_n` | rank 最小分组样本数 | `5` |

## 4. 物理核心变量池

每个核心变量生成 7 个物理截面字段：

```text
{var}_rank_all_desc
{var}_pct_all_desc
{var}_z_all
{var}_rank_market_desc
{var}_pct_market_desc
{var}_rank_sw_l2_desc
{var}_pct_sw_l2_desc
```

计算口径：

| 字段模式 | 逻辑 |
|---|---|
| `_rank_all_desc` | `rank(winsor(raw) DESC) over trade_date` |
| `_pct_all_desc` | `1 - (rank - 1) / (n - 1)`，数值越大表示降序位置越靠前 |
| `_z_all` | `zscore(winsor(raw, 1%, 99%)) over trade_date` |
| `_rank_market_desc` | 市场分组内降序排名 |
| `_pct_market_desc` | 市场分组内降序分位 |
| `_rank_sw_l2_desc` | 申万二级行业内降序排名 |
| `_pct_sw_l2_desc` | 申万二级行业内降序分位 |

实际纳入物理表的 45 个核心变量：

| 模块 | 来源表 | 字段 |
|---|---|---|
| 收益动量 | `derived_return_momentum` | `ret_20_hfq`, `ret_60_hfq`, `ret_120_hfq`, `ret_250_hfq`, `momentum_60_20_hfq`, `reversal_5_hfq` |
| 成交流动性 | `derived_volume_liquidity` | `amount_ma_20`, `turnover_rate_ma_20`, `amihud_20` |
| 波动风险 | `derived_volatility_risk` | `hv_20`, `hv_60`, `atr_14_pct_hfq`, `max_drawdown_60_hfq` |
| 估值规模 | `derived_valuation_size` | `log_total_mv`, `log_free_float_mv`, `pe_ttm`, `pb`, `earnings_yield_ttm`, `book_to_price`, `dividend_yield_ttm` |
| 财务质量 | `derived_financial_quality` | `roe_asof`, `roa_asof`, `roic_asof`, `gross_margin_asof`, `netprofit_margin_asof`, `ocf_to_profit_asof`, `accrual_ratio_asof`, `debt_to_assets_asof`, `current_ratio_asof`, `assets_turn_asof` |
| 财务成长 | `derived_financial_growth` | `revenue_yoy_asof`, `netprofit_yoy_asof`, `ocf_yoy_asof`, `revenue_cagr_3y_asof`, `net_profit_cagr_3y_asof` |
| 资金流 | `derived_capital_flow` | `main_flow_sum_20`, `main_flow_to_total_mv_20`, `main_flow_persist_ratio_20`, `margin_balance_chg_20`, `north_hold_ratio_chg_20` |
| 行业概念上下文 | `derived_sector_concept_context` | `stock_excess_sw_l2_20`, `concept_count`, `concept_avg_ret_20`, `concept_hot_count_20` |
| 指数市场上下文 | `derived_index_market_context` | `stock_excess_hs300_20` |

## 5. 中性化残差字段

第一阶段物理化 10 个规模与申万二级行业中性化残差字段：

```text
z(resid({var}_z_all ~ log_free_float_mv_z_all + sw_l2_dummy))
```

字段清单：

| 字段 |
|---|
| `ret_20_hfq_resid_size_sw_l2_z` |
| `ret_60_hfq_resid_size_sw_l2_z` |
| `momentum_60_20_hfq_resid_size_sw_l2_z` |
| `hv_60_resid_size_sw_l2_z` |
| `amihud_20_resid_size_sw_l2_z` |
| `earnings_yield_ttm_resid_size_sw_l2_z` |
| `book_to_price_resid_size_sw_l2_z` |
| `roe_asof_resid_size_sw_l2_z` |
| `revenue_yoy_asof_resid_size_sw_l2_z` |
| `main_flow_to_total_mv_20_resid_size_sw_l2_z` |

边界处理：

1. 当日有效样本不足 200，或申万二级行业数量不足 10，残差置空。
2. 回归矩阵不可解时置空。
3. 残差计算按年度批处理，避免 DuckDB 宽窗口 SQL 在大表上触发内部绑定错误。

## 6. 物理风格暴露字段

暴露字段是透明等权合成，不表达评分：

| 字段 | 公式 |
|---|---|
| `size_exposure_z` | `avg_z(log_total_mv_z_all, log_free_float_mv_z_all)` |
| `value_exposure_z` | `avg_z(earnings_yield_ttm_z_all, book_to_price_z_all, dividend_yield_ttm_z_all)` |
| `momentum_exposure_z` | `avg_z(ret_20_hfq_z_all, ret_60_hfq_z_all, momentum_60_20_hfq_z_all)` |
| `reversal_exposure_z` | `avg_z(reversal_5_hfq_z_all)` |
| `volatility_exposure_z` | `avg_z(hv_20_z_all, hv_60_z_all, atr_14_pct_hfq_z_all)` |
| `liquidity_exposure_z` | `avg_z(amount_ma_20_z_all, turnover_rate_ma_20_z_all, -amihud_20_z_all)` |
| `quality_exposure_z` | `avg_z(roe_asof_z_all, roa_asof_z_all, roic_asof_z_all, ocf_to_profit_asof_z_all, -accrual_ratio_asof_z_all)` |
| `growth_exposure_z` | `avg_z(revenue_yoy_asof_z_all, netprofit_yoy_asof_z_all, revenue_cagr_3y_asof_z_all, net_profit_cagr_3y_asof_z_all)` |
| `flow_exposure_z` | `avg_z(main_flow_to_total_mv_20_z_all, main_flow_persist_ratio_20_z_all, north_hold_ratio_chg_20_z_all)` |

规则：可用成分少于一半时，对应暴露字段置空。

## 7. 完整视图结构

`derived_cross_sectional_full_v` 继承 `derived_cross_sectional.*`，并扩展两类字段：

1. 对 45 个物理核心变量补充 8 个视图字段。
2. 对 23 个视图专属变量生成 15 个截面字段。

物理核心变量的视图扩展字段：

```text
{var}_z_market
{var}_rank_sw_l1_desc
{var}_pct_sw_l1_desc
{var}_z_sw_l1
{var}_z_sw_l2
{var}_rank_exchange_desc
{var}_pct_exchange_desc
{var}_z_exchange
```

说明：物理核心变量的视图扩展基于 `{var}_z_all` 再做分组 rank/z 转换，避免视图重复连接全部源表并降低查询成本。

视图专属变量的完整字段模式：

```text
{var}_rank_all_desc
{var}_pct_all_desc
{var}_z_all
{var}_rank_market_desc
{var}_pct_market_desc
{var}_rank_sw_l2_desc
{var}_pct_sw_l2_desc
{var}_z_market
{var}_rank_sw_l1_desc
{var}_pct_sw_l1_desc
{var}_z_sw_l1
{var}_z_sw_l2
{var}_rank_exchange_desc
{var}_pct_exchange_desc
{var}_z_exchange
```

## 8. 视图专属变量池

| 模块 | 来源表 | 字段 |
|---|---|---|
| 收益动量 | `derived_return_momentum` | `ret_5_hfq`, `up_days_20`, `down_days_20` |
| 成交流动性 | `derived_volume_liquidity` | `amount_ma_60`, `volume_ratio_20`, `amount_ratio_20` |
| 波动风险 | `derived_volatility_risk` | `parkinson_vol_20`, `max_drawdown_20_hfq` |
| 估值规模 | `derived_valuation_size` | `pe_ttm_pct_5y`, `pb_pct_5y`, `ps_ttm_pct_5y`, `total_mv_pct_5y` |
| 财务质量 | `derived_financial_quality` | `operating_profit_margin_asof`, `cash_to_assets_asof`, `goodwill_to_assets_asof`, `liabilities_to_equity_asof` |
| 财务成长 | `derived_financial_growth` | `revenue_change_4report_asof`, `net_profit_change_4report_asof`, `ocf_change_4report_asof` |
| 资金流 | `derived_capital_flow` | `main_flow_sum_60`, `small_net_amount_rate` |
| 行业概念上下文 | `derived_sector_concept_context` | `stock_excess_sw_l2_60` |
| 指数市场上下文 | `derived_index_market_context` | `stock_excess_zz1000_20` |

## 9. 视图扩展暴露字段

第二阶段完整视图补充 5 个扩展暴露字段：

| 字段 | 公式 |
|---|---|
| `profitability_exposure_z` | `avg_z(roe_asof_z_all, roa_asof_z_all, roic_asof_z_all, gross_margin_asof_z_all, netprofit_margin_asof_z_all)` |
| `cashflow_quality_exposure_z` | `avg_z(ocf_to_profit_asof_z_all, -accrual_ratio_asof_z_all)` |
| `leverage_exposure_z` | `avg_z(debt_to_assets_asof_z_all, liabilities_to_equity_asof_z_all)` |
| `concept_heat_exposure_z` | `avg_z(concept_hot_count_20_z_all, concept_avg_ret_20_z_all)` |
| `index_relative_exposure_z` | `avg_z(stock_excess_hs300_20_z_all, stock_excess_zz1000_20_z_all)` |

## 10. 实现脚本

| 脚本 | 用途 |
|---|---|
| `scripts/phase3_cross_sectional_config.py` | 统一维护核心变量池、视图变量池、暴露字段和参数 |
| `scripts/register_phase3_cross_sectional.py` | 注册 schema 和变量字典 |
| `scripts/reset_phase3_cross_sectional_table.py` | 重建核心物理表结构 |
| `scripts/build_phase3_cross_sectional_core.py` | 分年度构建核心物理表 |
| `scripts/create_phase3_cross_sectional_full_view.py` | 创建完整视图 |
| `scripts/generate_phase3_cross_sectional_audit.py` | 生成审计报告 |

## 11. 审计结论

截至 2026-06-04，本模块审计通过：

1. 核心物理表字段数与注册表一致：353 列。
2. 完整视图字段数与注册表一致：1,063 列。
3. 最新交易日 `ret_20_hfq_z_all`、`log_free_float_mv_z_all`、`roe_asof_z_all`、`main_flow_to_total_mv_20_z_all` 的均值接近 0、标准差为 1。
4. 最新交易日 `ret_20_hfq_rank_all_desc` 排名范围为 1 至 5,486，无越界。
5. 缺失主要来自未上市、停牌无有效价格、财务/资金流源变量不可得、特殊值过滤和小样本分组过滤，属于预期范围。

