# 全量拉齐执行记录

生成时间：2026-06-13

## 执行目标

将基础日频数据、主要市场行为数据、指数日行情和 Phase 3 衍生变量重新拉齐到当前最新 A 股交易日。

本地交易日历确认的最新交易日为：`2026-06-12`。

## 执行命令

```bash
.venv-wsl/bin/stock-maintain daily-full \
  --as-of-date 2026-06-13 \
  --reload-trade-days 1 \
  --refresh-weekly-snapshot \
  --output-prefix full_align_execute_20260613
```

补充重试：

```bash
.venv-wsl/bin/stock-maintain sync-market-behavior-range 20260612 20260612 --force
```

## 结果摘要

| 项目 | 结果 |
|---|---|
| 最新交易日 | `2026-06-12` |
| daily-full 状态 | `warning` |
| warning 原因 | `margin_detail` 已有 2026-06-12 数据，但行数 1980 低于近 5 日均值阈值；二次强制拉取仍返回 1980，判断为源端当前可得数据量偏低 |
| weekly 快照 | 已刷新 |
| weekly compare | `pass`，25 张表通过 |
| 状态汇总 | `pass` |

## 关键表覆盖

| 表 | 最新日期 | 最新日行数 |
|---|---:|---:|
| `stock_daily` | 2026-06-12 | 5512 |
| `stock_daily_basic` | 2026-06-12 | 5512 |
| `stock_adj_factor` | 2026-06-12 | 5529 |
| `stock_limit_price` | 2026-06-12 | 7651 |
| `stock_moneyflow_daily` | 2026-06-12 | 5194 |
| `margin_detail` | 2026-06-12 | 1980 |
| `northbound_daily` | 2026-06-12 | 1 |
| `northbound_holding` | 2026-06-12 | 944 |
| `index_daily` | 2026-06-12 | 14 |
| `derived_daily_spine` | 2026-06-12 | 5512 |
| `derived_price_technical` | 2026-06-12 | 5512 |
| `derived_volume_liquidity` | 2026-06-12 | 5512 |
| `derived_return_momentum` | 2026-06-12 | 5512 |
| `derived_volatility_risk` | 2026-06-12 | 5512 |
| `derived_trading_constraint` | 2026-06-12 | 5512 |
| `derived_valuation_size` | 2026-06-12 | 5512 |
| `derived_financial_asof` | 2026-06-12 | 5512 |
| `derived_financial_quality` | 2026-06-12 | 5512 |
| `derived_financial_growth` | 2026-06-12 | 5512 |
| `derived_capital_flow` | 2026-06-12 | 5512 |
| `derived_sector_concept_context` | 2026-06-12 | 5512 |
| `derived_index_market_context` | 2026-06-12 | 5512 |
| `derived_cross_sectional` | 2026-06-12 | 5512 |
| `derived_corporate_action` | 2026-06-12 | 5512 |
| `derived_ownership_governance` | 2026-06-12 | 5512 |
| `derived_composite_state` | 2026-06-12 | 5512 |

## 报告路径

| 报告 | 路径 |
|---|---|
| daily-full 执行报告 | `reports/full_align_execute_20260613.md` |
| daily-full postcheck | `reports/full_align_execute_20260613_postcheck.md` |
| weekly 快照刷新 | `reports/full_align_execute_20260613_weekly_snapshot.md` |
| weekly compare | `reports/full_align_weekly_compare_20260613.md` |
| 状态汇总 | `reports/summaries/status_after_full_align_20260613.md` |

## 后续观察

`margin_detail` 2026-06-12 行数偏低但源端二次拉取结果一致。建议在下一个交易日或下一个维护窗口再次执行 `daily-full --reload-trade-days 1` 或针对 2026-06-12 单独重试市场行为数据，以确认交易所/Tushare 是否补齐融资融券明细。
