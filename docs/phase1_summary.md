# Phase 1 完成记录

生成日期：2026-05-27

## 1. Phase 1 目标

Phase 1 的目标是把 Phase 0 和前置设计落成可执行的工程骨架，暂不拉取和写入真实数据。

本阶段完成：

1. Python 项目骨架。
2. 配置系统。
3. 数据源注册表。
4. pipeline 策略配置。
5. schema 注册表。
6. 变量注册表第一版。
7. CLI 基础命令。
8. 自动生成文档和漂移检查。
9. Phase 2 确认清单。

## 2. 产出文件

| 文件 | 说明 |
|---|---|
| `pyproject.toml` | Python 包和命令入口 |
| `README.md` | 项目入口说明 |
| `config/sources.json` | Tushare API 数据源注册 |
| `config/pipeline.json` | 日常更新、历史修复、股票范围、指数池策略 |
| `config/schema_registry.json` | Phase 1 schema 注册表 |
| `config/variables/base_variables.json` | 基础变量注册表示例 |
| `config/variables/derived_variables.json` | 衍生变量注册表示例 |
| `src/stock_maintainance/cli.py` | CLI 命令入口 |
| `src/stock_maintainance/schema.py` | DDL 生成 |
| `src/stock_maintainance/docs.py` | 自动文档生成和检查 |
| `src/stock_maintainance/validate.py` | 配置校验 |
| `docs/generated_schema_dictionary.md` | 自动生成 schema 字典 |
| `docs/generated_variable_dictionary.md` | 自动生成变量字典 |
| `docs/generated_source_dictionary.md` | 自动生成数据源字典 |
| `docs/phase2_confirmation_checklist.md` | Phase 2 前确认清单 |

## 3. 当前已固化的关键策略

| 主题 | 策略 |
|---|---|
| 股票范围 | A 股全市场：SSE/SZSE/BSE，主板、创业板、科创板、北交所，含退市历史 |
| 默认日常股票 | 日常行情更新默认追踪 `list_status=L` |
| 历史股票 | 退市和暂停上市纳入历史库 |
| 默认指数池 | 上证指数、上证50、科创50、沪深300、中证500、中证1000、深证成指、创业板指 |
| 日常修复窗口 | 最近 10 个交易日 |
| 远期修复 | 超过 10 个交易日需显式确认，基础库初建除外 |
| 财务报表 | raw/detail 全量 payload 保存 + 标准化视图 |
| 工程边界 | 只做数据维护，不做选股、回测、训练标签 |

## 4. 可用命令

```bash
python -m stock_maintainance.cli plan
python -m stock_maintainance.cli schema-summary
python -m stock_maintainance.cli emit-ddl
python -m stock_maintainance.cli docs-generate
python -m stock_maintainance.cli docs-check
python -m stock_maintainance.cli validate-config
```

## 5. Phase 1 验收口径

Phase 1 不验证真实数据入库，只验证：

1. 配置 JSON 可解析。
2. schema 注册表可生成 DDL。
3. 变量注册表满足必填字段。
4. 自动文档可生成并检查一致。
5. Phase 2 需要确认的事项已明确。
