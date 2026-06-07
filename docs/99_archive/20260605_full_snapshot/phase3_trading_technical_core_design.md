# Phase 3 交易行情与技术分析核心模块设计

生成日期：2026-06-01

状态：核心物理表与完整视图已实现，已完成全量历史构建与质量审计。

## 1. 设计目标

交易行情与技术分析核心模块负责把日频行情、成交量、成交额、换手率、涨跌停状态和复权价格加工成可复用的事实型衍生变量。模块不做选股评分，不生成主观综合分，只维护可解释、可复现、可审计的交易事实和统计特征。

本模块采用与财务成长二阶段一致的混合结构：

1. 核心物理表：保存高频查询、日常增量必须使用的变量。
2. 完整视图：保存更宽、更完整的扩展变量，按需计算。
3. 可选物化子表：后续如果某类视图字段成为稳定高频需求，再单独物理化。

## 0.1 实施记录

截至 2026-06-01，本模块已完成以下工作：

| 项目 | 结果 |
|---|---|
| 核心物理表 | 已全量构建 `derived_daily_spine`、`derived_price_technical`、`derived_return_momentum`、`derived_volatility_risk`、`derived_volume_liquidity`、`derived_trading_constraint` |
| 完整视图 | 已创建 `derived_daily_spine_full_v`、`derived_price_technical_full_v`、`derived_return_momentum_full_v`、`derived_volatility_risk_full_v`、`derived_volume_liquidity_full_v`、`derived_trading_constraint_full_v` |
| 历史覆盖 | 2006-01-04 至 2026-05-26，6 张核心表均为 15,295,776 行、5,809 只股票 |
| 字段一致性 | 核心物理表与完整视图的实际字段数均与 `config/schema_registry.json` 一致 |
| 价格 tick 口径 | 使用 `price_tick = 0.01`、`price_tick / 2 = 0.005` 判定涨跌停；全量实证中与旧比例口径存在少量差异，详见审计报告 |
| 数据字典 | 已刷新 `outputs/variable_dictionary/global_variable_dictionary.xlsx` |
| 审计报告 | 已生成 `reports/phase3_trading_technical_audit.md` |

说明：完整视图中的 `ema_*`、`macd_*`、`kdj_*` 当前采用滚动均值近似口径，作为非核心扩展视图字段提供。若后续需要严格技术分析经典递推算法，应单独实现递推计算或物化计算逻辑，并同步修订数据字典公式。

## 0. 已确认边界

| 事项 | 结论 |
|---|---|
| 核心物理表规模 | 本文列出每张核心物理表的明确字段清单，待审阅确认 |
| KDJ/MACD/布林带 | 只放完整视图，不进入核心物理表 |
| 波动率年化交易日 | 统一使用 242 |
| 涨跌停判断 | 采用最小价格变动单位处理，不再只用固定比例容差 |
| 前复权字段 | 从核心物理表迁移到完整视图 |

## 2. 复权口径原则

复权选择必须按业务场景判断，不能简单一律使用后复权或不复权。

| 场景 | 推荐口径 | 原因 |
|---|---|---|
| 连续历史收益、动量、均线、波动率、回撤、ATR、趋势强度 | 后复权 `hfq` | 保证除权除息前后历史序列连续，适合历史统计和滚动窗口 |
| 当前价格展示、与真实盘口价比较、涨跌停价比较、开盘封板、触板、价格有效性 | 不复权 `raw` | 涨跌停价、盘口价、成交价都是交易当日真实价格，必须用 raw |
| 截面价格水平对比、当前尺度图形展示 | 前复权 `qfq_current` 或 raw | 前复权便于当前尺度展示，但依赖最新复权因子，历史回看会随最新因子变化；本阶段迁移到完整视图 |
| 成交量、成交额、换手率、量比、流动性 | 不复权 `not_price` | 成交量和换手率不是价格序列，不应复权 |
| 日内振幅、实体、上下影线等纯当日形态 | raw 和 hfq 均可，核心用 raw，连续统计用 hfq | 单日形态 raw 更贴近交易事实；跨期统计用 hfq 更连续 |
| 与财务、市值、估值交叉 | raw 或 Tushare 原始市值口径 | 财务和市值是当时披露或交易口径，不宜用后复权价格重算 |

核心规则：

1. `*_hfq` 用于历史连续统计。
2. `*_raw` 用于交易制度、涨跌停、盘口事实。
3. `*_qfq` 不进入核心物理表，只在视图中提供展示和兼容用途。
4. 所有变量必须在数据字典中声明 `price_basis`。

### 2.1 最小价格变动单位规则

涨跌停、触板、封板等制度变量使用 raw 价格，并按最小价格变动单位判断：

```text
price_tick = 0.01
```

A 股股票日常最小报价单位通常为 0.01 元。本工程第一阶段统一按 0.01 元处理；若后续扩展到基金、可转债或其他品种，再按证券类型建立 `price_tick` 映射表。

判断规则：

| 场景 | 公式 |
|---|---|
| 收盘涨停 | `close_raw >= up_limit - price_tick / 2` |
| 收盘跌停 | `close_raw <= down_limit + price_tick / 2` |
| 盘中触及涨停 | `high_raw >= up_limit - price_tick / 2` |
| 盘中触及跌停 | `low_raw <= down_limit + price_tick / 2` |
| 开盘涨停 | `open_raw >= up_limit - price_tick / 2` |
| 开盘跌停 | `open_raw <= down_limit + price_tick / 2` |
| 一字涨停 | `open/high/low/close` 均在 `up_limit ± price_tick / 2` 范围内 |
| 一字跌停 | `open/high/low/close` 均在 `down_limit ± price_tick / 2` 范围内 |

## 3. 模块结构

| 模块 | 核心物理表 | 完整视图 | 主要职责 |
|---|---|---|---|
| 日频主干 | `derived_daily_spine` | `derived_daily_spine_full_v` | 价格口径、基础收益、交易状态、质量标记 |
| 价格技术 | `derived_price_technical` | `derived_price_technical_full_v` | 均线、趋势、位置、振荡指标 |
| 收益动量 | `derived_return_momentum` | `derived_return_momentum_full_v` | 多周期收益、动量、反转、收益路径 |
| 波动风险 | `derived_volatility_risk` | `derived_volatility_risk_full_v` | 历史波动、区间波动、回撤、下行风险 |
| 成交流动性 | `derived_volume_liquidity` | `derived_volume_liquidity_full_v` | 成交量、成交额、换手、量价流动性 |
| 交易约束 | `derived_trading_constraint` | `derived_trading_constraint_full_v` | 涨跌停、停牌/缺失、封板和连续状态 |

## 4. `derived_daily_spine`

`derived_daily_spine` 已经是核心物理表，应继续作为所有行情技术变量的底座。

### 4.1 核心物理字段

保留并完善以下字段：

| 字段组 | 字段 |
|---|---|
| 主键与状态 | `ts_code`, `trade_date`, `is_trade`, `is_listed_asof`, `list_status_asof`, `days_since_list`, `market`, `exchange` |
| raw OHLCV | `open_raw`, `high_raw`, `low_raw`, `close_raw`, `pre_close_raw`, `change_raw`, `pct_chg_raw`, `volume`, `amount`, `amplitude_raw` |
| 复权因子 | `adj_factor`, `latest_adj_factor_asof`, `has_adj_factor` |
| 后复权价格 | `open_hfq`, `high_hfq`, `low_hfq`, `close_hfq`, `pre_close_hfq` |
| 基础收益 | `ret_1_raw`, `ret_1_hfq`, `log_ret_1_hfq`, `overnight_ret_hfq`, `intraday_ret_hfq`, `gap_open_hfq` |
| 日内结构 | `high_low_range_hfq`, `close_position_hfq` |
| 涨跌停 | `up_limit`, `down_limit`, `limit_up_flag`, `limit_down_flag`, `touch_limit_up_flag`, `touch_limit_down_flag`, `open_limit_up_flag`, `open_limit_down_flag`, `limit_up_gap`, `limit_down_gap` |
| 质量标记 | `has_price`, `has_limit_price`, `price_valid_flag`, `missing_reason` |

核心物理字段数量：49 个。

从当前核心物理表迁移到完整视图的字段：

```text
open_qfq, high_qfq, low_qfq, close_qfq, pre_close_qfq
```

### 4.2 完整视图扩展

`derived_daily_spine_full_v` 建议增加：

| 字段组 | 示例字段 | 口径 |
|---|---|---|
| raw 日内结构 | `body_raw`, `upper_shadow_raw`, `lower_shadow_raw`, `body_ratio_raw`, `shadow_ratio_raw` | raw |
| hfq 日内结构 | `body_hfq`, `upper_shadow_hfq`, `lower_shadow_hfq`, `true_range_hfq` | hfq |
| 前复权价格 | `open_qfq`, `high_qfq`, `low_qfq`, `close_qfq`, `pre_close_qfq` | qfq_current |
| 交易状态 | `suspended_flag`, `zero_volume_flag`, `one_price_limit_flag`, `st_stock_flag` | raw/not_price |
| 质量诊断 | `ohlc_relation_error_flag`, `adj_factor_jump_flag`, `limit_price_conflict_flag` | mixed |

## 5. `derived_price_technical`

价格技术模块关注价格趋势、均线和振荡位置。核心物理表只保留最常用窗口；完整视图展开更多窗口和指标。

### 5.1 核心物理字段

| 字段 | 中文名 | 公式/来源 | 口径 |
|---|---|---|---|
| `ma_5_hfq` | 5日后复权均价 | `avg(close_hfq, 5)` | hfq |
| `ma_10_hfq` | 10日后复权均价 | `avg(close_hfq, 10)` | hfq |
| `ma_20_hfq` | 20日后复权均价 | `avg(close_hfq, 20)` | hfq |
| `ma_60_hfq` | 60日后复权均价 | `avg(close_hfq, 60)` | hfq |
| `ma_120_hfq` | 120日后复权均价 | `avg(close_hfq, 120)` | hfq |
| `ma_250_hfq` | 250日后复权均价 | `avg(close_hfq, 250)` | hfq |
| `close_to_ma_20_hfq` | 收盘价相对20日均线 | `close_hfq / ma_20_hfq - 1` | hfq |
| `close_to_ma_60_hfq` | 收盘价相对60日均线 | `close_hfq / ma_60_hfq - 1` | hfq |
| `ma_20_slope_20_hfq` | 20日均线20日斜率 | `ma_20_hfq / lag(ma_20_hfq,20) - 1` | hfq |
| `ma_60_slope_60_hfq` | 60日均线60日斜率 | `ma_60_hfq / lag(ma_60_hfq,60) - 1` | hfq |
| `rsi_14` | 14日相对强弱指标 | `RSI(close_hfq,14)` | hfq |
| `price_position_20_hfq` | 20日价格区间位置 | `(close_hfq - min(low_hfq,20)) / (max(high_hfq,20)-min(low_hfq,20))` | hfq |
| `price_position_60_hfq` | 60日价格区间位置 | 同上，窗口60 | hfq |

核心物理字段数量：15 个，含主键和 `updated_at` 为 18 列。

### 5.2 完整视图字段

`derived_price_technical_full_v` 建议展开：

| 字段组 | 窗口/字段 |
|---|---|
| 均线 | `ma_{3,5,10,20,30,60,90,120,180,250}_hfq` |
| EMA | `ema_{5,10,20,60,120}_hfq` |
| 均线距离 | `close_to_ma_{5,10,20,60,120,250}_hfq` |
| 均线斜率 | `ma_{5,20,60,120}_slope_{5,20,60,120}_hfq` |
| 均线排列 | `ma_bullish_5_20_60_flag`, `ma_bearish_5_20_60_flag` |
| 振荡指标 | `rsi_{6,14,24}`, `bias_{6,12,24}_hfq`, `cci_20_hfq`, `wr_14_hfq` |
| 通道位置 | `price_position_{20,60,120,250}_hfq`, `boll_mid_20_hfq`, `boll_upper_20_hfq`, `boll_lower_20_hfq`, `boll_width_20_hfq`, `boll_pct_b_20_hfq` |
| MACD | `macd_dif_12_26_hfq`, `macd_dea_9_hfq`, `macd_hist_12_26_9_hfq` |
| KDJ | `kdj_k_9_3_3_hfq`, `kdj_d_9_3_3_hfq`, `kdj_j_9_3_3_hfq` |

说明：KDJ、MACD、布林带只进入完整视图，不进入核心物理表。

## 6. `derived_return_momentum`

收益动量模块使用连续价格序列，因此核心采用后复权。

### 6.1 核心物理字段

| 字段 | 中文名 | 公式 | 口径 |
|---|---|---|---|
| `ret_2_hfq` | 2日收益率 | `close_hfq / lag(close_hfq,2) - 1` | hfq |
| `ret_5_hfq` | 5日收益率 | 同上，窗口5 | hfq |
| `ret_10_hfq` | 10日收益率 | 同上，窗口10 | hfq |
| `ret_20_hfq` | 20日收益率 | 同上，窗口20 | hfq |
| `ret_60_hfq` | 60日收益率 | 同上，窗口60 | hfq |
| `ret_120_hfq` | 120日收益率 | 同上，窗口120 | hfq |
| `ret_250_hfq` | 250日收益率 | 同上，窗口250 | hfq |
| `log_ret_sum_20_hfq` | 20日对数收益和 | `sum(log_ret_1_hfq,20)` | hfq |
| `momentum_20_5_hfq` | 20日动量剔除近5日 | `close_hfq lag5 / close_hfq lag20 - 1` | hfq |
| `momentum_60_20_hfq` | 60日动量剔除近20日 | `close_hfq lag20 / close_hfq lag60 - 1` | hfq |
| `reversal_5_hfq` | 5日短期反转 | `-ret_5_hfq` | hfq |
| `up_days_20` | 20日上涨天数 | `sum(ret_1_hfq > 0,20)` | hfq |
| `down_days_20` | 20日下跌天数 | `sum(ret_1_hfq < 0,20)` | hfq |

核心物理字段数量：13 个，含主键和 `updated_at` 为 16 列。

### 6.2 完整视图字段

`derived_return_momentum_full_v` 建议展开：

| 字段组 | 字段 |
|---|---|
| 多周期收益 | `ret_{1,2,3,5,10,20,30,60,90,120,180,250}_hfq` |
| 对数收益 | `log_ret_sum_{5,10,20,60,120,250}_hfq` |
| 动量剔除近端 | `momentum_20_5_hfq`, `momentum_60_20_hfq`, `momentum_120_20_hfq`, `momentum_250_20_hfq` |
| 路径强度 | `up_days_{5,10,20,60}`, `down_days_{5,10,20,60}`, `up_ratio_{20,60}` |
| 新高新低 | `new_high_{20,60,120,250}_flag`, `new_low_{20,60,120,250}_flag` |
| 距离高低点 | `drawdown_from_high_{20,60,120,250}_hfq`, `bounce_from_low_{20,60,120,250}_hfq` |

## 7. `derived_volatility_risk`

波动风险模块衡量历史路径风险。跨期波动和回撤使用后复权；单日涨跌停风险仍来自 raw 约束表。

### 7.1 核心物理字段

| 字段 | 中文名 | 公式 | 口径 |
|---|---|---|---|
| `hv_20` | 20日年化历史波动 | `stddev(log_ret_1_hfq,20)*sqrt(242)` | hfq |
| `hv_60` | 60日年化历史波动 | 同上，窗口60 | hfq |
| `hv_120` | 120日年化历史波动 | 同上，窗口120 | hfq |
| `parkinson_vol_20` | 20日 Parkinson 波动 | 基于 `ln(high_hfq/low_hfq)` | hfq |
| `atr_14_hfq` | 14日真实波幅 | `avg(true_range_hfq,14)` | hfq |
| `atr_14_pct_hfq` | 14日真实波幅占比 | `atr_14_hfq / close_hfq` | hfq |
| `max_drawdown_20_hfq` | 20日最大回撤 | `min(close_hfq / rolling_max(close_hfq)-1,20)` | hfq |
| `max_drawdown_60_hfq` | 60日最大回撤 | 同上，窗口60 | hfq |
| `downside_vol_60` | 60日下行波动 | `stddev(min(log_ret_1_hfq,0),60)*sqrt(242)` | hfq |
| `var_5pct_60` | 60日5%分位收益 | `quantile(ret_1_hfq,0.05,60)` | hfq |

核心物理字段数量：10 个，含主键和 `updated_at` 为 13 列。

### 7.2 完整视图字段

`derived_volatility_risk_full_v` 建议展开：

| 字段组 | 字段 |
|---|---|
| 历史波动 | `hv_{5,10,20,30,60,90,120,250}` |
| 高低价波动 | `parkinson_vol_{20,60}`, `garman_klass_vol_{20,60}` |
| ATR | `atr_{5,14,20}_hfq`, `atr_{5,14,20}_pct_hfq` |
| 回撤 | `max_drawdown_{20,60,120,250}_hfq`, `drawdown_days_{20,60,120}` |
| 下行风险 | `downside_vol_{20,60,120}`, `semi_deviation_{20,60}` |
| 尾部风险 | `var_5pct_{20,60,120}`, `cvar_5pct_{20,60,120}` |

## 8. `derived_volume_liquidity`

成交与流动性模块不使用复权价格，除非指标本身需要收益率参与。成交量、成交额、换手率均保持原始口径。

### 8.1 核心物理字段

| 字段 | 中文名 | 公式 | 口径 |
|---|---|---|---|
| `volume_ma_5` | 5日成交量均值 | `avg(volume,5)` | not_price |
| `volume_ma_20` | 20日成交量均值 | `avg(volume,20)` | not_price |
| `volume_ma_60` | 60日成交量均值 | `avg(volume,60)` | not_price |
| `amount_ma_20` | 20日成交额均值 | `avg(amount,20)` | not_price |
| `amount_ma_60` | 60日成交额均值 | `avg(amount,60)` | not_price |
| `turnover_rate_ma_20` | 20日换手率均值 | `avg(stock_daily_basic.turnover_rate,20)` | not_price |
| `turnover_rate_free_ma_20` | 20日自由流通换手率均值 | `avg(turnover_rate_free,20)` | not_price |
| `volume_ratio_20` | 成交量相对20日均量 | `volume / volume_ma_20` | not_price |
| `amount_ratio_20` | 成交额相对20日均额 | `amount / amount_ma_20` | not_price |
| `amihud_20` | 20日 Amihud 非流动性 | `avg(abs(ret_1_hfq)/amount,20)` | mixed |
| `zero_volume_days_20` | 20日零成交天数 | `sum(volume=0,20)` | not_price |

核心物理字段数量：11 个，含主键和 `updated_at` 为 14 列。

### 8.2 完整视图字段

`derived_volume_liquidity_full_v` 建议展开：

| 字段组 | 字段 |
|---|---|
| 成交量均线 | `volume_ma_{3,5,10,20,60,120}` |
| 成交额均线 | `amount_ma_{3,5,10,20,60,120}` |
| 换手率 | `turnover_rate_ma_{5,20,60}`, `turnover_rate_free_ma_{5,20,60}` |
| 相对成交 | `volume_ratio_{5,20,60}`, `amount_ratio_{5,20,60}` |
| 流动性 | `amihud_{5,20,60}`, `amount_cv_{20,60}`, `turnover_cv_{20,60}` |
| 缺流动性状态 | `zero_volume_days_{5,20,60}`, `low_amount_days_{20,60}` |

## 9. `derived_trading_constraint`

交易约束模块必须使用 raw 价格和 Tushare 涨跌停价，因为制度约束发生在真实交易价格上。

### 9.1 核心物理字段

| 字段 | 中文名 | 公式 | 口径 |
|---|---|---|---|
| `limit_up_days_5` | 5日涨停天数 | `sum(limit_up_flag,5)` | raw |
| `limit_up_days_20` | 20日涨停天数 | `sum(limit_up_flag,20)` | raw |
| `limit_down_days_5` | 5日跌停天数 | `sum(limit_down_flag,5)` | raw |
| `limit_down_days_20` | 20日跌停天数 | `sum(limit_down_flag,20)` | raw |
| `touch_limit_up_days_20` | 20日触及涨停天数 | `sum(touch_limit_up_flag,20)` | raw |
| `touch_limit_down_days_20` | 20日触及跌停天数 | `sum(touch_limit_down_flag,20)` | raw |
| `consecutive_limit_up_days` | 连续涨停天数 | 按交易日连续 `limit_up_flag` 计数 | raw |
| `consecutive_limit_down_days` | 连续跌停天数 | 按交易日连续 `limit_down_flag` 计数 | raw |
| `one_price_limit_up_flag` | 一字涨停 | `open=high=low=close≈up_limit` | raw |
| `one_price_limit_down_flag` | 一字跌停 | `open=high=low=close≈down_limit` | raw |
| `tradable_state` | 可交易状态 | `normal/suspended/limit_locked/missing` | raw/not_price |

核心物理字段数量：11 个，含主键和 `updated_at` 为 14 列。

### 9.2 完整视图字段

`derived_trading_constraint_full_v` 建议展开：

| 字段组 | 字段 |
|---|---|
| 涨跌停滚动 | `limit_up_days_{3,5,10,20,60}`, `limit_down_days_{3,5,10,20,60}` |
| 触板滚动 | `touch_limit_up_days_{5,20,60}`, `touch_limit_down_days_{5,20,60}` |
| 开盘封板 | `open_limit_up_days_{5,20}`, `open_limit_down_days_{5,20}` |
| 连续状态 | `consecutive_limit_up_days`, `consecutive_limit_down_days`, `limit_streak_direction` |
| 交易可达性 | `cannot_buy_open_flag`, `cannot_sell_open_flag`, `limit_locked_flag` |
| 缺失/停牌 | `suspended_days_{5,20,60}`, `missing_price_days_{5,20,60}` |

## 10. ?????????

??????????????????????????? `config/schema_registry.json`????????? Excel ??????????????????????????????????????

???????

```text
?????2, 3, 5, 10, 20, 30, 60, 120, 250
?????5, 10, 20, 30, 60, 120
?????5, 10, 20, 30, 60, 120, 250
??????2, 3, 5, 10, 20, 30, 60, 120
```

### 10.1 ????

| ?? | ?? | ??? | ?? |
|---|---|---:|---|
| `derived_daily_spine` | ????? | 49 | ??? |
| `derived_daily_spine_full_v` | ???? | 62 | ??? |
| `derived_price_technical` | ????? | 16 | ??? |
| `derived_price_technical_full_v` | ???? | 74 | ??? |
| `derived_return_momentum` | ????? | 16 | ??? |
| `derived_return_momentum_full_v` | ???? | 77 | ??? |
| `derived_volatility_risk` | ????? | 13 | ??? |
| `derived_volatility_risk_full_v` | ???? | 50 | ??? |
| `derived_volume_liquidity` | ????? | 14 | ??? |
| `derived_volume_liquidity_full_v` | ???? | 69 | ??? |
| `derived_trading_constraint` | ????? | 14 | ??? |
| `derived_trading_constraint_full_v` | ???? | 69 | ??? |

### 10.2 ??????????

### `derived_daily_spine`

```text
ts_code, trade_date, is_trade, is_listed_asof, list_status_asof, days_since_list, market, exchange,
open_raw, high_raw, low_raw, close_raw, pre_close_raw, change_raw, pct_chg_raw, volume,
amount, amplitude_raw, adj_factor, latest_adj_factor_asof, open_hfq, high_hfq, low_hfq, close_hfq,
pre_close_hfq, ret_1_raw, ret_1_hfq, log_ret_1_hfq, overnight_ret_hfq, intraday_ret_hfq, high_low_range_hfq, gap_open_hfq,
close_position_hfq, up_limit, down_limit, limit_up_flag, limit_down_flag, touch_limit_up_flag, touch_limit_down_flag, open_limit_up_flag,
open_limit_down_flag, limit_up_gap, limit_down_gap, has_price, has_adj_factor, has_limit_price, price_valid_flag, missing_reason,
updated_at
```

### `derived_price_technical`

```text
ts_code, trade_date, ma_5_hfq, ma_10_hfq, ma_20_hfq, ma_60_hfq, ma_120_hfq, ma_250_hfq,
close_to_ma_20_hfq, close_to_ma_60_hfq, ma_20_slope_20_hfq, ma_60_slope_60_hfq, rsi_14, price_position_20_hfq, price_position_60_hfq, updated_at
```

### `derived_return_momentum`

```text
ts_code, trade_date, ret_2_hfq, ret_5_hfq, ret_10_hfq, ret_20_hfq, ret_60_hfq, ret_120_hfq,
ret_250_hfq, log_ret_sum_20_hfq, momentum_20_5_hfq, momentum_60_20_hfq, reversal_5_hfq, up_days_20, down_days_20, updated_at
```

### `derived_volatility_risk`

```text
ts_code, trade_date, hv_20, hv_60, hv_120, parkinson_vol_20, atr_14_hfq, atr_14_pct_hfq,
max_drawdown_20_hfq, max_drawdown_60_hfq, downside_vol_60, var_5pct_60, updated_at
```

### `derived_volume_liquidity`

```text
ts_code, trade_date, volume_ma_5, volume_ma_20, volume_ma_60, amount_ma_20, amount_ma_60, turnover_rate_ma_20,
turnover_rate_free_ma_20, volume_ratio_20, amount_ratio_20, amihud_20, zero_volume_days_20, updated_at
```

### `derived_trading_constraint`

```text
ts_code, trade_date, limit_up_days_5, limit_up_days_20, limit_down_days_5, limit_down_days_20, touch_limit_up_days_20, touch_limit_down_days_20,
consecutive_limit_up_days, consecutive_limit_down_days, one_price_limit_up_flag, one_price_limit_down_flag, tradable_state, updated_at
```

### 10.3 ?????????

### `derived_daily_spine_full_v`

```text
ts_code, trade_date, is_trade, is_listed_asof, list_status_asof, days_since_list, market, exchange,
open_raw, high_raw, low_raw, close_raw, pre_close_raw, change_raw, pct_chg_raw, volume,
amount, amplitude_raw, adj_factor, latest_adj_factor_asof, open_hfq, high_hfq, low_hfq, close_hfq,
pre_close_hfq, ret_1_raw, ret_1_hfq, log_ret_1_hfq, overnight_ret_hfq, intraday_ret_hfq, high_low_range_hfq, gap_open_hfq,
close_position_hfq, up_limit, down_limit, limit_up_flag, limit_down_flag, touch_limit_up_flag, touch_limit_down_flag, open_limit_up_flag,
open_limit_down_flag, limit_up_gap, limit_down_gap, has_price, has_adj_factor, has_limit_price, price_valid_flag, missing_reason,
open_qfq, high_qfq, low_qfq, close_qfq, pre_close_qfq, body_raw, upper_shadow_raw, lower_shadow_raw,
body_ratio_raw, true_range_hfq, suspended_flag, one_price_limit_flag, ohlc_relation_error_flag, updated_at
```

### `derived_price_technical_full_v`

```text
ts_code, trade_date, ma_5_hfq, ma_10_hfq, ma_20_hfq, ma_60_hfq, ma_120_hfq, ma_250_hfq,
close_to_ma_20_hfq, close_to_ma_60_hfq, ma_20_slope_20_hfq, ma_60_slope_60_hfq, rsi_14, price_position_20_hfq, price_position_60_hfq, ma_2_hfq,
ma_3_hfq, ma_30_hfq, close_to_ma_2_hfq, close_to_ma_3_hfq, close_to_ma_5_hfq, close_to_ma_10_hfq, close_to_ma_30_hfq, close_to_ma_120_hfq,
close_to_ma_250_hfq, ma_2_slope_2_hfq, ma_3_slope_3_hfq, ma_5_slope_5_hfq, ma_10_slope_10_hfq, ma_30_slope_30_hfq, ma_120_slope_120_hfq, ma_bullish_5_20_60_flag,
ma_bullish_10_30_120_flag, ma_bearish_5_20_60_flag, ma_bearish_10_30_120_flag, rsi_6, rsi_9, rsi_24, bias_3_hfq, bias_5_hfq,
bias_6_hfq, bias_10_hfq, bias_12_hfq, bias_20_hfq, bias_24_hfq, bias_30_hfq, bias_60_hfq, price_position_5_hfq,
price_position_10_hfq, price_position_30_hfq, price_position_120_hfq, price_position_250_hfq, boll_mid_20_hfq, boll_upper_20_hfq, boll_lower_20_hfq, boll_width_20_hfq,
boll_pct_b_20_hfq, boll_mid_30_hfq, boll_upper_30_hfq, boll_lower_30_hfq, boll_width_30_hfq, boll_pct_b_30_hfq, boll_mid_60_hfq, boll_upper_60_hfq,
boll_lower_60_hfq, boll_width_60_hfq, boll_pct_b_60_hfq, macd_dif_12_26_hfq, macd_dea_9_hfq, macd_hist_12_26_9_hfq, kdj_k_9_3_3_hfq, kdj_d_9_3_3_hfq,
kdj_j_9_3_3_hfq, updated_at
```

### `derived_return_momentum_full_v`

```text
ts_code, trade_date, ret_2_hfq, ret_5_hfq, ret_10_hfq, ret_20_hfq, ret_60_hfq, ret_120_hfq,
ret_250_hfq, log_ret_sum_20_hfq, momentum_20_5_hfq, momentum_60_20_hfq, reversal_5_hfq, up_days_20, down_days_20, ret_1_hfq,
ret_3_hfq, ret_30_hfq, log_ret_sum_2_hfq, log_ret_sum_3_hfq, log_ret_sum_5_hfq, log_ret_sum_10_hfq, log_ret_sum_30_hfq, log_ret_sum_60_hfq,
log_ret_sum_120_hfq, log_ret_sum_250_hfq, momentum_30_10_hfq, momentum_120_20_hfq, momentum_250_20_hfq, reversal_2_hfq, reversal_3_hfq, reversal_10_hfq,
up_days_5, up_days_10, up_days_30, up_days_60, up_days_120, down_days_5, down_days_10, down_days_30,
down_days_60, down_days_120, up_ratio_5, up_ratio_10, up_ratio_20, up_ratio_30, up_ratio_60, up_ratio_120,
new_high_5_flag, new_high_10_flag, new_high_20_flag, new_high_30_flag, new_high_60_flag, new_high_120_flag, new_high_250_flag, new_low_5_flag,
new_low_10_flag, new_low_20_flag, new_low_30_flag, new_low_60_flag, new_low_120_flag, new_low_250_flag, drawdown_from_high_5_hfq, drawdown_from_high_10_hfq,
drawdown_from_high_20_hfq, drawdown_from_high_30_hfq, drawdown_from_high_60_hfq, drawdown_from_high_120_hfq, drawdown_from_high_250_hfq, bounce_from_low_5_hfq, bounce_from_low_10_hfq, bounce_from_low_20_hfq,
bounce_from_low_30_hfq, bounce_from_low_60_hfq, bounce_from_low_120_hfq, bounce_from_low_250_hfq, updated_at
```

### `derived_volatility_risk_full_v`

```text
ts_code, trade_date, hv_20, hv_60, hv_120, parkinson_vol_20, atr_14_hfq, atr_14_pct_hfq,
max_drawdown_20_hfq, max_drawdown_60_hfq, downside_vol_60, var_5pct_60, hv_5, hv_10, hv_30, hv_250,
parkinson_vol_5, parkinson_vol_10, parkinson_vol_30, parkinson_vol_60, parkinson_vol_120, atr_5_hfq, atr_10_hfq, atr_20_hfq,
atr_30_hfq, atr_60_hfq, atr_5_pct_hfq, atr_10_pct_hfq, atr_20_pct_hfq, atr_30_pct_hfq, atr_60_pct_hfq, max_drawdown_5_hfq,
max_drawdown_10_hfq, max_drawdown_30_hfq, max_drawdown_120_hfq, max_drawdown_250_hfq, downside_vol_20, downside_vol_30, downside_vol_120, downside_vol_250,
var_5pct_20, var_5pct_30, var_5pct_120, var_5pct_250, cvar_5pct_20, cvar_5pct_30, cvar_5pct_60, cvar_5pct_120,
cvar_5pct_250, updated_at
```

### `derived_volume_liquidity_full_v`

```text
ts_code, trade_date, volume_ma_5, volume_ma_20, volume_ma_60, amount_ma_20, amount_ma_60, turnover_rate_ma_20,
turnover_rate_free_ma_20, volume_ratio_20, amount_ratio_20, amihud_20, zero_volume_days_20, volume_ma_2, volume_ma_3, volume_ma_10,
volume_ma_30, volume_ma_120, amount_ma_2, amount_ma_3, amount_ma_5, amount_ma_10, amount_ma_30, amount_ma_120,
turnover_rate_ma_2, turnover_rate_ma_3, turnover_rate_ma_5, turnover_rate_ma_10, turnover_rate_ma_30, turnover_rate_ma_60, turnover_rate_ma_120, turnover_rate_free_ma_2,
turnover_rate_free_ma_3, turnover_rate_free_ma_5, turnover_rate_free_ma_10, turnover_rate_free_ma_30, turnover_rate_free_ma_60, turnover_rate_free_ma_120, volume_ratio_2, volume_ratio_3,
volume_ratio_5, volume_ratio_10, volume_ratio_30, volume_ratio_60, volume_ratio_120, amount_ratio_2, amount_ratio_3, amount_ratio_5,
amount_ratio_10, amount_ratio_30, amount_ratio_60, amount_ratio_120, amihud_5, amihud_10, amihud_30, amihud_60,
amihud_120, zero_volume_days_5, zero_volume_days_10, zero_volume_days_30, zero_volume_days_60, zero_volume_days_120, amount_cv_5, amount_cv_10,
amount_cv_20, amount_cv_30, amount_cv_60, amount_cv_120, updated_at
```

### `derived_trading_constraint_full_v`

```text
ts_code, trade_date, limit_up_days_5, limit_up_days_20, limit_down_days_5, limit_down_days_20, touch_limit_up_days_20, touch_limit_down_days_20,
consecutive_limit_up_days, consecutive_limit_down_days, one_price_limit_up_flag, one_price_limit_down_flag, tradable_state, limit_up_days_2, limit_up_days_3, limit_up_days_10,
limit_up_days_30, limit_up_days_60, limit_up_days_120, limit_down_days_2, limit_down_days_3, limit_down_days_10, limit_down_days_30, limit_down_days_60,
limit_down_days_120, touch_limit_up_days_2, touch_limit_up_days_3, touch_limit_up_days_5, touch_limit_up_days_10, touch_limit_up_days_30, touch_limit_up_days_60, touch_limit_up_days_120,
touch_limit_down_days_2, touch_limit_down_days_3, touch_limit_down_days_5, touch_limit_down_days_10, touch_limit_down_days_30, touch_limit_down_days_60, touch_limit_down_days_120, open_limit_up_days_2,
open_limit_up_days_3, open_limit_up_days_5, open_limit_up_days_10, open_limit_up_days_20, open_limit_up_days_30, open_limit_up_days_60, open_limit_up_days_120, open_limit_down_days_2,
open_limit_down_days_3, open_limit_down_days_5, open_limit_down_days_10, open_limit_down_days_20, open_limit_down_days_30, open_limit_down_days_60, open_limit_down_days_120, limit_locked_flag,
missing_price_days_5, missing_price_days_10, missing_price_days_20, missing_price_days_30, missing_price_days_60, missing_price_days_120, suspended_days_5, suspended_days_10,
suspended_days_20, suspended_days_30, suspended_days_60, suspended_days_120, updated_at
```

????????? `EMA/MACD/KDJ` ?????????????????????????????????????????????????? Excel ???????

### 10.4 ????????

| ?? | ???? |
|---|---|
| ???? | ???? `EMA/MACD/KDJ`?`CCI`?`WR`????????? |
| ???? | ???????????????????????? |
| ???? | `garman_klass_vol`??? `drawdown_days`??????????? |
| ????? | ???????????????????????? |
| ???? | ?????????????/???????????????????? |

## 11. 实施步骤

### 阶段 A：注册设计

1. 更新 `config/schema_registry.json`，扩展核心物理表字段。
2. 新增各模块完整视图表项，设置 `table_type = "view"`。
3. 更新 `config/variables/derived_variables.json`，核心物理字段完整注册变量；完整视图字段进入 schema 字典，但避免变量名重复注册。
4. 刷新全局 Excel 数据字典。

### 阶段 B：构建核心物理表

1. 先重建 `derived_daily_spine`，确认后复权、前复权、涨跌停和质量标记稳定。
2. 重建 `derived_price_technical`、`derived_return_momentum`、`derived_volatility_risk`、`derived_volume_liquidity`、`derived_trading_constraint`。
3. 使用年度分片全历史构建，避免一次性窗口计算过宽导致内存压力。

### 阶段 C：创建完整视图

1. 创建 `*_full_v` 视图。
2. 对每个视图选取最近 10 个交易日样本做字段可查询验证。
3. 对核心表和视图分别生成审计报告。

### 阶段 D：质量审计

审计项目：

1. 行数、股票数、日期范围与 `derived_daily_spine` 对齐。
2. 每个核心字段非空率。
3. 初始窗口空值是否符合 `min_history`。
4. 复权因子缺失导致的空值比例。
5. 涨跌停字段与 raw 价格和 `stock_limit_price` 的一致性。
6. 收益、波动、均线字段是否存在异常极值。
7. 数据字典中文名、含义、公式、复权口径是否齐全。

## 12. 下一步确认

本阶段已完成核心物理表、完整视图、全量历史构建、审计报告和 Excel 数据字典刷新。后续逐一模块推进时，建议优先审阅第 10.2 和第 10.3 节的最终字段清单，再决定是否将第 10.4 节的候选增强字段纳入下一轮实现。
