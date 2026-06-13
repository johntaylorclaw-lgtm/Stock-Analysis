# Stock_Maintainance 2026-06-08 审计修复报告

生成日期：2026-06-08

## 1. 对第三方审计结论的判断

总体判断：审计结论大体客观，尤其是以下判断成立：

1. `daily-light` 于 15:56 执行过早，未覆盖 Tushare 晚间 T+0 API 发布窗口。
2. 2026-06-08 晚间可补齐的表包括 `stock_daily_basic`、`stock_moneyflow_daily`、`northbound_daily`、`top_list_daily`、`top_inst_detail`、`index_daily` 以及级联的 `derived_index_daily_cache`。
3. `margin_detail` 与 `northbound_holding` 在最新交易日属于 T+1 延迟特征，不应作为 20:00 日批阻塞项。
4. `margin_detail` 2026-06-05 的 1,981 行属于非零但明显不完整的数据缺口，原验证逻辑确实未能发现这类异常。
5. `derived_ownership_governance` 未纳入股票级衍生表行数对齐检查，属于监控盲区。
6. `audit_tmp_phase4_*` 临时审计表应清理。

部分建议需要按当前工程实际调整：

1. 报告中提到的 `daily-light-late` 命令当前并不存在，因此未直接照搬该命令名。
2. 当前工程已有 `sync-daily-range`、`sync-market-behavior-range`、`sync-index-daily` 和 `build-features`，本次按现有 CLI 架构完成补数与修复。
3. 进一步发现 `sync_market_behavior_range` 会跳过已记录 success 的日期，即使当时 API 返回 0 行；这会阻止晚间重试，是本次额外修复的关键工程问题。

## 2. 已完成修复

### 2.1 补数

已执行：

```bash
.venv-wsl/bin/stock-maintain sync-market-behavior-range 20260605 20260605 --force
.venv-wsl/bin/stock-maintain sync-daily-range 20260608 20260608
.venv-wsl/bin/stock-maintain sync-market-behavior-range 20260608 20260608 --force
.venv-wsl/bin/stock-maintain sync-index-daily 20260608 20260608
.venv-wsl/bin/stock-maintain build-features --start-date 2026-06-05 --end-date 2026-06-08 --allow-confirmed-history
.venv-wsl/bin/stock-maintain create-views
```

补数后关键行数：

| 日期 | 表 | 行数 | 结论 |
|---|---|---:|---|
| 2026-06-05 | `margin_detail` | 4,367 | 已由 1,981 补齐至正常量级 |
| 2026-06-08 | `stock_daily_basic` | 5,515 | 已补齐 |
| 2026-06-08 | `stock_moneyflow_daily` | 5,198 | 已补齐 |
| 2026-06-08 | `northbound_daily` | 1 | 已补齐 |
| 2026-06-08 | `top_list_daily` | 109 | 已补齐 |
| 2026-06-08 | `top_inst_detail` | 1,028 | 已补齐 |
| 2026-06-08 | `index_daily` | 14 | 已补齐 |
| 2026-06-08 | `derived_index_daily_cache` | 14 | 已补齐 |
| 2026-06-08 | `margin_detail` | 0 | 预期 T+1 延迟 |
| 2026-06-08 | `northbound_holding` | 0 | 预期 T+1 延迟 |

### 2.2 验证逻辑

已修改 `src/stock_maintainance/daily_validate.py`：

1. 将 `derived_ownership_governance` 纳入 `STOCK_LEVEL_DERIVED_TABLES` 和默认 `DEFAULT_COMPARE_TABLES`，确保日验证与周度窗口对照都会覆盖该表。
2. 新增 `ROW_COUNT_MONITOR_TABLES`，对重点日频表执行近 5 个交易日均值对比。
3. 当最新目标日行数低于近 5 日均值的 80% 时输出行数波动预警。
4. 对 `margin_detail`、`northbound_holding` 最新交易日缺失识别为预期 T+1 延迟。
5. 修复 `validation_days=0` 时 Python `[-0:]` 导致全量切片的问题。

### 2.3 同步逻辑

已修改 `src/stock_maintainance/ingest.py` 与 CLI：

1. `sync_market_behavior_range` 增加 `force` 参数。
2. `stock-maintain sync-market-behavior-range` 增加 `--force`。
3. `daily-light` 内部调用市场行为增量同步时默认使用 `force=True`，避免早间/下午 0 行 success 状态阻止晚间重试。

### 2.4 临时表清理

新增并执行：

```bash
.venv-wsl/bin/stock-maintain cleanup-audit-tmp
```

清理结果：

| 项目 | 结果 |
|---|---:|
| 清理前 `audit_tmp_phase4_%` 表数 | 25 |
| 清理后 `audit_tmp_phase4_%` 表数 | 0 |

### 2.5 Hermes 20:00 日加载规则

已更新：

1. `config/pipeline.json`：`latest_trade_cutoff_hour_local` 调整为 20，并增加 `api_release_phases`。
2. `config/hermes_agent.json`：记录 Hermes daily-light 20:00 调度与 Markdown 汇总命令。
3. `Skill/stock-maintenance-ops/SKILL.md`
4. `Skill/stock-maintenance-ops/references/hermes_agent.md`
5. `Skill/stock-maintenance-ops/references/operations.md`
6. `docs/13_AgentSkill运行手册与自动报告设计.md`
7. `docs/14_运行手册.md`

## 3. 修复后验收

已执行：

```bash
.venv-wsl/bin/stock-maintain validate-daily --as-of-date 2026-06-08 --output-prefix audit_fix_post_20260608
```

结果：

| 指标 | 值 |
|---|---:|
| status | pass |
| table_count | 40 |
| missing_table_count | 0 |
| coverage_issue_table_count | 0 |
| duplicate_issue_table_count | 0 |
| stock_level_row_count_issue_table_count | 0 |
| expected_delay_table_count | 2 |
| row_count_warning_table_count | 0 |

输出：

1. `reports/audit_fix_post_20260608.json`
2. `reports/audit_fix_post_20260608.md`

## 4. 结论

第三方审计报告的核心结论客观。问题已按当前工程架构完成修复。

修复后，2026-06-08 日加载缺失的晚间 T+0 表已补齐，2026-06-05 `margin_detail` 缺口已补齐，日验证通过。最新交易日仍缺失的 `margin_detail` 与 `northbound_holding` 被归类为预期 T+1 延迟，不再阻塞 20:00 日批。
