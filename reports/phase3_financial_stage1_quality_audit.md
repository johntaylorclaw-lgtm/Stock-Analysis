# Phase 3 财务衍生第一阶段质量审计

生成时间：2026-05-31 15:03:05

## 表级覆盖

| 表 | 行数 | 股票数 | 起始日期 | 结束日期 | 字段数 |
|---|---:|---:|---|---|---:|
| `derived_financial_asof` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 | 30 |
| `derived_financial_quality` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 | 119 |

## 点时安全
- `latest_financial_effective_date <= trade_date` 违反行数：0
- 报告期随交易日倒退行数：0

## 关键字段非空率
| 表 | 字段 | 非空行数 | 非空率 |
|---|---|---:|---:|
| `derived_financial_asof` | `latest_report_end_date` | 12,397,832 | 81.05% |
| `derived_financial_asof` | `latest_financial_effective_date` | 12,397,832 | 81.05% |
| `derived_financial_asof` | `report_age_days` | 12,397,832 | 81.05% |
| `derived_financial_asof` | `statement_available_count` | 15,295,776 | 100.00% |
| `derived_financial_asof` | `has_income_statement` | 11,933,051 | 78.02% |
| `derived_financial_asof` | `has_balance_sheet` | 12,115,716 | 79.21% |
| `derived_financial_asof` | `has_cashflow_statement` | 12,146,355 | 79.41% |
| `derived_financial_asof` | `has_indicator_statement` | 12,397,832 | 81.05% |
| `derived_financial_asof` | `has_forecast_asof` | 15,295,776 | 100.00% |
| `derived_financial_asof` | `has_express_asof` | 15,295,776 | 100.00% |
| `derived_financial_quality` | `roe_asof` | 12,327,174 | 80.59% |
| `derived_financial_quality` | `roa_asof` | 12,158,027 | 79.49% |
| `derived_financial_quality` | `gross_margin_asof` | 12,151,549 | 79.44% |
| `derived_financial_quality` | `netprofit_margin_asof` | 12,389,908 | 81.00% |
| `derived_financial_quality` | `ocf_to_profit_asof` | 11,705,416 | 76.53% |
| `derived_financial_quality` | `ocf_to_revenue_asof` | 11,699,472 | 76.49% |
| `derived_financial_quality` | `cash_to_assets_asof` | 11,987,800 | 78.37% |
| `derived_financial_quality` | `debt_to_assets_asof` | 12,395,032 | 81.04% |
| `derived_financial_quality` | `current_ratio_asof` | 12,173,999 | 79.59% |
| `derived_financial_quality` | `accounts_receivable_to_revenue_asof` | 11,397,643 | 74.51% |
| `derived_financial_quality` | `goodwill_to_assets_asof` | 6,165,719 | 40.31% |
| `derived_financial_quality` | `expense_to_revenue_asof` | 11,905,514 | 77.84% |
| `derived_financial_quality` | `dupont_roe_calc_asof` | 11,694,487 | 76.46% |
| `derived_financial_quality` | `liability_equity_balance_gap_asof` | 12,095,326 | 79.08% |
| `derived_financial_quality` | `cashflow_cash_balance_gap_asof` | 12,116,434 | 79.21% |

## 年度覆盖率
| 年份 | 行数 | 有财报行数 | 覆盖率 |
|---:|---:|---:|---:|
| 2006 | 288,399 | 365 | 0.13% |
| 2007 | 323,844 | 4,723 | 1.46% |
| 2008 | 360,812 | 7,487 | 2.08% |
| 2009 | 375,776 | 8,617 | 2.29% |
| 2010 | 432,136 | 10,815 | 2.50% |
| 2011 | 512,177 | 17,905 | 3.50% |
| 2012 | 566,395 | 166,563 | 29.41% |
| 2013 | 564,854 | 537,739 | 95.20% |
| 2014 | 571,035 | 561,877 | 98.40% |
| 2015 | 575,184 | 565,681 | 98.35% |
| 2016 | 652,864 | 642,131 | 98.36% |
| 2017 | 754,372 | 741,907 | 98.35% |
| 2018 | 824,535 | 811,255 | 98.39% |
| 2019 | 894,177 | 878,929 | 98.29% |
| 2020 | 964,131 | 946,904 | 98.21% |
| 2021 | 1,085,445 | 1,063,095 | 97.94% |
| 2022 | 1,179,072 | 1,153,570 | 97.84% |
| 2023 | 1,258,734 | 1,230,618 | 97.77% |
| 2024 | 1,293,893 | 1,266,802 | 97.91% |
| 2025 | 1,313,898 | 1,287,244 | 97.97% |
| 2026 | 504,043 | 493,605 | 97.93% |

## 极值抽查
| 字段 | min | p01 | median | p99 | max |
|---|---:|---:|---:|---:|---:|
| `roe_asof` | -19210 | -28.4145 | 2.8735 | 25.852 | 80618.6 |
| `roa_asof` | -1.15774e+06 | -7.4219 | 2.1809 | 18.4385 | 1716.61 |
| `gross_margin_asof` | -2.99147e+10 | -1.37421e+07 | 2.03211e+08 | 1.3459e+10 | 7.11232e+11 |
| `debt_to_assets_asof` | -68.3827 | 4.7493 | 40.5208 | 94.8066 | 19173.9 |
| `ocf_to_profit_asof` | -41307.7 | -49.8663 | 0.580615 | 39.6765 | 25613.6 |
| `goodwill_to_assets_asof` | -0.000868956 | 0 | 0.0110857 | 0.414243 | 0.841591 |
| `liability_equity_balance_gap_ratio_asof` | -0.130384 | -1.60341e-16 | 0 | 1.59813e-16 | 0.0476122 |
| `cashflow_cash_balance_gap_ratio_asof` | -19.6777 | -0.0328095 | 0.000195772 | nan | nan |
