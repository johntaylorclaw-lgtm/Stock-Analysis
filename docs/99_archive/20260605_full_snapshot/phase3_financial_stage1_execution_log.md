# Phase 3 财务衍生第一阶段执行记录

生成日期：2026-05-31

## 执行边界

第一阶段只实现事实层财务变量：

1. `derived_financial_asof`：日频财报可得时点、报告期状态、四张财务表完整性、预告快报可得状态。
2. `derived_financial_quality`：盈利结构、现金流质量、资产结构、债务结构、营运效率、费用结构、杜邦拆解、事实型风险标记、报表勾稽和披露完整性。

第一阶段不实现：

1. 同比、环比、多周期变化率、跨年 CAGR。
2. 综合评分、排名、分位数、主观权重变量。
3. 选股、回测、训练标签。

## 关键实现

1. 扩展 `config/schema_registry.json`：
   - `derived_financial_asof` 扩展到 30 个字段。
   - `derived_financial_quality` 扩展到 119 个字段。
2. 扩展 `config/variables/derived_variables.json`：
   - 注册 `financial_asof` 模块 27 个业务变量。
   - 注册 `financial_quality` 模块 114 个业务变量。
   - 为新增财务质量字段补充中文名和衍生公式。
3. 扩展 `src/stock_maintainance/features/modules.py`：
   - `build_financial_asof` 从占位字段改为完整点时可得表。
   - `build_financial_quality` 从占位字段改为完整财务质量事实表。
4. 修正点时逻辑：
   - 原始财报表物理 `effective_date` 为空时，统一使用 `coalesce(effective_date, first_ann_date, ann_date)`。
   - 财务指标表使用 `coalesce(effective_date, ann_date)`。
   - `latest_report_end_date` 定义为截至交易日已可见的最高报告期，避免旧报告修订导致报告期倒退。

## 全历史构建结果

构建区间：2006-01-01 至 2026-05-26。

| 表 | 写入行数 | 股票数 | 日期范围 |
|---|---:|---:|---|
| `derived_financial_asof` | 15,295,776 | 5,809 | 2006-01-04 至 2026-05-26 |
| `derived_financial_quality` | 15,295,776 | 5,809 | 2006-01-04 至 2026-05-26 |

## 质量结论

专项审计报告：`reports/phase3_financial_stage1_quality_audit.md`

审计报告由 `scripts/generate_phase3_financial_stage1_audit.py` 生成，文件统一以 UTF-8 写入。后续不要通过 PowerShell 管道临时写入中文 Markdown，避免中文在命令传递阶段被替换成乱码。

核心结论：

1. `latest_financial_effective_date <= trade_date` 违反行数为 0。
2. `latest_report_end_date` 随交易日推进倒退行数为 0。
3. `latest_report_end_date` 全历史非空率约 81%，早期覆盖率较低主要来自源财报历史覆盖边界。
4. 核心质量字段如 `roe_asof`、`debt_to_assets_asof`、`ocf_to_revenue_asof`、`dupont_roe_calc_asof` 已形成可用覆盖。
5. `ocf_to_profit_asof` 使用 Tushare 字段为主；当源字段为空时，用 `financial_cashflow_raw.cf_from_operating / financial_income_raw.net_profit` 兜底计算。

## 后续衔接

第二阶段 `derived_financial_growth` 应以第一阶段字段作为主要输入：

1. 对 `derived_financial_quality` 中的比例、利润率、周转率、债务率做上一报告期变化、去年同期变化、近 4 报告期变化。
2. 对利润表、资产负债表、现金流量表的金额字段做同比、环比、多周期 CAGR。
3. 对第一阶段的事实标记做状态延续、首次出现、连续期数等事实型变量。
