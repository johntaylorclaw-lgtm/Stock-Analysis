# Phase 3 Batch 1 启动与进展记录

生成日期：2026-05-30

## 1. 用户确认

进入 Phase 3 Batch 1 前，用户已确认：

1. Phase 3 按 `core first` 推进。
2. 衍生变量 Excel 字典按实际落库字段生成，不以未落库注册草案作为最终字典。
3. 事件和治理模块先做分红、质押、披露、预告快报、审计和主营构成；股东户数、十大股东若结构化不足，则列为延期项。

## 2. Batch 1 范围

| 任务 | 状态 |
|---|---|
| 记录确认事项 | 完成 |
| 建立 Feature Planner 骨架 | 完成 |
| 增加 `plan-features` CLI | 完成 |
| 生成 Batch 1 示例计划 | 完成 |
| 扩展领域驱动衍生变量注册表 | 完成 |
| 增加领域物理表 schema | 完成 |
| 建立计算引擎骨架 | 完成 |
| 实现 `derived_daily_spine` | 完成 |
| 实现 17 个 Phase 3 第一批衍生表近期窗口构建 | 完成 |
| 生成实际落库衍生变量 Excel 字典 | 完成 |
| 生成近期窗口质量审计 | 完成 |
| 建立 `stock_features_core/plus/full` 统一出口视图 | 完成 |
| 增加远期/历史窗口显式确认保护 | 完成 |
| WSL 环境历史全量构建 | 完成 |
| 生成历史全量质量审计 | 完成 |
| 扩展并重建 `derived_daily_spine` | 完成 |

## 3. 已新增工程能力

| 对象 | 路径 |
|---|---|
| Planner | `src/stock_maintainance/features/planner.py` |
| Builder | `src/stock_maintainance/features/modules.py` |
| Writer | `src/stock_maintainance/features/writer.py` |
| CLI | `stock_maintainance.cli plan-features` / `stock_maintainance.cli build-features` |
| 示例计划 | `reports/phase3_feature_plan_batch1.md` |
| 衍生变量 Excel 字典 | `outputs/phase3/derived_variable_dictionary_v1.xlsx` |
| 质量审计 JSON | `outputs/phase3/derived_variable_audit.json` |
| 质量审计报告 | `reports/phase3_batch1_quality_audit.md` |
| 历史全量审计 JSON | `outputs/phase3/derived_variable_audit_full.json` |
| 历史全量审计报告 | `reports/phase3_history_full_quality_audit.md` |
| 统一出口视图 | `stock_features_core` / `stock_features_plus` / `stock_features_full` |
| 历史构建保护 | `build-features --allow-confirmed-history` |
| 历史分块脚本 | `scripts/run_phase3_history_build.py` |
| `daily_spine` 扩展报告 | `reports/phase3_daily_spine_rebuild_report.md` |

Planner 当前支持：

1. 读取变量注册表。
2. 按领域模块展开依赖。
3. 计算 `read_start_date`、`write_start_date`、`write_end_date`。
4. 判断超过默认近期窗口时是否需要确认。
5. 输出 JSON 或 Markdown 计划。

## 4. 当前质量事实

本批次先按默认近期窗口 `2026-05-20` 至 `2026-05-29` 构建。随后在用户确认 Phase 3 目标是历史衍生变量库后，已在 WSL 环境执行历史全量构建，覆盖 `2006-01-04` 至 `2026-05-26`。

历史全量构建采用按月分块，245 个唯一月度块全部成功。第一批 17 个衍生表均已写入历史数据。

统一出口视图已创建并验证：

| 视图 | 行数 | 日期范围 | 股票数 |
|---|---:|---|---:|
| `stock_features_core` | 15295776 | 2006-01-04 至 2026-05-26 | 5809 |
| `stock_features_plus` | 15295776 | 2006-01-04 至 2026-05-26 | 5809 |
| `stock_features_full` | 15295776 | 2006-01-04 至 2026-05-26 | 5809 |

历史或超过默认近期窗口的构建已加入保护：`build-features` 在未传入 `--allow-confirmed-history` 时会阻断执行并输出 `blocked` 状态。

当前需要后续拆解的质量事实：

1. `derived_daily_spine.close_hfq` 历史全量非空率约 97.50%，需进一步区分价格缺失、复权因子缺失和停牌/历史源缺失。
2. `derived_capital_flow` 从 2007-01-04 起覆盖，与资金流基础源起点一致。
3. 财务、质押和组合变量低频覆盖率受公告起点、报表披露和源字段覆盖影响，需要进入后续质量解释报告。

`derived_daily_spine` 已按 2026-05-31 确认方案扩展并重建，新增原始行情、后复权、前复权、基础收益、涨跌停状态、交易状态和质量字段。`stock_features_core` 已改为带出完整 spine 字段。

## 5. 下一步

1. 将第一批核心衍生变量扩展为多字段版本，而不是每个模块仅保留一个代表变量。
2. 将质量审计纳入 Phase 3 日常构建后置步骤。
3. 继续扩展第一批模块的多字段变量设计，并补齐 schema、构建器和数据字典。
