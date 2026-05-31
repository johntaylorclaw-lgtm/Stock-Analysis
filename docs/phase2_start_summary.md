# Phase 2 启动实施记录

生成日期：2026-05-27

## 1. 本次已完成

Phase 2 已从设计确认进入工程实施。本次先建设可运行的数据维护底座，不直接启动 2006 年以来的全量历史行情和全量财务长任务。

已完成内容：

1. 创建新项目 `.env`，复用旧项目 Tushare token，token 不写入代码和文档。
2. 创建运行目录：`data/duckdb/`、`data/parquet/`、`data/snapshots/`、`logs/`、`reports/`。
3. 创建 DuckDB 数据库：`data/duckdb/stock_data.duckdb`。
4. 实现 schema 初始化命令。
5. 实现 Tushare 客户端封装，支持 token 读取、限速、重试。
6. 实现通用 DuckDB upsert，支持按主键删除后插入，并在写入前按主键去重。
7. 实现任务状态表 `metadata_task_state`，为后续断点续跑打基础。
8. 实现首批同步命令：`init-db`、`smoke-tushare`、`sync-master`、`sync-daily-date`、`sync-financial-sample`。
9. 扩展指数池，加入中证全指、中证800、中证100、国证A指、国证1000、创业板50。
10. 新增 `financial_indicator_raw` 宽表，并保留 `payload_json`。

## 2. 已实证通过的写入结果

本次未跑历史全量，只跑了可控样例和主数据同步。

| 命令 | 写入结果 |
|---|---:|
| `smoke-tushare` | 当前上市股票 5524、退市股票 325、中证指数基础 4879、概念 879 |
| `sync-master` | 股票主表 5849、交易日历 7670、指数基础 7696 |
| `sync-daily-date 20260526` | 日行情 5504、日估值 5504、涨跌停 7619 |
| `sync-financial-sample 600519.SH --start-date 20240101 --end-date 20260526` | 利润表 10、资产负债表 10、现金流量表 10、财务指标 9 |

## 3. 当前命令

运行前建议设置：

```powershell
$env:PYTHONPATH='src'
```

初始化数据库：

```powershell
python -m stock_maintainance.cli init-db
```

验证 Tushare 关键接口：

```powershell
python -m stock_maintainance.cli smoke-tushare
```

同步主数据：

```powershell
python -m stock_maintainance.cli sync-master
```

同步某个交易日的日增量：

```powershell
python -m stock_maintainance.cli sync-daily-date 20260526
```

验证单只股票财务混合存储：

```powershell
python -m stock_maintainance.cli sync-financial-sample 600519.SH --start-date 20240101 --end-date 20260526
```

## 4. 本次发现并修正的问题

1. 财务接口 `f_ann_date` 重命名为 `first_ann_date` 后，需要继续执行日期归一化，否则 DuckDB DATE 类型写入失败。
2. 财报接口可能返回同一主键的多个版本，通用 upsert 已先按主键去重保留最后一条。后续全量财务阶段应进一步评估是否引入 `update_flag`、`publish_version` 或源记录哈希以保留版本审计。

## 5. 下一步

Phase 2 下一步进入批处理器建设：

1. 按交易日批量回补 `daily`、`daily_basic`、`adj_factor`、`stk_limit`。
2. 按股票批量回补财务报表和财务指标。
3. 建设指数日线和指数成分月度快照。
4. 建设申万行业分类、申万行业指数日线、概念和概念成分。
5. 将任务状态表升级为完整断点续跑和失败重试机制。
