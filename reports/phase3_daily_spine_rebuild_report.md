# Phase 3 `derived_daily_spine` 扩展与重建报告

生成日期：2026-05-31

## 1. 本次完成

1. 扩展 `derived_daily_spine` schema，从原来的少数字段扩展为日频主干、原始行情、复权价格、基础收益、涨跌停状态和质量标记。
2. 明确变量复权口径：连续历史变量使用后复权，涨跌停和财务交叉相关字段使用原始价格，前复权字段仅作为当前尺度展示口径。
3. 新增 `config/variables/derived_daily_spine_variables.json`，维护新增字段的中文名、含义、算法、复权口径和用途。
4. 修改 `build_daily_spine` 构建器，支持新增字段落库。
5. 使用 WSL 环境按月重建 `2006-01-04` 至 `2026-05-26` 的 `derived_daily_spine` 历史全量数据。
6. 刷新 `stock_features_core`，使统一出口视图包含完整 spine 字段。
7. 刷新衍生变量 Excel 字典和 `000001.SZ` 抽样 Excel。

## 2. 落库覆盖

| 指标 | 结果 |
|---|---:|
| 行数 | 15295776 |
| 开始日期 | 2006-01-04 |
| 结束日期 | 2026-05-26 |
| 股票数 | 5809 |
| 历史重建分块 | 245 |

## 3. 质量概览

| 指标 | 行数 | 占比 |
|---|---:|---:|
| 有价格 `has_price` | 15295776 | 100.00% |
| 有复权因子 `has_adj_factor` | 14913039 | 97.50% |
| 有涨跌停价 `has_limit_price` | 14912922 | 97.50% |
| 价格关系有效 `price_valid_flag` | 15295774 | 100.00% |

缺失原因分布：

| 缺失原因 | 行数 |
|---|---:|
| 无缺失原因 | 14549967 |
| `missing_adj_factor` | 382737 |
| `missing_limit_price` | 363072 |

## 4. 产物

| 产物 | 路径 |
|---|---|
| `daily_spine` 设计文档 | `docs/phase3_daily_spine_design.md` |
| 衍生变量 Excel 字典 | `outputs/phase3/derived_variable_dictionary_v1.xlsx` |
| 样例 Excel | `outputs/phase3/sample_derived_variables_000001_SZ.xlsx` |
| 重建日志 | `logs/phase3_daily_spine_rebuild_progress.jsonl` |

## 5. 注意事项

1. `log_ret_1` 暂作为兼容字段保留，规范字段为 `log_ret_1_hfq`。
2. `latest_adj_factor_asof` 和 `*_qfq` 使用当前数据库最新复权因子，不是严格点时安全口径，主要用于展示和人工读图。
3. `adj_factor`、`up_limit`、`down_limit` 因基础变量注册表已有同名字段，当前未在新增 spine 注册文件中重复注册，但字段已在物理表落库。
4. 下游 `derived_price_technical` 等表尚未按新的 spine 扩展重建；后续逐表确认结构后再统一更新。
