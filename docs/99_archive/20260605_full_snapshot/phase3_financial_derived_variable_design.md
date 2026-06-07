# Phase 3 财务衍生变量完整设计

生成日期：2026-05-31

## 1. 设计边界

本设计覆盖 Phase 3 下一批优先实现的三个财务衍生变量模块：

1. `derived_financial_asof`：财务可得状态与报告时点。
2. `derived_financial_quality`：盈利结构、现金流质量、资产负债结构、偿债能力、经营效率、费用结构、杜邦拆解和事实型风险标记。
3. `derived_financial_growth`：成长、边际变化、单季趋势、多周期同环比、跨年成长和财务改善/恶化事实。

本工程只维护股票数据和事实型变量，不生成未来收益、选股标签、回测字段、模型训练字段，也不生成带主观权重的综合评分字段。

## 2. 重要调整

根据你的反馈，本版明确剔除以下类型变量：

| 剔除类型 | 示例 | 原因 |
|---|---|---|
| 综合评分 | `financial_quality_score`、`profitability_score`、`financial_growth_score` | 权重和评分逻辑带主观判断，不属于事实层 |
| 截面排名/分位评分 | `rank_pct(...)`、行业内质量分 | 排名口径依赖策略目标，应由下游分析工程决定 |
| 风险评分 | `asset_quality_risk_score` | “风险”可以拆成事实指标，但不在本工程合成为分数 |

保留的变量必须能回答“这个事实是什么”，而不是“这个股票好不好”。

## 3. 通用口径

### 3.1 点时安全

所有日频财务衍生变量必须满足：

```text
trade_date >= effective_date
effective_date = coalesce(first_ann_date, ann_date, end_date)
```

其中 `end_date` 只作为源数据缺失时的兜底，不代表真实披露可得日。后续质量审计必须抽查 `latest_financial_effective_date <= trade_date`。

### 3.2 默认数据入口

| 标准入口 | 用途 |
|---|---|
| `financial_indicator_asof` | 财务指标点时安全入口 |
| `financial_income_statement` | 利润表结构化入口 |
| `financial_balance_sheet` | 资产负债表结构化入口 |
| `financial_cashflow_statement` | 现金流量表结构化入口 |
| `financial_statement_latest` | 财务报告版本状态入口 |
| `financial_forecast` / `financial_express` | 预告、快报事件入口 |
| `financial_disclosure_schedule` | 披露计划入口 |

实现时不应在衍生模块中解析 `payload_json`。若标准入口字段不足，应先补基础标准视图。

### 3.3 单位

| 类型 | 约定 |
|---|---|
| Tushare 原始百分比字段 | 保持原百分比口径，例如 `roe=10` 表示 10% |
| 新构造比率 | 使用小数比例，例如 `goodwill_to_assets=0.05` |
| 金额 | 保持源表金额单位，不在 Phase 3 内强制换算 |
| 天数 | 自然日 |
| 标记 | `BOOLEAN` |

### 3.4 缺失策略

| 场景 | 策略 |
|---|---|
| 公司尚未披露财报 | NULL |
| 早期年份源字段不存在 | NULL，并在质量报告解释为源覆盖边界 |
| 分母为 0 或 NULL | NULL |
| 金融/保险专用字段 | 非金融公司为空属于正常 |
| 预告/快报不存在 | NULL 或 `false` |

## 4. `derived_financial_asof`

### 4.1 表定位

`derived_financial_asof` 是财务日频衍生变量的状态主干，回答：

1. 当前交易日可见的最新财报是哪一期。
2. 财报何时公告，距离交易日多久。
3. 利润表、资产负债表、现金流量表、指标表是否均已可得。
4. 是否已有预告、快报和披露计划。

### 4.2 推荐字段

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `ts_code` | 股票代码 | VARCHAR | `stock_daily.ts_code` | 主键 | required |
| `trade_date` | 交易日期 | DATE | `stock_daily.trade_date` | 主键 | required |
| `latest_report_end_date` | 最新可得财报报告期 | DATE | `financial_indicator_asof.latest_report_end_date` | `asof(financial_indicator.end_date)` | financial_not_disclosed |
| `latest_financial_effective_date` | 最新财报可得日期 | DATE | `financial_indicator_asof.latest_financial_effective_date` | `asof(financial_indicator.effective_date)` | financial_not_disclosed |
| `latest_financial_ann_date` | 最新财报公告日期 | DATE | `financial_indicator_asof.latest_financial_ann_date` | `asof(financial_indicator.ann_date)` | financial_not_disclosed |
| `report_age_days` | 财报已披露天数 | BIGINT | 上述字段 | `trade_date - latest_financial_effective_date` | financial_not_disclosed |
| `report_lag_days` | 财报披露滞后天数 | BIGINT | 上述字段 | `latest_financial_effective_date - latest_report_end_date` | financial_not_disclosed |
| `report_year` | 报告年度 | INTEGER | `latest_report_end_date` | `year(latest_report_end_date)` | financial_not_disclosed |
| `report_quarter` | 报告季度 | INTEGER | `latest_report_end_date` | `quarter(latest_report_end_date)` | financial_not_disclosed |
| `report_period_type` | 报告期类型 | VARCHAR | `latest_report_end_date` | `Q1/H1/Q3/FY` | financial_not_disclosed |
| `is_annual_report` | 是否年报 | BOOLEAN | `latest_report_end_date` | `month=12 and day=31` | false_when_missing |
| `is_interim_report` | 是否中报 | BOOLEAN | `latest_report_end_date` | `month=6 and day=30` | false_when_missing |
| `is_q1_report` | 是否一季报 | BOOLEAN | `latest_report_end_date` | `month=3 and day=31` | false_when_missing |
| `is_q3_report` | 是否三季报 | BOOLEAN | `latest_report_end_date` | `month=9 and day=30` | false_when_missing |
| `income_report_end_date` | 利润表最新报告期 | DATE | `financial_income_statement` | `asof(income.end_date)` | financial_not_disclosed |
| `balance_report_end_date` | 资产负债表最新报告期 | DATE | `financial_balance_sheet` | `asof(balance.end_date)` | financial_not_disclosed |
| `cashflow_report_end_date` | 现金流量表最新报告期 | DATE | `financial_cashflow_statement` | `asof(cashflow.end_date)` | financial_not_disclosed |
| `indicator_report_end_date` | 指标表最新报告期 | DATE | `financial_indicator_statement` | `asof(indicator.end_date)` | financial_not_disclosed |
| `statement_available_count` | 当期可得报表数量 | INTEGER | 四张财务表 | `count(latest_*_end_date = latest_report_end_date)` | 0_when_missing |
| `has_income_statement` | 是否有利润表 | BOOLEAN | `financial_income_statement` | `income_report_end_date is not null` | false_when_missing |
| `has_balance_sheet` | 是否有资产负债表 | BOOLEAN | `financial_balance_sheet` | `balance_report_end_date is not null` | false_when_missing |
| `has_cashflow_statement` | 是否有现金流量表 | BOOLEAN | `financial_cashflow_statement` | `cashflow_report_end_date is not null` | false_when_missing |
| `has_indicator_statement` | 是否有指标表 | BOOLEAN | `financial_indicator_statement` | `indicator_report_end_date is not null` | false_when_missing |
| `next_disclosure_pre_date` | 下一次预计披露日期 | DATE | `financial_disclosure_schedule.pre_date` | `min(pre_date where pre_date >= trade_date)` | source_optional |
| `days_to_next_disclosure` | 距预计披露日天数 | BIGINT | 上述字段 | `next_disclosure_pre_date - trade_date` | source_optional |
| `has_forecast_asof` | 是否已有业绩预告 | BOOLEAN | `financial_forecast` | `exists(ann_date <= trade_date)` | false_when_missing |
| `latest_forecast_end_date` | 最新预告报告期 | DATE | `financial_forecast.end_date` | `asof(forecast.end_date)` | source_optional |
| `has_express_asof` | 是否已有业绩快报 | BOOLEAN | `financial_express` | `exists(ann_date <= trade_date)` | false_when_missing |
| `latest_express_end_date` | 最新快报报告期 | DATE | `financial_express.end_date` | `asof(express.end_date)` | source_optional |

## 5. `derived_financial_quality`

### 5.1 表定位

`derived_financial_quality` 只描述已披露财务事实，不做综合评价。变量分为：

1. 盈利能力和利润结构。
2. 现金流质量和收现质量。
3. 资产结构和营运资本。
4. 债务结构和偿债能力。
5. 经营效率。
6. 费用结构和投入强度。
7. 杜邦拆解。
8. 事实型风险标记。
9. 报表勾稽和披露质量事实。

### 5.2 推荐字段

#### 5.2.1 盈利能力和利润结构

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `roe_asof` | ROE | DOUBLE | `financial_indicator_asof.roe` | `asof(roe)` | financial_not_disclosed |
| `roe_waa_asof` | 加权 ROE | DOUBLE | `financial_indicator_asof.roe_waa` | `asof(roe_waa)` | financial_not_disclosed |
| `roe_dt_asof` | 扣非 ROE | DOUBLE | `financial_indicator_asof.roe_dt` | `asof(roe_dt)` | financial_not_disclosed |
| `roa_asof` | ROA | DOUBLE | `financial_indicator_asof.roa` | `asof(roa)` | financial_not_disclosed |
| `roic_asof` | ROIC | DOUBLE | `financial_indicator_asof.roic` | `asof(roic)` | financial_not_disclosed |
| `gross_margin_asof` | 毛利率 | DOUBLE | `financial_indicator_asof.gross_margin` | `asof(gross_margin)` | financial_not_disclosed |
| `grossprofit_margin_asof` | 销售毛利率 | DOUBLE | `financial_indicator_asof.grossprofit_margin` | `asof(grossprofit_margin)` | financial_not_disclosed |
| `netprofit_margin_asof` | 净利率 | DOUBLE | `financial_indicator_asof.netprofit_margin` | `asof(netprofit_margin)` | financial_not_disclosed |
| `operating_profit_margin_asof` | 营业利润率 | DOUBLE | `financial_income_statement.operating_profit`, `revenue` | `asof(operating_profit / nullif(revenue,0))` | denominator_null |
| `total_profit_margin_asof` | 利润总额率 | DOUBLE | `financial_income_statement.total_profit`, `revenue` | `asof(total_profit / nullif(revenue,0))` | denominator_null |
| `net_profit_margin_calc_asof` | 净利润率计算值 | DOUBLE | `financial_income_statement.net_profit`, `revenue` | `asof(net_profit / nullif(revenue,0))` | denominator_null |
| `parent_net_profit_margin_asof` | 归母净利率 | DOUBLE | `net_profit_attr_parent`, `revenue` | `asof(net_profit_attr_parent / nullif(revenue,0))` | denominator_null |
| `minority_profit_ratio_asof` | 少数股东损益占比 | DOUBLE | `minority_profit`, `net_profit` | `asof(minority_profit / nullif(net_profit,0))` | denominator_null |
| `non_operating_income_ratio_asof` | 营业外收入/利润总额 | DOUBLE | `non_operating_income`, `total_profit` | `asof(non_operating_income / nullif(total_profit,0))` | denominator_null |
| `investment_income_ratio_asof` | 投资收益/利润总额 | DOUBLE | `investment_income`, `total_profit` | `asof(investment_income / nullif(total_profit,0))` | denominator_null |
| `fair_value_gain_ratio_asof` | 公允价值变动收益/利润总额 | DOUBLE | `fair_value_change_income`, `total_profit` | `asof(fair_value_change_income / nullif(total_profit,0))` | denominator_null |
| `asset_impairment_to_profit_asof` | 资产减值损失/利润总额 | DOUBLE | `asset_impairment_loss`, `total_profit` | `asof(asset_impairment_loss / nullif(total_profit,0))` | denominator_null |
| `deducted_profit_to_net_profit_asof` | 扣非净利/净利润 | DOUBLE | `financial_indicator_asof.profit_dedt`, `net_profit` | `asof(profit_dedt / nullif(net_profit,0))` | denominator_null |

#### 5.2.2 现金流质量和收现质量

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `ocf_to_profit_asof` | 经营现金流/利润 | DOUBLE | `financial_indicator_asof.ocf_to_profit` | `asof(ocf_to_profit)` | financial_not_disclosed |
| `ocf_to_revenue_asof` | 经营现金流/营业收入 | DOUBLE | `cf_from_operating`, `revenue` | `asof(cf_from_operating / nullif(revenue,0))` | denominator_null |
| `free_cashflow_to_revenue_asof` | 自由现金流/营业收入 | DOUBLE | `free_cashflow`, `revenue` | `asof(free_cashflow / nullif(revenue,0))` | denominator_null |
| `cash_received_to_revenue_asof` | 销售收现/营业收入 | DOUBLE | `cash_received_from_sales`, `revenue` | `asof(cash_received_from_sales / nullif(revenue,0))` | denominator_null |
| `cash_paid_goods_to_cost_asof` | 购货付现/营业成本 | DOUBLE | `cash_paid_for_goods`, `operating_cost` | `asof(cash_paid_for_goods / nullif(operating_cost,0))` | denominator_null |
| `capex_to_revenue_asof` | 资本开支/营业收入 | DOUBLE | `cash_paid_for_capex`, `revenue` | `asof(cash_paid_for_capex / nullif(revenue,0))` | denominator_null |
| `capex_to_ocf_asof` | 资本开支/经营现金流 | DOUBLE | `cash_paid_for_capex`, `cf_from_operating` | `asof(cash_paid_for_capex / nullif(cf_from_operating,0))` | denominator_null |
| `fcf_to_ocf_asof` | 自由现金流/经营现金流 | DOUBLE | `free_cashflow`, `cf_from_operating` | `asof(free_cashflow / nullif(cf_from_operating,0))` | denominator_null |
| `cash_end_to_assets_asof` | 期末现金/总资产 | DOUBLE | `cash_at_end`, `total_assets` | `asof(cash_at_end / nullif(total_assets,0))` | denominator_null |
| `cash_net_increase_to_assets_asof` | 现金净增加/总资产 | DOUBLE | `net_increase_in_cash`, `total_assets` | `asof(net_increase_in_cash / nullif(total_assets,0))` | denominator_null |
| `accrual_ratio_asof` | 应计利润占比 | DOUBLE | `net_profit`, `cf_from_operating`, `total_assets` | `asof((net_profit - cf_from_operating) / nullif(total_assets,0))` | denominator_null |

#### 5.2.3 资产结构和营运资本

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `cash_to_assets_asof` | 货币资金/总资产 | DOUBLE | `cash_and_equivalents`, `total_assets` | `asof(cash_and_equivalents / nullif(total_assets,0))` | denominator_null |
| `current_assets_to_assets_asof` | 流动资产/总资产 | DOUBLE | `current_assets`, `total_assets` | `asof(current_assets / nullif(total_assets,0))` | denominator_null |
| `noncurrent_assets_to_assets_asof` | 非流动资产/总资产 | DOUBLE | `total_noncurrent_assets`, `total_assets` | `asof(total_noncurrent_assets / nullif(total_assets,0))` | denominator_null |
| `fixed_assets_to_assets_asof` | 固定资产/总资产 | DOUBLE | `fixed_assets`, `total_assets` | `asof(fixed_assets / nullif(total_assets,0))` | denominator_null |
| `construction_to_assets_asof` | 在建工程/总资产 | DOUBLE | `construction_in_process`, `total_assets` | `asof(construction_in_process / nullif(total_assets,0))` | denominator_null |
| `goodwill_to_assets_asof` | 商誉/总资产 | DOUBLE | `goodwill`, `total_assets` | `asof(goodwill / nullif(total_assets,0))` | denominator_null |
| `intangible_to_assets_asof` | 无形资产/总资产 | DOUBLE | `intangible_assets`, `total_assets` | `asof(intangible_assets / nullif(total_assets,0))` | denominator_null |
| `development_exp_to_assets_asof` | 开发支出/总资产 | DOUBLE | `development_expenditure`, `total_assets` | `asof(development_expenditure / nullif(total_assets,0))` | denominator_null |
| `accounts_receivable_to_revenue_asof` | 应收账款/营业收入 | DOUBLE | `accounts_receivable`, `revenue` | `asof(accounts_receivable / nullif(revenue,0))` | denominator_null |
| `inventory_to_revenue_asof` | 存货/营业收入 | DOUBLE | `inventories`, `revenue` | `asof(inventories / nullif(revenue,0))` | denominator_null |
| `contract_assets_to_revenue_asof` | 合同资产/营业收入 | DOUBLE | `contract_assets`, `revenue` | `asof(contract_assets / nullif(revenue,0))` | denominator_null |
| `contract_liability_to_revenue_asof` | 合同负债/营业收入 | DOUBLE | `contract_liabilities`, `revenue` | `asof(contract_liabilities / nullif(revenue,0))` | denominator_null |
| `working_capital_asof` | 营运资本 | DOUBLE | `current_assets`, `current_liabilities` | `asof(current_assets - current_liabilities)` | financial_not_disclosed |
| `working_capital_to_assets_asof` | 营运资本/总资产 | DOUBLE | `working_capital_asof`, `total_assets` | `asof(working_capital / nullif(total_assets,0))` | denominator_null |
| `net_working_capital_asof` | 净营运资本 | DOUBLE | `financial_indicator_asof.networking_capital` | `asof(networking_capital)` | financial_not_disclosed |
| `net_working_capital_to_assets_asof` | 净营运资本/总资产 | DOUBLE | `networking_capital`, `total_assets` | `asof(networking_capital / nullif(total_assets,0))` | denominator_null |

#### 5.2.4 债务结构和偿债能力

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `debt_to_assets_asof` | 资产负债率 | DOUBLE | `financial_indicator_asof.debt_to_assets` | `asof(debt_to_assets)` | financial_not_disclosed |
| `assets_to_equity_asof` | 权益乘数 | DOUBLE | `financial_indicator_asof.assets_to_eqt` | `asof(assets_to_eqt)` | financial_not_disclosed |
| `interestdebt_asof` | 有息负债 | DOUBLE | `financial_indicator_asof.interestdebt` | `asof(interestdebt)` | financial_not_disclosed |
| `netdebt_asof` | 净债务 | DOUBLE | `financial_indicator_asof.netdebt` | `asof(netdebt)` | financial_not_disclosed |
| `interestdebt_to_assets_asof` | 有息负债/总资产 | DOUBLE | `interestdebt`, `total_assets` | `asof(interestdebt / nullif(total_assets,0))` | denominator_null |
| `netdebt_to_assets_asof` | 净债务/总资产 | DOUBLE | `netdebt`, `total_assets` | `asof(netdebt / nullif(total_assets,0))` | denominator_null |
| `short_borrowing_to_assets_asof` | 短期借款/总资产 | DOUBLE | `short_term_borrowings`, `total_assets` | `asof(short_term_borrowings / nullif(total_assets,0))` | denominator_null |
| `long_borrowing_to_assets_asof` | 长期借款/总资产 | DOUBLE | `long_term_borrowings`, `total_assets` | `asof(long_term_borrowings / nullif(total_assets,0))` | denominator_null |
| `bonds_payable_to_assets_asof` | 应付债券/总资产 | DOUBLE | `bonds_payable`, `total_assets` | `asof(bonds_payable / nullif(total_assets,0))` | denominator_null |
| `current_debt_to_total_debt_asof` | 流动负债/总负债 | DOUBLE | `financial_indicator_asof.currentdebt_to_debt` | `asof(currentdebt_to_debt)` | financial_not_disclosed |
| `longdebt_to_total_debt_asof` | 长期负债/总负债 | DOUBLE | `financial_indicator_asof.longdeb_to_debt` | `asof(longdeb_to_debt)` | financial_not_disclosed |
| `current_ratio_asof` | 流动比率 | DOUBLE | `financial_indicator_asof.current_ratio` | `asof(current_ratio)` | financial_not_disclosed |
| `quick_ratio_asof` | 速动比率 | DOUBLE | `financial_indicator_asof.quick_ratio` | `asof(quick_ratio)` | financial_not_disclosed |
| `cash_ratio_asof` | 现金比率 | DOUBLE | `financial_indicator_asof.cash_ratio` | `asof(cash_ratio)` | financial_not_disclosed |
| `ocf_to_debt_asof` | 经营现金流/总债务 | DOUBLE | `financial_indicator_asof.ocf_to_debt` | `asof(ocf_to_debt)` | financial_not_disclosed |
| `ocf_to_interestdebt_asof` | 经营现金流/有息负债 | DOUBLE | `financial_indicator_asof.ocf_to_interestdebt` | `asof(ocf_to_interestdebt)` | financial_not_disclosed |
| `ebit_to_interest_asof` | EBIT/利息 | DOUBLE | `financial_indicator_asof.ebit_to_interest` | `asof(ebit_to_interest)` | financial_not_disclosed |
| `ebitda_to_debt_asof` | EBITDA/债务 | DOUBLE | `financial_indicator_asof.ebitda_to_debt` | `asof(ebitda_to_debt)` | financial_not_disclosed |

#### 5.2.5 经营效率

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `ar_turn_asof` | 应收账款周转率 | DOUBLE | `financial_indicator_asof.ar_turn` | `asof(ar_turn)` | financial_not_disclosed |
| `current_asset_turn_asof` | 流动资产周转率 | DOUBLE | `financial_indicator_asof.ca_turn` | `asof(ca_turn)` | financial_not_disclosed |
| `fixed_asset_turn_asof` | 固定资产周转率 | DOUBLE | `financial_indicator_asof.fa_turn` | `asof(fa_turn)` | financial_not_disclosed |
| `assets_turn_asof` | 总资产周转率 | DOUBLE | `financial_indicator_asof.assets_turn` | `asof(assets_turn)` | financial_not_disclosed |
| `turn_days_asof` | 营业周期天数 | DOUBLE | `financial_indicator_asof.turn_days` | `asof(turn_days)` | financial_not_disclosed |
| `total_fa_turn_asof` | 固定资产合计周转率 | DOUBLE | `financial_indicator_asof.total_fa_trun` | `asof(total_fa_trun)` | financial_not_disclosed |
| `revenue_to_assets_asof` | 营业收入/总资产 | DOUBLE | `revenue`, `total_assets` | `asof(revenue / nullif(total_assets,0))` | denominator_null |
| `revenue_to_fixed_assets_asof` | 营业收入/固定资产 | DOUBLE | `revenue`, `fixed_assets` | `asof(revenue / nullif(fixed_assets,0))` | denominator_null |

#### 5.2.6 费用结构和投入强度

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `selling_expense_to_revenue_asof` | 销售费用率 | DOUBLE | `selling_expense`, `revenue` | `asof(selling_expense / nullif(revenue,0))` | denominator_null |
| `admin_expense_to_revenue_asof` | 管理费用率 | DOUBLE | `admin_expense`, `revenue` | `asof(admin_expense / nullif(revenue,0))` | denominator_null |
| `rd_exp_to_revenue_asof` | 研发费用率 | DOUBLE | `rd_expense`, `revenue` | `asof(rd_expense / nullif(revenue,0))` | denominator_null |
| `finance_expense_to_revenue_asof` | 财务费用率 | DOUBLE | `finance_expense`, `revenue` | `asof(finance_expense / nullif(revenue,0))` | denominator_null |
| `expense_to_revenue_asof` | 期间费用率 | DOUBLE | 销售、管理、研发、财务费用 | `asof((selling_expense+admin_expense+rd_expense+finance_expense)/nullif(revenue,0))` | denominator_null |
| `business_tax_to_revenue_asof` | 税金及附加/营业收入 | DOUBLE | `business_tax_surcharge`, `revenue` | `asof(business_tax_surcharge / nullif(revenue,0))` | denominator_null |
| `income_tax_to_profit_asof` | 所得税/利润总额 | DOUBLE | `income_tax`, `total_profit` | `asof(income_tax / nullif(total_profit,0))` | denominator_null |
| `rd_exp_asof` | 研发费用 | DOUBLE | `financial_income_statement.rd_expense` | `asof(rd_expense)` | financial_not_disclosed |
| `finance_expense_asof` | 财务费用 | DOUBLE | `financial_income_statement.finance_expense` | `asof(finance_expense)` | financial_not_disclosed |

#### 5.2.7 杜邦拆解事实变量

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `dupont_net_margin_asof` | 杜邦净利率 | DOUBLE | `net_profit_attr_parent`, `revenue` | `asof(net_profit_attr_parent / nullif(revenue,0))` | denominator_null |
| `dupont_asset_turnover_asof` | 杜邦资产周转率 | DOUBLE | `revenue`, `total_assets` | `asof(revenue / nullif(total_assets,0))` | denominator_null |
| `dupont_equity_multiplier_asof` | 杜邦权益乘数 | DOUBLE | `total_assets`, `equity_attr_parent` | `asof(total_assets / nullif(equity_attr_parent,0))` | denominator_null |
| `dupont_roe_calc_asof` | 杜邦 ROE 计算值 | DOUBLE | 上述三项 | `dupont_net_margin * dupont_asset_turnover * dupont_equity_multiplier` | denominator_null |
| `roe_calc_gap_asof` | 披露 ROE 与计算 ROE 差异 | DOUBLE | `roe_asof`, `dupont_roe_calc_asof` | `roe_asof - dupont_roe_calc_asof` | source_optional |

#### 5.2.8 事实型风险标记

这些字段只表达事实条件是否成立，不合成为评分。

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `negative_equity_flag` | 负归母权益标记 | BOOLEAN | `equity_attr_parent` | `equity_attr_parent < 0` | false_when_missing |
| `negative_net_profit_flag` | 净利润为负标记 | BOOLEAN | `net_profit` | `net_profit < 0` | false_when_missing |
| `negative_parent_net_profit_flag` | 归母净利润为负标记 | BOOLEAN | `net_profit_attr_parent` | `net_profit_attr_parent < 0` | false_when_missing |
| `negative_ocf_flag` | 经营现金流为负标记 | BOOLEAN | `cf_from_operating` | `cf_from_operating < 0` | false_when_missing |
| `high_goodwill_flag` | 商誉占比较高标记 | BOOLEAN | `goodwill_to_assets_asof` | `goodwill_to_assets_asof >= 0.2` | false_when_missing |
| `high_receivable_flag` | 应收占收入较高标记 | BOOLEAN | `accounts_receivable_to_revenue_asof` | `accounts_receivable_to_revenue_asof >= 0.5` | false_when_missing |
| `high_inventory_flag` | 存货占收入较高标记 | BOOLEAN | `inventory_to_revenue_asof` | `inventory_to_revenue_asof >= 0.5` | false_when_missing |
| `high_leverage_flag` | 资产负债率较高标记 | BOOLEAN | `debt_to_assets_asof` | `debt_to_assets_asof >= 70` if source percent | false_when_missing |
| `low_current_ratio_flag` | 流动比率偏低标记 | BOOLEAN | `current_ratio_asof` | `current_ratio_asof < 1` | false_when_missing |
| `ocf_profit_mismatch_flag` | 净利润为正但经营现金流为负标记 | BOOLEAN | `net_profit`, `cf_from_operating` | `net_profit > 0 and cf_from_operating < 0` | false_when_missing |

#### 5.2.9 报表勾稽和披露质量事实

这些字段用于描述财务报表内部一致性、披露完整性和数据可解释性，不评价公司优劣。

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `liability_equity_balance_gap_asof` | 资产负债权益勾稽差额 | DOUBLE | `total_assets`, `total_liabilities`, `total_equity` | `asof(total_assets - total_liabilities - total_equity)` | financial_not_disclosed |
| `liability_equity_balance_gap_ratio_asof` | 资产负债权益勾稽差额/总资产 | DOUBLE | 上述字段 | `liability_equity_balance_gap / nullif(total_assets,0)` | denominator_null |
| `cashflow_cash_balance_gap_asof` | 现金流量表现金首尾差额 | DOUBLE | `cash_at_beginning`, `net_increase_in_cash`, `fx_effect_on_cash`, `cash_at_end` | `asof(cash_at_beginning + net_increase_in_cash + coalesce(fx_effect_on_cash,0) - cash_at_end)` | financial_not_disclosed |
| `cashflow_cash_balance_gap_ratio_asof` | 现金首尾差额/期末现金 | DOUBLE | 上述字段 | `cashflow_cash_balance_gap / nullif(cash_at_end,0)` | denominator_null |
| `statement_available_count_asof` | 当前报告期可得报表数量 | INTEGER | `derived_financial_asof.statement_available_count` | `asof(statement_available_count)` | 0_when_missing |
| `has_complete_statement_set_asof` | 当前报告期三表及指标完整标记 | BOOLEAN | `derived_financial_asof` | `statement_available_count >= 4` | false_when_missing |
| `report_age_days_asof` | 财报披露后经过天数 | BIGINT | `derived_financial_asof.report_age_days` | `asof(report_age_days)` | financial_not_disclosed |
| `report_lag_days_asof` | 财报披露滞后天数 | BIGINT | `derived_financial_asof.report_lag_days` | `asof(report_lag_days)` | financial_not_disclosed |
| `has_forecast_asof` | 已有业绩预告标记 | BOOLEAN | `derived_financial_asof.has_forecast_asof` | `asof(has_forecast_asof)` | false_when_missing |
| `has_express_asof` | 已有业绩快报标记 | BOOLEAN | `derived_financial_asof.has_express_asof` | `asof(has_express_asof)` | false_when_missing |

### 5.3 第一批实现建议

第一批建议优先实现：

1. 所有可直接 `asof` 映射的指标字段。
2. 分母清晰的比例字段。
3. 事实型布尔标记。
4. 杜邦拆解字段。
5. 报表勾稽和披露质量事实。

不实现任何综合评分、排名、分位数、主观权重变量。

## 6. `derived_financial_growth`

### 6.1 表定位

`derived_financial_growth` 描述当前已披露财务数据的跨期变化，不构造未来收益标签。  
从工程实现角度看，它比 `financial_asof` 和 `financial_quality` 更复杂，因为它依赖稳定的报告期序列、上一报告期、去年同期、近多期窗口、跨年比较和部分质量变量的变化量。因此将它放在第二阶段实现是适当的。

### 6.2 同环比口径

增长变量统一使用“报告期序列”而不是固定交易日窗口：

| 口径 | 解释 | 示例 |
|---|---|---|
| 上一报告期环比 | 当前可得报告期 vs 上一可得报告期 | 2025Q3 vs 2025H1 |
| 去年同期同比 | 当前可得报告期 vs 去年同一报告期 | 2025Q3 vs 2024Q3 |
| 近2期变化 | 当前报告期 vs 向前2个报告期 | 2025Q3 vs 2025Q1 |
| 近4期变化 | 当前报告期 vs 向前4个报告期 | 2025Q3 vs 2024Q3 |
| 近8期变化 | 当前报告期 vs 向前8个报告期 | 2025Q3 vs 2023Q3 |
| 2年/3年 CAGR | 当前年度或滚动报告期 vs 2年/3年前同期 | `power(current / lag_n, 1/n) - 1` |

所有字段仍必须满足 `effective_date <= trade_date`。

### 6.3 推荐字段

#### 6.3.1 Tushare 已提供同比/环比字段

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `revenue_yoy_asof` | 营业收入同比 | DOUBLE | `financial_indicator_asof.or_yoy` | `asof(or_yoy)` | financial_not_disclosed |
| `total_revenue_yoy_asof` | 营业总收入同比 | DOUBLE | `financial_indicator_asof.tr_yoy` | `asof(tr_yoy)` | financial_not_disclosed |
| `netprofit_yoy_asof` | 净利润同比 | DOUBLE | `financial_indicator_asof.netprofit_yoy` | `asof(netprofit_yoy)` | financial_not_disclosed |
| `deducted_netprofit_yoy_asof` | 扣非净利润同比 | DOUBLE | `financial_indicator_asof.dt_netprofit_yoy` | `asof(dt_netprofit_yoy)` | financial_not_disclosed |
| `ocf_yoy_asof` | 经营现金流同比 | DOUBLE | `financial_indicator_asof.ocf_yoy` | `asof(ocf_yoy)` | financial_not_disclosed |
| `eps_yoy_asof` | EPS 同比 | DOUBLE | `financial_indicator_asof.basic_eps_yoy` | `asof(basic_eps_yoy)` | financial_not_disclosed |
| `cfps_yoy_asof` | 每股现金流同比 | DOUBLE | `financial_indicator_asof.cfps_yoy` | `asof(cfps_yoy)` | financial_not_disclosed |
| `roe_yoy_asof` | ROE 同比 | DOUBLE | `financial_indicator_asof.roe_yoy` | `asof(roe_yoy)` | financial_not_disclosed |
| `bps_yoy_asof` | 每股净资产同比 | DOUBLE | `financial_indicator_asof.bps_yoy` | `asof(bps_yoy)` | financial_not_disclosed |
| `assets_yoy_asof` | 总资产同比 | DOUBLE | `financial_indicator_asof.assets_yoy` | `asof(assets_yoy)` | financial_not_disclosed |
| `equity_yoy_asof` | 所有者权益同比 | DOUBLE | `financial_indicator_asof.eqt_yoy` | `asof(eqt_yoy)` | financial_not_disclosed |
| `q_revenue_yoy_asof` | 单季收入同比 | DOUBLE | `financial_indicator_raw.q_sales_yoy` | `asof(q_sales_yoy)` | financial_not_disclosed |
| `q_revenue_qoq_asof` | 单季收入环比 | DOUBLE | `financial_indicator_raw.q_sales_qoq` | `asof(q_sales_qoq)` | financial_not_disclosed |
| `q_netprofit_yoy_asof` | 单季净利润同比 | DOUBLE | `financial_indicator_raw.q_netprofit_yoy` | `asof(q_netprofit_yoy)` | financial_not_disclosed |
| `q_netprofit_qoq_asof` | 单季净利润环比 | DOUBLE | `financial_indicator_raw.q_netprofit_qoq` | `asof(q_netprofit_qoq)` | financial_not_disclosed |
| `q_operating_profit_yoy_asof` | 单季营业利润同比 | DOUBLE | `financial_indicator_raw.q_op_yoy` | `asof(q_op_yoy)` | financial_not_disclosed |
| `q_operating_profit_qoq_asof` | 单季营业利润环比 | DOUBLE | `financial_indicator_raw.q_op_qoq` | `asof(q_op_qoq)` | financial_not_disclosed |
| `q_roe_asof` | 单季 ROE | DOUBLE | `financial_indicator_raw.q_roe` | `asof(q_roe)` | financial_not_disclosed |
| `q_netprofit_margin_asof` | 单季净利率 | DOUBLE | `financial_indicator_raw.q_netprofit_margin` | `asof(q_netprofit_margin)` | financial_not_disclosed |
| `q_grossprofit_margin_asof` | 单季毛利率 | DOUBLE | `financial_indicator_raw.q_gsprofit_margin` | `asof(q_gsprofit_margin)` | financial_not_disclosed |

#### 6.3.2 多周期同比和跨年变化

这些字段使用基础报表或 as-of 指标按报告期序列计算。

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `revenue_yoy_1y_calc_asof` | 营业收入1年同比计算值 | DOUBLE | `financial_income_statement.revenue` | `current / lag_same_period_1y - 1` | financial_not_disclosed |
| `revenue_yoy_2y_calc_asof` | 营业收入2年累计同比 | DOUBLE | `revenue` | `current / lag_same_period_2y - 1` | financial_not_disclosed |
| `revenue_yoy_3y_calc_asof` | 营业收入3年累计同比 | DOUBLE | `revenue` | `current / lag_same_period_3y - 1` | financial_not_disclosed |
| `revenue_cagr_2y_asof` | 营业收入2年复合增速 | DOUBLE | `revenue` | `power(current / lag_same_period_2y, 1/2) - 1` | denominator_null |
| `revenue_cagr_3y_asof` | 营业收入3年复合增速 | DOUBLE | `revenue` | `power(current / lag_same_period_3y, 1/3) - 1` | denominator_null |
| `parent_net_profit_yoy_1y_calc_asof` | 归母净利润1年同比计算值 | DOUBLE | `net_profit_attr_parent` | `current / lag_same_period_1y - 1` | financial_not_disclosed |
| `parent_net_profit_yoy_2y_calc_asof` | 归母净利润2年累计同比 | DOUBLE | `net_profit_attr_parent` | `current / lag_same_period_2y - 1` | financial_not_disclosed |
| `parent_net_profit_yoy_3y_calc_asof` | 归母净利润3年累计同比 | DOUBLE | `net_profit_attr_parent` | `current / lag_same_period_3y - 1` | financial_not_disclosed |
| `parent_net_profit_cagr_2y_asof` | 归母净利润2年复合增速 | DOUBLE | `net_profit_attr_parent` | `signed_cagr(current, lag_same_period_2y, 2)` | source_optional |
| `parent_net_profit_cagr_3y_asof` | 归母净利润3年复合增速 | DOUBLE | `net_profit_attr_parent` | `signed_cagr(current, lag_same_period_3y, 3)` | source_optional |
| `ocf_yoy_1y_calc_asof` | 经营现金流1年同比计算值 | DOUBLE | `cf_from_operating` | `current / lag_same_period_1y - 1` | financial_not_disclosed |
| `ocf_yoy_2y_calc_asof` | 经营现金流2年累计同比 | DOUBLE | `cf_from_operating` | `current / lag_same_period_2y - 1` | financial_not_disclosed |
| `ocf_yoy_3y_calc_asof` | 经营现金流3年累计同比 | DOUBLE | `cf_from_operating` | `current / lag_same_period_3y - 1` | financial_not_disclosed |
| `total_assets_yoy_1y_calc_asof` | 总资产1年同比计算值 | DOUBLE | `total_assets` | `current / lag_same_period_1y - 1` | financial_not_disclosed |
| `equity_yoy_1y_calc_asof` | 归母权益1年同比计算值 | DOUBLE | `equity_attr_parent` | `current / lag_same_period_1y - 1` | financial_not_disclosed |

#### 6.3.3 多周期环比和报告期变化

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `revenue_qoq_report_asof` | 营业收入上一报告期环比 | DOUBLE | `revenue` | `current / lag_report_1 - 1` | financial_not_disclosed |
| `revenue_change_2report_asof` | 营业收入近2期变化 | DOUBLE | `revenue` | `current / lag_report_2 - 1` | financial_not_disclosed |
| `revenue_change_4report_asof` | 营业收入近4期变化 | DOUBLE | `revenue` | `current / lag_report_4 - 1` | financial_not_disclosed |
| `revenue_change_8report_asof` | 营业收入近8期变化 | DOUBLE | `revenue` | `current / lag_report_8 - 1` | financial_not_disclosed |
| `parent_net_profit_qoq_report_asof` | 归母净利润上一报告期环比 | DOUBLE | `net_profit_attr_parent` | `current / lag_report_1 - 1` | financial_not_disclosed |
| `parent_net_profit_change_2report_asof` | 归母净利润近2期变化 | DOUBLE | `net_profit_attr_parent` | `current / lag_report_2 - 1` | financial_not_disclosed |
| `parent_net_profit_change_4report_asof` | 归母净利润近4期变化 | DOUBLE | `net_profit_attr_parent` | `current / lag_report_4 - 1` | financial_not_disclosed |
| `parent_net_profit_change_8report_asof` | 归母净利润近8期变化 | DOUBLE | `net_profit_attr_parent` | `current / lag_report_8 - 1` | financial_not_disclosed |
| `ocf_qoq_report_asof` | 经营现金流上一报告期环比 | DOUBLE | `cf_from_operating` | `current / lag_report_1 - 1` | financial_not_disclosed |
| `ocf_change_4report_asof` | 经营现金流近4期变化 | DOUBLE | `cf_from_operating` | `current / lag_report_4 - 1` | financial_not_disclosed |
| `roe_change_1report_asof` | ROE 上一报告期变化 | DOUBLE | `derived_financial_quality.roe_asof` | `current - lag_report_1` | financial_not_disclosed |
| `roe_change_4report_asof` | ROE 近4期变化 | DOUBLE | `derived_financial_quality.roe_asof` | `current - lag_report_4` | financial_not_disclosed |
| `gross_margin_change_1report_asof` | 毛利率上一报告期变化 | DOUBLE | `derived_financial_quality.gross_margin_asof` | `current - lag_report_1` | financial_not_disclosed |
| `gross_margin_change_4report_asof` | 毛利率近4期变化 | DOUBLE | `derived_financial_quality.gross_margin_asof` | `current - lag_report_4` | financial_not_disclosed |
| `debt_to_assets_change_1report_asof` | 资产负债率上一报告期变化 | DOUBLE | `derived_financial_quality.debt_to_assets_asof` | `current - lag_report_1` | financial_not_disclosed |
| `debt_to_assets_change_4report_asof` | 资产负债率近4期变化 | DOUBLE | `derived_financial_quality.debt_to_assets_asof` | `current - lag_report_4` | financial_not_disclosed |
| `ocf_to_profit_change_1report_asof` | 经营现金流/利润上一报告期变化 | DOUBLE | `derived_financial_quality.ocf_to_profit_asof` | `current - lag_report_1` | financial_not_disclosed |
| `ocf_to_profit_change_4report_asof` | 经营现金流/利润近4期变化 | DOUBLE | `derived_financial_quality.ocf_to_profit_asof` | `current - lag_report_4` | financial_not_disclosed |

#### 6.3.4 财务质量字段的增长和变化

原本容易被放入 `derived_financial_quality` 的同环比增长，统一归入 `derived_financial_growth`。

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `gross_margin_yoy_change_asof` | 毛利率同比变化 | DOUBLE | `derived_financial_quality.gross_margin_asof` | `current - lag_same_period_1y` | financial_not_disclosed |
| `netprofit_margin_yoy_change_asof` | 净利率同比变化 | DOUBLE | `derived_financial_quality.netprofit_margin_asof` | `current - lag_same_period_1y` | financial_not_disclosed |
| `ocf_to_profit_yoy_change_asof` | 经营现金流/利润同比变化 | DOUBLE | `derived_financial_quality.ocf_to_profit_asof` | `current - lag_same_period_1y` | financial_not_disclosed |
| `accounts_receivable_to_revenue_yoy_change_asof` | 应收/收入同比变化 | DOUBLE | `derived_financial_quality.accounts_receivable_to_revenue_asof` | `current - lag_same_period_1y` | financial_not_disclosed |
| `inventory_to_revenue_yoy_change_asof` | 存货/收入同比变化 | DOUBLE | `derived_financial_quality.inventory_to_revenue_asof` | `current - lag_same_period_1y` | financial_not_disclosed |
| `goodwill_to_assets_yoy_change_asof` | 商誉/总资产同比变化 | DOUBLE | `derived_financial_quality.goodwill_to_assets_asof` | `current - lag_same_period_1y` | financial_not_disclosed |
| `interestdebt_to_assets_yoy_change_asof` | 有息负债/总资产同比变化 | DOUBLE | `derived_financial_quality.interestdebt_to_assets_asof` | `current - lag_same_period_1y` | financial_not_disclosed |
| `expense_to_revenue_yoy_change_asof` | 期间费用率同比变化 | DOUBLE | `derived_financial_quality.expense_to_revenue_asof` | `current - lag_same_period_1y` | financial_not_disclosed |
| `rd_exp_to_revenue_yoy_change_asof` | 研发费用率同比变化 | DOUBLE | `derived_financial_quality.rd_exp_to_revenue_asof` | `current - lag_same_period_1y` | financial_not_disclosed |

#### 6.3.5 事实型成长状态标记

| 字段名 | 中文名 | 类型 | 来源 | 衍生逻辑 | 缺失策略 |
|---|---|---|---|---|---|
| `revenue_positive_growth_flag` | 收入正增长标记 | BOOLEAN | `revenue_yoy_asof` | `revenue_yoy_asof > 0` | false_when_missing |
| `netprofit_positive_growth_flag` | 净利润正增长标记 | BOOLEAN | `netprofit_yoy_asof` | `netprofit_yoy_asof > 0` | false_when_missing |
| `deducted_profit_positive_growth_flag` | 扣非净利润正增长标记 | BOOLEAN | `deducted_netprofit_yoy_asof` | `deducted_netprofit_yoy_asof > 0` | false_when_missing |
| `ocf_positive_growth_flag` | 经营现金流正增长标记 | BOOLEAN | `ocf_yoy_asof` | `ocf_yoy_asof > 0` | false_when_missing |
| `revenue_multi_year_growth_flag` | 收入多年正增长标记 | BOOLEAN | `revenue_yoy_1y_calc_asof`, `revenue_yoy_2y_calc_asof`, `revenue_yoy_3y_calc_asof` | all available values > 0 | false_when_missing |
| `profit_multi_year_growth_flag` | 归母净利润多年正增长标记 | BOOLEAN | 归母净利润多周期字段 | all available values > 0 | false_when_missing |
| `growth_profit_match_flag` | 收入利润同向成长标记 | BOOLEAN | `revenue_yoy_asof`, `netprofit_yoy_asof` | `revenue_yoy_asof > 0 and netprofit_yoy_asof > 0` | false_when_missing |
| `growth_cashflow_match_flag` | 利润现金流同向成长标记 | BOOLEAN | `netprofit_yoy_asof`, `ocf_yoy_asof` | `netprofit_yoy_asof > 0 and ocf_yoy_asof > 0` | false_when_missing |
| `growth_acceleration_flag` | 收入和利润同比同时改善标记 | BOOLEAN | `revenue_yoy_1y_calc_asof`, `parent_net_profit_yoy_1y_calc_asof` 与上一报告期 | both improved from previous report | false_when_missing |
| `margin_improving_flag` | 毛利率和净利率同时改善标记 | BOOLEAN | `gross_margin_yoy_change_asof`, `netprofit_margin_yoy_change_asof` | both > 0 | false_when_missing |
| `leverage_increasing_flag` | 资产负债率上升标记 | BOOLEAN | `debt_to_assets_change_1report_asof` | `debt_to_assets_change_1report_asof > 0` | false_when_missing |

## 7. 表结构规模

| 表 | 推荐业务字段数 | 说明 |
|---|---:|---|
| `derived_financial_asof` | 约 28 | 状态、报告期、披露计划、预告快报 |
| `derived_financial_quality` | 约 95 | 全部为事实型财务质量变量，不含评分；不放同环比增长字段 |
| `derived_financial_growth` | 约 75 | Tushare 原始同环比、多周期同环比、跨年变化、质量字段变化和事实标记，不含评分 |

## 8. 实现依赖顺序

```text
financial_indicator_asof / financial_*_statement views
  -> derived_financial_asof
  -> derived_financial_quality
  -> derived_financial_growth
  -> derived_valuation_size 扩展
  -> derived_composite_state 事实字段更新
```

`derived_financial_quality` 依赖 `derived_financial_asof`。  
`derived_financial_growth` 依赖 `derived_financial_asof`，部分趋势字段依赖 `derived_financial_quality`。

### 8.1 阶段拆分建议

客观评价后，建议将财务衍生变量拆成两阶段实现：

| 阶段 | 实现表 | 原因 | 验收重点 |
|---|---|---|---|
| 第一阶段 | `derived_financial_asof`、`derived_financial_quality` | 两张表主要描述“当前可见财务事实”和“当前财务结构事实”，计算依赖较少，能先建立稳定事实底座 | 点时安全、字段覆盖率、财务报表勾稽、字段非空率 |
| 第二阶段 | `derived_financial_growth` | 成长字段需要报告期序列、上一期/去年同期/多年前同期匹配、跨年窗口和质量字段变化；在质量表稳定后再实现可减少返工 | 多周期匹配正确性、同比环比口径一致性、跨年字段覆盖率 |

这个拆分是适当的。它的代价是第一阶段完成后暂时缺少完整成长变量，但收益是先把财务事实层打稳，第二阶段可以复用质量表字段计算变化，不会把同环比逻辑散落到多个表里。

## 9. 质量审计要求

实现后必须生成专项审计：

1. 每张表字段数、行数、日期范围、股票数量。
2. 每个字段非空率。
3. 分年度覆盖率。
4. 极值检查，至少覆盖 `roe_asof`、`roa_asof`、`gross_margin_asof`、`debt_to_assets_asof`、`revenue_yoy_asof`、`netprofit_yoy_asof`。
5. 点时安全抽查：`latest_financial_effective_date <= trade_date`。
6. 报告期单调性抽查：同一股票随时间推进，`latest_report_end_date` 不应倒退，除非源数据修正导致历史重写。
7. 分母为 0 的字段必须返回 NULL，不得生成无穷大或异常大值。

## 10. 待确认

进入实现前，请确认：

1. 是否同意第一阶段先实现 `derived_financial_asof` 和 `derived_financial_quality`，第二阶段再实现 `derived_financial_growth`。
2. 是否同意所有同环比、跨期变化、多周期变化字段统一放入 `derived_financial_growth`，不放入 `derived_financial_quality`。
3. 是否同意财务同比、环比字段继续保留 Tushare 百分比口径，而新构造比例字段使用小数比例。
4. 是否同意趋势变化字段按“上一可得报告期 / 去年同期报告期 / 多年前同期报告期”计算，而不是固定交易日窗口。
5. 是否同意本工程彻底剔除评分、排名、分位数、主观权重类财务衍生变量。
