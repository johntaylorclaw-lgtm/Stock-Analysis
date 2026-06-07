# Phase 3 综合事实状态模块执行记录

生成日期：2026-06-05

## 1. 完成范围

已完成 `composite_state` 模块全量历史构建。模块定位为事实状态汇总层，不生成选股分、不生成买卖信号、不生成未来收益标签。

旧占位字段 `value_quality_score` 已从 `derived_composite_state` 中删除，本模块不包含任何 `score` 字段。

## 2. 产出对象

| 对象 | 类型 | 列数 | 行数/状态 |
|---|---|---:|---:|
| `derived_composite_state` | 物理表 | 92 | 15,295,776 |
| `derived_composite_state_full_v` | 视图 | 115 | 15,295,776 |
| `composite_state_condition_detail_v` | 视图 | 10 | 长表视图 |
| `composite_state_module_coverage_v` | 视图 | 8 | 按交易日和模块统计 |

## 3. 关键口径

1. 状态枚举统一使用英文编码。
2. 暴露 z 值状态采用 `low/mid/high/unknown`，对应 `<= -1`、`-1~1`、`>= 1` 和缺失。
3. 截面分位和历史分位状态采用 `low/mid/high/unknown`，对应 `<20%`、`20%-80%`、`>80%` 和缺失。
4. 条件计数字段只统计明确布尔事实成立数量，不加权、不表达好坏。
5. 条件计数解释入口为 `composite_state_condition_detail_v`。
6. 公司行为和持有人治理状态只做事实枚举，不做风险或机会判断。

## 4. 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/register_phase3_composite_state.py` | 注册表结构和变量字典 |
| `scripts/reset_phase3_composite_state_table.py` | 重建核心物理表 |
| `scripts/build_phase3_composite_state_core.py` | 分年构建核心日频事实状态 |
| `scripts/create_phase3_composite_state_views.py` | 创建完整视图、条件明细视图和模块覆盖视图 |
| `scripts/generate_phase3_composite_state_audit.py` | 生成审计报告 |

## 5. 验收

审计报告：`reports/phase3_composite_state_audit.md`

| 检查项 | 结果 |
|---|---:|
| 主键重复组数 | 0 |
| `score` 字段数量 | 0 |
| 最新交易日条件明细 true 数与核心表不一致行数 | 0 |
| 枚举字段非法值 | 0 |

测试结果：`python -m pytest`，11 项通过。

## 6. 数据字典

已刷新全局 Excel 数据字典：

`outputs/variable_dictionary/global_variable_dictionary.xlsx`

由于 Excel sheet 名长度限制，composite 相关 sheet 名可能会自动截短。可从 `Table_Index` 的中文表名定位：

| 对象 | 中文表名 |
|---|---|
| `derived_composite_state` | 综合事实状态衍生表 |
| `derived_composite_state_full_v` | 综合事实状态完整视图 |
| `composite_state_condition_detail_v` | 综合事实状态条件明细视图 |
| `composite_state_module_coverage_v` | 综合事实状态模块覆盖视图 |
