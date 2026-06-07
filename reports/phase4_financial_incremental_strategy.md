# Phase 4 财务报表增量补拉专项设计与实测

- 生成日期：2026-06-06
- 测试窗口：2026-05-27 至 2026-06-05
- 目标：为财务四大报表建立独立的增量补拉路径，避免日批对全市场股票无差别逐股调用。

## 背景

Tushare 的 `income`、`balancesheet`、`cashflow`、`fina_indicator` 已实测不能按全市场公告日直接拉取，接口要求 `ts_code`。如果对全 A 股逐股调用四张报表，单次日批大约会产生 `股票数 * 4` 次 API 调用，成本高、耗时长，也容易触发接口限流。

因此 Phase 4 财务报表增量采用“全市场候选发现 + 候选逐股补拉”的策略。

## 增量策略

1. 先调用 `disclosure_date`，按日期窗口拉取全市场财报披露计划。
2. 从 `financial_disclosure_schedule` 中筛选 `ann_date`、`actual_date`、`modify_date` 落在增量窗口内的股票。
3. 对候选股票逐股调用：
   - `income` -> `financial_income_raw`
   - `balancesheet` -> `financial_balance_raw`
   - `cashflow` -> `financial_cashflow_raw`
   - `fina_indicator` -> `financial_indicator_raw`
4. 每只股票使用 `metadata_task_state` 记录任务状态，支持断点续跑。
5. 若需要强制全市场逐股补拉，可使用 `--all-stocks`，但该模式不建议作为普通日批默认路径。

## 新增命令

```bash
stock-maintain sync-financial-incremental-range 20260527 20260605
```

可选参数：

- `--report-start-date`：覆盖候选股票的报表起始期。
- `--report-end-date`：覆盖候选股票的报表结束期。
- `--limit`：限制候选股票数量，用于冒烟测试。
- `--no-resume`：禁用断点续跑。
- `--all-stocks`：强制全市场逐股补拉。

## 本次实测结果

本次执行：

```bash
stock-maintain sync-financial-incremental-range 20260527 20260605
```

结果：

| 指标 | 数值 |
|---|---:|
| disclosure_rows | 0 |
| candidates_seen | 0 |
| stocks_done | 0 |
| stocks_failed | 0 |
| financial_income_raw | 0 |
| financial_balance_raw | 0 |
| financial_cashflow_raw | 0 |
| financial_indicator_raw | 0 |

结论：2026-05-27 至 2026-06-05 窗口内，`disclosure_date` 未返回财报披露候选，因此没有触发逐股四表补拉。该结果与“日批只处理变更范围”的 Phase 4 原则一致。

## 风险与后续优化

- 若披露计划接口漏报，需要增加第二候选来源，例如从 `financial_event_raw` 的 forecast/express/disclosure_date 增量中补充候选。
- 强制 `--all-stocks` 可用于月度或人工复核任务，但不建议进入默认日批。
- 下一步可增加专项验收：构造或选择有真实财报公告的历史窗口，验证候选发现、逐股补拉、财务 ASOF 衍生重建的一致性。
