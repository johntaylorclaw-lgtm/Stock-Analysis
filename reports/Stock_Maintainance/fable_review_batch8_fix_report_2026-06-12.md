# Fable 审计修复报告 Batch 8

生成时间：2026-06-12

## 修复范围

本批次处理 M9 中交易行情与技术分析完整视图的核心口径不一致问题。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| M9 完整视图扩展 `max_drawdown_*` 与核心表定义不同 | 客观 | 扩展回撤字段改为窗口内峰谷最大回撤，并要求完整窗口观测数 |
| M9 完整视图扩展 `downside_vol_*` 用 `ELSE 0` 计算下行波动 | 客观 | 改为仅统计负收益日，且负收益观测数不足 2 时输出 NULL |

## 实际刷新

执行 `scripts/create_phase3_trading_technical_full_views.py`，刷新：

| 视图 | 列数 |
|---|---:|
| `derived_daily_spine_full_v` | 62 |
| `derived_price_technical_full_v` | 74 |
| `derived_return_momentum_full_v` | 77 |
| `derived_volatility_risk_full_v` | 50 |
| `derived_volume_liquidity_full_v` | 69 |
| `derived_trading_constraint_full_v` | 69 |

## 抽查

`derived_volatility_risk_full_v` 在 `2026-06-11` 的截面抽查：

| 指标 | 结果 |
|---|---:|
| 行数 | 5,511 |
| `max_drawdown_30_hfq` 非空 | 5,489 |
| `downside_vol_30` 非空 | 5,510 |
| `max_drawdown_30_hfq` 最小值 | -0.9680851064 |
| `max_drawdown_30_hfq` 最大值 | -0.0198675497 |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_technical_windows.py tests/test_views_compat.py` | 5 passed |
| `.venv-wsl/bin/pytest -q` | 70 passed |

## 保留说明

MACD/KDJ 扩展字段仍为近似滚动指标，尚未在本批改成标准 EMA/递归 KDJ。建议后续作为技术指标专项，统一补充 EMA 字段与字典说明。

