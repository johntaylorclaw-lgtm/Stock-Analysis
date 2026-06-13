# Fable 审计修复报告 Batch 10

生成时间：2026-06-12

## 修复范围

本批次处理 M22：衍生变量注册表中财务 as-of 与财务质量模块存在中文名乱码。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| M22 `financial_asof` 27 个 `label_zh` 为纯问号 | 客观 | 全部替换为中文变量名 |
| M22 `financial_quality` 63 个 `label_zh` 为纯问号 | 客观 | 全部替换为中文变量名 |
| M22 字典链路会传导乱码 | 客观 | 重新生成 generated docs 与全局 Excel 数据字典 |

## 验证

| 检查 | 结果 |
|---|---:|
| `derived_financial_asof` / `derived_financial_quality` 纯问号中文名剩余数 | 0 |

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/stock-maintain docs-generate` | regenerated |
| `.venv-wsl/bin/stock-maintain refresh-dictionary --output-prefix global_variable_dictionary` | pass |
| `.venv-wsl/bin/pytest -q tests/test_docs.py` | 3 passed |
| `.venv-wsl/bin/pytest -q` | 72 passed |

