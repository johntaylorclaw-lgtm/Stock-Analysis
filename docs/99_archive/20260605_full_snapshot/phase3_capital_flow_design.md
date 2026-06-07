# Phase 3 资金流与交易行为模块设计

生成日期：2026-06-02

状态：已实施。核心表、北向缓存、事件缓存、完整视图和审计报告已生成。

实施结果：

1. `derived_capital_flow`：64 列，15,295,776 行，覆盖 5,809 只股票，日期范围 2006-01-04 至 2026-05-26。
2. `derived_northbound_flow_cache`：41 列，15,295,776 行。
3. `derived_capital_flow_event_cache`：32 列，15,295,776 行。
4. `derived_capital_flow_full_v`：246 列。
5. 审计报告：`reports/phase3_capital_flow_audit.md`。
6. 全局 Excel 数据字典已刷新：`outputs/variable_dictionary/global_variable_dictionary.xlsx`。

## 1. 设计目标

资金流与交易行为模块负责把个股资金流、大小单结构、融资融券、北向资金持仓、北向市场资金流、龙虎榜和机构席位数据整理成可复用的事实型衍生变量。模块不做主观评分，不生成综合资金强弱分，只维护可解释、可复现、可审计的资金参与者行为事实。

本模块沿用前序模块的混合结构：

1. 核心物理表：`derived_capital_flow`，保存日常高频使用、可稳定增量维护的资金流核心变量。
2. 完整视图：`derived_capital_flow_full_v`，保存更宽周期、更丰富比例、变化率、均线和事件字段。
3. 事件缓存表：`derived_capital_flow_event_cache`，物理保存龙虎榜与机构席位等稀疏事件聚合，供完整视图轻量 join。
4. 北向缓存表：`derived_northbound_flow_cache`，物理保存北向持仓变化和全市场北向流入的滚动字段，避免完整视图重复构造长窗口。

## 2. 口径原则

| 场景 | 口径 | 说明 |
|---|---|---|
| 大小单资金流 | Tushare `stock_moneyflow_daily` 原始金额和成交量 | 不复权，金额为交易当日事实 |
| 主力资金 | 大单 + 超大单 | `main_net_amount = large_net_amount + extra_large_net_amount` |
| 散户资金 | 小单 | `retail_net_amount = small_net_amount` |
| 净流入率 | 除以当日成交额 | `net_amount / stock_daily.amount`，需单位校准 |
| 成交额、市值交叉 | 使用 `derived_daily_spine.amount` 与 `derived_valuation_size.total_mv/circ_mv` | 成交额为千元，市值为万元，跨单位比例使用 `amount / 10 / mv` |
| 融资融券 | Tushare `margin_detail` 原始口径 | 交易所覆盖不同，缺失显式标记 |
| 北向持股 | `northbound_holding` 个股持股 | 只对陆股通可覆盖股票有值 |
| 北向市场流 | `northbound_daily.north_money` 等市场级字段 | 可按交易日广播到个股视图，标记为 market-level |
| 龙虎榜 | `top_list_daily/top_inst_detail` 稀疏事件 | 未上榜不是缺失，事件字段默认为 0 或 false |

单位校准结论：

1. `stock_moneyflow_daily` 金额字段为万元，`derived_daily_spine.amount` 为千元；资金流占成交额统一采用 `moneyflow_amount * 10 / amount`。
2. `margin_detail` 金额字段为元，`derived_daily_spine.amount` 为千元；融资买入占成交额统一采用 `margin_buy / (amount * 1000)`。
3. 市值字段 `derived_valuation_size.total_mv/circ_mv` 为万元；资金流占市值采用 `moneyflow_amount / mv`。

### 2.1 北向市场流广播口径说明

`northbound_daily.north_money/hgt/sgt` 是市场级数据，不是某只股票自己的北向买卖额；同一个交易日只有一组市场值。所谓“按交易日广播到个股视图”，含义是：在 `derived_capital_flow_full_v` 中，每只股票同一天都会带上同一个 `north_money`、`hgt`、`sgt` 及其滚动统计，用作当日市场资金背景变量。

该字段的正确用途是解释市场环境，例如“个股主力流入发生在北向整体净流入还是净流出背景下”；不能解释为“北向资金买入了该股票”。个股层面的北向持仓事实仍以 `northbound_holding.hold_shares/hold_ratio` 及其变化字段为准。

因此实现时会把字段分为两类：

1. 个股级北向变量：`north_hold_shares`、`north_hold_ratio`、`north_hold_*_chg_N`。
2. 市场级北向背景变量：`north_money`、`hgt`、`sgt`、`north_money_ma_N/sum_N/zscore_N`，字段说明和数据字典中明确标记为“市场级背景变量”。

## 3. 数据来源

| 来源表 | 字段 | 用途 |
|---|---|---|
| `stock_moneyflow_daily` | `buy_sm_amount/sell_sm_amount` 等 | 大小单买卖金额、成交量、净流入 |
| `stock_daily` / `derived_daily_spine` | `amount`, `volume`, `ret_1_hfq`, `has_price` | 资金流占成交额、量价交叉、缺失标记 |
| `derived_valuation_size` | `total_mv`, `circ_mv`, `free_float_mv` | 资金流占市值、成交额占市值 |
| `margin_detail` | `margin_balance`, `short_balance`, `margin_buy`, `margin_repay` 等 | 融资融券余额和交易行为 |
| `northbound_holding` | `hold_shares`, `hold_ratio` | 北向个股持仓变化 |
| `northbound_daily` | `north_money`, `hgt`, `sgt` 等 | 市场级北向资金流 |
| `top_list_daily` | `net_amount`, `net_rate`, `amount_rate`, `reason` | 龙虎榜个股事件 |
| `top_inst_detail` | `buy`, `sell`, `net_buy`, `side` | 龙虎榜机构席位事件 |

## 4. 周期体系

```text
完整滚动周期：2, 3, 5, 10, 20, 30, 60, 120, 250
核心落库锚点周期：5, 20, 60, 120
长周期持仓变化：5, 20, 60, 120, 250
事件统计周期：2, 3, 5, 10, 20, 30, 60, 120, 250
```

说明：

1. 资金流日频字段波动较大，完整视图采用完整周期族，避免只提供 5/20 导致变量覆盖不足。
2. 核心物理表只保留 5/20/60/120 这类常用锚点周期，用于日常增量、质量审计和下游高频读取。
3. 北向持仓和两融余额有更强趋势属性，完整视图保留 250 日长周期变化；核心表保留到 120 日。
4. 龙虎榜是事件稀疏数据，事件窗口不进入核心表，放在缓存表和完整视图。

## 5. 核心物理表：`derived_capital_flow`

核心物理表定位为“个股日频资金流主干”，保留大小单、主力、两融、北向持仓的核心字段，并增加 60/120 日锚点周期。完整的 2/3/5/10/20/30/60/120/250 周期在视图层展开，核心表目标控制在 70 列以内。

### 5.1 完整字段清单

| 字段 | 中文名 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|
| `ts_code` | 股票代码 | 主键 | required |
| `trade_date` | 交易日期 | 主键 | required |
| `small_buy_amount` | 小单买入额 | `stock_moneyflow_daily.buy_sm_amount` | source_optional |
| `small_sell_amount` | 小单卖出额 | `stock_moneyflow_daily.sell_sm_amount` | source_optional |
| `small_net_amount` | 小单净流入额 | `buy_sm_amount - sell_sm_amount` | source_optional |
| `medium_buy_amount` | 中单买入额 | `buy_md_amount` | source_optional |
| `medium_sell_amount` | 中单卖出额 | `sell_md_amount` | source_optional |
| `medium_net_amount` | 中单净流入额 | `buy_md_amount - sell_md_amount` | source_optional |
| `large_buy_amount` | 大单买入额 | `buy_lg_amount` | source_optional |
| `large_sell_amount` | 大单卖出额 | `sell_lg_amount` | source_optional |
| `large_net_amount` | 大单净流入额 | `buy_lg_amount - sell_lg_amount` | source_optional |
| `extra_large_buy_amount` | 超大单买入额 | `buy_elg_amount` | source_optional |
| `extra_large_sell_amount` | 超大单卖出额 | `sell_elg_amount` | source_optional |
| `extra_large_net_amount` | 超大单净流入额 | `buy_elg_amount - sell_elg_amount` | source_optional |
| `main_net_amount` | 主力净流入额 | `large_net_amount + extra_large_net_amount` | source_optional |
| `main_buy_amount` | 主力买入额 | `large_buy_amount + extra_large_buy_amount` | source_optional |
| `main_sell_amount` | 主力卖出额 | `large_sell_amount + extra_large_sell_amount` | source_optional |
| `retail_net_amount` | 散户净流入额 | `small_net_amount` | source_optional |
| `net_mf_amount` | 总净流入额 | `stock_moneyflow_daily.net_mf_amount` | source_optional |
| `net_mf_vol` | 总净流入量 | `stock_moneyflow_daily.net_mf_vol` | source_optional |
| `main_net_amount_rate` | 主力净流入占成交额 | `main_net_amount / amount`，同源单位校准后计算 | source_optional |
| `large_net_amount_rate` | 大单净流入占成交额 | `large_net_amount / amount` | source_optional |
| `extra_large_net_amount_rate` | 超大单净流入占成交额 | `extra_large_net_amount / amount` | source_optional |
| `small_net_amount_rate` | 小单净流入占成交额 | `small_net_amount / amount` | source_optional |
| `main_flow_ma_5` | 5日主力净流入均值 | `avg(main_net_amount,5)` | initial_window_null |
| `main_flow_ma_20` | 20日主力净流入均值 | `avg(main_net_amount,20)` | initial_window_null |
| `main_flow_ma_60` | 60日主力净流入均值 | `avg(main_net_amount,60)` | initial_window_null |
| `main_flow_ma_120` | 120日主力净流入均值 | `avg(main_net_amount,120)` | initial_window_null |
| `main_flow_sum_5` | 5日主力净流入累计 | `sum(main_net_amount,5)` | initial_window_null |
| `main_flow_sum_20` | 20日主力净流入累计 | `sum(main_net_amount,20)` | initial_window_null |
| `main_flow_sum_60` | 60日主力净流入累计 | `sum(main_net_amount,60)` | initial_window_null |
| `main_flow_sum_120` | 120日主力净流入累计 | `sum(main_net_amount,120)` | initial_window_null |
| `main_flow_positive_days_20` | 20日主力净流入为正天数 | `sum(main_net_amount > 0,20)` | initial_window_null |
| `main_flow_persist_ratio_20` | 20日主力净流入持续比例 | `main_flow_positive_days_20 / 20` | initial_window_null |
| `main_flow_to_total_mv_20` | 20日主力净流入占总市值 | `sum(main_net_amount,20) / total_mv`，需单位校准 | source_optional |
| `main_flow_to_circ_mv_20` | 20日主力净流入占流通市值 | `sum(main_net_amount,20) / circ_mv`，需单位校准 | source_optional |
| `margin_balance` | 融资余额 | `margin_detail.margin_balance` | source_optional |
| `short_balance` | 融券余额 | `margin_detail.short_balance` | source_optional |
| `margin_buy` | 融资买入额 | `margin_detail.margin_buy` | source_optional |
| `margin_repay` | 融资偿还额 | `margin_detail.margin_repay` | source_optional |
| `short_sell_volume` | 融券卖出量 | `margin_detail.short_sell_volume` | source_optional |
| `short_repay_volume` | 融券偿还量 | `margin_detail.short_repay_volume` | source_optional |
| `total_margin_short_balance` | 两融总余额 | `margin_detail.total_balance` | source_optional |
| `margin_balance_chg_5` | 5日融资余额变化 | `margin_balance / lag(margin_balance,5) - 1` | initial_window_null |
| `margin_balance_chg_20` | 20日融资余额变化 | `margin_balance / lag(margin_balance,20) - 1` | initial_window_null |
| `margin_balance_chg_60` | 60日融资余额变化 | `margin_balance / lag(margin_balance,60) - 1` | initial_window_null |
| `margin_balance_chg_120` | 120日融资余额变化 | `margin_balance / lag(margin_balance,120) - 1` | initial_window_null |
| `margin_buy_to_amount` | 融资买入占成交额 | `margin_buy / amount`，单位校准后计算 | source_optional |
| `margin_short_ratio` | 融券余额/融资余额 | `short_balance / margin_balance` | source_optional |
| `north_hold_shares` | 北向持股数量 | `northbound_holding.hold_shares` | source_optional |
| `north_hold_ratio` | 北向持股比例 | `northbound_holding.hold_ratio` | source_optional |
| `north_hold_shares_chg_5` | 5日北向持股数量变化 | `hold_shares / lag(hold_shares,5) - 1` | initial_window_null |
| `north_hold_shares_chg_20` | 20日北向持股数量变化 | `hold_shares / lag(hold_shares,20) - 1` | initial_window_null |
| `north_hold_shares_chg_60` | 60日北向持股数量变化 | `hold_shares / lag(hold_shares,60) - 1` | initial_window_null |
| `north_hold_shares_chg_120` | 120日北向持股数量变化 | `hold_shares / lag(hold_shares,120) - 1` | initial_window_null |
| `north_hold_ratio_chg_20` | 20日北向持股比例变化 | `hold_ratio - lag(hold_ratio,20)` | initial_window_null |
| `north_hold_ratio_chg_60` | 60日北向持股比例变化 | `hold_ratio - lag(hold_ratio,60)` | initial_window_null |
| `north_hold_ratio_chg_120` | 120日北向持股比例变化 | `hold_ratio - lag(hold_ratio,120)` | initial_window_null |
| `has_moneyflow` | 是否有个股资金流数据 | `stock_moneyflow_daily` 是否匹配 | quality |
| `has_margin` | 是否有两融数据 | `margin_detail` 是否匹配 | quality |
| `has_north_holding` | 是否有北向持股数据 | `northbound_holding` 是否匹配 | quality |
| `capital_flow_missing_reason` | 资金流缺失原因 | `missing_moneyflow/missing_price/no_margin_coverage/no_north_coverage/null` | quality |
| `updated_at` | 更新时间 | `CURRENT_TIMESTAMP` | metadata |

核心物理表最终字段：

```text
ts_code, trade_date,
small_buy_amount, small_sell_amount, small_net_amount,
medium_buy_amount, medium_sell_amount, medium_net_amount,
large_buy_amount, large_sell_amount, large_net_amount,
extra_large_buy_amount, extra_large_sell_amount, extra_large_net_amount,
main_net_amount, main_buy_amount, main_sell_amount, retail_net_amount,
net_mf_amount, net_mf_vol,
main_net_amount_rate, large_net_amount_rate, extra_large_net_amount_rate, small_net_amount_rate,
main_flow_ma_5, main_flow_ma_20, main_flow_ma_60, main_flow_ma_120,
main_flow_sum_5, main_flow_sum_20, main_flow_sum_60, main_flow_sum_120,
main_flow_positive_days_20, main_flow_persist_ratio_20,
main_flow_to_total_mv_20, main_flow_to_circ_mv_20,
margin_balance, short_balance, margin_buy, margin_repay,
short_sell_volume, short_repay_volume, total_margin_short_balance,
margin_balance_chg_5, margin_balance_chg_20, margin_balance_chg_60, margin_balance_chg_120,
margin_buy_to_amount, margin_short_ratio,
north_hold_shares, north_hold_ratio,
north_hold_shares_chg_5, north_hold_shares_chg_20, north_hold_shares_chg_60, north_hold_shares_chg_120,
north_hold_ratio_chg_20, north_hold_ratio_chg_60, north_hold_ratio_chg_120,
has_moneyflow, has_margin, has_north_holding,
capital_flow_missing_reason,
updated_at
```

## 6. 北向缓存表：`derived_northbound_flow_cache`

北向缓存表承接市场级北向资金流和个股北向持仓长周期变化。市场级字段按交易日保存，个股字段按 `ts_code + trade_date` 保存。

### 6.1 字段清单

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `ts_code` | 股票代码 | 个股代码；市场级广播到个股时使用 |
| `trade_date` | 交易日期 | 主键 |
| `north_money` | 北向资金净流入 | `northbound_daily.north_money` |
| `north_money_ma_2` | 2日北向净流入均值 | `avg(north_money,2)` |
| `north_money_ma_3` | 3日北向净流入均值 | `avg(north_money,3)` |
| `north_money_ma_5` | 5日北向净流入均值 | `avg(north_money,5)` |
| `north_money_ma_10` | 10日北向净流入均值 | `avg(north_money,10)` |
| `north_money_ma_20` | 20日北向净流入均值 | `avg(north_money,20)` |
| `north_money_ma_30` | 30日北向净流入均值 | `avg(north_money,30)` |
| `north_money_ma_60` | 60日北向净流入均值 | `avg(north_money,60)` |
| `north_money_ma_120` | 120日北向净流入均值 | `avg(north_money,120)` |
| `north_money_ma_250` | 250日北向净流入均值 | `avg(north_money,250)` |
| `north_money_sum_2` | 2日北向净流入累计 | `sum(north_money,2)` |
| `north_money_sum_3` | 3日北向净流入累计 | `sum(north_money,3)` |
| `north_money_sum_5` | 5日北向净流入累计 | `sum(north_money,5)` |
| `north_money_sum_10` | 10日北向净流入累计 | `sum(north_money,10)` |
| `north_money_sum_20` | 20日北向净流入累计 | `sum(north_money,20)` |
| `north_money_sum_30` | 30日北向净流入累计 | `sum(north_money,30)` |
| `north_money_sum_60` | 60日北向净流入累计 | `sum(north_money,60)` |
| `north_money_sum_120` | 120日北向净流入累计 | `sum(north_money,120)` |
| `north_money_sum_250` | 250日北向净流入累计 | `sum(north_money,250)` |
| `north_money_zscore_20` | 20日北向净流入Z值 | `(north_money - avg(north_money,20)) / stddev(north_money,20)` |
| `north_money_zscore_60` | 60日北向净流入Z值 | `(north_money - avg(north_money,60)) / stddev(north_money,60)` |
| `north_money_zscore_120` | 120日北向净流入Z值 | `(north_money - avg(north_money,120)) / stddev(north_money,120)` |
| `north_money_zscore_250` | 250日北向净流入Z值 | `(north_money - avg(north_money,250)) / stddev(north_money,250)` |
| `hgt` | 沪股通资金流 | `northbound_daily.hgt` |
| `sgt` | 深股通资金流 | `northbound_daily.sgt` |
| `north_hold_shares_chg_60` | 60日北向持股数量变化 | `hold_shares / lag(hold_shares,60) - 1` |
| `north_hold_shares_chg_120` | 120日北向持股数量变化 | `hold_shares / lag(hold_shares,120) - 1` |
| `north_hold_shares_chg_250` | 250日北向持股数量变化 | `hold_shares / lag(hold_shares,250) - 1` |
| `north_hold_ratio_chg_60` | 60日北向持股比例变化 | `hold_ratio - lag(hold_ratio,60)` |
| `north_hold_ratio_chg_120` | 120日北向持股比例变化 | `hold_ratio - lag(hold_ratio,120)` |
| `north_hold_ratio_chg_250` | 250日北向持股比例变化 | `hold_ratio - lag(hold_ratio,250)` |
| `updated_at` | 更新时间 | `CURRENT_TIMESTAMP` |

## 7. 事件缓存表：`derived_capital_flow_event_cache`

事件缓存表保存龙虎榜和机构席位聚合。未上榜股票也应在完整视图中得到 `0/false` 的事件字段，不能视为数据缺失。

### 7.1 字段清单

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `ts_code` | 股票代码 | 主键 |
| `trade_date` | 交易日期 | 主键 |
| `top_list_flag` | 是否龙虎榜上榜 | 当日 `top_list_daily` 有记录 |
| `top_list_net_amount` | 龙虎榜净买入额 | `top_list_daily.net_amount` |
| `top_list_net_rate` | 龙虎榜净买入率 | `top_list_daily.net_rate` |
| `top_list_amount_rate` | 龙虎榜成交额占比 | `top_list_daily.amount_rate` |
| `top_list_reason` | 龙虎榜上榜原因 | `top_list_daily.reason` |
| `top_inst_flag` | 是否有机构席位记录 | 当日 `top_inst_detail` 有记录 |
| `top_inst_buy_amount` | 机构席位买入额 | `sum(top_inst_detail.buy)` |
| `top_inst_sell_amount` | 机构席位卖出额 | `sum(top_inst_detail.sell)` |
| `top_inst_net_buy` | 机构席位净买入额 | `sum(top_inst_detail.net_buy)` |
| `top_inst_buy_sell_ratio` | 机构买卖比 | `buy_amount / sell_amount` |
| `top_inst_count` | 机构席位记录数 | `count(*)` |
| `top_list_days_2` | 2日龙虎榜上榜天数 | `sum(top_list_flag,2)` |
| `top_list_days_3` | 3日龙虎榜上榜天数 | `sum(top_list_flag,3)` |
| `top_list_days_5` | 5日龙虎榜上榜天数 | `sum(top_list_flag,5)` |
| `top_list_days_10` | 10日龙虎榜上榜天数 | `sum(top_list_flag,10)` |
| `top_list_days_20` | 20日龙虎榜上榜天数 | `sum(top_list_flag,20)` |
| `top_list_days_30` | 30日龙虎榜上榜天数 | `sum(top_list_flag,30)` |
| `top_list_days_60` | 60日龙虎榜上榜天数 | `sum(top_list_flag,60)` |
| `top_list_days_120` | 120日龙虎榜上榜天数 | `sum(top_list_flag,120)` |
| `top_list_days_250` | 250日龙虎榜上榜天数 | `sum(top_list_flag,250)` |
| `top_inst_net_buy_sum_2` | 2日机构净买入累计 | `sum(top_inst_net_buy,2)` |
| `top_inst_net_buy_sum_3` | 3日机构净买入累计 | `sum(top_inst_net_buy,3)` |
| `top_inst_net_buy_sum_5` | 5日机构净买入累计 | `sum(top_inst_net_buy,5)` |
| `top_inst_net_buy_sum_10` | 10日机构净买入累计 | `sum(top_inst_net_buy,10)` |
| `top_inst_net_buy_sum_20` | 20日机构净买入累计 | `sum(top_inst_net_buy,20)` |
| `top_inst_net_buy_sum_30` | 30日机构净买入累计 | `sum(top_inst_net_buy,30)` |
| `top_inst_net_buy_sum_60` | 60日机构净买入累计 | `sum(top_inst_net_buy,60)` |
| `top_inst_net_buy_sum_120` | 120日机构净买入累计 | `sum(top_inst_net_buy,120)` |
| `top_inst_net_buy_sum_250` | 250日机构净买入累计 | `sum(top_inst_net_buy,250)` |
| `updated_at` | 更新时间 | `CURRENT_TIMESTAMP` |

## 8. 完整视图：`derived_capital_flow_full_v`

完整视图在核心表基础上扩展更多周期和事件字段。字段分为核心继承、资金流周期扩展、两融扩展、北向扩展、龙虎榜事件扩展、市值成交交叉。

### 8.1 完整字段清单

```text
ts_code, trade_date,
small_buy_amount, small_sell_amount, small_net_amount,
medium_buy_amount, medium_sell_amount, medium_net_amount,
large_buy_amount, large_sell_amount, large_net_amount,
extra_large_buy_amount, extra_large_sell_amount, extra_large_net_amount,
main_net_amount, main_buy_amount, main_sell_amount, retail_net_amount,
net_mf_amount, net_mf_vol,
main_net_amount_rate, large_net_amount_rate, extra_large_net_amount_rate, small_net_amount_rate,
main_flow_ma_5, main_flow_ma_20, main_flow_sum_5, main_flow_sum_20,
main_flow_positive_days_20, main_flow_persist_ratio_20,
main_flow_to_total_mv_20, main_flow_to_circ_mv_20,
margin_balance, short_balance, margin_buy, margin_repay,
short_sell_volume, short_repay_volume, total_margin_short_balance,
margin_balance_chg_5, margin_balance_chg_20, margin_buy_to_amount, margin_short_ratio,
north_hold_shares, north_hold_ratio,
north_hold_shares_chg_5, north_hold_shares_chg_20, north_hold_ratio_chg_20,
has_moneyflow, has_margin, has_north_holding,
capital_flow_missing_reason,
main_flow_ma_2, main_flow_ma_3, main_flow_ma_10, main_flow_ma_30, main_flow_ma_250,
main_flow_sum_2, main_flow_sum_3, main_flow_sum_10, main_flow_sum_30, main_flow_sum_250,
main_flow_positive_days_2, main_flow_positive_days_3, main_flow_positive_days_5, main_flow_positive_days_10, main_flow_positive_days_20, main_flow_positive_days_30, main_flow_positive_days_60, main_flow_positive_days_120, main_flow_positive_days_250,
main_flow_persist_ratio_2, main_flow_persist_ratio_3, main_flow_persist_ratio_5, main_flow_persist_ratio_10, main_flow_persist_ratio_20, main_flow_persist_ratio_30, main_flow_persist_ratio_60, main_flow_persist_ratio_120, main_flow_persist_ratio_250,
main_flow_to_total_mv_2, main_flow_to_total_mv_3, main_flow_to_total_mv_5, main_flow_to_total_mv_10, main_flow_to_total_mv_30, main_flow_to_total_mv_60, main_flow_to_total_mv_120, main_flow_to_total_mv_250,
main_flow_to_circ_mv_2, main_flow_to_circ_mv_3, main_flow_to_circ_mv_5, main_flow_to_circ_mv_10, main_flow_to_circ_mv_30, main_flow_to_circ_mv_60, main_flow_to_circ_mv_120, main_flow_to_circ_mv_250,
large_net_amount_rate_ma_2, large_net_amount_rate_ma_3, large_net_amount_rate_ma_5, large_net_amount_rate_ma_10, large_net_amount_rate_ma_20, large_net_amount_rate_ma_30, large_net_amount_rate_ma_60, large_net_amount_rate_ma_120, large_net_amount_rate_ma_250,
extra_large_net_amount_rate_ma_2, extra_large_net_amount_rate_ma_3, extra_large_net_amount_rate_ma_5, extra_large_net_amount_rate_ma_10, extra_large_net_amount_rate_ma_20, extra_large_net_amount_rate_ma_30, extra_large_net_amount_rate_ma_60, extra_large_net_amount_rate_ma_120, extra_large_net_amount_rate_ma_250,
small_net_amount_rate_ma_2, small_net_amount_rate_ma_3, small_net_amount_rate_ma_5, small_net_amount_rate_ma_10, small_net_amount_rate_ma_20, small_net_amount_rate_ma_30, small_net_amount_rate_ma_60, small_net_amount_rate_ma_120, small_net_amount_rate_ma_250,
main_vs_retail_net_amount, main_vs_retail_net_amount_rate,
main_flow_price_divergence_20,
margin_balance_chg_2, margin_balance_chg_3, margin_balance_chg_10, margin_balance_chg_30, margin_balance_chg_250,
short_balance_chg_2, short_balance_chg_3, short_balance_chg_5, short_balance_chg_10, short_balance_chg_20, short_balance_chg_30, short_balance_chg_60, short_balance_chg_120, short_balance_chg_250,
total_margin_short_balance_chg_2, total_margin_short_balance_chg_3, total_margin_short_balance_chg_5, total_margin_short_balance_chg_10, total_margin_short_balance_chg_20, total_margin_short_balance_chg_30, total_margin_short_balance_chg_60, total_margin_short_balance_chg_120, total_margin_short_balance_chg_250,
margin_buy_ma_2, margin_buy_ma_3, margin_buy_ma_5, margin_buy_ma_10, margin_buy_ma_20, margin_buy_ma_30, margin_buy_ma_60, margin_buy_ma_120, margin_buy_ma_250,
margin_buy_to_amount_ma_2, margin_buy_to_amount_ma_3, margin_buy_to_amount_ma_5, margin_buy_to_amount_ma_10, margin_buy_to_amount_ma_20, margin_buy_to_amount_ma_30, margin_buy_to_amount_ma_60, margin_buy_to_amount_ma_120, margin_buy_to_amount_ma_250,
short_balance_to_margin_balance,
north_money, north_money_ma_2, north_money_ma_3, north_money_ma_5, north_money_ma_10, north_money_ma_20, north_money_ma_30, north_money_ma_60, north_money_ma_120, north_money_ma_250,
north_money_sum_2, north_money_sum_3, north_money_sum_5, north_money_sum_10, north_money_sum_20, north_money_sum_30, north_money_sum_60, north_money_sum_120, north_money_sum_250,
north_money_zscore_20, north_money_zscore_60, north_money_zscore_120, north_money_zscore_250,
hgt, sgt,
north_hold_shares_chg_60, north_hold_shares_chg_120, north_hold_shares_chg_250,
north_hold_ratio_chg_60, north_hold_ratio_chg_120, north_hold_ratio_chg_250,
top_list_flag, top_list_net_amount, top_list_net_rate, top_list_amount_rate, top_list_reason,
top_inst_flag, top_inst_buy_amount, top_inst_sell_amount, top_inst_net_buy,
top_inst_buy_sell_ratio, top_inst_count,
top_list_days_2, top_list_days_3, top_list_days_5, top_list_days_10, top_list_days_20, top_list_days_30, top_list_days_60, top_list_days_120, top_list_days_250,
top_inst_net_buy_sum_2, top_inst_net_buy_sum_3, top_inst_net_buy_sum_5, top_inst_net_buy_sum_10, top_inst_net_buy_sum_20, top_inst_net_buy_sum_30, top_inst_net_buy_sum_60, top_inst_net_buy_sum_120, top_inst_net_buy_sum_250,
updated_at
```

### 8.2 关键公式说明

| 字段 | 公式 |
|---|---|
| `main_net_amount` | `(buy_lg_amount - sell_lg_amount) + (buy_elg_amount - sell_elg_amount)` |
| `main_net_amount_rate` | `main_net_amount / amount`，实现阶段需实证 `moneyflow.amount` 与 `stock_daily.amount` 单位 |
| `main_flow_to_total_mv_N` | `sum(main_net_amount,N) / total_mv`，单位校准后计算 |
| `main_flow_price_divergence_20` | `sign(main_flow_sum_20) != sign(ret_20_hfq)`，事实型背离标记 |
| `margin_balance_chg_N` | `margin_balance / lag(margin_balance,N) - 1` |
| `north_hold_ratio_chg_N` | `north_hold_ratio - lag(north_hold_ratio,N)` |
| `top_list_days_N` | `sum(top_list_flag,N)` |

## 9. 字段规模

| 对象 | 类型 | 预计字段数 | 说明 |
|---|---|---:|---|
| `derived_capital_flow` | 核心物理表 | 65-70 | 高频资金流、两融、北向持仓核心字段，含 5/20/60/120 锚点周期 |
| `derived_northbound_flow_cache` | 物理缓存表 | 35-40 | 北向市场流、市场级滚动统计和长周期持仓变化 |
| `derived_capital_flow_event_cache` | 物理缓存表 | 30-35 | 龙虎榜与机构席位稀疏事件，含完整事件周期 |
| `derived_capital_flow_full_v` | 完整视图 | 190-220 | 核心表 + 缓存表 + 2/3/5/10/20/30/60/120/250 完整周期字段 |

## 10. 实施步骤

### 阶段 A：单位实证与边界确认

1. 实证 `stock_moneyflow_daily.*_amount` 与 `stock_daily.amount` 的单位关系。
2. 实证 `margin_detail.margin_buy` 与成交额单位关系。
3. 确认北向持股数据覆盖范围，缺失是否主要由非陆股通覆盖造成。

### 阶段 B：注册设计

1. 更新 `config/schema_registry.json`。
2. 注册 `derived_capital_flow` 核心变量。
3. 注册缓存表和完整视图 schema。
4. 刷新 Excel 数据字典。

### 阶段 C：构建核心物理表和缓存表

1. 全量构建 `derived_capital_flow`。
2. 全量构建 `derived_northbound_flow_cache`。
3. 全量构建 `derived_capital_flow_event_cache`。

### 阶段 D：创建完整视图与审计

1. 创建 `derived_capital_flow_full_v`。
2. 对最近 10 个交易日验证可查询性。
3. 审计覆盖率、非空率、事件稀疏性和单位校准结论。

## 11. 待确认问题

1. 已按要求修正周期体系：完整视图采用 2/3/5/10/20/30/60/120/250，核心物理表保留 5/20/60/120 锚点周期。
2. 已确认：龙虎榜和机构席位单独进入事件缓存表，而非直接进入核心物理表。
3. 待确认：是否接受北向市场流 `north_money/hgt/sgt` 作为“市场级背景变量”按交易日广播到个股完整视图？注意它不是个股北向买卖额。
4. 已确认：实现前先实证资金流金额单位；若发现与成交额单位不一致，按实证结果校准。
