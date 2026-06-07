# Phase 2 财务基础数据补强执行记录

生成日期：2026-05-31

## 1. 本次优化范围

本次根据 `docs/phase2_financial_base_enhancement_plan.md` 的确认结果，执行 Phase 2 财务基础库补强：

1. 三大财务报表按“尽量完整结构化”推进。
2. 财务事件先采用结构化视图方案，保留 `financial_event_raw` 原始池。
3. 财务 as-of 标准层作为后续 Phase 3 财务衍生变量的推荐入口。
4. 同步更新 schema、变量注册、视图、回填脚本、自动文档和全局 Excel 数据字典。

## 2. Schema 补强

新增结构化字段：

| 表名 | 新增字段数 | 说明 |
|---|---:|---|
| `financial_income_raw` | 25 | 补强 EPS、税金及附加、费用、减值、投资收益、公允价值、营业外收支、少数股东损益、综合收益、金融/保险类收入支出等字段 |
| `financial_balance_raw` | 43 | 补强流动资产、非流动资产、流动负债、非流动负债、权益类细分字段 |
| `financial_cashflow_raw` | 30 | 补强经营、投资、筹资现金流入流出明细，以及现金流间接法勾稽字段 |

设计原则：

- 保留原有主键不变。
- 保留 `payload_json`，不牺牲原始可追溯性。
- 新增字段均可空，以兼容不同公司类型和历史披露差异。
- 采集映射统一维护在 `src/stock_maintainance/ingest.py`。

## 3. 历史数据回填

新增脚本：

`scripts/backfill_financial_structured_fields.py`

该脚本从已落库的 `payload_json` 中解析新增字段，并回填至结构化列。本次已执行：

```text
backfilled financial_income_raw: 25 fields
backfilled financial_balance_raw: 43 fields
backfilled financial_cashflow_raw: 30 fields
```

## 4. 视图增强

新增或增强的财务标准化视图：

| 视图 | 说明 |
|---|---|
| `financial_income_statement` | 利润表结构化全字段视图，排除 `payload_json` 和 `updated_at` |
| `financial_balance_sheet` | 资产负债表结构化全字段视图，排除 `payload_json` 和 `updated_at` |
| `financial_cashflow_statement` | 现金流量表结构化全字段视图，排除 `payload_json` 和 `updated_at` |
| `financial_indicator_statement` | 财务指标结构化全字段视图，排除 `payload_json` 和 `updated_at` |
| `financial_statement_latest` | 每个股票、报告期、报表类型的最新公告版本索引 |
| `financial_indicator_asof` | 日频点时安全财务指标入口 |
| `financial_statement_asof` | 当前指向 `financial_indicator_asof`，作为后续财务 as-of 标准入口 |

新增或增强的财务事件结构化视图：

| 视图 | 来源 |
|---|---|
| `financial_forecast` | `forecast` |
| `financial_express` | `express` |
| `financial_audit_opinion` | `fina_audit` |
| `financial_main_business` | `fina_mainbz` |
| `financial_holder_number` | `stk_holdernumber` |
| `financial_top10_holders` | `top10_holders` |
| `financial_top10_float_holders` | `top10_floatholders` |
| `financial_pledge_detail` | `pledge_detail` |
| `financial_repurchase` | `repurchase` |
| `financial_share_float` | `share_float` |

旧视图保留，以保证兼容性。

## 5. 数据字典和文档同步

本次同步更新：

- `config/schema_registry.json`
- `config/variables/base_variables.json`
- `src/stock_maintainance/ingest.py`
- `src/stock_maintainance/views.py`
- `scripts/backfill_financial_structured_fields.py`
- `scripts/build_global_variable_dictionary.mjs`
- `docs/generated_schema_dictionary.md`
- `docs/generated_variable_dictionary.md`
- `outputs/variable_dictionary/global_variable_dictionary*.xlsx`

全局 Excel 数据字典中，新增财务字段优先使用中文字段名，并保留来源 API 与来源字段。

## 6. 后续建议

下一步建议继续做“财务字段质量审计和财务 as-of 口径抽检”：

1. 检查新增字段的非空率和年度覆盖率。
2. 抽样核对 `financial_indicator_asof` 是否严格按公告日生效。
3. 将 Phase 3 财务衍生变量逐步切换到 `financial_statement_asof` / `financial_indicator_asof`。
