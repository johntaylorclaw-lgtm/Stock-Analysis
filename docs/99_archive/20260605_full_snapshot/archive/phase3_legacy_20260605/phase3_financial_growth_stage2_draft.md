# Phase 3 财务衍生第二阶段完整设计：`derived_financial_growth`

生成日期：2026-05-31

## 1. 设计边界

第二阶段只实现跨期变化事实，不实现评分、排名、分位数、选股标签、回测字段或模型训练字段。

本阶段输入：

1. `derived_financial_asof`：提供点时安全的当前可得报告期。
2. `derived_financial_quality`：提供第一阶段已落库的财务质量事实字段。
3. `financial_income_raw`、`financial_balance_raw`、`financial_cashflow_raw`、`financial_indicator_raw`：提供报告期金额和 Tushare 原始成长字段。

所有字段必须满足：

```text
latest_financial_effective_date <= trade_date
```

## 2. 特殊值规则

所有由“分子 / 分母”生成的比率、增长率、变化率字段，统一采用：

```text
-9ABCDEF
```

详见：[ratio_special_value_policy.md](ratio_special_value_policy.md)

含义简表：

| 位 | 含义 |
|---|---|
| A | 分子为 0 |
| B | 分子为空 |
| C | 分子为负 |
| D | 分母为 0 |
| E | 分母为空 |
| F | 分母为负 |

正常增长率：

```text
current / prior - 1
```

如果 `current` 或 `prior` 出现 0、NULL、负值，则返回特殊编码。

普通差值字段不使用特殊编码：

```text
current_ratio - prior_ratio
```

如果任一输入为空，则返回 NULL。

## 3. 报告期序列

第二阶段先建立报告期序列 CTE 或中间逻辑，不单独要求物理表。

### 3.1 当前报告期

```text
current_report = derived_financial_asof.latest_report_end_date
```

### 3.2 历史匹配报告期

| 名称 | 匹配逻辑 | 用途 |
|---|---|---|
| `prev_report_end_date` | 同股票上一可得报告期 | 报告期环比 |
| `lag_2report_end_date` | 同股票前 2 个可得报告期 | 近 2 期变化 |
| `lag_4report_end_date` | 同股票前 4 个可得报告期 | 近 4 期变化 |
| `lag_8report_end_date` | 同股票前 8 个可得报告期 | 近 8 期变化 |
| `same_period_1y_end_date` | 同股票、同月日、年份 - 1 | 标准同比 |
| `same_period_2y_end_date` | 同股票、同月日、年份 - 2 | 两年累计同比、两年 CAGR |
| `same_period_3y_end_date` | 同股票、同月日、年份 - 3 | 三年累计同比、三年 CAGR |

## 4. 累计报表倒推单季口径

你已确认单季字段使用累计报表倒推。

### 4.1 适用字段

只对流量型字段倒推单季值：

1. 利润表字段：收入、成本、费用、利润。
2. 现金流量表字段：经营、投资、筹资现金流及现金流入流出。

资产负债表字段是时点存量，不倒推单季。

### 4.2 倒推规则

| 报告期 | 单季值 |
|---|---|
| Q1 | `current_cumulative` |
| H1 | `current_cumulative - Q1_cumulative` |
| Q3 | `current_cumulative - H1_cumulative` |
| FY | `current_cumulative - Q3_cumulative` |

若前序累计报告缺失，则单季倒推值返回 NULL。

## 5. 表结构

主键：

```text
ts_code, trade_date
```

元数据字段：

| 字段 | 中文名 | 类型 | 逻辑 |
|---|---|---|---|
| `ts_code` | 股票代码 | VARCHAR | 主键 |
| `trade_date` | 交易日期 | DATE | 主键 |
| `current_report_end_date` | 当前可得报告期 | DATE | `derived_financial_asof.latest_report_end_date` |
| `prev_report_end_date` | 上一报告期 | DATE | 报告期序列上一期 |
| `same_period_1y_end_date` | 去年同期报告期 | DATE | 同月日年份减 1 |
| `same_period_2y_end_date` | 两年前同期报告期 | DATE | 同月日年份减 2 |
| `same_period_3y_end_date` | 三年前同期报告期 | DATE | 同月日年份减 3 |
| `updated_at` | 更新时间 | TIMESTAMP | 构建时间 |

## 6. 字段生成规则

第二阶段字段数量较多，采用“指标基表 + 后缀规则”的方式注册和生成，避免文档与实现长期漂移。

### 6.1 金额类增长字段

金额类字段统一生成以下后缀：

| 后缀 | 中文含义 | 公式 |
|---|---|---|
| `_qoq_report_asof` | 上一报告期变化率 | `safe_growth(current, prev_report)` |
| `_change_2report_asof` | 近 2 报告期变化率 | `safe_growth(current, lag_2report)` |
| `_change_4report_asof` | 近 4 报告期变化率 | `safe_growth(current, lag_4report)` |
| `_change_8report_asof` | 近 8 报告期变化率 | `safe_growth(current, lag_8report)` |
| `_yoy_1y_calc_asof` | 1 年同比计算值 | `safe_growth(current, same_period_1y)` |
| `_yoy_2y_calc_asof` | 2 年累计同比 | `safe_growth(current, same_period_2y)` |
| `_yoy_3y_calc_asof` | 3 年累计同比 | `safe_growth(current, same_period_3y)` |
| `_cagr_2y_asof` | 2 年复合增速 | `safe_cagr(current, same_period_2y, 2)` |
| `_cagr_3y_asof` | 3 年复合增速 | `safe_cagr(current, same_period_3y, 3)` |

金额类基础指标：

| 指标前缀 | 中文名 | 来源 |
|---|---|---|
| `revenue` | 营业收入 | `financial_income_raw.revenue` |
| `total_revenue` | 营业总收入 | `financial_income_raw.total_revenue` |
| `operating_cost` | 营业成本 | `financial_income_raw.operating_cost` |
| `total_cogs` | 营业总成本 | `financial_income_raw.total_cogs` |
| `operating_profit` | 营业利润 | `financial_income_raw.operating_profit` |
| `total_profit` | 利润总额 | `financial_income_raw.total_profit` |
| `net_profit` | 净利润 | `financial_income_raw.net_profit` |
| `parent_net_profit` | 归母净利润 | `financial_income_raw.net_profit_attr_parent` |
| `deducted_profit` | 扣非净利润 | `financial_indicator_raw.profit_dedt` |
| `ebit` | EBIT | `financial_income_raw.ebit` |
| `ebitda` | EBITDA | `financial_income_raw.ebitda` |
| `ocf` | 经营现金流净额 | `financial_cashflow_raw.cf_from_operating` |
| `icf` | 投资现金流净额 | `financial_cashflow_raw.cf_from_investing` |
| `fcf` | 筹资现金流净额 | `financial_cashflow_raw.cf_from_financing` |
| `free_cashflow` | 自由现金流 | `financial_cashflow_raw.free_cashflow` |
| `cash_received_from_sales` | 销售商品提供劳务收到现金 | `financial_cashflow_raw.cash_received_from_sales` |
| `cash_paid_for_goods` | 购买商品接受劳务支付现金 | `financial_cashflow_raw.cash_paid_for_goods` |
| `cash_paid_for_capex` | 购建固定资产等支付现金 | `financial_cashflow_raw.cash_paid_for_capex` |
| `total_assets` | 总资产 | `financial_balance_raw.total_assets` |
| `current_assets` | 流动资产 | `financial_balance_raw.current_assets` |
| `noncurrent_assets` | 非流动资产 | `financial_balance_raw.total_noncurrent_assets` |
| `total_liabilities` | 总负债 | `financial_balance_raw.total_liabilities` |
| `current_liabilities` | 流动负债 | `financial_balance_raw.current_liabilities` |
| `total_equity` | 所有者权益 | `financial_balance_raw.total_equity` |
| `equity_attr_parent` | 归母权益 | `financial_balance_raw.equity_attr_parent` |
| `interestdebt` | 有息负债 | `financial_indicator_raw.interestdebt` |
| `netdebt` | 净债务 | `financial_indicator_raw.netdebt` |
| `rd_expense` | 研发费用 | `financial_income_raw.rd_expense` |
| `selling_expense` | 销售费用 | `financial_income_raw.selling_expense` |
| `admin_expense` | 管理费用 | `financial_income_raw.admin_expense` |
| `finance_expense` | 财务费用 | `financial_income_raw.finance_expense` |

### 6.2 单季倒推增长字段

对流量型金额指标生成单季值和单季增长：

| 后缀 | 中文含义 | 公式 |
|---|---|---|
| `_single_quarter_value_asof` | 倒推单季值 | 见第 4 节 |
| `_single_quarter_yoy_asof` | 单季同比 | `safe_growth(current_single_quarter, prior_year_single_quarter)` |
| `_single_quarter_qoq_asof` | 单季环比 | `safe_growth(current_single_quarter, previous_quarter_single_quarter)` |

适用指标：

```text
revenue, total_revenue, operating_cost, total_cogs,
operating_profit, total_profit, net_profit, parent_net_profit,
deducted_profit, ocf, icf, fcf, free_cashflow,
cash_received_from_sales, cash_paid_for_goods, cash_paid_for_capex,
rd_expense, selling_expense, admin_expense, finance_expense
```

### 6.3 Tushare 原始成长字段

保留 Tushare 原始口径，字段值不做特殊编码转换。

| 字段 | 中文名 | 来源 |
|---|---|---|
| `revenue_yoy_asof` | 营业收入同比 | `financial_indicator_raw.or_yoy` |
| `total_revenue_yoy_asof` | 营业总收入同比 | `financial_indicator_raw.tr_yoy` |
| `netprofit_yoy_asof` | 净利润同比 | `financial_indicator_raw.netprofit_yoy` |
| `deducted_netprofit_yoy_asof` | 扣非净利润同比 | `financial_indicator_raw.dt_netprofit_yoy` |
| `ocf_yoy_asof` | 经营现金流同比 | `financial_indicator_raw.ocf_yoy` |
| `eps_yoy_asof` | EPS 同比 | `financial_indicator_raw.basic_eps_yoy` |
| `dt_eps_yoy_asof` | 扣非 EPS 同比 | `financial_indicator_raw.dt_eps_yoy` |
| `cfps_yoy_asof` | 每股现金流同比 | `financial_indicator_raw.cfps_yoy` |
| `roe_yoy_asof` | ROE 同比 | `financial_indicator_raw.roe_yoy` |
| `bps_yoy_asof` | 每股净资产同比 | `financial_indicator_raw.bps_yoy` |
| `assets_yoy_asof` | 总资产同比 | `financial_indicator_raw.assets_yoy` |
| `equity_yoy_asof` | 所有者权益同比 | `financial_indicator_raw.eqt_yoy` |
| `q_revenue_yoy_asof` | Tushare 单季收入同比 | `financial_indicator_raw.q_sales_yoy` |
| `q_revenue_qoq_asof` | Tushare 单季收入环比 | `financial_indicator_raw.q_sales_qoq` |
| `q_operating_profit_yoy_asof` | Tushare 单季营业利润同比 | `financial_indicator_raw.q_op_yoy` |
| `q_operating_profit_qoq_asof` | Tushare 单季营业利润环比 | `financial_indicator_raw.q_op_qoq` |
| `q_netprofit_yoy_asof` | Tushare 单季净利润同比 | `financial_indicator_raw.q_netprofit_yoy` |
| `q_netprofit_qoq_asof` | Tushare 单季净利润环比 | `financial_indicator_raw.q_netprofit_qoq` |

### 6.4 财务质量字段变化

对 `derived_financial_quality` 中所有数值型业务字段生成变化字段。

变化字段分为两种：

1. 差值变化：适合百分比、比例、周转率、天数、杠杆率。
2. 变化率：适合用户明确希望观察比例本身多周期变化率的字段，例如 `roe_asof`。

统一后缀：

| 后缀 | 中文含义 | 公式 |
|---|---|---|
| `_diff_1report_asof` | 上一报告期差值 | `current - prev_report` |
| `_diff_4report_asof` | 近 4 报告期差值 | `current - lag_4report` |
| `_diff_8report_asof` | 近 8 报告期差值 | `current - lag_8report` |
| `_yoy_diff_asof` | 同比差值 | `current - same_period_1y` |
| `_growth_1report_asof` | 上一报告期变化率 | `safe_growth(current, prev_report)` |
| `_growth_4report_asof` | 近 4 报告期变化率 | `safe_growth(current, lag_4report)` |
| `_growth_8report_asof` | 近 8 报告期变化率 | `safe_growth(current, lag_8report)` |
| `_yoy_growth_asof` | 同比变化率 | `safe_growth(current, same_period_1y)` |

需要覆盖的第一阶段数值字段包括：

```text
roe_asof, roe_waa_asof, roe_dt_asof, roa_asof, roic_asof,
gross_margin_asof, grossprofit_margin_asof, netprofit_margin_asof,
operating_profit_margin_asof, total_profit_margin_asof,
net_profit_margin_calc_asof, parent_net_profit_margin_asof,
minority_profit_ratio_asof, non_operating_income_ratio_asof,
investment_income_ratio_asof, fair_value_gain_ratio_asof,
asset_impairment_to_profit_asof, deducted_profit_to_net_profit_asof,
eps_asof, dt_eps_asof, bps_asof, ocfps_asof, cfps_asof,
ocf_to_profit_asof, ocf_to_revenue_asof, free_cashflow_to_revenue_asof,
cash_received_to_revenue_asof, cash_paid_goods_to_cost_asof,
capex_to_revenue_asof, capex_to_ocf_asof, fcf_to_ocf_asof,
cash_end_to_assets_asof, cash_net_increase_to_assets_asof, accrual_ratio_asof,
cash_to_assets_asof, current_assets_to_assets_asof,
noncurrent_assets_to_assets_asof, fixed_assets_to_assets_asof,
construction_to_assets_asof, goodwill_to_assets_asof,
intangible_to_assets_asof, development_exp_to_assets_asof,
accounts_receivable_to_revenue_asof, inventory_to_revenue_asof,
contract_assets_to_revenue_asof, contract_liability_to_revenue_asof,
working_capital_asof, working_capital_to_assets_asof,
net_working_capital_asof, net_working_capital_to_assets_asof,
debt_to_assets_asof, assets_to_equity_asof, interestdebt_asof, netdebt_asof,
interestdebt_to_assets_asof, netdebt_to_assets_asof,
short_borrowing_to_assets_asof, long_borrowing_to_assets_asof,
bonds_payable_to_assets_asof, current_debt_to_total_debt_asof,
longdebt_to_total_debt_asof, current_ratio_asof, quick_ratio_asof,
cash_ratio_asof, ocf_to_debt_asof, ocf_to_interestdebt_asof,
ebit_to_interest_asof, ebitda_to_debt_asof,
liabilities_to_equity_asof, current_liabilities_to_liabilities_asof,
ar_turn_asof, current_asset_turn_asof, fixed_asset_turn_asof,
assets_turn_asof, turn_days_asof, total_fa_turn_asof,
revenue_to_assets_asof, revenue_to_fixed_assets_asof,
selling_expense_to_revenue_asof, admin_expense_to_revenue_asof,
rd_exp_to_revenue_asof, finance_expense_to_revenue_asof,
expense_to_revenue_asof, business_tax_to_revenue_asof,
income_tax_to_profit_asof, rd_exp_asof, selling_expense_asof,
admin_expense_asof, finance_expense_asof,
dupont_net_margin_asof, dupont_asset_turnover_asof,
dupont_equity_multiplier_asof, dupont_roe_calc_asof, roe_calc_gap_asof,
liability_equity_balance_gap_asof,
liability_equity_balance_gap_ratio_asof,
cashflow_cash_balance_gap_asof,
cashflow_cash_balance_gap_ratio_asof,
statement_available_count_asof, report_age_days_asof, report_lag_days_asof
```

布尔字段不生成增长率，但可以生成状态延续字段。

### 6.5 事实型状态字段

| 字段 | 中文名 | 逻辑 |
|---|---|---|
| `revenue_positive_growth_flag` | 收入正增长标记 | `revenue_yoy_1y_calc_asof > 0` |
| `profit_positive_growth_flag` | 归母净利润正增长标记 | `parent_net_profit_yoy_1y_calc_asof > 0` |
| `deducted_profit_positive_growth_flag` | 扣非净利润正增长标记 | `deducted_profit_yoy_1y_calc_asof > 0` |
| `ocf_positive_growth_flag` | 经营现金流正增长标记 | `ocf_yoy_1y_calc_asof > 0` |
| `revenue_profit_same_direction_flag` | 收入利润同向标记 | 收入和归母净利润同比同号 |
| `profit_ocf_same_direction_flag` | 利润现金流同向标记 | 归母净利润和经营现金流同比同号 |
| `roe_yoy_improving_flag` | ROE 同比改善标记 | `roe_asof_yoy_diff_asof > 0` |
| `gross_margin_yoy_improving_flag` | 毛利率同比改善标记 | `gross_margin_asof_yoy_diff_asof > 0` |
| `debt_to_assets_yoy_increasing_flag` | 资产负债率同比上升标记 | `debt_to_assets_asof_yoy_diff_asof > 0` |
| `ocf_to_profit_yoy_improving_flag` | 经营现金流/净利润同比改善标记 | `ocf_to_profit_asof_yoy_diff_asof > 0` |
| `negative_profit_continued_flag` | 净利润连续为负标记 | 当前与上一报告期均 `negative_net_profit_flag = true` |
| `negative_ocf_continued_flag` | 经营现金流连续为负标记 | 当前与上一报告期均 `negative_ocf_flag = true` |
| `high_goodwill_continued_flag` | 高商誉状态延续标记 | 当前与上一报告期均 `high_goodwill_flag = true` |
| `high_leverage_continued_flag` | 高杠杆状态延续标记 | 当前与上一报告期均 `high_leverage_flag = true` |

## 7. 字段规模估计

| 字段来源 | 估计字段数 |
|---|---:|
| 元数据字段 | 8 |
| Tushare 原始成长字段 | 18 |
| 金额类增长字段 | 约 32 × 9 = 288 |
| 单季倒推字段 | 约 20 × 3 = 60 |
| 财务质量字段差值和变化率 | 约 99 × 8 = 792 |
| 事实型状态字段 | 约 14 |

第二阶段若完全实现所有字段，字段数可能超过 1,100。  
这是可实现的，但会带来较宽的物理表。我的建议是仍按“完整注册、分批落库”的方式推进：

1. 先实现元数据、Tushare 原始成长、金额类增长、单季倒推。
2. 再实现所有 `derived_financial_quality` 数值字段的差值和变化率。
3. 最后实现布尔状态延续字段。

## 8. 质量审计

第二阶段完成后必须审计：

1. 每个字段特殊值编码分布。
2. 正常值非空率。
3. 特殊值中 0、NULL、负值来源占比。
4. 报告期匹配覆盖率。
5. 单季倒推覆盖率。
6. 点时安全：`latest_financial_effective_date <= trade_date`。
7. 抽样核对：至少 10 只股票、4 个报告期，人工核验累计倒推单季和同比匹配。

## 9. 待执行前确认

你已确认：

1. 负值、0 值、空值使用 `-9ABCDEF` 特殊值规则分类。
2. 单季值使用累计报表倒推。
3. 第二阶段实现所有字段。

下一步进入实现前，只需要确认是否接受“完整注册、分批落库”的执行方式，以降低一次性超宽表实现风险。
