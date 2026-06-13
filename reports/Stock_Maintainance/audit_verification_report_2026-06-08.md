# Stock_Maintainance 审计修复验证报告

审计日期：2026-06-08 (最终验证 23:30 CST)
验证依据：`reports/Stock_Maintainance/audit_fix_report_2026-06-08.md`

---

## 1. 验证结论

**审计修复报告中的 20 项声明全部通过实证验证。** 修复后的工程状态显著优于原始审计时的状态。

---

## 2. 逐项验证结果

### 2.1 补数数据验证（10/10 通过）

| # | 声明 | 声称值 | 实际查询值 | 结果 |
|---|---|---|---|---|
| 1 | `margin_detail` 0605 补齐 | 4,367 | **4,367** | ✓ |
| 2 | `stock_daily_basic` 0608 | 5,515 | **5,515** | ✓ |
| 3 | `stock_moneyflow_daily` 0608 | 5,198 | **5,198** | ✓ |
| 4 | `northbound_daily` 0608 | 1 | **1** | ✓ |
| 5 | `top_list_daily` 0608 | 109 | **109** | ✓ |
| 6 | `top_inst_detail` 0608 | 1,028 | **1,028** | ✓ |
| 7 | `index_daily` 0608 | 14 | **14** | ✓ |
| 8 | `derived_index_daily_cache` 0608 | 14 | **14** | ✓ |
| 9 | `margin_detail` 0608 T+1预期 | 0 | **0** | ✓ |
| 10 | `northbound_holding` 0608 T+1预期 | 0 | **0** | ✓ |

### 2.2 代码修改验证（5/5 通过）

| # | 声明 | 证据 | 结果 |
|---|---|---|---|
| 1 | `derived_ownership_governance` 纳入 `STOCK_LEVEL_DERIVED_TABLES` | `daily_validate.py:81` | ✓ |
| 2 | 新增 `ROW_COUNT_MONITOR_TABLES` 行数波动监控 | `daily_validate.py:52-62` | ✓ |
| 3 | 新增 `DEFAULT_EXPECTED_DELAY_TABLES` + `_expected_delay_tables()` | `daily_validate.py:47-50, 208-218` | ✓ |
| 4 | `sync_market_behavior_range` 增加 `force` 参数 | `ingest.py:241, 256-260` | ✓ |
| 5 | `daily-light` 内部市场行为增量使用 `force=True` | `daily_light.py:199` | ✓ |

### 2.3 配置与文档验证（4/4 通过）

| # | 声明 | 证据 | 结果 |
|---|---|---|---|
| 1 | `pipeline.json` `latest_trade_cutoff_hour_local: 20` | `config/pipeline.json:3` | ✓ |
| 2 | `pipeline.json` `api_release_phases` (fast/evening/next_day) | `config/pipeline.json:8-24` | ✓ |
| 3 | `config/hermes_agent.json` 创建，20:00调度 | `config/hermes_agent.json:3` | ✓ |
| 4 | `docs/14_运行手册.md` 更新20:00说明 | 手册第16-22行 | ✓ |

### 2.4 临时表清理验证（1/1 通过）

| 声明 | 声称值 | 实际查询值 | 结果 |
|---|---|---|---|
| 清理前后对比 | 25 → 0 | 143 objects → 118 (0 audit_tmp) | ✓ |

---

## 3. 测试与质量门禁

| 门禁 | 审计前 | 修复后 | 变化 |
|---|---|---|---|
| `pytest -v` | 43 passed | **46 passed** | +3 |
| `validate-config` | passed | passed | — |
| `docs-check` | passed | passed | — |
| `validate-daily` postcheck status | **warning** (9 fail) | **pass** (0 fail, 2 expected_delay) | 修正 |

---

## 4. 修复后验收报告实证

`reports/audit_fix_post_20260608.md` (生成时间 23:22:00)：

| 指标 | 值 | 评估 |
|---|---|---|
| status | **pass** | 从原始warning提升 ✓ |
| table_count | 40 | 含衍生表完整 ✓ |
| missing_table_count | 0 | ✓ |
| coverage_issue_table_count | 0 | 从9降至0 ✓ |
| duplicate_issue_table_count | 0 | 维持 ✓ |
| stock_level_row_count_issue_table_count | 0 | 维持 ✓ |
| expected_delay_table_count | 2 | margin_detail + northbound_holding ✓ |
| row_count_warning_table_count | 0 | 无异常波动 ✓ |

40张表全部 `pass` 或 `warning`（2张预期延迟表以warning标注但不阻塞整体pass）。

---

## 5. 原始审计问题解决状态

| 原始问题 | 严重度 | 解决状态 |
|---|---|---|
| `margin_detail` 0605 数据缺口 (1,981行) | MAJOR | **已修复** → 4,367行 |
| 晚间7张API表0608缺失 | MAJOR | **已补齐** → 全部有数据 |
| `pipeline.json` 单一截止时间 | MINOR | **已修改** → 20:00 + api_release_phases |
| 25张审计临时表 | MINOR | **已清理** → 0张 |
| `ownership_governance` 监控盲区 | MINOR | **已修复** → 纳入检查 |
| postcheck 无行数波动检测 | (新增) | **已实现** → ROW_COUNT_MONITOR + 80%阈值 |
| success状态阻止晚间重试 | (修复过程中发现) | **已修复** → force参数 |

---

## 6. 衍生数据完整性

补数后所有17张衍生核心表在2026-06-08均与spine对齐（5,515行）：

`derived_daily_spine`, `derived_price_technical`, `derived_financial_asof`, `derived_financial_quality`, `derived_financial_growth`, `derived_capital_flow`, `derived_composite_state`, `derived_cross_sectional`, `derived_ownership_governance` — 全部 5,515 行，与spine一致。

---

## 7. 最终结论

### Verdict: **APPROVED**

原始审计中 `APPROVED WITH NOTES` 的 MAJOR 问题已全部解决。修复后的工程具备：

1. **完整的日批次运行窗口**：20:00 执行，覆盖晚间 T+0 API 发布
2. **正确的预期延迟管理**：`margin_detail` 和 `northbound_holding` 的 T+1 延迟不再阻塞日批
3. **增强的监控能力**：行数波动检测（80%阈值）、完整的衍生表对齐检查
4. **改进的同步逻辑**：`force` 参数允许晚间重试覆盖早间的0行success记录
5. **清理的数据库**：24张临时审计表已移除，对象数从143降至118

**2张真正T+1表（`margin_detail`、`northbound_holding`）的0608数据预计在2026-06-09的下次日批中自然补齐。**
