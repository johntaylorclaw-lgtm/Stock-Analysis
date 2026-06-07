# Phase 2 设计蓝图与 Data Contract 完成确认

生成日期：2026-05-30

## 1. 总体结论

Phase 2 已按当前 `docs/rebuild_plan.md` 与 `docs/data_contract.md` 的基础库范围完成全量建设、基础变量注册、质量审计与文档同步检查。

本阶段完成内容包括：

1. A 股全市场证券主数据、交易日历、行情、复权、日度基础指标与涨跌停价格。
2. 资金流、两融、北向、龙虎榜等市场行为数据的历史回补。
3. 四大财务报表、财务指标、分红、披露日程、股权质押统计与高价值财务事件结构化视图。
4. 指数基础信息、指数行情、指数成分权重、概念、申万行业与日频聚合视图。
5. 前/后复权行情视图、基础日频宽表、市场宽度视图、财务标准化视图。
6. 正式基础变量注册表 `config/variables/base_variables.json`，以及 Excel 基础变量数据字典。
7. Phase 2 质量审计报告、schema/变量/source 自动生成文档与文档同步检查。

需要说明的是，若 Tushare 源接口在较早年份返回空数据，本项目将其记录为“源数据可获得边界”，不视为工程失败。例如北向数据起点晚于 2006 年，两融明细起点晚于 2006 年，均符合市场制度和接口历史覆盖情况。

## 2. Data Contract 对照

| Data Contract 域 | 完成状态 | 说明 |
|---|---|---|
| S0 股票主数据 | 完成 | `stock_basic_info`、`stock_company_info`、`stock_status_history` 已建设；覆盖上市、退市、北交所等 A 股证券范围。 |
| S1 交易日历 | 完成 | `trade_calendar` 覆盖 2006 年起至当前可用区间。 |
| S2 行情 | 完成 | `stock_daily` 覆盖 2006-01-04 至 2026-05-26。 |
| S3 复权 | 完成 | `stock_adj_factor` 与 `stock_price_adjusted` 支持前复权、后复权视图。 |
| S4 日度基础指标 | 完成 | `stock_daily_basic` 与 `stock_base_daily`、`stock_base_daily_enriched` 已建设。 |
| S5 资金/两融/北向/龙虎榜 | 完成 | `stock_moneyflow_daily`、`margin_detail`、`northbound_daily`、`northbound_holding`、`top_list_daily`、`top_inst_detail` 已按历史区间回补；早期空区间为源数据边界。 |
| S6 财务 | 完成 | 四大财务报表、财务指标、分红、披露日程、质押统计与高价值财务事件结构化视图已建设。 |
| S7 行业/概念/指数成分 | 完成 | 指数基础、指数行情、指数权重、概念、申万行业及 `concept_daily`、`industry_daily` 已建设。 |
| S8 市场环境 | 完成 | `market_breadth_daily` 已建设；风格环境变量留到衍生变量阶段展开。 |
| S9 元数据与审计 | 完成 | schema registry、base variable registry、任务状态、失败记录、质量报告、自动生成文档与 docs check 已就绪。 |

## 3. 核心数据规模

| 对象 | 行数 |
|---|---:|
| `stock_basic_info` | 5,850 |
| `stock_company_info` | 6,271 |
| `stock_status_history` | 6,175 |
| `trade_calendar` | 7,670 |
| `stock_daily` | 15,295,776 |
| `stock_adj_factor` | 15,653,891 |
| `stock_daily_basic` | 15,204,489 |
| `stock_limit_price` | 17,533,118 |
| `stock_moneyflow_daily` | 14,186,050 |
| `margin_detail` | 6,486,792 |
| `northbound_daily` | 2,710 |
| `northbound_holding` | 5,669,689 |
| `top_list_daily` | 241,799 |
| `top_inst_detail` | 2,494,834 |
| `financial_income_raw` | 294,351 |
| `financial_balance_raw` | 272,771 |
| `financial_cashflow_raw` | 297,550 |
| `financial_indicator_raw` | 253,004 |
| `financial_dividend_raw` | 163,213 |
| `financial_disclosure_schedule` | 270,515 |
| `pledge_stat` | 2,204,384 |
| `financial_event_raw` | 16,390,985 |
| `index_basic_info` | 7,696 |
| `index_daily` | 63,767 |
| `index_weight` | 2,899,016 |
| `concept_basic` | 879 |
| `concept_member` | 34,444 |
| `sw_industry_classify` | 511 |
| `sw_industry_member` | 5,847 |

## 4. 视图与结构化层

| 视图 | 行数 | 用途 |
|---|---:|---|
| `stock_price_adjusted` | 15,295,776 | 原始、前复权、后复权行情统一视图。 |
| `stock_base_daily` | 15,295,776 | 日线、日度基础指标、涨跌停、复权因子基础宽表。 |
| `stock_base_daily_enriched` | 15,295,776 | 增强日频基础宽表，连接市场行为类字段。 |
| `market_breadth_daily` | 4,951 | 市场宽度、涨跌数量、成交额、涨跌停统计。 |
| `concept_daily` | 4,265,393 | 概念板块日频聚合。 |
| `industry_daily` | 153,480 | 申万行业日频聚合。 |
| `financial_income` | 294,351 | 利润表标准化视图。 |
| `financial_balance` | 272,771 | 资产负债表标准化视图。 |
| `financial_cashflow` | 297,550 | 现金流量表标准化视图。 |
| `financial_indicator` | 253,004 | 财务指标标准化视图。 |
| `financial_dividend` | 163,213 | 分红结构化视图。 |
| `financial_pledge_stat` | 2,204,384 | 股权质押统计结构化视图。 |

## 5. 数据质量结论

质量审计报告：`reports/quality_audit_report.md`

审计结论：

1. 被检查表数量：32。
2. 交易日历覆盖年份：2006 - 2026。
3. 非零质量问题数量：0。
4. `stock_daily`、`stock_daily_basic`、`stock_adj_factor`、`financial_income_raw`、`financial_indicator_raw` 主键重复检查均为 0。
5. 行情收盘价、复权因子、财务报表关键生效日期、财务指标公告日期等关键空值/非法值检查均为 0。

当前 2026 年只覆盖至 2026-05-26，是因为 Phase 2 全量回补执行时的 Tushare 可用交易数据截止到该日期。

## 6. 基础变量注册与数据字典

正式注册文件：`config/variables/base_variables.json`

注册结果：

1. 正式基础变量数量：445。
2. 注册来源：`config/schema_registry.json` 中非元数据业务字段。
3. 命名策略：字段名全局唯一时使用原字段名；跨表重复字段使用 `{table}_{field}` 形式避免歧义。
4. 映射策略：每个变量保留 `table`、`source_api`、`source_field`、`dtype`、`frequency`、`grain`、`unit`、`missing_policy` 等元数据。

Excel 数据字典：

- `outputs/phase2/base_variable_dictionary_v2.xlsx`

该文件包含：

1. `Summary`：总览、表级覆盖、缺口统计。
2. `Registered_Base`：正式注册基础变量。
3. `Schema_Candidates`：schema 推导候选变量。
4. `Coverage_Gaps`：未注册候选变量。
5. `Draft_Registry`：草案注册内容。
6. `Module_Summary`：模块分布摘要。

## 7. 验收命令

本次确认已执行并通过：

```powershell
$env:PYTHONPATH='src'; python -m stock_maintainance.cli validate-config
$env:PYTHONPATH='src'; python -m stock_maintainance.cli docs-generate
$env:PYTHONPATH='src'; python -m stock_maintainance.cli docs-check
$env:PYTHONPATH='src'; python -m stock_maintainance.cli audit-quality
```

其中：

1. `validate-config` 输出 `config validation passed`。
2. `docs-check` 输出 `generated docs are up to date`。
3. `audit-quality` 重新生成 Phase 2 质量报告与 CSV 明细。

