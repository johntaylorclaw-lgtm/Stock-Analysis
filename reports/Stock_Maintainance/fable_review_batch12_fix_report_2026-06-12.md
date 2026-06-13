# Fable 审计修复报告 Batch 12

生成时间：2026-06-12

## 修复范围

本批次处理 M24：Excel 数据字典生成链路对单机 Windows Node 路径和 artifact-tool 环境依赖过强。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| M24 `dictionary.py` 硬编码特定 Windows Node 路径 | 客观 | 增加 Node 自动发现：`STOCK_MAINTAIN_NODE`、WSL/PATH `node`、bundled Windows Node |
| M24 WSL Node 可能加载 Windows 原生模块失败 | 客观 | WSL Node 失败后自动尝试 Windows bundled Node + PowerShell |
| M24 失败信息缺少降级建议 | 客观 | 失败时输出 stdout/stderr 细节，并提示 `--skip-excel` 降级 |

## 实证

本机 WSL `node` 可执行，但会因 `@oai/artifact-tool` 软链到 Windows 原生模块出现 `invalid ELF header`；修复后自动回退 Windows bundled Node，`refresh-dictionary` 成功。

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_dictionary.py` | 5 passed |
| `.venv-wsl/bin/stock-maintain refresh-dictionary --output-prefix fable_fix_dictionary_portability` | pass |
| `.venv-wsl/bin/pytest -q` | 76 passed |

