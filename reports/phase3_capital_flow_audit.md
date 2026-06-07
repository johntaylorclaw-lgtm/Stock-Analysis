# Phase 3 资金流与交易行为模块审计报告

生成时间：2026-06-02T21:52:40

## 1. 表覆盖

| 表 | 行数 | 股票数 | 起始日期 | 截止日期 | 字段数 |
|---|---:|---:|---|---|---:|
| `derived_capital_flow` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 | 64 |
| `derived_northbound_flow_cache` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 | 41 |
| `derived_capital_flow_event_cache` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 | 32 |

## 2. 关键字段非空率

### derived_capital_flow

| 字段 | 非空行数 | 非空率 |
|---|---:|---:|
| `main_net_amount` | 13,586,039 | 88.82% |
| `main_net_amount_rate` | 13,586,039 | 88.82% |
| `main_flow_ma_20` | 12,879,348 | 84.20% |
| `margin_balance` | 5,853,466 | 38.27% |
| `margin_buy_to_amount` | 5,853,466 | 38.27% |
| `north_hold_shares` | 4,156,356 | 27.17% |
| `has_moneyflow` | 15,295,776 | 100.00% |

### derived_northbound_flow_cache

| 字段 | 非空行数 | 非空率 |
|---|---:|---:|
| `north_money` | 10,984,017 | 71.81% |
| `north_money_ma_20` | 11,013,383 | 72.00% |
| `north_money_sum_60` | 11,013,383 | 72.00% |
| `north_hold_shares_chg_250` | 3,227,006 | 21.10% |

### derived_capital_flow_event_cache

| 字段 | 非空行数 | 非空率 |
|---|---:|---:|
| `top_list_flag` | 15,295,776 | 100.00% |
| `top_inst_flag` | 15,295,776 | 100.00% |
| `top_list_days_20` | 15,185,523 | 99.28% |
| `top_inst_net_buy_sum_20` | 15,185,523 | 99.28% |

## 3. 单位实证结论

- 个股资金流金额实证样本数：2,957,801；`sum(buy/sell amount) / stock_daily.amount` 中位数：0.200000，均值：0.199989。
- 解释：Tushare 个股资金流金额为万元，`stock_daily.amount` 为千元；总买卖额约等于两倍成交额，因此未换算比值约为 0.2。资金流占成交额统一采用 `moneyflow_amount * 10 / amount`。
- 两融金额实证样本数：2,011,440；`margin_buy / amount` 中位数：90.335978，`margin_buy / (amount * 1000)` 中位数：0.090336。
- 解释：两融金额按元计，成交额按千元计；融资买入占成交额统一采用 `margin_buy / (amount * 1000)`。

## 4. 完整视图最近10个交易日抽检

| 指标 | 数值 |
|---|---:|
| 行数 | 54,985 |
| `main_flow_ma_20` 非空 | 51,785 |
| `north_money` 非空 | 49,481 |
| `top_list_flag` 非空 | 54,985 |
| `margin_buy_to_amount_ma_20` 非空 | 37,539 |

## 5. 结论

资金流与交易行为模块已完成核心物理表、北向缓存、事件缓存和完整视图构建。市场级北向资金流已按交易日广播到个股完整视图，并在字段说明中标记为市场级背景变量。
