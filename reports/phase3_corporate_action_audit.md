# Phase 3 Corporate Action 审计报告

- 生成时间：2026-06-05 08:16:19
- 数据库：`/mnt/d/Opencode Workspace/Stock_Maintainance/data/duckdb/stock_data.duckdb`

## 1. 表规模

| 项目 | 结果 |
|---|---:|
| 核心物理表列数 | 104 |
| 完整视图列数 | 144 |
| 事件时间线视图列数 | 10 |
| 核心表行数 | 15,295,776 |
| 覆盖股票数 | 5,809 |
| 覆盖交易日数 | 4,951 |
| 日期范围 | 2006-01-04 至 2026-05-26 |

## 2. 来源对象行数

| 对象 | 行数 |
|---|---:|
| `financial_dividend` | 163,213 |
| `financial_forecast` | 139,145 |
| `financial_express` | 28,163 |
| `financial_audit_opinion` | 86,452 |
| `financial_main_business` | 828,236 |
| `financial_repurchase` | 68,573 |
| `financial_share_float` | 10,288,758 |
| `derived_corporate_action` | 15,295,776 |
| `derived_corporate_action_full_v` | 15,295,776 |
| `corporate_action_event_timeline_v` | 11,602,540 |

## 3. 核心字段覆盖率

| 字段 | 非空行数 | 全历史覆盖率 | 最新交易日非空数 |
|---|---:|---:|---:|
| `cash_dividend_ttm` | 15,295,776 | 100.0000% | 5,504 |
| `has_forecast_asof` | 15,295,776 | 100.0000% | 5,504 |
| `has_express_asof` | 15,295,776 | 100.0000% | 5,504 |
| `audit_opinion_code_latest` | 14,851,216 | 97.0936% | 5,461 |
| `mainbz_top1_revenue_ratio_latest` | 8,078,080 | 52.8125% | 5,454 |
| `repurchase_amount_365d` | 15,295,776 | 100.0000% | 5,504 |
| `share_float_share_365d` | 8,188,384 | 53.5336% | 1,397 |
| `next_share_float_share_30d` | 339,444 | 2.2192% | 0 |
| `next_share_float_share_90d` | 933,578 | 6.1035% | 0 |
| `float_share_ratio_asof` | 15,204,488 | 99.4032% | 5,504 |
| `total_share_chg_20d` | 13,799,086 | 90.2150% | 5,489 |

## 4. Point-in-time 检查

| 检查项 | 结果 |
|---|---:|
| 未来90日解禁窗口无已公告事件支撑行数 | 0 |

## 5. 完整视图运行检查

| 字段 | 最新交易日非空数 |
|---|---:|
| `cash_dividend_5y_sum` | 5,477 |
| `forecast_count_365d` | 5,504 |
| `mainbz_hhi_revenue_latest` | 5,455 |
| `next_share_float_share_180d` | 0 |

## 6. 结论

- `derived_corporate_action` 已按公司行为事实口径落库。
- 分红现金字段保留 Tushare 原始每股口径，不做复权。
- 未来解禁窗口仅统计 `ann_date <= trade_date < float_date` 的已公告事件。
- 质押、股东户数、十大股东未进入本模块，后续由 `ownership_governance` 维护。
