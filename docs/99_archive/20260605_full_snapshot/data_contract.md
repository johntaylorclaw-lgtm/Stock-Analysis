# Phase 1 前置设计：数据契约

生成日期：2026-05-27  
项目定位：股票数据维护工程  
设计原则：数据尽量丰富详实，字段命名稳定，优先连接 Tushare 可获取数据源，所有低频数据必须可 point-in-time 映射。

## 1. 数据契约目标

本文件定义 Phase 1 进入代码实现前的数据契约，包括：

1. 新项目需要维护的数据域。
2. 每个基础表的主键、时间键、字段命名和 Tushare 可获取来源。
3. 财务明细、概念板块、市场环境等需要增强的基础数据设计。
4. 日频连接方式、缺失策略和更新频率。

本工程不做选股、回测、训练标签。它只负责把股票数据维护成可复现、可审计、可连接、可导出的基础库和变量库。

## 2. Tushare 可获取性基线

设计基础变量时优先使用 Tushare Pro。原项目已经稳定使用了 `stock_basic`、`daily`、`daily_basic`、`adj_factor`、`index_daily`、`moneyflow`、`margin_detail`、`income`、`balancesheet`、`cashflow`、`fina_indicator`、`concept`、`concept_detail` 等接口。

官方权限页显示，Tushare 股票、财务、指数等接口覆盖面较广：日线 `daily`、每日指标 `daily_basic`、龙虎榜 `top_list/top_inst`、融资融券 `margin/margin_detail`、资金流 `moneyflow`、涨跌停价格 `stk_limit`、沪深股通持股 `hk_hold`、利润表 `income`、资产负债表 `balancesheet`、现金流量表 `cashflow`、业绩预告 `forecast`、业绩快报 `express`、分红送股 `dividend`、财务指标 `fina_indicator`、审计意见 `fina_audit`、主营业务构成 `fina_mainbz`、财报披露计划 `disclosure_date`、指数行情 `index_daily`、指数成分权重 `index_weight`、申万行业分类 `index_classify` 和申万行业成分 `index_member_all` 等均在权限清单中。Tushare 的 `daily_basic` 文档也明确返回换手率、量比、PE/PB/PS、股息率、股本、市值等字段。

### 2.1 实证验证结论

已使用老项目 `.env` 中的 Tushare token 做小样本 API 调用验证，详见 `docs/tushare_api_feasibility_20260527.md`。验证结论：

| 主题 | 实证结果 |
|---|---|
| A 股上市股票 | `stock_basic(exchange="", list_status="L")` 返回 5,524 只 |
| A 股退市股票 | `stock_basic(exchange="", list_status="D")` 返回 325 只 |
| 市场覆盖 | 深交所主板/创业板、上交所主板/科创板、北交所均可识别 |
| 日线行情 | `daily(trade_date=20260526)` 返回 5,504 行 |
| 日度基础指标 | `daily_basic(trade_date=20260526)` 返回 5,504 行、18 列 |
| 涨跌停价格 | `stk_limit(trade_date=20260526)` 返回 7,619 行 |
| 指数基础信息 | `index_basic` 在 SSE/SZSE/CSI/CNI/SW 市场均可用 |
| 指数成分权重 | `index_weight` 对上证指数、上证50、沪深300、中证500、中证1000、深证成指、创业板指均可用 |
| 申万行业 | `index_classify(src=SW2021)`、`index_member_all` 可用 |
| 概念 | `concept`、`concept_detail` 可用 |
| 财务三大报表 | `income` 85 列、`balancesheet` 152 列、`cashflow` 97 列可用 |
| 财务增强 | 财务指标、预告、审计、主营构成、股东户数、十大股东、十大流通股东、回购等接口可用 |

因此，Phase 1 数据设计应以实证可用接口为基础，并为事件稀疏接口保留表结构。

参考：

- [Tushare Pro 权限与接口清单](https://tushare.pro/document/2?doc_id=108)
- [Tushare daily_basic 文档](https://tushare.pro/document/2?doc_id=32)

## 3. 命名规范

### 3.1 通用规则

| 规则 | 说明 |
|---|---|
| 字段名 | 英文 `snake_case` |
| 股票代码 | 统一使用 `ts_code`，格式如 `600519.SH` |
| 交易日期 | 日频数据统一使用 `trade_date`，类型 `DATE` |
| 公告日期 | 财务和事件数据使用 `ann_date`，类型 `DATE` |
| 报告期 | 财报使用 `end_date`，类型 `DATE` |
| 生效日期 | 低频数据映射到日频时使用 `effective_date` |
| 更新时间 | 表内维护字段统一使用 `updated_at` |
| 来源字段 | 如需保留原始字段名，使用 `source_field` 元数据，不直接混入业务字段 |
| 金额单位 | 字段元数据必须声明单位，表字段名不强行加单位后缀，除非同表存在多个单位 |

### 3.2 常用后缀

| 后缀 | 含义 |
|---|---|
| `_raw` | 原始未复权或源值 |
| `_qfq` | 前复权口径 |
| `_hfq` | 后复权口径 |
| `_rate` | 比率，通常百分比或小数需在元数据中声明 |
| `_ratio` | 比值 |
| `_amount` | 金额 |
| `_volume` | 成交量或数量 |
| `_mv` | 市值 |
| `_flag` | 0/1 标记 |
| `_status` | 状态枚举 |
| `_count` | 数量 |
| `_rank` | 排名 |
| `_pct` | 分位或百分位 |

### 3.3 口径规则

| 变量类型 | 默认价格口径 |
|---|---|
| 行情源表 | 原始不复权价格 |
| 技术、收益、波动变量 | 后复权价格，字段使用 `_hfq` 或元数据声明 |
| 估值、市值、股本变量 | 原始价格或 Tushare `daily_basic` 字段 |
| 成交额、资金流 | 源数据原始金额口径 |
| 财务变量 | 公告日可得口径，不按报告期末提前可用 |

## 4. 数据域总览

| 域 | 表前缀 | 说明 | Phase 1 优先级 |
|---|---|---|---|
| S0 证券主数据 | `security_*`、`stock_*` | 股票身份、上市状态、公司信息 | P0 |
| S1 交易日历 | `trade_*` | A 股交易日历和时间维度 | P0 |
| S2 行情 | `stock_daily`、`index_daily` | 个股和指数 OHLCV | P0 |
| S3 复权与公司行为 | `stock_adj_factor`、`corporate_action_*` | 复权因子、分红、送转、股本变动 | P0 |
| S4 日度基础指标 | `stock_daily_basic` | 换手、估值、市值、股本 | P0 |
| S5 资金交易行为 | `stock_moneyflow_*`、`margin_*`、`northbound_*`、`top_list_*` | 资金流、两融、北向、龙虎榜 | P1 |
| S6 财务 | `financial_*` | 三大报表、指标、明细、披露计划 | P0/P1 |
| S7 行业/概念/指数成分 | `sector_*`、`concept_*`、`index_*` | 行业、概念、成分、映射历史 | P1 |
| S8 市场环境 | `market_*` | 市场宽度、涨跌停、风格环境 | P1 |
| S9 元数据 | `metadata_*`、`audit_*` | 字段、变量、血缘、质量、任务状态 | P0 |

### 4.1 股票范围确认

新项目引入 A 股全部市场，不做子集抽样：

| 交易所 | 市场 | 是否纳入 | 实证上市数量 |
|---|---|---|---:|
| SSE | 主板 | 是 | 1,705 |
| SSE | 科创板 | 是 | 610 |
| SZSE | 主板 | 是 | 1,495 |
| SZSE | 创业板 | 是 | 1,398 |
| BSE | 北交所 | 是 | 316 |

同时保留退市股票历史。实证 `list_status="D"` 返回 325 只退市股票，需进入证券主数据和历史行情/财务维护范围。暂停上市 `list_status="P"` 当前样本返回 0 行，但表结构保留该状态。

股票池维护规则：

1. 默认股票池 = `list_status in ("L", "D", "P")` 的全部 A 股证券。
2. 日常行情更新只追踪当前上市和可交易股票。
3. 历史库、财务库、公司行为和退市前行情必须保留退市股票。
4. `stock_basic_info` 保存当前快照，`stock_status_history` 保存状态历史。

### 4.2 默认指数池

新项目设置指数基础数据，包括指数基本信息、指数行情和指数成分权重。指数池配置化，第一阶段默认包含：

| 指数代码 | 指数名称 | 类型 | 用途 |
|---|---|---|---|
| `000001.SH` | 上证指数 | 交易所宽基 | 市场基准 |
| `000016.SH` | 上证50 | 大盘蓝筹 | 风格/规模基准 |
| `000688.SH` | 科创50 | 科创板 | 科创板基准 |
| `000300.SH` | 沪深300 | 宽基核心 | 默认 Beta/Alpha 基准 |
| `000905.SH` | 中证500 | 中盘 | 规模风格 |
| `000852.SH` | 中证1000 | 小盘 | 规模风格 |
| `399001.SZ` | 深证成指 | 交易所宽基 | 深市基准 |
| `399006.SZ` | 创业板指 | 创业板 | 创业板基准 |
| `399005.SZ` | 中小100 | 深市规模 | 可选风格 |
| `399300.SZ` | 沪深300 | 深交所行情代码 | 兼容 |

指数表：

| 表 | 说明 | 来源 |
|---|---|---|
| `index_basic_info` | 指数基本信息 | Tushare `index_basic` |
| `index_daily` | 指数日线行情 | Tushare `index_daily` |
| `index_weight` | 指数成分和权重 | Tushare `index_weight` |

指数成分股列表必须纳入数据维护，用于指数成员标记、指数权重、相对收益、Beta、行业/风格暴露等基础变量。

## 5. P0 基础表设计

### 5.1 `trade_calendar`

用途：统一交易日期基准。

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `cal_date` | DATE | 日历日期，主键 | Tushare `trade_cal` |
| `exchange` | VARCHAR | 交易所，默认 `SSE`/`SZSE` 或 `A` | Tushare `trade_cal` |
| `is_open` | BOOLEAN | 是否交易日 | Tushare `trade_cal` |
| `pretrade_date` | DATE | 前一交易日 | Tushare `trade_cal` |
| `next_trade_date` | DATE | 后一交易日，本地推导 | 本地 |
| `is_month_end_trade` | BOOLEAN | 是否月末交易日 | 本地 |
| `is_quarter_end_trade` | BOOLEAN | 是否季末交易日 | 本地 |
| `updated_at` | TIMESTAMP | 更新时间 | 本地 |

主键：`(cal_date, exchange)`。  
默认日频任务使用 A 股统一日历时，可在视图中暴露 `cal_date` 单主键。

### 5.2 `stock_basic_info`

用途：股票主数据当前快照。

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `ts_code` | VARCHAR | 股票代码，主键 | Tushare `stock_basic` |
| `symbol` | VARCHAR | 纯数字代码 | Tushare `stock_basic` |
| `name` | VARCHAR | 股票简称 | Tushare `stock_basic` |
| `area` | VARCHAR | 地域 | Tushare `stock_basic` |
| `industry` | VARCHAR | Tushare 行业名称 | Tushare `stock_basic` |
| `market` | VARCHAR | 主板、创业板、科创板、北交所等 | Tushare `stock_basic` |
| `exchange` | VARCHAR | SH/SZ/BJ | 从 `ts_code` 推导 |
| `list_status` | VARCHAR | L/D/P | Tushare `stock_basic` |
| `list_date` | DATE | 上市日期 | Tushare `stock_basic` |
| `delist_date` | DATE | 退市日期 | Tushare `stock_basic` |
| `is_active` | BOOLEAN | 当前是否上市交易 | 本地 |
| `is_st` | BOOLEAN | 当前是否 ST，后续可从名称/状态源推导 | Tushare/本地 |
| `company_name` | VARCHAR | 公司全称 | Tushare `stock_company`，可选增强 |
| `legal_representative` | VARCHAR | 法人代表 | Tushare `stock_company`，可选 |
| `registered_capital` | DOUBLE | 注册资本 | Tushare `stock_company`，可选 |
| `province` | VARCHAR | 省份 | Tushare/本地标准化 |
| `city` | VARCHAR | 城市 | Tushare/本地标准化 |
| `website` | VARCHAR | 公司网站 | Tushare `stock_company`，可选 |
| `business_scope` | VARCHAR | 经营范围 | Tushare `stock_company`，可选 |
| `updated_at` | TIMESTAMP | 更新时间 | 本地 |

主键：`ts_code`。

### 5.3 `stock_status_history`

用途：保存证券状态历史，避免只有当前快照。

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `ts_code` | VARCHAR | 股票代码 | Tushare `stock_basic`/本地快照 |
| `effective_date` | DATE | 状态生效日期 | 本地快照差异 |
| `list_status` | VARCHAR | L/D/P | Tushare |
| `name` | VARCHAR | 当时简称 | Tushare |
| `is_st` | BOOLEAN | 是否 ST | 名称/状态源推导 |
| `change_reason` | VARCHAR | 状态变化原因 | 本地/可选源 |
| `updated_at` | TIMESTAMP | 更新时间 | 本地 |

主键：`(ts_code, effective_date)`。

### 5.4 `stock_daily`

用途：个股日行情原始事实表。

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `ts_code` | VARCHAR | 股票代码 | Tushare `daily` |
| `trade_date` | DATE | 交易日 | Tushare `daily` |
| `open` | DOUBLE | 开盘价，原始不复权 | Tushare `daily` |
| `high` | DOUBLE | 最高价，原始不复权 | Tushare `daily` |
| `low` | DOUBLE | 最低价，原始不复权 | Tushare `daily` |
| `close` | DOUBLE | 收盘价，原始不复权 | Tushare `daily` |
| `pre_close` | DOUBLE | 昨收价 | Tushare `daily` |
| `change` | DOUBLE | 涨跌额 | Tushare `daily` |
| `pct_chg` | DOUBLE | 涨跌幅，百分比 | Tushare `daily` |
| `volume` | DOUBLE | 成交量，手；源字段 `vol` | Tushare `daily` |
| `amount` | DOUBLE | 成交额，千元；源字段 `amount` | Tushare `daily` |
| `amplitude` | DOUBLE | 振幅，本地或源补充 | 本地 |
| `is_trading` | BOOLEAN | 是否真实交易 | 本地 |
| `updated_at` | TIMESTAMP | 更新时间 | 本地 |

主键：`(ts_code, trade_date)`。

### 5.5 `stock_adj_factor`

用途：复权因子基础表。

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `ts_code` | VARCHAR | 股票代码 | Tushare `adj_factor` |
| `trade_date` | DATE | 交易日 | Tushare `adj_factor` |
| `adj_factor` | DOUBLE | Tushare 原始复权因子 | Tushare `adj_factor` |
| `qfq_factor` | DOUBLE | 前复权因子，若无法独立获取则与 `adj_factor` 同源并标注 | Tushare/本地 |
| `hfq_factor` | DOUBLE | 后复权因子，若无法独立获取则与 `adj_factor` 同源并标注 | Tushare/本地 |
| `factor_source` | VARCHAR | 因子来源和算法说明 | 本地 |
| `updated_at` | TIMESTAMP | 更新时间 | 本地 |

主键：`(ts_code, trade_date)`。  
注意：原项目将 `adj_factor` 同时写入 `qfq_factor` 和 `hfq_factor`，新项目必须在元数据中明确该口径，后续可考虑使用 `pro_bar` 或独立算法校验前/后复权价格。

### 5.6 `stock_daily_basic`

用途：日度估值、市值、股本、换手基础表。该表是一等源表。

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `ts_code` | VARCHAR | 股票代码 | Tushare `daily_basic` |
| `trade_date` | DATE | 交易日 | Tushare `daily_basic` |
| `close` | DOUBLE | 当日收盘价 | Tushare `daily_basic` |
| `turnover_rate` | DOUBLE | 换手率，% | Tushare `daily_basic` |
| `turnover_rate_f` | DOUBLE | 自由流通股换手率，% | Tushare `daily_basic` |
| `volume_ratio` | DOUBLE | 量比 | Tushare `daily_basic` |
| `pe` | DOUBLE | 静态市盈率 | Tushare `daily_basic` |
| `pe_ttm` | DOUBLE | TTM 市盈率 | Tushare `daily_basic` |
| `pb` | DOUBLE | 市净率 | Tushare `daily_basic` |
| `ps` | DOUBLE | 市销率 | Tushare `daily_basic` |
| `ps_ttm` | DOUBLE | TTM 市销率 | Tushare `daily_basic` |
| `dv_ratio` | DOUBLE | 股息率，% | Tushare `daily_basic` |
| `dv_ttm` | DOUBLE | TTM 股息率，% | Tushare `daily_basic` |
| `total_share` | DOUBLE | 总股本，万股 | Tushare `daily_basic` |
| `float_share` | DOUBLE | 流通股本，万股 | Tushare `daily_basic` |
| `free_share` | DOUBLE | 自由流通股本，万股 | Tushare `daily_basic` |
| `total_mv` | DOUBLE | 总市值，万元 | Tushare `daily_basic` |
| `circ_mv` | DOUBLE | 流通市值，万元 | Tushare `daily_basic` |
| `updated_at` | TIMESTAMP | 更新时间 | 本地 |

主键：`(ts_code, trade_date)`。

## 6. 财务数据增强设计

财务域必须比原项目更细。原项目的 `financial_detail` 过于混合，新项目拆分为标准报表、指标、披露、分红、主营构成、股东、审计、业绩预告/快报等子域。

### 6.0 财务报表设计原则

实证验证显示，当前 token 下三大报表可获取字段远多于原项目实际入库字段：

| 报表 | Tushare API | 实证字段数 | 原项目问题 | 新项目设计 |
|---|---|---:|---|---|
| 利润表 | `income` | 85 | 只保留约 19 个字段 | 建 `financial_income_raw` 保留详细字段，另建标准化视图 |
| 资产负债表 | `balancesheet` | 152 | 只保留约 25 个字段 | 建 `financial_balance_raw` 保留详细字段，另建标准化视图 |
| 现金流量表 | `cashflow` | 97 | 只保留约 13 个字段 | 建 `financial_cashflow_raw` 保留详细字段，另建标准化视图 |
| 财务指标 | `fina_indicator` | 108 | 只保留约 29 个字段 | 建 `financial_indicator_raw` 保留详细字段，另建标准化视图 |

因此新项目采用三层结构：

1. Raw wide 表：尽量展开 Tushare 返回字段为物理列，充分利用 DuckDB 列式查询和逐列审计。
2. `payload_json` 留痕：raw wide 表同时保留原始 payload，作为字段变更兜底和审计快照。
3. Standard/asof 表或视图：将关键字段重命名为稳定变量名，供衍生变量和日频映射使用。

财务表统一要求：

| 字段 | 规则 |
|---|---|
| `ann_date` | 公告日期 |
| `first_ann_date` | 来源 `f_ann_date`，如果存在 |
| `end_date` | 报告期 |
| `report_type` | 报告类型 |
| `comp_type` | 合并/母公司类型 |
| `end_type` | 报告期类型，若源提供 |
| `effective_date` | 日频可用日，默认取 `first_ann_date` 优先，否则 `ann_date` |
| `update_flag` | 源提供时保留，用于修订识别 |

Raw 表字段很多，不应在普通业务代码里手写维护 300 多个字段。Phase 2 应通过 API 字段探测生成 raw wide 字段清单，写入 `metadata_table_schema`，人工审阅关键字段命名映射后再生成 DDL。

### 6.1 `financial_income`

来源：Tushare `income`。  
Raw 表：`financial_income_raw`。  
标准化表/视图：`financial_income`。  
主键：`(ts_code, end_date, comp_type, report_type, ann_date)`。

核心字段：

| 字段 | 类型 | 说明 | 来源字段 |
|---|---|---|---|
| `ts_code` | VARCHAR | 股票代码 | `ts_code` |
| `ann_date` | DATE | 公告日 | `ann_date` |
| `f_ann_date` | DATE | 实际公告日/首次公告日 | `f_ann_date` |
| `end_date` | DATE | 报告期 | `end_date` |
| `report_type` | VARCHAR | 报告类型 | `report_type` |
| `comp_type` | VARCHAR | 合并/母公司 | `comp_type` |
| `total_revenue` | DOUBLE | 营业总收入 | `total_revenue` |
| `revenue` | DOUBLE | 营业收入 | `revenue`，增强字段 |
| `operating_cost` | DOUBLE | 营业成本 | `oper_cost` |
| `selling_expense` | DOUBLE | 销售费用 | `sell_exp` |
| `admin_expense` | DOUBLE | 管理费用 | `admin_exp` |
| `rd_expense` | DOUBLE | 研发费用 | `rd_exp` |
| `finance_expense` | DOUBLE | 财务费用 | `fin_exp` |
| `operating_profit` | DOUBLE | 营业利润 | `operate_profit` |
| `total_profit` | DOUBLE | 利润总额 | `total_profit` |
| `income_tax` | DOUBLE | 所得税 | `income_tax` |
| `net_profit` | DOUBLE | 净利润 | `n_income` |
| `n_income_attr_p` | DOUBLE | 归母净利润 | `n_income_attr_p` |
| `minority_profit` | DOUBLE | 少数股东损益 | `minority_int` |
| `basic_eps` | DOUBLE | 基本 EPS | `basic_eps` |
| `diluted_eps` | DOUBLE | 稀释 EPS | `diluted_eps` |
| `effective_date` | DATE | 日频可用日 | `ann_date`/`f_ann_date` |
| `updated_at` | TIMESTAMP | 更新时间 | 本地 |

Raw 表还应保留以下详细字段组：

| 字段组 | 来源字段示例 | 说明 |
|---|---|---|
| 金融行业收入 | `int_income`、`prem_earned`、`comm_income`、`n_commis_income` | 银行、保险、券商适用 |
| 投资收益 | `fv_value_chg_gain`、`invest_income`、`ass_invest_income`、`forex_gain` | 公允价值、投资和汇兑损益 |
| 成本费用明细 | `total_cogs`、`biz_tax_surchg`、`assets_impair_loss`、`credit_impa_loss` | 成本、税金、减值 |
| 非经常损益 | `non_oper_income`、`non_oper_exp`、`nca_disploss` | 非经营项目 |
| 综合收益 | `oth_compr_income`、`t_compr_income`、`compr_inc_attr_p` | 综合收益 |
| EBIT/EBITDA | `ebit`、`ebitda` | 财务质量和估值使用 |
| 利润分配 | `undist_profit`、`distable_profit`、`distr_profit_shrhder` | 分配相关 |

### 6.2 `financial_balance`

来源：Tushare `balancesheet`。  
Raw 表：`financial_balance_raw`。  
标准化表/视图：`financial_balance`。  
主键：`(ts_code, end_date, comp_type, report_type, ann_date)`。

建议字段覆盖：

| 字段 | 说明 | 来源字段 |
|---|---|---|
| `total_assets` | 总资产 | `total_assets` |
| `current_assets` | 流动资产 | `total_cur_assets` |
| `cash_and_equivalents` | 货币资金 | `money_cap` |
| `accounts_receivable` | 应收账款 | `accounts_receiv` |
| `notes_receivable` | 应收票据 | Tushare 可用则接入 |
| `prepayment` | 预付款项 | Tushare 可用则接入 |
| `inventories` | 存货 | `inventories` |
| `fixed_assets` | 固定资产 | `fix_assets` |
| `construction_in_process` | 在建工程 | 可用则接入 |
| `goodwill` | 商誉 | `goodwill` |
| `intangible_assets` | 无形资产 | `intan_assets` |
| `total_liabilities` | 总负债 | `total_liab` |
| `current_liabilities` | 流动负债 | `total_cur_liab` |
| `short_term_borrowings` | 短期借款 | `st_borr` |
| `accounts_payable` | 应付账款 | `acct_payable` |
| `long_term_borrowings` | 长期借款 | `lt_borr` |
| `bonds_payable` | 应付债券 | `bond_payable` |
| `total_equity` | 所有者权益合计 | `total_hldr_eqy_inc_min_int` |
| `equity_attr_p` | 归母权益 | `total_hldr_eqy_exc_min_int` |
| `minority_interest` | 少数股东权益 | `minority_int` |
| `total_shares` | 期末总股本 | `total_share` |

Raw 表还应保留以下详细字段组：

| 字段组 | 来源字段示例 | 说明 |
|---|---|---|
| 流动资产明细 | `trad_asset`、`notes_receiv`、`oth_receiv`、`prepayment`、`div_receiv`、`int_receiv`、`oth_cur_assets` | 资产质量分析 |
| 非流动资产明细 | `lt_eqt_invest`、`invest_real_estate`、`lt_rec`、`cip`、`r_and_d`、`lt_amor_exp`、`defer_tax_assets`、`total_nca` | 长期资产结构 |
| 金融行业资产 | `cash_reser_cb`、`depos_in_oth_bfi`、`premium_receiv`、`refund_depos`、`client_depos` | 银行、保险、券商适用 |
| 流动负债明细 | `cb_borr`、`depos_ib_deposits`、`trading_fl`、`notes_payable`、`adv_receipts`、`taxes_payable`、`oth_payable` | 短期负债结构 |
| 非流动负债明细 | `lt_payable`、`specific_payables`、`defer_tax_liab`、`defer_inc_non_cur_liab`、`total_ncl` | 长期负债结构 |
| 权益明细 | `treasury_share`、`surplus_rese`、`special_rese`、`oth_eqt_tools`、`oth_compr_income` | 股东权益结构 |

### 6.3 `financial_cashflow`

来源：Tushare `cashflow`。  
Raw 表：`financial_cashflow_raw`。  
标准化表/视图：`financial_cashflow`。  
主键：`(ts_code, end_date, comp_type, report_type, ann_date)`。

建议字段覆盖：

| 字段 | 说明 | 来源字段 |
|---|---|---|
| `cf_from_operating` | 经营活动现金流净额 | `n_cashflow_act` |
| `cash_received_from_sales` | 销售商品、提供劳务收到的现金 | `c_fr_sale_sg` |
| `cf_from_investing` | 投资活动现金流净额 | `n_cashflow_inv_act` |
| `cf_from_financing` | 筹资活动现金流净额 | `n_cash_flows_fnc_act` |
| `capex` | 购建固定资产等支付现金 | 可用则接入 |
| `net_increase_in_cash` | 现金及等价物净增加 | `n_incr_cash_cash_equ` |
| `cash_at_beginning` | 期初现金 | `c_cash_equ_beg_period` |
| `cash_at_end` | 期末现金 | `c_cash_equ_end_period` |
| `ocfps` | 每股经营现金流 | `ocfps` |

Raw 表还应保留以下详细字段组：

| 字段组 | 来源字段示例 | 说明 |
|---|---|---|
| 经营现金流入 | `c_fr_sale_sg`、`recp_tax_rends`、`c_fr_oth_operate_a`、`c_inf_fr_operate_a` | 经营现金来源 |
| 经营现金流出 | `c_paid_goods_s`、`c_paid_to_for_empl`、`c_paid_for_taxes`、`oth_cash_pay_oper_act`、`st_cash_out_act` | 经营现金支出 |
| 投资现金流 | `c_disp_withdrwl_invest`、`c_recp_return_invest`、`c_pay_acq_const_fiolta`、`c_paid_invest`、`stot_inflows_inv_act`、`stot_out_inv_act` | 投资活动明细 |
| 筹资现金流 | `c_recp_borrow`、`proc_issue_bonds`、`c_prepay_amt_borr`、`c_pay_dist_dpcp_int_exp`、`stot_cash_in_fnc_act`、`stot_cashout_fnc_act` | 筹资活动明细 |
| 间接法补充 | `depr_fa_coga_dpba`、`amort_intang_assets`、`decr_inventories`、`decr_oper_payable` | 现金流质量分析 |
| 自由现金流 | `free_cashflow` | 如源提供则保留 |

### 6.4 `financial_indicator`

来源：Tushare `fina_indicator`。  
Raw 表：`financial_indicator_raw`。  
标准化表/视图：`financial_indicator`。  
主键：`(ts_code, end_date, ann_date)`。

字段分组：

| 分组 | 推荐字段 |
|---|---|
| 每股指标 | `eps`、`dt_eps`、`bps`、`ocfps`、`cfps` |
| 盈利能力 | `roe`、`roa`、`gross_margin`、`net_margin`、`profit_dedt` |
| 偿债能力 | `debt_ratio`、`current_ratio`、`quick_ratio`、`equity_ratio` |
| 成长能力 | `revenue_yoy`、`profit_yoy`、`assets_yoy`、`or_yoy` |
| 营运能力 | `ar_turnover`、`inventory_turnover`、`assets_turnover` |
| 现金流质量 | `cf_sales`、`ocf_to_profit`，可源字段或本地推导 |

Raw 表应完整保留 Tushare 返回的每股指标、盈利能力、偿债能力、营运能力、成长能力、资本结构、现金流质量和杜邦分析相关字段。标准化视图只暴露命名稳定、口径明确的字段。

估值指标仍以 `stock_daily_basic` 为日频基准，财务指标表不承担日度估值职责。

### 6.5 `financial_disclosure_schedule`

来源：Tushare `disclosure_date`。  
用途：财报披露计划和实际披露日期。

| 字段 | 类型 | 说明 |
|---|---|---|
| `ts_code` | VARCHAR | 股票代码 |
| `end_date` | DATE | 报告期 |
| `pre_date` | DATE | 预计披露日期 |
| `actual_date` | DATE | 实际披露日期 |
| `modify_date` | DATE | 修订日期 |
| `updated_at` | TIMESTAMP | 更新时间 |

主键：`(ts_code, end_date)`。

### 6.6 `financial_forecast`

来源：Tushare `forecast`。  
用途：业绩预告。

字段建议：`ts_code`、`ann_date`、`end_date`、`type`、`p_change_min`、`p_change_max`、`net_profit_min`、`net_profit_max`、`last_parent_net`、`first_ann_date`、`summary`、`change_reason`、`effective_date`。

主键：`(ts_code, end_date, ann_date)`。

### 6.7 `financial_express`

来源：Tushare `express`。  
用途：业绩快报。

字段建议：`ts_code`、`ann_date`、`end_date`、`revenue`、`operate_profit`、`total_profit`、`n_income`、`total_assets`、`total_hldr_eqy_exc_min_int`、`diluted_eps`、`diluted_roe`、`yoy_sales`、`yoy_op`、`yoy_tp`、`yoy_dedu_np`、`effective_date`。

主键：`(ts_code, end_date, ann_date)`。

### 6.8 `financial_dividend`

来源：Tushare `dividend`。  
用途：分红送股、除权除息、现金分红。

字段建议：`ts_code`、`end_date`、`ann_date`、`div_proc`、`stk_div`、`stk_bo_rate`、`stk_co_rate`、`cash_div`、`cash_div_tax`、`record_date`、`ex_date`、`pay_date`、`div_listdate`、`implementation_status`。

主键：`(ts_code, end_date, ann_date, ex_date)`。

### 6.9 `financial_audit`

来源：Tushare `fina_audit`。  
用途：审计意见、审计机构。

字段建议：`ts_code`、`ann_date`、`end_date`、`audit_result`、`audit_fees`、`audit_agency`、`audit_sign`、`effective_date`。

主键：`(ts_code, end_date, ann_date)`。

### 6.10 `financial_main_business`

来源：Tushare `fina_mainbz`。  
用途：主营业务构成。

| 字段 | 类型 | 说明 |
|---|---|---|
| `ts_code` | VARCHAR | 股票代码 |
| `end_date` | DATE | 报告期 |
| `ann_date` | DATE | 公告日 |
| `bz_item` | VARCHAR | 业务项目 |
| `bz_code` | VARCHAR | 项目代码，如源支持 |
| `bz_type` | VARCHAR | 按产品/行业/地区 |
| `currency` | VARCHAR | 币种 |
| `revenue` | DOUBLE | 主营收入 |
| `cost` | DOUBLE | 主营成本 |
| `profit` | DOUBLE | 主营利润 |
| `gross_margin` | DOUBLE | 毛利率 |
| `revenue_ratio` | DOUBLE | 收入占比 |
| `effective_date` | DATE | 可用日 |

主键：`(ts_code, end_date, bz_type, bz_item)`。

### 6.11 `holder_number`

来源：Tushare `stk_holdernumber`。  
用途：股东户数。

字段建议：`ts_code`、`ann_date`、`end_date`、`holder_num`、`holder_num_change`、`holder_num_rate`、`effective_date`。

主键：`(ts_code, end_date, ann_date)`。

### 6.12 股东和股本扩展

Phase 1 设计保留以下表位，具体字段在实现前根据 Tushare 当前权限和返回字段确认：

| 表 | 来源候选 | 用途 |
|---|---|---|
| `top10_holders` | Tushare 十大股东相关接口 | 十大股东持股比例、集中度 |
| `top10_float_holders` | Tushare 十大流通股东相关接口 | 流通股东集中度 |
| `share_float_unlock` | `share_float` | 限售股解禁 |
| `pledge_detail` | `pledge_detail` | 股权质押明细 |
| `pledge_stat` | `pledge_stat` | 股权质押统计 |
| `repurchase` | `repurchase` | 股票回购 |

这些表进入“丰富数据域”，但可按权限和稳定性分批接入。

## 7. 行业、概念和板块增强设计

### 7.1 `sector_classification`

用途：行业分类体系定义。

来源候选：Tushare `index_classify`，申万行业分类优先；保留 Tushare 行业和同花顺行业作为备用分类体系。

| 字段 | 类型 | 说明 |
|---|---|---|
| `class_system` | VARCHAR | 分类体系，如 `sw`、`ths`、`tushare` |
| `sector_code` | VARCHAR | 行业代码 |
| `sector_name` | VARCHAR | 行业名称 |
| `level` | INTEGER | 层级 |
| `parent_code` | VARCHAR | 父级行业代码 |
| `src` | VARCHAR | 来源 |
| `updated_at` | TIMESTAMP | 更新时间 |

主键：`(class_system, sector_code)`。

### 7.2 `sector_member_history`

用途：股票行业归属历史。

来源候选：Tushare `index_member_all`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `class_system` | VARCHAR | 分类体系 |
| `sector_code` | VARCHAR | 行业代码 |
| `ts_code` | VARCHAR | 股票代码 |
| `in_date` | DATE | 纳入日期 |
| `out_date` | DATE | 剔除日期 |
| `is_new` | BOOLEAN | 是否新纳入 |
| `updated_at` | TIMESTAMP | 更新时间 |

主键：`(class_system, sector_code, ts_code, in_date)`。

### 7.3 `concept_basic`

用途：概念定义。

来源候选：Tushare `concept`，必要时补充 THS/其他来源。

| 字段 | 类型 | 说明 |
|---|---|---|
| `concept_code` | VARCHAR | 概念代码 |
| `concept_name` | VARCHAR | 概念名称 |
| `source` | VARCHAR | 来源，如 `tushare` |
| `description` | VARCHAR | 概念描述，可选 |
| `created_date` | DATE | 创建日期，可选 |
| `updated_at` | TIMESTAMP | 更新时间 |

主键：`(source, concept_code)`。

### 7.4 `concept_member_history`

用途：股票-概念映射历史。

来源候选：Tushare `concept_detail`。若源只提供当前成分，新项目通过每日快照差异构造历史。

| 字段 | 类型 | 说明 |
|---|---|---|
| `source` | VARCHAR | 来源 |
| `concept_code` | VARCHAR | 概念代码 |
| `ts_code` | VARCHAR | 股票代码 |
| `in_date` | DATE | 首次观察到纳入 |
| `out_date` | DATE | 首次观察到剔除 |
| `is_active` | BOOLEAN | 当前是否属于该概念 |
| `snapshot_date` | DATE | 最近一次快照日期 |
| `updated_at` | TIMESTAMP | 更新时间 |

主键：`(source, concept_code, ts_code, in_date)`。

### 7.5 `concept_daily`

用途：概念日频聚合表现。若 Tushare/第三方直接概念行情不可稳定获取，可由成员股日频聚合。

| 字段 | 类型 | 说明 |
|---|---|---|
| `source` | VARCHAR | 概念来源 |
| `concept_code` | VARCHAR | 概念代码 |
| `trade_date` | DATE | 交易日 |
| `member_count` | INTEGER | 成分股数量 |
| `ret_equal_weight` | DOUBLE | 等权收益 |
| `ret_mv_weight` | DOUBLE | 市值加权收益 |
| `amount` | DOUBLE | 成交额合计 |
| `turnover_rate` | DOUBLE | 成分加权换手 |
| `limit_up_count` | INTEGER | 涨停家数 |
| `limit_down_count` | INTEGER | 跌停家数 |
| `main_net_inflow` | DOUBLE | 主力净流入合计 |
| `hot_score` | DOUBLE | 热度分，本地聚合 |

主键：`(source, concept_code, trade_date)`。

## 8. 资金、两融、北向和交易行为

### 8.1 `stock_moneyflow_daily`

来源：Tushare `moneyflow`。

字段：`ts_code`、`trade_date`、`buy_sm_amount`、`sell_sm_amount`、`buy_md_amount`、`sell_md_amount`、`buy_lg_amount`、`sell_lg_amount`、`buy_elg_amount`、`sell_elg_amount`、`net_mf_amount`、`main_net_inflow`、`main_net_inflow_rate`。

主键：`(ts_code, trade_date)`。

### 8.2 `margin_detail`

来源：Tushare `margin_detail`。

字段：`ts_code`、`trade_date`、`margin_balance`、`margin_buy`、`margin_repay`、`short_balance`、`short_sell`、`short_repay`、`short_amount`、`total_balance`。

主键：`(ts_code, trade_date)`。

### 8.3 `northbound_daily`

来源：Tushare `moneyflow_hsgt`。

字段：`trade_date`、`north_money`、`sh_net`、`sz_net`、`hgt`、`sgt`、`source_status`。

主键：`trade_date`。

### 8.4 `northbound_holding`

来源：优先 Tushare `hk_hold`；原项目 `hsgt_top10` 只覆盖 Top10，信息不完整。

字段：`ts_code`、`trade_date`、`hold_shares`、`hold_value`、`hold_ratio`、`exchange_type`、`source_status`。

主键：`(ts_code, trade_date, exchange_type)`。

### 8.5 `top_list_daily` 和 `top_inst_detail`

来源：Tushare `top_list`、`top_inst`。

用途：龙虎榜每日明细和机构席位明细。

字段建议：

| 表 | 字段 |
|---|---|
| `top_list_daily` | `ts_code`、`trade_date`、`name`、`close`、`pct_chg`、`turnover_rate`、`amount`、`l_sell`、`l_buy`、`l_amount`、`net_amount`、`reason` |
| `top_inst_detail` | `ts_code`、`trade_date`、`exalter`、`buy`、`sell`、`net_buy`、`side`、`reason` |

## 9. 市场环境和涨跌停

### 9.1 `stock_limit_price`

来源：Tushare `stk_limit`。

字段：`ts_code`、`trade_date`、`up_limit`、`down_limit`。

主键：`(ts_code, trade_date)`。

### 9.2 `market_breadth_daily`

来源：由 `stock_daily`、`stock_limit_price`、`stock_basic_info` 聚合。

字段：`trade_date`、`stock_count`、`up_count`、`down_count`、`flat_count`、`limit_up_count`、`limit_down_count`、`amount_total`、`amount_median`、`ret_median`、`ret_equal_weight`、`ret_mv_weight`。

主键：`trade_date`。

## 10. 元数据和审计表

### 10.1 `metadata_source_api`

记录 API 可获取性、权限、更新时间和字段。

字段：`source_name`、`api_name`、`domain`、`min_points`、`update_time_hint`、`history_start`、`fetch_strategy`、`rate_limit_policy`、`fields_json`、`doc_url`、`status`、`updated_at`。

### 10.2 `metadata_table_schema`

记录表结构生成源。

字段：`table_name`、`field_name`、`dtype`、`nullable`、`primary_key_order`、`unit`、`description`、`source_api`、`source_field`、`is_point_in_time`、`missing_policy`。

### 10.3 `audit_pipeline_run`

记录每次 pipeline。

字段：`run_id`、`run_mode`、`started_at`、`finished_at`、`status`、`latest_trade_date`、`write_window_start`、`write_window_end`、`rows_inserted`、`rows_updated`、`report_path`、`error_summary`。

### 10.4 `audit_data_quality`

记录每次质量检查。

字段：`run_id`、`table_name`、`field_name`、`check_name`、`status`、`metric_value`、`threshold`、`sample_json`、`created_at`。

## 11. 更新频率和触发策略

| 数据域 | 默认频率 | 日常模式 | 远期修复规则 |
|---|---|---|---|
| 交易日历 | 年度/按需 | 检查未来一年 | 可自动 |
| 股票主数据 | 每日或每周 | 每日轻检查 | 可自动 |
| 日线行情 | 每交易日盘后 | 自动 | 超 10 日需确认 |
| 复权因子 | 每交易日盘后 | 自动 | 超 10 日需确认 |
| daily_basic | 每交易日盘后 | 自动 | 超 10 日需确认，基础库初建除外 |
| 资金流 | 每交易日 19 点后 | 自动 | 超 10 日需确认 |
| 两融 | 每日 9 点后 | 自动追缺口 | 超 10 日需确认 |
| 财务报表 | 财报披露期 | 只补缺失季度 | 近期刷新需显式参数 |
| 财务明细 | 财报披露期/不定期 | 检查披露计划 | 历史初建优先完成 |
| 概念/行业映射 | 每周/每日快照 | 快照差异 | 历史由快照累积 |
| 衍生变量 | 每交易日 | 最近 10 日自动 | 超 10 日需确认 |

## 12. Phase 1 交付判定

进入代码实现前，本数据契约需要满足：

1. P0/P1 表名、主键和字段名冻结。
2. 每个表至少有一个 Tushare 主来源或明确的本地推导来源。
3. 财务明细和概念板块不再混入单张泛化表，而是拆分成可维护子表。
4. 所有低频数据定义 `effective_date` 或可推导的日频映射规则。
5. 元数据表能支撑自动生成数据字典、字段标签和文档漂移检查。

## 13. 编码和中文报告

本工程所有 Markdown、JSON、Excel 字典生成源文件必须使用 UTF-8。

对于包含中文的 Markdown 报告，不应通过临时 PowerShell 管道直接写入正文，因为控制台编码可能在脚本收到内容之前把中文替换成乱码。推荐使用：

1. 已纳入项目的 Python 或 Node 生成脚本，并显式使用 UTF-8 写文件。
2. `apply_patch` 进行人工文档编辑。
3. 已有自动文档和变量字典生成器。

当前中文审计报告生成关系：

| 报告 | 生成脚本 |
|---|---|
| `reports/phase3_financial_stage1_quality_audit.md` | `scripts/generate_phase3_financial_stage1_audit.py` |
## 附录：大型衍生表的物理表与视图策略

当衍生变量字段数超过数百列且全历史行数达到千万级时，默认不再采用“全部字段单一物理宽表”的方案。推荐采用：

1. 核心物理表：保留日常增量、常规分析和高频查询字段。
2. 完整视图：保留完整变量设计和可追溯计算逻辑，按需查询。
3. 可选物化子集：当完整视图中的某一字段组成为稳定高频需求时，再单独物理化。

`derived_financial_growth` 已按该规则执行：

| 对象 | 类型 | 字段数 | 职责 |
|---|---|---:|---|
| `derived_financial_growth` | 物理表 | 255 | 财务成长核心变量，参与日常增量维护 |
| `derived_financial_growth_full_v` | 视图 | 1,196 | 财务成长完整变量设计，按需计算 |

该策略优先保证日常维护效率，同时不牺牲变量设计完整性。若需要真实释放 DuckDB 删除宽表后的磁盘空间，应执行独立的数据库压缩或重写任务。
