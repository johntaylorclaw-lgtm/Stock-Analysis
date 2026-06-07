# Phase 3 交易行情与技术分析核心模块审计报告

- 生成时间：2026-06-01T21:15:06
- 数据库：`/mnt/d/Opencode Workspace/Stock_Maintainance/data/duckdb/stock_data.duckdb`
- 价格最小变动单位口径：`price_tick = 0.01`，涨跌停判断容忍区间为 `price_tick / 2 = 0.005`

## 1. 字段注册与实际落库核对

| 对象 | 类型 | 注册字段数 | 实际字段数 | 状态 |
|---|---:|---:|---:|---|
| `derived_daily_spine` | 物理表 | 49 | 49 | OK |
| `derived_price_technical` | 物理表 | 16 | 16 | OK |
| `derived_return_momentum` | 物理表 | 16 | 16 | OK |
| `derived_volatility_risk` | 物理表 | 13 | 13 | OK |
| `derived_volume_liquidity` | 物理表 | 14 | 14 | OK |
| `derived_trading_constraint` | 物理表 | 14 | 14 | OK |
| `derived_daily_spine_full_v` | 视图 | 62 | 62 | OK |
| `derived_price_technical_full_v` | 视图 | 74 | 74 | OK |
| `derived_return_momentum_full_v` | 视图 | 77 | 77 | OK |
| `derived_volatility_risk_full_v` | 视图 | 50 | 50 | OK |
| `derived_volume_liquidity_full_v` | 视图 | 69 | 69 | OK |
| `derived_trading_constraint_full_v` | 视图 | 69 | 69 | OK |

## 2. 核心物理表覆盖率

| 表 | 行数 | 股票数 | 最早交易日 | 最新交易日 |
|---|---:|---:|---|---|
| `derived_daily_spine` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 |
| `derived_price_technical` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 |
| `derived_return_momentum` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 |
| `derived_volatility_risk` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 |
| `derived_volume_liquidity` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 |
| `derived_trading_constraint` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 |

## 3. 完整视图近端可查询核对

| 视图 | 2026-05-20 至 2026-05-26 行数 | 股票数 | 日期范围 |
|---|---:|---:|---|
| `derived_daily_spine_full_v` | 27,511 | 5,506 | 2026-05-20 ~ 2026-05-26 |
| `derived_price_technical_full_v` | 27,511 | 5,506 | 2026-05-20 ~ 2026-05-26 |
| `derived_return_momentum_full_v` | 27,511 | 5,506 | 2026-05-20 ~ 2026-05-26 |
| `derived_volatility_risk_full_v` | 27,511 | 5,506 | 2026-05-20 ~ 2026-05-26 |
| `derived_volume_liquidity_full_v` | 27,511 | 5,506 | 2026-05-20 ~ 2026-05-26 |
| `derived_trading_constraint_full_v` | 27,511 | 5,506 | 2026-05-20 ~ 2026-05-26 |

## 4. 关键字段非空率

| 表 | 字段 | 非空行数 | 总行数 | 非空率 |
|---|---|---:|---:|---:|
| `derived_daily_spine` | `close_hfq` | 14,913,039 | 15,295,776 | 97.4978% |
| `derived_daily_spine` | `log_ret_1_hfq` | 14,905,798 | 15,295,776 | 97.4504% |
| `derived_daily_spine` | `limit_up_flag` | 14,912,922 | 15,295,776 | 97.4970% |
| `derived_daily_spine` | `price_valid_flag` | 15,295,776 | 15,295,776 | 100.0000% |
| `derived_price_technical` | `ma_20_hfq` | 14,802,042 | 15,295,776 | 96.7721% |
| `derived_price_technical` | `ma_250_hfq` | 13,457,705 | 15,295,776 | 87.9831% |
| `derived_price_technical` | `rsi_14` | 14,831,169 | 15,295,776 | 96.9625% |
| `derived_price_technical` | `price_position_60_hfq` | 14,912,283 | 15,295,776 | 97.4928% |
| `derived_return_momentum` | `ret_20_hfq` | 14,796,205 | 15,295,776 | 96.7339% |
| `derived_return_momentum` | `ret_250_hfq` | 13,451,790 | 15,295,776 | 87.9445% |
| `derived_return_momentum` | `up_days_20` | 14,772,058 | 15,295,776 | 96.5761% |
| `derived_volatility_risk` | `hv_60` | 14,554,200 | 15,295,776 | 95.1518% |
| `derived_volatility_risk` | `atr_14_hfq` | 14,829,850 | 15,295,776 | 96.9539% |
| `derived_volatility_risk` | `var_5pct_60` | 14,554,200 | 15,295,776 | 95.1518% |
| `derived_volume_liquidity` | `volume_ma_20` | 15,175,795 | 15,295,776 | 99.2156% |
| `derived_volume_liquidity` | `amount_ma_20` | 15,175,795 | 15,295,776 | 99.2156% |
| `derived_volume_liquidity` | `amihud_20` | 14,795,200 | 15,295,776 | 96.7274% |
| `derived_trading_constraint` | `limit_up_days_20` | 15,295,776 | 15,295,776 | 100.0000% |
| `derived_trading_constraint` | `consecutive_limit_up_days` | 15,295,776 | 15,295,776 | 100.0000% |
| `derived_trading_constraint` | `tradable_state` | 15,295,776 | 15,295,776 | 100.0000% |

## 5. 涨跌停口径实证

| 口径项 | 数值 |
|---|---:|
| `rows_checked` | 15,295,776 |
| `tick_up_count` | 272,004 |
| `ratio_up_count` | 272,037 |
| `up_diff_count` | 33 |
| `tick_down_count` | 145,056 |
| `ratio_down_count` | 145,095 |
| `down_diff_count` | 39 |

结论：本模块采用最小价格变动单位半档作为涨跌停判断容忍区间，更贴近A股报价规则；与旧比例口径存在差异的样本已在上表列出，后续如需进一步精细化，可按股票价格档位和历史规则版本拆分审计。

