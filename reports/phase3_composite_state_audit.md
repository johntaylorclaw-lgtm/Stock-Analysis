# Phase 3 Composite State 审计报告

- 生成时间：2026-06-05 22:45:05
- 数据库：`/mnt/d/Opencode Workspace/Stock_Maintainance/data/duckdb/stock_data.duckdb`

## 1. 表规模

| 项目 | 结果 |
|---|---:|
| 核心物理表列数 | 92 |
| 完整视图列数 | 115 |
| 条件明细视图列数 | 10 |
| 模块覆盖视图列数 | 8 |
| 核心表行数 | 15,295,776 |
| 覆盖股票数 | 5,809 |
| 覆盖交易日数 | 4,951 |
| 日期范围 | 2006-01-04 至 2026-05-26 |

## 2. 核心字段覆盖率

| 字段 | 非空行数 | 全历史覆盖率 | 最新交易日非空数 |
|---|---:|---:|---:|
| `composite_available_flag` | 15,295,776 | 100.0000% | 5,504 |
| `module_available_ratio` | 15,295,776 | 100.0000% | 5,504 |
| `state_condition_count` | 15,295,776 | 100.0000% | 5,504 |
| `trend_state` | 15,295,776 | 100.0000% | 5,504 |
| `financial_available_flag` | 15,295,776 | 100.0000% | 5,504 |
| `capital_flow_available_flag` | 15,295,776 | 100.0000% | 5,504 |
| `corporate_action_available_flag` | 15,295,776 | 100.0000% | 5,504 |
| `ownership_available_flag` | 15,295,776 | 100.0000% | 5,504 |
| `multi_domain_condition_count` | 15,295,776 | 100.0000% | 5,504 |

## 3. 枚举和一致性检查

| 检查项 | 结果 |
|---|---:|
| 主键重复组数 | 0 |
| `score` 字段数量 | 0 |
| 最新交易日条件明细 true 数与核心表不一致行数 | 0 |
| `list_age_bucket` 非法枚举行数 | 0 |
| `price_valid_state` 非法枚举行数 | 0 |
| `limit_lock_state` 非法枚举行数 | 0 |
| `ma_alignment_state` 非法枚举行数 | 0 |
| `trend_state` 非法枚举行数 | 0 |
| `amount_activity_state` 非法枚举行数 | 0 |
| `volatility_state` 非法枚举行数 | 0 |
| `valuation_percentile_state` 非法枚举行数 | 0 |
| `financial_staleness_state` 非法枚举行数 | 0 |
| `main_flow_persist_state` 非法枚举行数 | 0 |
| `margin_balance_change_state` 非法枚举行数 | 0 |
| `sector_relative_return_state` 非法枚举行数 | 0 |
| `market_context_state` 非法枚举行数 | 0 |
| `pledge_ratio_state` 非法枚举行数 | 0 |

## 4. 最新交易日模块覆盖率

| 模块 | 可用行数 | 应覆盖行数 | 可用率 |
|---|---:|---:|---:|
| `capital_flow` | 5,501 | 5,504 | 99.9455% |
| `corporate_action` | 5,504 | 5,504 | 100.0000% |
| `cross_sectional` | 5,504 | 5,504 | 100.0000% |
| `financial_asof` | 5,390 | 5,504 | 97.9288% |
| `financial_growth` | 5,390 | 5,504 | 97.9288% |
| `financial_quality` | 5,504 | 5,504 | 100.0000% |
| `index_market` | 5,504 | 5,504 | 100.0000% |
| `ownership_governance` | 5,503 | 5,504 | 99.9818% |
| `price_technical` | 5,488 | 5,504 | 99.7093% |
| `return_momentum` | 5,486 | 5,504 | 99.6730% |
| `sector_concept` | 5,497 | 5,504 | 99.8728% |
| `trading_constraint` | 5,504 | 5,504 | 100.0000% |
| `valuation_size` | 5,464 | 5,504 | 99.2733% |
| `volatility_risk` | 5,458 | 5,504 | 99.1642% |
| `volume_liquidity` | 5,491 | 5,504 | 99.7638% |

## 5. 结论

- `derived_composite_state` 已按事实状态汇总层口径落库。
- 本模块不包含 `score` 字段，不生成选股分、买卖信号或未来收益标签。
- 条件计数字段只统计明确布尔事实成立数量，解释入口为 `composite_state_condition_detail_v`。
