# Fable Review 第一批修复报告

生成日期：2026-06-11

## 1. 修复范围

本批按用户确认的边界，优先处理 Fable 独立审计报告中的地基与高危问题：

| 编号 | 状态 | 本批处理 |
|---|---|---|
| H1 Python 3.11 兼容 | 已修复 | `views.py` 动态 f-string 中的 `join` 提前到局部变量，保留 Python 3.11 兼容 |
| H2 DELETE+INSERT 无事务 | 已部分修复 | `upsert_dataframe`、通用 `_rebuild_table` 和 `daily_spine` 写入增加事务边界；corporate_action 全量脚本增加事务 |
| H4 fina_indicator ann_date 前视 | 已修复采集层与存量 8 行 | 取消 `ann_date=end_date` 回填；用同报告期三大报表公告日恢复存量污染行 |
| H5 分红未实施旗标恒真 | 已修复并重建 | `count(*)` 改为 `count(e.ts_code)`，并重建 `derived_corporate_action` |
| H6 corporate_action 年度滚动截断 | 已修复并重建 | 逐年全量构建增加向前 370 日上下文，写出仍限定自然年 |
| H9 optional 数据域失败阻塞日批 | 已修复 | 市场行为 optional API 单项降级并写入 `optional_failures`；daily-light 失败时产出报告 |
| H10 weekly compare 快照侧未过滤窗口 | 已修复 | snapshot CTE 与 current CTE 使用同一日期窗口 |

## 2. 数据修复结果

### 2.1 corporate_action 全量重建

已执行：

```bash
.venv-wsl/bin/python scripts/build_phase3_corporate_action_core.py --start-year 2006 --end-year 2026
```

重建结果：

| 指标 | 值 |
|---|---:|
| `derived_corporate_action` 行数 | 15,356,387 |
| 日期范围 | 2006-01-04 至 2026-06-10 |
| `has_dividend_announced_not_executed = true` | 1,939,701 |
| `has_dividend_announced_not_executed = false` | 13,416,686 |
| 2026-01 `cash_dividend_ttm > 0` 行数 | 75,070 |

结论：H5 的恒真问题已消除；H6 的跨年 TTM 上下文已重新落库。

### 2.2 financial_indicator 公告日修复

已执行：

```bash
.venv-wsl/bin/python scripts/repair_financial_indicator_ann_date.py
```

结果：

| 指标 | 值 |
|---|---:|
| 修复前 `ann_date = end_date` 行数 | 8 |
| 修复后 `ann_date = end_date` 行数 | 0 |
| 使用同报告期报表公告日恢复 | 8 |
| 使用保守 fallback | 0 |

修复报告：

`reports/financial_indicator_ann_date_repair_20260611.json`

## 3. 运行验证

### 3.1 单元测试与配置

| 检查 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q` | 50 passed |
| `stock-maintain validate-config` | passed |
| `stock-maintain docs-check` | passed |
| `stock-maintain create-views` | passed |

新增测试覆盖：

1. `views.py` Python 3.11 grammar parse。
2. weekly compare snapshot 窗口过滤。
3. daily-light optional market behavior warning。
4. corporate_action SQL 的分红未实施旗标与跨年上下文。

### 3.2 日批实测

已执行：

```bash
.venv-wsl/bin/stock-maintain daily-light --as-of-date 2026-06-11 --output-prefix fable_fix_daily_20260611
```

结果：

| 阶段 | 状态 | 说明 |
|---|---|---|
| precheck | warning | 2026-06-11 是新增待补交易日 |
| base-incremental | done | 当日晚间 T+0 数据已补入 |
| feature-build | done | 17 个模块完成 |
| create-views | done | 视图刷新完成 |
| postcheck | pass | 40 张表验证通过 |

postcheck 输出：

`reports/fable_fix_daily_20260611_postcheck.md`

说明：`daily-light` 总报告保留 warning，是因为 precheck 记录了补数前的真实缺口；补数后 postcheck 已 pass。

## 4. 仍待处理

本批没有进入以下问题的完整修复：

1. H3 / M21：financial_quality / financial_growth 的 PIT 数值版本选择。
2. H7：财务 growth 同向旗标剔除 `-9` 哨兵。
3. H8：杜邦 ROE 校验字段量纲统一。
4. H11：逐表 gap planning 与新股覆盖检查增强。
5. M1/M2/M3/M5/M8/M11-M16/M22-M25 等中危与文档类问题。

建议下一批优先进入财务 PIT 数值层，因为它影响衍生变量事实口径。

