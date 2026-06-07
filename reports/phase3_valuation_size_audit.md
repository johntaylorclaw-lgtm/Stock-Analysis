# Phase 3 估值与规模模块审计报告

- 生成时间：2026-06-01T23:27:48
- 数据库：`/mnt/d/Opencode Workspace/Stock_Maintainance/data/duckdb/stock_data.duckdb`
- 说明：历史分位字段采用物理缓存表 `derived_valuation_percentile_cache`，完整视图通过 join 读取，避免视图查询时重复构造 10 年滚动窗口。

## 1. 字段注册与实际对象核对

| 对象 | 注册字段数 | 实际字段数 | 状态 |
|---|---:|---:|---|
| `derived_valuation_size` | 34 | 34 | OK |
| `derived_valuation_percentile_cache` | 43 | 43 | OK |
| `derived_valuation_size_full_v` | 165 | 165 | OK |

## 2. 覆盖率

| 表 | 行数 | 股票数 | 最早日期 | 最新日期 |
|---|---:|---:|---|---|
| `derived_valuation_size` | 15,295,776 | 5,809 | 2006-01-04 | 2026-05-26 |
| `derived_valuation_percentile_cache` | 15,295,776 | 5,809 | 2006-01-04 00:00:00 | 2026-05-26 00:00:00 |

## 3. 关键字段非空率

| 表 | 字段 | 非空行数 | 总行数 | 非空率 |
|---|---|---:|---:|---:|
| `derived_valuation_size` | `pe_ttm` | 12,648,143 | 15,295,776 | 82.6904% |
| `derived_valuation_size` | `pb` | 15,076,765 | 15,295,776 | 98.5682% |
| `derived_valuation_size` | `ps_ttm` | 15,189,331 | 15,295,776 | 99.3041% |
| `derived_valuation_size` | `total_mv` | 15,204,488 | 15,295,776 | 99.4032% |
| `derived_valuation_size` | `free_float_mv` | 15,198,673 | 15,295,776 | 99.3652% |
| `derived_valuation_size` | `pe_ttm_pct_5y` | 12,648,143 | 15,295,776 | 82.6904% |
| `derived_valuation_size` | `pb_pct_5y` | 15,076,765 | 15,295,776 | 98.5682% |
| `derived_valuation_size` | `ps_ttm_pct_5y` | 15,189,331 | 15,295,776 | 99.3041% |
| `derived_valuation_size` | `total_mv_pct_5y` | 15,204,488 | 15,295,776 | 99.4032% |
| `derived_valuation_percentile_cache` | `pe_ttm_pct_10y` | 12,648,143 | 15,295,776 | 82.6904% |
| `derived_valuation_percentile_cache` | `pb_pct_10y` | 15,076,765 | 15,295,776 | 98.5682% |
| `derived_valuation_percentile_cache` | `ps_ttm_pct_10y` | 15,189,331 | 15,295,776 | 99.3041% |
| `derived_valuation_percentile_cache` | `total_mv_pct_10y` | 15,204,488 | 15,295,776 | 99.4032% |
| `derived_valuation_percentile_cache` | `free_float_mv_pct_10y` | 15,198,673 | 15,295,776 | 99.3652% |

## 4. 完整视图近端可查询核对

| 项目 | 数值 |
|---|---:|
| 行数 | 27,511 |
| 股票数 | 5,506 |
| 日期范围 | 2026-05-20 ~ 2026-05-26 |
| `pe_ttm_pct_10y` 非空 | 19,799 |
| `amount_to_total_mv` 非空 | 27,511 |
| `peg_ttm` 非空 | 8,560 |

## 5. 单位校准结论

- `free_float_mv = close_raw * free_share`，与 Tushare `total_mv/circ_mv` 的万元口径一致。
- `stock_daily.amount` 为千元口径，`total_mv/circ_mv` 为万元口径，因此 `amount_to_total_mv = amount / 10 / total_mv`。
