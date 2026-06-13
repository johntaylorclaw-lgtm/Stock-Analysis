# Fable 审计修复报告 Batch 26

生成时间：2026-06-13

## 修复范围

本批次收尾 Batch 25 留下的两项低危但影响文档可信度的问题：

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L23 基础变量中文字段说明不足 | 客观 | `config/variables/base_variables.json` 已从 Draft 说明升级为正式维护说明，543 个基础变量均有中文 `label_zh`，并补齐财务单季度指标等 22 个兜底字段 |
| L24 截面 full view winsor/rank 口径说明不足 | 客观 | `scripts/register_phase3_cross_sectional.py` 改为按实际生成逻辑输出公式说明，区分原始来源缩尾后的 rank/z 与基于核心表 `*_z_all` 的二次分组 rank/z |

## 关键变更

1. 新增 `scripts/repair_base_variable_labels.py`，用于维护基础变量中文字段名，避免基础变量字典回退到英文草稿。
2. 增强 `derived_cross_sectional_full_v` 注册说明，明确：
   - 有效样本条件：`xs_universe_flag=true`、source 非空、非特殊值，并按变量 `valid_rule` 过滤正值或非负值。
   - 视图扩展变量：先做 `winsor(source,1%,99%)`，再按全市场、市场、申万行业或交易所分组计算 rank/pct/z。
   - 核心变量扩展分组：基于核心表已落库的 `{variable}_z_all` 再做分组 rank/pct/z。
   - rank 最小样本数为 5，z-score 最小样本数为 20，样本不足或标准差为 0 时返回 `NULL`。
3. 增加防回归测试：
   - 基础变量注册表不得再含 Draft 说明、纯英文 `label_zh` 或 `字段：xxx` 兜底标签。
   - 截面 full view 生成后的 schema 不得再含占位式“完整视图扩展截面字段”说明。

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_docs.py tests/test_cross_sectional_script.py` | 7 passed |
| `.venv-wsl/bin/stock-maintain validate-config` | config validation passed |
| `.venv-wsl/bin/pytest -q` | 103 passed |
| `.venv-wsl/bin/stock-maintain refresh-dictionary --output-prefix global_variable_dictionary` | pass，Excel 与 JSON 字典已刷新 |
| `.venv-wsl/bin/stock-maintain docs-check` | docs are up to date |

## 当前结论

截至本批次，Fable 审计中已经确认客观且可在当前工程边界内修复的事项均已完成代码、配置、文档和字典层面的修复。尚未执行的是生产库历史全量重算；涉及口径变化的模块若要让数据库中既有历史数值完全反映新口径，需要按后续运维窗口进行模块级或全量刷新。
