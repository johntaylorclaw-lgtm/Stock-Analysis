# Phase 2 Quality Audit Report

Generated at: 2026-05-30T07:18:23 UTC

## Summary

- Tables inspected: 32
- Years covered by trading calendar: 2006 - 2026
- Quality checks with non-zero issues: 0

## Year Coverage

|   year |   open_trade_days |   daily_trade_days |   daily_basic_trade_days |   limit_trade_days |       daily_rows |   daily_basic_rows |       limit_rows |   daily_day_coverage |   daily_basic_day_coverage |   limit_day_coverage |
|-------:|------------------:|-------------------:|-------------------------:|-------------------:|-----------------:|-------------------:|-----------------:|---------------------:|---------------------------:|---------------------:|
|   2006 |               241 |                241 |                      241 |                  0 | 288399           |   288229           |      0           |               1      |                     1      |               0      |
|   2007 |               242 |                242 |                      242 |                242 | 323844           |   323844           | 354200           |               1      |                     1      |               1      |
|   2008 |               246 |                246 |                      246 |                246 | 360812           |   360807           | 387682           |               1      |                     1      |               1      |
|   2009 |               244 |                244 |                      244 |                244 | 375776           |   375770           | 395239           |               1      |                     1      |               1      |
|   2010 |               242 |                242 |                      242 |                242 | 432136           |   432129           | 445760           |               1      |                     1      |               1      |
|   2011 |               244 |                244 |                      244 |                244 | 512177           |   512176           | 529189           |               1      |                     1      |               1      |
|   2012 |               243 |                243 |                      243 |                243 | 566395           |   566389           | 581887           |               1      |                     1      |               1      |
|   2013 |               238 |                238 |                      238 |                238 | 564854           |   564815           | 586145           |               1      |                     1      |               1      |
|   2014 |               245 |                245 |                      245 |                245 | 571035           |   570677           | 619566           |               1      |                     1      |               1      |
|   2015 |               244 |                244 |                      244 |                244 | 575184           |   570310           | 665312           |               1      |                     1      |               1      |
|   2016 |               244 |                244 |                      244 |                244 | 652864           |   642209           | 704154           |               1      |                     1      |               1      |
|   2017 |               244 |                244 |                      244 |                244 | 754372           |   743941           | 798651           |               1      |                     1      |               1      |
|   2018 |               243 |                243 |                      243 |                243 | 824535           |   817638           | 856589           |               1      |                     1      |               1      |
|   2019 |               244 |                244 |                      244 |                244 | 894177           |   885332           | 998531           |               1      |                     1      |               1      |
|   2020 |               243 |                243 |                      243 |                243 | 964131           |   946332           |      1.17652e+06 |               1      |                     1      |               1      |
|   2021 |               243 |                243 |                      243 |                243 |      1.08544e+06 |        1.06191e+06 |      1.30096e+06 |               1      |                     1      |               1      |
|   2022 |               242 |                242 |                      242 |                242 |      1.17907e+06 |        1.17142e+06 |      1.463e+06   |               1      |                     1      |               1      |
|   2023 |               242 |                242 |                      242 |                242 |      1.25873e+06 |        1.25873e+06 |      1.57707e+06 |               1      |                     1      |               1      |
|   2024 |               242 |                242 |                      242 |                242 |      1.29389e+06 |        1.29389e+06 |      1.65513e+06 |               1      |                     1      |               1      |
|   2025 |               243 |                243 |                      243 |                243 |      1.3139e+06  |        1.3139e+06  |      1.74681e+06 |               1      |                     1      |               1      |
|   2026 |               242 |                 92 |                       92 |                 92 | 504043           |   504043           | 690721           |               0.3802 |                     0.3802 |               0.3802 |

## Null / Value Checks

| check_name                                 |   issue_count |
|:-------------------------------------------|--------------:|
| stock_daily.close_null                     |             0 |
| stock_daily.non_positive_close             |             0 |
| stock_adj_factor.null_factor               |             0 |
| stock_adj_factor.non_positive_factor       |             0 |
| financial_income_raw.null_effective_date   |             0 |
| financial_balance_raw.null_effective_date  |             0 |
| financial_cashflow_raw.null_effective_date |             0 |
| financial_indicator_raw.null_ann_date      |             0 |

## Duplicate Checks

| check_name                            |   duplicate_groups |
|:--------------------------------------|-------------------:|
| stock_daily.pk_duplicates             |                  0 |
| stock_daily_basic.pk_duplicates       |                  0 |
| stock_adj_factor.pk_duplicates        |                  0 |
| financial_income_raw.pk_duplicates    |                  0 |
| financial_indicator_raw.pk_duplicates |                  0 |

## View Counts

| view_name                     |     rows |
|:------------------------------|---------:|
| stock_price_adjusted          | 15295776 |
| stock_base_daily              | 15295776 |
| market_breadth_daily          |     4951 |
| concept_daily                 |  4265393 |
| industry_daily                |   153480 |
| stock_base_daily_enriched     | 15295776 |
| financial_income              |   294351 |
| financial_balance             |   272771 |
| financial_cashflow            |   297550 |
| financial_indicator           |   253004 |
| financial_event_forecast      |   139145 |
| financial_event_audit         |    86452 |
| financial_event_mainbz        |   828236 |
| financial_event_holdernumber  |   492451 |
| financial_event_top10_holders |  4242597 |
| financial_event_pledge_detail |   216610 |
| financial_event_repurchase    |    68573 |
| financial_event_share_float   | 10288758 |
| financial_dividend            |   163213 |
| financial_pledge_stat         |  2204384 |