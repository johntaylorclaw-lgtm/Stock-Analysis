# Fable 审计修复报告 Batch 11

生成时间：2026-06-12

## 修复范围

本批次处理 M10 中估值分位字段依赖缓存回填的剩余运行风险。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| M10 `valuation_size` 若跳过缓存步骤会把 5 年分位字段保留为 NULL | 客观 | 真实执行中禁止对发布缓存支撑核心字段的模块跳过必要缓存 |
| 同类风险 `capital_flow` 后置缓存也可能被跳过 | 客观 | 同一保护覆盖 `POST_CACHE_STEPS` 中的模块，当前包括 `valuation_size` 与 `capital_flow` |

## 行为变化

| 场景 | 结果 |
|---|---|
| `build-features --module valuation_size --skip-cache-steps --dry-run` | 允许，用于查看计划 |
| `build-features --module valuation_size --skip-cache-steps` | blocked，返回码 2 |
| `build-features --module valuation_size` | 正常执行模块并运行 `valuation_percentile_cache` |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_phase4_dry_run.py` | 8 passed |
| `.venv-wsl/bin/pytest -q` | 73 passed |
| `stock_maintainance.cli.main([... --skip-cache-steps])` | `RETURN_CODE 2` |

