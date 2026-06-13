# Fable 审计修复报告 Batch 25

生成时间：2026-06-13

## 修复范围

本批次继续处理 Fable 审计中尚未完成的低危项，覆盖 L1、L6、L7、L8、L9、L10、L11、L12、L13、L20、L22 的全部或主要可执行修复。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L1 `gap_open_hfq` 与 `overnight_ret_hfq` 重复 | 客观 | `overnight_ret_hfq` 保留有方向隔夜收益；`gap_open_hfq` 改为无方向绝对跳空幅度 |
| L6 交易约束滚动计数无观测守门 | 客观 | 5/20 日涨跌停与触板统计增加有效 flag 观测数守门；read-context 已由现有参数覆盖 |
| L7 概念缓存 `up_ratio` 名称误导 | 客观 | 概念缓存内部改用 `limit_up_ratio`，schema 说明改为“概念涨停占比均值” |
| L8 主营构成缺公告日合成 PIT 未登记 | 客观 | 在 `docs/03_数据契约与命名规范.md` 登记 `end_date + 120 天` 保守可得日兜底 |
| L9 波动风险短窗使用宽窗观测守门 | 客观 | `hv/parkinson/ATR/回撤/downside/var` 改为各自窗口的观测数守门 |
| L10 北向持股数量与比例聚合口径不一致 | 客观 | `north_hold_ratio` 改为 `sum(hold_ratio)`，与 `sum(hold_shares)` 一致 |
| L11 估值分位短样本和负 PE 问题 | 客观 | 历史分位要求至少 60 个正值观测，PE/PB/PS/市值分位排除非正样本 |
| L12 composite trend 空值落入 bear | 客观 | 增加趋势观察数，全部缺失时 `trend_state='unknown'` |
| L13 独立截面脚本年批次无事务 | 客观 | 每个年度窗口加入 `BEGIN/COMMIT/ROLLBACK` |
| L20 DuckDB 单写锁重试 | 部分修复 | `connect()` 增加 DuckDB IO 异常重试；长连接重构仍可作为后续性能专项 |
| L22 daily spine 空壳变量文件和公式不足 | 客观 | 删除空壳 `derived_daily_spine_variables.json`，为 43 个 spine 变量补充公式和依赖 |

## 仍未完全完成

| 审计项 | 状态 | 原因/建议 |
|---|---|---|
| L23 基础变量中文字段说明 | 未完全完成 | `base_variables.json` 仍有大量英文 `label_zh`，需要按 Tushare 字段说明做专项翻译和校验 |
| L24 截面 full view winsor/rank 口径说明 | 未完全完成 | 需要补充字典说明或进一步统一核心表与 full view 的 rank/winsor 口径 |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_technical_windows.py tests/test_phase3_composite_state.py tests/test_capital_flow_cache_script.py tests/test_sector_index_cache_script.py tests/test_cross_sectional_script.py tests/test_database_connect.py tests/test_valuation_percentile_cache.py` | 16 passed |
| `.venv-wsl/bin/stock-maintain validate-config` | passed |
| `.venv-wsl/bin/stock-maintain docs-generate` | passed |
| `.venv-wsl/bin/stock-maintain refresh-dictionary --output-prefix global_variable_dictionary` | completed; global dictionary generated |
| `.venv-wsl/bin/stock-maintain docs-check` | docs are up to date |
| `.venv-wsl/bin/pytest -q` | 101 passed |

## 说明

本批次未执行全历史重算，仅修复代码、配置、文档与字典生成物。涉及数值口径变化的模块包括 `daily_spine`、`trading_constraint`、`volatility_risk`、`capital_flow`、`valuation_percentile_cache`、`composite_state`；后续如需生产库数值完全刷新，应按模块窗口或全量重建策略执行。
