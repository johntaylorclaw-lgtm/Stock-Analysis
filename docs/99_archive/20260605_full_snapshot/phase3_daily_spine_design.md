# Phase 3 `derived_daily_spine` 设计方案

生成日期：2026-05-31

## 1. 定位

`derived_daily_spine` 是所有日频衍生变量的股票-交易日主干表。它负责统一样本空间、价格口径、基础收益、交易约束和基础质量标记。

该表不承载复杂技术分析、财务分析或截面分析变量。复杂变量应进入后续领域表，例如 `derived_price_technical`、`derived_return_momentum`、`derived_financial_quality` 等。

主键：

| 字段 | 含义 |
|---|---|
| `ts_code` | 股票代码 |
| `trade_date` | 交易日 |

覆盖范围：全 A 股，含退市股票、北交所，历史起点沿用基础库从 2006 年开始。

## 2. 复权使用原则

用户确认的复权原则是正确的，应作为 Phase 3 变量设计的基础约束：

1. 对需要历史连续性的价格、收益、动量、波动、趋势类变量，优先使用后复权口径。
2. 对需要与当期财务、市值、估值、成交金额、股本、价格阈值或公告事件交叉解释的变量，应使用不复权口径或明确指定原始价格口径。
3. 前复权价格主要用于贴近当前交易观察和人工读图，不作为默认历史建模口径。
4. 所有变量必须在变量字典中明确 `price_basis`，避免后续使用者误把不同价格口径混用。

建议 `price_basis` 枚举：

| 取值 | 含义 | 适用场景 |
|---|---|---|
| `raw` | 不复权价格 | 估值、市值、成交额、涨跌停价、财务区间交叉、公告事件交叉 |
| `hfq` | 后复权价格 | 历史收益、动量、波动、均线、趋势、回撤 |
| `qfq_current` | 以前复权当前口径生成的价格 | 人工读图、贴近当前价格尺度的展示 |
| `not_price` | 非价格变量 | 财务、资金流、行业、概念、状态标记 |
| `mixed_explicit` | 多口径组合，必须在算法中显式说明 | 少数需要同时使用 raw 和 hfq 的变量 |

## 3. 数据字典维护要求

每个落库变量必须维护以下字段：

| 字典字段 | 说明 |
|---|---|
| `name` | 英文字段名，稳定、可查询 |
| `label_zh` | 中文变量名 |
| `description_zh` | 变量具体含义 |
| `table` | 所属物理表 |
| `module` | 所属模块 |
| `dtype` | 数据类型 |
| `unit` | 单位 |
| `frequency` | 频率 |
| `grain` | 粒度 |
| `source_fields` | 来源字段 |
| `formula_zh` | 中文算法说明 |
| `formula_sql` | 可落地 SQL 或伪 SQL |
| `price_basis` | 复权口径 |
| `point_in_time` | 是否点时安全 |
| `missing_policy` | 缺失处理规则 |
| `use_case_zh` | 变量用途 |
| `quality_check` | 质量检查规则 |

## 4. 建议字段结构

### 4.1 主键与状态

| 字段 | 中文名 | 含义 | 价格口径 |
|---|---|---|---|
| `ts_code` | 股票代码 | Tushare 股票代码 | `not_price` |
| `trade_date` | 交易日 | 日频交易日期 | `not_price` |
| `is_trade` | 是否交易 | 当日是否有行情记录 | `not_price` |
| `is_listed_asof` | 当日是否上市 | 该股票在当日是否已上市且未退市 | `not_price` |
| `list_status_asof` | 当日上市状态 | L/D/P 等状态 | `not_price` |
| `days_since_list` | 上市以来天数 | 从上市日到当前交易日的天数 | `not_price` |
| `market` | 市场板块 | 主板、创业板、科创板、北交所等 | `not_price` |
| `exchange` | 交易所 | SSE/SZSE/BSE | `not_price` |

### 4.2 原始行情

| 字段 | 中文名 | 含义 | 价格口径 |
|---|---|---|---|
| `open_raw` | 原始开盘价 | Tushare 日行情开盘价 | `raw` |
| `high_raw` | 原始最高价 | Tushare 日行情最高价 | `raw` |
| `low_raw` | 原始最低价 | Tushare 日行情最低价 | `raw` |
| `close_raw` | 原始收盘价 | Tushare 日行情收盘价 | `raw` |
| `pre_close_raw` | 原始昨收价 | Tushare 日行情昨收价 | `raw` |
| `change_raw` | 原始涨跌额 | 原始价格涨跌额 | `raw` |
| `pct_chg_raw` | 原始涨跌幅 | 原始价格涨跌幅 | `raw` |
| `volume` | 成交量 | 成交量，沿用 Tushare 单位 | `not_price` |
| `amount` | 成交额 | 成交额，沿用 Tushare 单位 | `not_price` |
| `amplitude_raw` | 原始振幅 | 原始高低价振幅 | `raw` |

### 4.3 复权价格

| 字段 | 中文名 | 含义 | 算法 | 价格口径 |
|---|---|---|---|---|
| `adj_factor` | 复权因子 | 当日复权因子 | 来自 `stock_adj_factor.adj_factor` | `not_price` |
| `latest_adj_factor_asof` | 最新复权因子 | 当前样本库最新复权因子 | 股票维度最新 `adj_factor` | `not_price` |
| `open_hfq` | 后复权开盘价 | 连续历史开盘价 | `open_raw * adj_factor` | `hfq` |
| `high_hfq` | 后复权最高价 | 连续历史最高价 | `high_raw * adj_factor` | `hfq` |
| `low_hfq` | 后复权最低价 | 连续历史最低价 | `low_raw * adj_factor` | `hfq` |
| `close_hfq` | 后复权收盘价 | 连续历史收盘价 | `close_raw * adj_factor` | `hfq` |
| `pre_close_hfq` | 后复权昨收价 | 连续历史昨收价 | `pre_close_raw * adj_factor` | `hfq` |
| `open_qfq` | 前复权开盘价 | 当前价格尺度开盘价 | `open_raw * adj_factor / latest_adj_factor_asof` | `qfq_current` |
| `high_qfq` | 前复权最高价 | 当前价格尺度最高价 | `high_raw * adj_factor / latest_adj_factor_asof` | `qfq_current` |
| `low_qfq` | 前复权最低价 | 当前价格尺度最低价 | `low_raw * adj_factor / latest_adj_factor_asof` | `qfq_current` |
| `close_qfq` | 前复权收盘价 | 当前价格尺度收盘价 | `close_raw * adj_factor / latest_adj_factor_asof` | `qfq_current` |
| `pre_close_qfq` | 前复权昨收价 | 当前价格尺度昨收价 | `pre_close_raw * adj_factor / latest_adj_factor_asof` | `qfq_current` |

说明：`qfq_current` 依赖当前数据库最新复权因子，不是严格 point-in-time 口径，应主要用于展示，不作为默认历史建模变量。

### 4.4 基础收益与日内结构

| 字段 | 中文名 | 含义 | 算法 | 价格口径 |
|---|---|---|---|---|
| `ret_1_raw` | 原始 1 日收益率 | 原始收盘价日收益 | `close_raw / lag(close_raw, 1) - 1` | `raw` |
| `ret_1_hfq` | 后复权 1 日收益率 | 连续历史日收益 | `close_hfq / lag(close_hfq, 1) - 1` | `hfq` |
| `log_ret_1_hfq` | 后复权 1 日对数收益率 | 连续历史对数收益 | `ln(close_hfq / lag(close_hfq, 1))` | `hfq` |
| `overnight_ret_hfq` | 隔夜收益率 | 昨收至今开收益 | `open_hfq / lag(close_hfq, 1) - 1` | `hfq` |
| `intraday_ret_hfq` | 日内收益率 | 今开至今收收益 | `close_hfq / open_hfq - 1` | `hfq` |
| `high_low_range_hfq` | 后复权日内振幅 | 高低价区间幅度 | `(high_hfq - low_hfq) / lag(close_hfq, 1)` | `hfq` |
| `gap_open_hfq` | 后复权开盘跳空 | 今开相对昨收跳空 | `open_hfq / lag(close_hfq, 1) - 1` | `hfq` |
| `close_position_hfq` | 收盘区间位置 | 收盘处于当日高低区间的位置 | `(close_hfq - low_hfq) / nullif(high_hfq - low_hfq, 0)` | `hfq` |

收益、趋势、波动相关字段默认采用 `hfq`，因为它们要求历史连续性。

### 4.5 涨跌停与交易约束基础

涨跌停价本身是交易规则下的真实当日价格，不应复权。

| 字段 | 中文名 | 含义 | 算法 | 价格口径 |
|---|---|---|---|---|
| `up_limit` | 涨停价 | 当日涨停价格 | 来自 `stock_limit_price.up_limit` | `raw` |
| `down_limit` | 跌停价 | 当日跌停价格 | 来自 `stock_limit_price.down_limit` | `raw` |
| `limit_up_flag` | 收盘涨停 | 收盘价达到涨停价 | `close_raw >= up_limit * threshold` | `raw` |
| `limit_down_flag` | 收盘跌停 | 收盘价达到跌停价 | `close_raw <= down_limit * threshold` | `raw` |
| `touch_limit_up_flag` | 盘中触及涨停 | 最高价触及涨停价 | `high_raw >= up_limit * threshold` | `raw` |
| `touch_limit_down_flag` | 盘中触及跌停 | 最低价触及跌停价 | `low_raw <= down_limit * threshold` | `raw` |
| `open_limit_up_flag` | 开盘涨停 | 开盘价达到涨停价 | `open_raw >= up_limit * threshold` | `raw` |
| `open_limit_down_flag` | 开盘跌停 | 开盘价达到跌停价 | `open_raw <= down_limit * threshold` | `raw` |
| `limit_up_gap` | 距涨停空间 | 收盘价距离涨停价比例 | `up_limit / close_raw - 1` | `raw` |
| `limit_down_gap` | 距跌停空间 | 收盘价距离跌停价比例 | `close_raw / down_limit - 1` | `raw` |

### 4.6 质量字段

| 字段 | 中文名 | 含义 |
|---|---|---|
| `has_price` | 有行情价格 | OHLC 至少满足基本可用 |
| `has_adj_factor` | 有复权因子 | 当日复权因子非空 |
| `has_limit_price` | 有涨跌停价 | 涨停价和跌停价可用 |
| `price_valid_flag` | 价格关系有效 | 高低开收关系满足基本逻辑 |
| `missing_reason` | 缺失原因 | 初步解释缺失来源 |
| `updated_at` | 更新时间 | 构建更新时间 |

## 5. 与当前落库版本差距

当前 `derived_daily_spine` 仅有：

| 当前字段 | 处理建议 |
|---|---|
| `close_hfq` | 保留 |
| `log_ret_1` | 重命名为 `log_ret_1_hfq` |
| `limit_up_flag` | 保留，但算法明确使用 `raw` 价格 |
| `updated_at` | 保留 |

下一步应扩展 schema、构建器和变量注册表，并重建历史全量数据。
