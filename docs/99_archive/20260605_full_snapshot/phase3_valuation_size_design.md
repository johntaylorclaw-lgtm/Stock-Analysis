# Phase 3 估值与规模模块设计

生成日期：2026-06-01

状态：完整设计稿，待实现。

已确认边界：

1. 核心物理表可扩展到约 34 列，并保留 `pe_ttm_pct_5y` 作为兼容字段。
2. 完整视图使用 `1y/3y/5y/10y` 历史分位窗口，即 `250/750/1250/2500` 交易日。
3. `free_float_mv` 暂按 `close_raw * free_share` 推导，实现阶段用样本与 `total_mv/circ_mv` 单位关系校准。
4. 财务交叉估值先实现依赖已存在字段的部分，暂缺字段进入后续增强。

## 1. 设计目标

估值与规模模块负责把日频估值、市值、股本、股息率和财务 asof 变量连接成可复用的事实型衍生变量。模块不生成主观综合分，不做选股评价，只维护可解释、可复现、可审计的估值与规模事实。

本模块沿用交易行情与技术分析模块的混合结构：

1. 核心物理表：保存高频使用、增量计算稳定、字段数量适中的估值与规模变量。
2. 完整视图：保存更宽的周期分位、估值变化、估值-财务交叉变量，按需计算。
3. 历史分位缓存表：`derived_valuation_percentile_cache` 物理保存滚动历史分位，供完整视图轻量 join，避免查询完整视图时重复构造 10 年滚动窗口。
4. 后续可选物化：若完整视图中的其他字段成为稳定高频需求，再拆分物化子表。

## 2. 口径原则

| 场景 | 口径 | 说明 |
|---|---|---|
| PE/PB/PS/股息率 | Tushare `stock_daily_basic` 原始口径 | 保留源数据口径，不用复权价格重算 |
| 总市值/流通市值 | Tushare `stock_daily_basic.total_mv/circ_mv` | 单位为万元，属于当日市场事实 |
| 股本结构 | Tushare `total_share/float_share/free_share` | 单位保持源表口径 |
| 盈利收益率、账面市值比等倒数指标 | 由估值原始字段派生 | 对 PE/PB/PS 为 0、空值或负值时保留空值或特殊标记字段，不做主观修正 |
| 财务交叉估值 | 连接 `derived_financial_quality`、`derived_financial_growth` | 使用 asof 口径，避免未来函数 |
| 历史分位 | 只使用截至当日的历史窗口 | 窗口包含当前日，空值不参与分位计算 |
| 行业相对估值 | 后续行业上下文模块确认后进入增强 | 本阶段可预留视图字段组，但不依赖未确认行业口径 |

## 3. 数据来源

| 来源表 | 主要字段 | 用途 |
|---|---|---|
| `stock_daily_basic` | `pe`, `pe_ttm`, `pb`, `ps`, `ps_ttm`, `dv_ratio`, `dv_ttm` | 估值与股息率基础 |
| `stock_daily_basic` | `total_share`, `float_share`, `free_share`, `total_mv`, `circ_mv` | 股本、市值、规模 |
| `stock_daily_basic` | `turnover_rate`, `turnover_rate_free`, `volume_ratio` | 与规模交叉的换手/拥挤度辅助字段 |
| `derived_daily_spine` | `close_raw`, `amount`, `has_price`, `is_listed_asof`, `market`, `exchange` | 交易状态、市值成交比、质量控制 |
| `derived_financial_quality` | `roe_asof`, `bps_asof`, `eps_asof`, `ocfps_asof`, `cfps_asof` | 估值-质量交叉 |
| `derived_financial_growth` | `revenue_yoy_asof`, `parent_net_profit_yoy_asof` 等 | PEG、估值-成长交叉 |

## 4. 周期体系

估值与规模变量的周期不同于技术指标。建议使用“交易日窗口 + 年度窗口”混合体系：

```text
短期变化窗口：2, 3, 5, 10, 20, 30, 60, 120, 250
历史分位窗口：250, 750, 1250, 2500
历史分位别名：1y, 3y, 5y, 10y
```

说明：

1. 估值分位更适合用年度窗口，避免过多短周期分位制造噪音。
2. 市值、估值变化率可使用短期变化窗口，方便观察估值扩张/收缩。
3. 完整视图可比核心物理表更宽，但仍避免无法解释的评分变量。

## 5. 核心物理表：`derived_valuation_size`

核心物理表保留日常最常用字段，目标控制在 40 列以内。

### 5.1 完整字段清单

| 字段 | 中文名 | 衍生逻辑 | 口径 |
|---|---|---|---|
| `ts_code` | 股票代码 | 主键 | not_price |
| `trade_date` | 交易日期 | 主键 | not_price |
| `pe` | 市盈率 | `stock_daily_basic.pe` | source |
| `pe_ttm` | 滚动市盈率 | `stock_daily_basic.pe_ttm` | source |
| `pb` | 市净率 | `stock_daily_basic.pb` | source |
| `ps` | 市销率 | `stock_daily_basic.ps` | source |
| `ps_ttm` | 滚动市销率 | `stock_daily_basic.ps_ttm` | source |
| `dv_ratio` | 股息率 | `stock_daily_basic.dv_ratio` | source |
| `dv_ttm` | 滚动股息率 | `stock_daily_basic.dv_ttm` | source |
| `total_share` | 总股本 | `stock_daily_basic.total_share` | source |
| `float_share` | 流通股本 | `stock_daily_basic.float_share` | source |
| `free_share` | 自由流通股本 | `stock_daily_basic.free_share` | source |
| `total_mv` | 总市值 | `stock_daily_basic.total_mv` | source |
| `circ_mv` | 流通市值 | `stock_daily_basic.circ_mv` | source |
| `free_float_mv` | 自由流通市值 | `close_raw * free_share`，单位需与源表股本口径校准 | raw/source |
| `log_total_mv` | 总市值对数 | `ln(total_mv)` | source |
| `log_circ_mv` | 流通市值对数 | `ln(circ_mv)` | source |
| `log_free_float_mv` | 自由流通市值对数 | `ln(free_float_mv)` | source |
| `float_share_ratio` | 流通股本占比 | `float_share / total_share` | ratio |
| `free_share_ratio` | 自由流通股本占比 | `free_share / total_share` | ratio |
| `earnings_yield_ttm` | 滚动盈利收益率 | `1 / pe_ttm`，仅 `pe_ttm > 0` | ratio |
| `book_to_price` | 账面市值比 | `1 / pb`，仅 `pb > 0` | ratio |
| `sales_yield_ttm` | 滚动销售收益率 | `1 / ps_ttm`，仅 `ps_ttm > 0` | ratio |
| `dividend_yield_ttm` | 滚动股息收益率 | `dv_ttm / 100` | ratio |
| `pe_ttm_pct_5y` | 5年PE_TTM历史分位 | `percentile_rank(pe_ttm, 1250日历史窗口)` | source |
| `pb_pct_5y` | 5年PB历史分位 | `percentile_rank(pb, 1250日历史窗口)` | source |
| `ps_ttm_pct_5y` | 5年PS_TTM历史分位 | `percentile_rank(ps_ttm, 1250日历史窗口)` | source |
| `total_mv_pct_5y` | 5年总市值历史分位 | `percentile_rank(total_mv, 1250日历史窗口)` | source |
| `pe_ttm_valid_flag` | PE_TTM有效标记 | `pe_ttm > 0` | quality |
| `pb_valid_flag` | PB有效标记 | `pb > 0` | quality |
| `ps_ttm_valid_flag` | PS_TTM有效标记 | `ps_ttm > 0` | quality |
| `mv_valid_flag` | 市值有效标记 | `total_mv > 0 and circ_mv > 0` | quality |
| `valuation_missing_reason` | 估值缺失原因 | `missing_daily_basic/missing_price/invalid_valuation/null` | quality |
| `updated_at` | 更新时间 | `CURRENT_TIMESTAMP` | metadata |

核心物理表最终字段：

```text
ts_code, trade_date,
pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm,
total_share, float_share, free_share,
total_mv, circ_mv, free_float_mv,
log_total_mv, log_circ_mv, log_free_float_mv,
float_share_ratio, free_share_ratio,
earnings_yield_ttm, book_to_price, sales_yield_ttm, dividend_yield_ttm,
pe_ttm_pct_5y, pb_pct_5y, ps_ttm_pct_5y, total_mv_pct_5y,
pe_ttm_valid_flag, pb_valid_flag, ps_ttm_valid_flag, mv_valid_flag,
valuation_missing_reason,
updated_at
```

### 5.2 核心表保留理由

1. PE/PB/PS/股息率是日常最常用估值事实，应物理化。
2. 市值与规模对截面分析、行业聚合、流动性筛选非常常用，应物理化。
3. 5年分位是核心估值状态，但只保留 5y 一组，避免核心表过宽。
4. 1y/3y/10y 分位、变化率、估值-财务交叉放入完整视图。

## 6. 完整视图：`derived_valuation_size_full_v`

完整视图在核心表基础上扩展更丰富周期和交叉变量。以下为完整字段设计，不再仅作示例。

完整视图字段规模预计为 149 列：

```text
核心继承字段 34
估值基础扩展 7
历史分位扩展 29
估值/市值变化率 54
估值/市值均线 20
规模结构扩展 5
财务交叉估值 8
```

## 6A. 历史分位缓存表：`derived_valuation_percentile_cache`

由于 1年/3年/5年/10年滚动历史分位在完整视图中即时计算会消耗大量内存，本模块将全部历史分位物理缓存到 `derived_valuation_percentile_cache`。该表不是核心业务宽表，而是完整视图的性能支撑层。

字段范围：

```text
ts_code, trade_date,
pe_pct_1y, pe_pct_3y, pe_pct_5y, pe_pct_10y,
pe_ttm_pct_1y, pe_ttm_pct_3y, pe_ttm_pct_5y, pe_ttm_pct_10y,
pb_pct_1y, pb_pct_3y, pb_pct_5y, pb_pct_10y,
ps_pct_1y, ps_pct_3y, ps_pct_5y, ps_pct_10y,
ps_ttm_pct_1y, ps_ttm_pct_3y, ps_ttm_pct_5y, ps_ttm_pct_10y,
dv_ratio_pct_1y, dv_ratio_pct_3y, dv_ratio_pct_5y, dv_ratio_pct_10y,
dv_ttm_pct_1y, dv_ttm_pct_3y, dv_ttm_pct_5y, dv_ttm_pct_10y,
total_mv_pct_1y, total_mv_pct_3y, total_mv_pct_5y, total_mv_pct_10y,
circ_mv_pct_1y, circ_mv_pct_3y, circ_mv_pct_5y, circ_mv_pct_10y,
free_float_mv_pct_1y, free_float_mv_pct_3y, free_float_mv_pct_5y, free_float_mv_pct_10y,
updated_at
```

实现口径：

```text
rolling_percentile_rank(field, window) = 当前值在同股票最近 window 个交易样本中的百分位排名
```

空值不参与排序；当前值为空时分位为空。核心表中的 `pe_ttm_pct_5y`、`pb_pct_5y`、`ps_ttm_pct_5y`、`total_mv_pct_5y` 由该缓存表同步回填，保持兼容。

### 6.1 估值基础扩展

| 字段 | 中文名 | 衍生逻辑 | 口径 |
|---|---|---|---|
| `earnings_yield` | 静态盈利收益率 | `1 / pe`，仅 `pe > 0` | ratio |
| `sales_yield` | 静态销售收益率 | `1 / ps`，仅 `ps > 0` | ratio |
| `dividend_yield` | 静态股息收益率 | `dv_ratio / 100` | ratio |
| `log_pe_ttm` | PE_TTM对数 | `ln(pe_ttm)`，仅 `pe_ttm > 0` | source |
| `log_pb` | PB对数 | `ln(pb)`，仅 `pb > 0` | source |
| `log_ps_ttm` | PS_TTM对数 | `ln(ps_ttm)`，仅 `ps_ttm > 0` | source |
| `dv_valid_flag` | 股息率有效标记 | `dv_ratio IS NOT NULL OR dv_ttm IS NOT NULL` | quality |

### 6.2 历史分位扩展

历史分位窗口：

```text
1y = 250
3y = 750
5y = 1250
10y = 2500
```

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `pe_pct_1y`, `pe_pct_3y`, `pe_pct_5y`, `pe_pct_10y` | PE历史分位 | `percentile_rank(pe, window)` |
| `pe_ttm_pct_1y`, `pe_ttm_pct_3y`, `pe_ttm_pct_5y`, `pe_ttm_pct_10y` | PE_TTM历史分位 | `percentile_rank(pe_ttm, window)` |
| `pb_pct_1y`, `pb_pct_3y`, `pb_pct_5y`, `pb_pct_10y` | PB历史分位 | `percentile_rank(pb, window)` |
| `ps_pct_1y`, `ps_pct_3y`, `ps_pct_5y`, `ps_pct_10y` | PS历史分位 | `percentile_rank(ps, window)` |
| `ps_ttm_pct_1y`, `ps_ttm_pct_3y`, `ps_ttm_pct_5y`, `ps_ttm_pct_10y` | PS_TTM历史分位 | `percentile_rank(ps_ttm, window)` |
| `dv_ratio_pct_1y`, `dv_ratio_pct_3y`, `dv_ratio_pct_5y`, `dv_ratio_pct_10y` | 静态股息率历史分位 | `percentile_rank(dv_ratio, window)` |
| `dv_ttm_pct_1y`, `dv_ttm_pct_3y`, `dv_ttm_pct_5y`, `dv_ttm_pct_10y` | 滚动股息率历史分位 | `percentile_rank(dv_ttm, window)` |
| `total_mv_pct_1y`, `total_mv_pct_3y`, `total_mv_pct_5y`, `total_mv_pct_10y` | 总市值历史分位 | `percentile_rank(total_mv, window)` |
| `circ_mv_pct_1y`, `circ_mv_pct_3y`, `circ_mv_pct_5y`, `circ_mv_pct_10y` | 流通市值历史分位 | `percentile_rank(circ_mv, window)` |
| `free_float_mv_pct_1y`, `free_float_mv_pct_3y`, `free_float_mv_pct_5y`, `free_float_mv_pct_10y` | 自由流通市值历史分位 | `percentile_rank(free_float_mv, window)` |

说明：分位为事实型历史位置，不是评分。分位值越高仅表示当前值处于自身历史更高位置，不代表好坏。

### 6.3 估值变化率扩展

短期变化窗口：

```text
2, 3, 5, 10, 20, 30, 60, 120, 250
```

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `pe_ttm_chg_2`, `pe_ttm_chg_3`, `pe_ttm_chg_5`, `pe_ttm_chg_10`, `pe_ttm_chg_20`, `pe_ttm_chg_30`, `pe_ttm_chg_60`, `pe_ttm_chg_120`, `pe_ttm_chg_250` | PE_TTM变化率 | `pe_ttm / lag(pe_ttm, N) - 1` |
| `pb_chg_2`, `pb_chg_3`, `pb_chg_5`, `pb_chg_10`, `pb_chg_20`, `pb_chg_30`, `pb_chg_60`, `pb_chg_120`, `pb_chg_250` | PB变化率 | `pb / lag(pb, N) - 1` |
| `ps_ttm_chg_2`, `ps_ttm_chg_3`, `ps_ttm_chg_5`, `ps_ttm_chg_10`, `ps_ttm_chg_20`, `ps_ttm_chg_30`, `ps_ttm_chg_60`, `ps_ttm_chg_120`, `ps_ttm_chg_250` | PS_TTM变化率 | `ps_ttm / lag(ps_ttm, N) - 1` |
| `total_mv_chg_2`, `total_mv_chg_3`, `total_mv_chg_5`, `total_mv_chg_10`, `total_mv_chg_20`, `total_mv_chg_30`, `total_mv_chg_60`, `total_mv_chg_120`, `total_mv_chg_250` | 总市值变化率 | `total_mv / lag(total_mv, N) - 1` |
| `circ_mv_chg_2`, `circ_mv_chg_3`, `circ_mv_chg_5`, `circ_mv_chg_10`, `circ_mv_chg_20`, `circ_mv_chg_30`, `circ_mv_chg_60`, `circ_mv_chg_120`, `circ_mv_chg_250` | 流通市值变化率 | `circ_mv / lag(circ_mv, N) - 1` |
| `free_float_mv_chg_2`, `free_float_mv_chg_3`, `free_float_mv_chg_5`, `free_float_mv_chg_10`, `free_float_mv_chg_20`, `free_float_mv_chg_30`, `free_float_mv_chg_60`, `free_float_mv_chg_120`, `free_float_mv_chg_250` | 自由流通市值变化率 | `free_float_mv / lag(free_float_mv, N) - 1` |

变化率公式：

```text
field_chg_N = field / lag(field, N) - 1
```

仅当当前值和滞后值均为正时计算，否则为空。

估值与市值均线字段：

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `pe_ttm_ma_20`, `pe_ttm_ma_60`, `pe_ttm_ma_120`, `pe_ttm_ma_250` | PE_TTM均值 | `avg(pe_ttm, N)` |
| `pb_ma_20`, `pb_ma_60`, `pb_ma_120`, `pb_ma_250` | PB均值 | `avg(pb, N)` |
| `ps_ttm_ma_20`, `ps_ttm_ma_60`, `ps_ttm_ma_120`, `ps_ttm_ma_250` | PS_TTM均值 | `avg(ps_ttm, N)` |
| `total_mv_ma_20`, `total_mv_ma_60`, `total_mv_ma_120`, `total_mv_ma_250` | 总市值均值 | `avg(total_mv, N)` |
| `circ_mv_ma_20`, `circ_mv_ma_60`, `circ_mv_ma_120`, `circ_mv_ma_250` | 流通市值均值 | `avg(circ_mv, N)` |

### 6.4 规模结构扩展

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `float_to_total_share_ratio` | 流通股本占总股本比例 | `float_share / total_share` |
| `free_to_total_share_ratio` | 自由流通股本占总股本比例 | `free_share / total_share` |
| `free_to_float_share_ratio` | 自由流通股本占流通股本比例 | `free_share / float_share` |
| `circ_mv_to_total_mv_ratio` | 流通市值占总市值比例 | `circ_mv / total_mv` |
| `free_float_mv_to_total_mv_ratio` | 自由流通市值占总市值比例 | `free_float_mv / total_mv` |
| `amount_to_total_mv` | 成交额占总市值比例 | `derived_daily_spine.amount / total_mv`，需单位校准 |
| `amount_to_circ_mv` | 成交额占流通市值比例 | `derived_daily_spine.amount / circ_mv`，需单位校准 |

### 6.5 财务交叉估值扩展

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `peg_ttm` | PEG_TTM | `pe_ttm / parent_net_profit_yoy_asof`，仅增长率为正时计算 |
| `pb_to_roe` | PB/ROE | `pb / roe_asof`，仅 ROE 为正时计算 |
| `pe_to_roe` | PE/ROE | `pe_ttm / roe_asof`，仅 PE 和 ROE 为正时计算 |
| `price_to_bps_asof` | 每股价格/每股净资产 | `close_raw / bps_asof` |
| `price_to_eps_asof` | 每股价格/每股收益 | `close_raw / eps_asof` |
| `price_to_ocfps_asof` | 每股价格/每股经营现金流 | `close_raw / ocfps_asof` |
| `market_cap_to_parent_profit` | 总市值/归母净利润 | `total_mv / parent_net_profit_asof`，需单位校准 |
| `market_cap_to_ocf` | 总市值/经营现金流 | `total_mv / net_cashflow_oper_act_asof`，需字段可得后实现 |

说明：财务交叉变量只使用已 asof 的财务数据，不能直接连接未来披露的报表。

### 6.6 完整视图最终字段清单

```text
ts_code, trade_date,
pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm,
total_share, float_share, free_share,
total_mv, circ_mv, free_float_mv,
log_total_mv, log_circ_mv, log_free_float_mv,
float_share_ratio, free_share_ratio,
earnings_yield_ttm, book_to_price, sales_yield_ttm, dividend_yield_ttm,
pe_ttm_pct_5y, pb_pct_5y, ps_ttm_pct_5y, total_mv_pct_5y,
pe_ttm_valid_flag, pb_valid_flag, ps_ttm_valid_flag, mv_valid_flag,
valuation_missing_reason,
earnings_yield, sales_yield, dividend_yield,
log_pe_ttm, log_pb, log_ps_ttm, dv_valid_flag,
pe_pct_1y, pe_pct_3y, pe_pct_5y, pe_pct_10y,
pe_ttm_pct_1y, pe_ttm_pct_3y, pe_ttm_pct_5y, pe_ttm_pct_10y,
pb_pct_1y, pb_pct_3y, pb_pct_5y, pb_pct_10y,
ps_pct_1y, ps_pct_3y, ps_pct_5y, ps_pct_10y,
ps_ttm_pct_1y, ps_ttm_pct_3y, ps_ttm_pct_5y, ps_ttm_pct_10y,
dv_ratio_pct_1y, dv_ratio_pct_3y, dv_ratio_pct_5y, dv_ratio_pct_10y,
dv_ttm_pct_1y, dv_ttm_pct_3y, dv_ttm_pct_5y, dv_ttm_pct_10y,
total_mv_pct_1y, total_mv_pct_3y, total_mv_pct_5y, total_mv_pct_10y,
circ_mv_pct_1y, circ_mv_pct_3y, circ_mv_pct_5y, circ_mv_pct_10y,
free_float_mv_pct_1y, free_float_mv_pct_3y, free_float_mv_pct_5y, free_float_mv_pct_10y,
pe_ttm_chg_2, pe_ttm_chg_3, pe_ttm_chg_5, pe_ttm_chg_10, pe_ttm_chg_20, pe_ttm_chg_30, pe_ttm_chg_60, pe_ttm_chg_120, pe_ttm_chg_250,
pb_chg_2, pb_chg_3, pb_chg_5, pb_chg_10, pb_chg_20, pb_chg_30, pb_chg_60, pb_chg_120, pb_chg_250,
ps_ttm_chg_2, ps_ttm_chg_3, ps_ttm_chg_5, ps_ttm_chg_10, ps_ttm_chg_20, ps_ttm_chg_30, ps_ttm_chg_60, ps_ttm_chg_120, ps_ttm_chg_250,
total_mv_chg_2, total_mv_chg_3, total_mv_chg_5, total_mv_chg_10, total_mv_chg_20, total_mv_chg_30, total_mv_chg_60, total_mv_chg_120, total_mv_chg_250,
circ_mv_chg_2, circ_mv_chg_3, circ_mv_chg_5, circ_mv_chg_10, circ_mv_chg_20, circ_mv_chg_30, circ_mv_chg_60, circ_mv_chg_120, circ_mv_chg_250,
free_float_mv_chg_2, free_float_mv_chg_3, free_float_mv_chg_5, free_float_mv_chg_10, free_float_mv_chg_20, free_float_mv_chg_30, free_float_mv_chg_60, free_float_mv_chg_120, free_float_mv_chg_250,
pe_ttm_ma_20, pe_ttm_ma_60, pe_ttm_ma_120, pe_ttm_ma_250,
pb_ma_20, pb_ma_60, pb_ma_120, pb_ma_250,
ps_ttm_ma_20, ps_ttm_ma_60, ps_ttm_ma_120, ps_ttm_ma_250,
total_mv_ma_20, total_mv_ma_60, total_mv_ma_120, total_mv_ma_250,
circ_mv_ma_20, circ_mv_ma_60, circ_mv_ma_120, circ_mv_ma_250,
float_to_total_share_ratio, free_to_total_share_ratio, free_to_float_share_ratio,
circ_mv_to_total_mv_ratio, free_float_mv_to_total_mv_ratio,
amount_to_total_mv, amount_to_circ_mv,
peg_ttm, pb_to_roe, pe_to_roe,
price_to_bps_asof, price_to_eps_asof, price_to_ocfps_asof,
market_cap_to_parent_profit,
updated_at
```

## 7. 完整视图建议字段规模

| 字段组 | 预计字段数 |
|---|---:|
| 核心表继承字段 | 34 |
| 估值基础扩展 | 7 |
| 历史分位扩展 | 36 |
| 估值/市值变化率 | 54 |
| 估值/市值均线 | 20 |
| 规模结构 | 7 |
| 财务交叉估值 | 7 |
| 合计 | 165 |

视图字段数量较多，但不物理落库，查询时按需计算。若后续性能压力明显，可优先物化历史分位字段。

## 8. 实施步骤

### 阶段 A：注册设计

1. 扩展 `config/schema_registry.json` 中 `derived_valuation_size`。
2. 新增 `derived_valuation_size_full_v` 视图表项。
3. 注册核心物理变量，完整视图进入 schema 字典。
4. 刷新 Excel 数据字典。

### 阶段 B：核心物理表构建

1. 重建 `derived_valuation_size`。
2. 保留旧字段 `pe_ttm_pct_5y` 的兼容含义，但统一口径为 1250 交易日窗口。
3. 全历史年度分片构建。

### 阶段 C：完整视图创建

1. 创建 `derived_valuation_size_full_v`。
2. 对最近 10 个交易日验证字段可查询性。
3. 对历史分位、变化率、财务交叉字段抽样验证。

### 阶段 D：质量审计

审计项目：

1. 行数、股票数、日期范围与 `derived_daily_spine` 对齐。
2. PE/PB/PS/市值字段非空率。
3. 负 PE、负 PB、空 PE 的分布。
4. 历史分位初始窗口空值是否合理。
5. 自由流通市值单位是否与 Tushare 市值单位一致。
6. 财务交叉变量是否严格使用 asof 财务表。
7. Excel 数据字典中文名、公式、口径是否与代码一致。

## 9. 已确认问题

1. 接受核心物理表扩展到约 34 列，并保留 `pe_ttm_pct_5y` 作为兼容字段。
2. 接受完整视图使用 `1y/3y/5y/10y` 历史分位窗口，即 `250/750/1250/2500` 交易日。
3. `free_float_mv` 暂按 `close_raw * free_share` 推导，实现阶段用样本与 `total_mv/circ_mv` 单位关系校准后确定最终公式。
4. 财务交叉估值先实现依赖已存在字段的部分，对暂缺字段进入后续增强。
