# Fable 审计修复报告 Batch 7

生成时间：2026-06-12

## 修复范围

本批次处理 Fable 审计中偏运行机制、视图刷新、来源注册和文档入口的中低风险问题。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| M17 统一出口视图刷新缺少错误隔离 | 客观 | `create_views` 改为逐视图尝试刷新，最终汇总错误并返回失败，避免一个普通视图阻断全部后续视图 |
| M20 `run_summary` 空库可能误报 pass、日报默认前缀不匹配 | 客观 | status 模式在交易日或数据锚点缺失时返回 `blocked`；daily 默认报告前缀改为当前 `daily_` |
| M23 README 与当前工程阶段脱节 | 客观 | 重写 README，改为 Phase 5/WSL/日批周批/主文档入口 |
| M25 `sources.json` 缺少 `stock_company` | 客观 | 补充 `stock_company` Tushare 来源注册，并重新生成 source dictionary |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_run_summary.py tests/test_views_compat.py tests/test_docs.py` | 8 passed |
| `.venv-wsl/bin/pytest -q` | 69 passed |
| `.venv-wsl/bin/stock-maintain docs-generate` | regenerated generated docs |

## 说明

`create_views` 仍会在任一视图刷新失败时以非零错误结束；变化点只是会尽量刷新独立后续视图，并把所有失败点一次性汇总，便于定位。

