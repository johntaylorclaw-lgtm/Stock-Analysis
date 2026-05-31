# Phase 2 批处理能力进展

生成日期：2026-05-27

## 1. 本次新增能力

在 Phase 2 启动底座之后，本次继续补充批处理和板块/指数维护能力。

新增 CLI：

```powershell
python -m stock_maintainance.cli sync-daily-range 20260525 20260526 --limit 2
python -m stock_maintainance.cli sync-adj-factor 600519.SH --start-date 20260501 --end-date 20260526
python -m stock_maintainance.cli sync-index-daily 20260501 20260526 --index-code 000300.SH
python -m stock_maintainance.cli sync-index-weight-month 202605 --index-code 000300.SH
python -m stock_maintainance.cli sync-sw-industry --limit-members 2
python -m stock_maintainance.cli sync-concepts --limit-concepts 3
```

新增或补强的数据域：

1. 日行情批量按交易日区间同步。
2. 单股票复权因子同步。
3. 指数日线按指数池和日期区间同步。
4. 指数成分权重按月同步，查询整月实际可用权重日期。
5. 申万 2021 行业分类和行业成分同步。
6. Tushare 概念基础信息和概念成分同步。

## 2. 实证写入结果

| 命令 | 写入结果 |
|---|---:|
| `sync-daily-range 20260525 20260526 --limit 2` | 日行情 11008、日估值 11008、涨跌停 15234 |
| `sync-adj-factor 600519.SH --start-date 20260501 --end-date 20260526` | 复权因子 15 |
| `sync-index-daily 20260501 20260526 --index-code 000300.SH --index-code 000985.CSI --index-code 399317.SZ` | 指数日线 45 |
| `sync-index-weight-month 202605 --index-code 000300.SH --index-code 000985.CSI --index-code 399317.SZ` | 指数权重 300 |
| `sync-sw-industry --limit-members 2` | 申万行业分类 511、样例行业成分 581 |
| `sync-concepts --limit-concepts 3` | 概念基础 879、样例概念成分 54 |

## 3. 本次发现并修正的问题

1. DuckDB 单文件写库不适合多个写入命令并行执行。后续批处理应采用单写进程，读取和校验可并行。
2. 指数权重不能简单使用月初日期作为 `trade_date` 精确查询，应查询整个月区间并保存源端实际返回日期。
3. 申万 `index_classify` 同时返回 `index_code` 和 `industry_code`，本工程使用 `industry_code` 保存可交易/可查询的行业指数代码，另设 `sw_code` 保存申万数字行业码。
4. `concept_detail` 返回字段 `id`，与本工程补充的 `concept_id` 会冲突，已修正为仅在源端缺失时补充。

## 4. 下一步

下一步应把当前小范围命令升级为全量调度：

1. 日行情按交易日循环，支持断点、失败日期重试、近 10 个交易日自动修复。
2. 复权因子按股票循环，覆盖上市和退市股票。
3. 财务报表按股票循环，保留宽表字段和 `payload_json`。
4. 指数日线覆盖默认指数池和申万行业指数。
5. 指数成分按月循环保存。
6. 概念和行业成员做全量同步，并记录接口失败列表。
