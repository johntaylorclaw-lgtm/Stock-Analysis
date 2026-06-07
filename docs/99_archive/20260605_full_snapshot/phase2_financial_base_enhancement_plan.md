# Phase 2 财务基础数据补强设计清单

生成日期：2026-05-31

## 1. 结论

建议 Phase 2 下一步优先做“财务基础数据补强”。当前项目已经完成财务基础库的主要骨架，但从股票分析模型需要看，仍有三个短板：

1. 三大财务报表当前是“精选字段结构化 + 全量 payload_json 保底”，可追溯性较好，但结构化字段不够完整，后续财务衍生变量会被迫频繁解析 JSON。
2. 财务事件已经通过 `financial_event_raw` 和若干视图保留了大量历史数据，但高价值事件的稳定结构化程度还不够统一，尤其是十大股东、十大流通股东、主营业务构成、业绩预告、业绩快报、股份解禁/流通、回购、质押明细。
3. 财务点时口径已经有 `effective_date = coalesce(first_ann_date, ann_date)` 的基础，但还缺少统一的“报告版本选择、TTM/单季/累计口径、报告期序列、公告日可得性”的标准化层。

推荐采用 **“raw 原始保全 + structured 明细宽表 + asof 标准化视图”** 的混合方案：

- `raw` 层继续保留 Tushare 原始 payload，保证未来字段补漏和审计可回放。
- `structured` 层把高频使用字段稳定拆列，避免衍生变量阶段反复解析 JSON。
- `asof` 层按交易日或公告日提供点时安全的最新可得财务状态，为 Phase 3 财务衍生变量服务。

## 2. 当前已完成状态

### 2.1 已落库基础表

| 表名 | 当前行数 | 当前定位 | 评价 |
|---|---:|---|---|
| `financial_income_raw` | 294,351 | 利润表精选字段 + payload_json | 已可用，但结构化字段偏少 |
| `financial_balance_raw` | 272,771 | 资产负债表精选字段 + payload_json | 已可用，但资产/负债/权益拆分不够细 |
| `financial_cashflow_raw` | 297,550 | 现金流量表精选字段 + payload_json | 已可用，但经营/投资/筹资明细需扩展 |
| `financial_indicator_raw` | 253,004 | Tushare 财务指标 151 个字段 | 较完整，是当前财务衍生变量主来源 |
| `financial_dividend_raw` | 163,213 | 分红送转原始数据 | 已结构化，建议保留 |
| `financial_disclosure_schedule` | 270,515 | 财报披露计划 | 已结构化，点时安全很重要 |
| `pledge_stat` | 2,204,384 | 股权质押统计 | 已结构化，建议纳入治理/风险基础层 |
| `financial_event_raw` | 16,390,985 | 财务增强事件原始池 | 数据丰富，但稳定拆表还不够 |

### 2.2 已有结构化视图

当前已有视图包括：

`financial_income`、`financial_balance`、`financial_cashflow`、`financial_indicator`、`financial_dividend`、`financial_pledge_stat`、`financial_event_forecast`、`financial_event_audit`、`financial_event_mainbz`、`financial_event_holdernumber`、`financial_event_top10_holders`、`financial_event_pledge_detail`、`financial_event_repurchase`、`financial_event_share_float`。

这些视图证明 Tushare API 和本地 payload 的可用性已经被实证验证。下一步的问题不是“能不能取到”，而是“哪些字段要稳定拆列、如何命名、如何为衍生层提供点时安全口径”。

## 3. 推荐目标结构

### 3.1 财务报表 raw 层

继续保留并增强当前四张 raw 表：

| 表名 | 推荐动作 | 说明 |
|---|---|---|
| `financial_income_raw` | 扩字段 | 利润表核心字段从当前约 24 列扩展为更完整结构化列 |
| `financial_balance_raw` | 扩字段 | 资产、负债、所有者权益明细需要显著补强 |
| `financial_cashflow_raw` | 扩字段 | 经营、投资、筹资现金流明细需要补强 |
| `financial_indicator_raw` | 保持完整并校准中文名 | 当前字段数量已经较充分，重点是中文名、含义、单位和字段质量 |

raw 层主键建议维持：

- 报表表：`ts_code, end_date, comp_type, report_type, ann_date`
- 指标表：`ts_code, end_date, ann_date`

原因：同一报告期可能存在不同公告版本、不同报表类型或更正报告，不能简单用 `ts_code + end_date` 覆盖。

### 3.2 财务报表 structured 层

新增或改造为稳定结构化视图，而不是立刻新增实体表：

| 推荐视图 | 来源 | 用途 |
|---|---|---|
| `financial_income_statement` | `financial_income_raw` | 利润表完整结构化口径 |
| `financial_balance_sheet` | `financial_balance_raw` | 资产负债表完整结构化口径 |
| `financial_cashflow_statement` | `financial_cashflow_raw` | 现金流量表完整结构化口径 |
| `financial_indicator_statement` | `financial_indicator_raw` | 指标表完整结构化口径 |
| `financial_statement_latest` | 四张 statement 视图 | 每个股票每个报告期的最新公告版本 |
| `financial_statement_asof` | `financial_statement_latest` + 交易日历 | 点时安全的最新可得财务状态 |

先做视图的原因：

1. 不增加重复存储。
2. 可以快速调整字段口径。
3. 与当前 `payload_json` 方案兼容。
4. Phase 3 衍生层可以统一依赖视图，后续若性能不足再物化。

### 3.3 财务事件 structured 层

建议把 `financial_event_raw` 中高价值事件稳定拆成以下结构化视图或表：

| 推荐对象 | 来源 API | 优先级 | 说明 |
|---|---|---:|---|
| `financial_forecast` | `forecast` | P0 | 业绩预告，影响预期和风险 |
| `financial_express` | `express` | P0 | 业绩快报，早于正式财报 |
| `financial_audit_opinion` | `fina_audit` | P0 | 审计意见，治理/质量风险 |
| `financial_main_business` | `fina_mainbz` | P0 | 主营业务构成，行业和业务结构分析 |
| `financial_holder_number` | `stk_holdernumber` | P0 | 股东户数，筹码集中度 |
| `financial_top10_holders` | `top10_holders` | P0 | 十大股东 |
| `financial_top10_float_holders` | `top10_floatholders` | P0 | 十大流通股东 |
| `financial_pledge_detail` | `pledge_detail` | P1 | 股权质押明细 |
| `financial_repurchase` | `repurchase` | P1 | 回购 |
| `financial_share_float` | `share_float` | P1 | 限售解禁/流通股本变化 |

`financial_dividend_raw` 和 `pledge_stat` 已经有独立表，继续保留。

## 4. 财务报表字段补强建议

### 4.1 利润表 `financial_income_raw`

当前已结构化字段覆盖收入、成本、费用、利润和所得税主线。建议补强以下字段组：

| 字段组 | 建议字段方向 | 用途 |
|---|---|---|
| 收入层级 | 营业总收入、营业收入、利息收入、手续费及佣金收入、已赚保费 | 适配金融类和非金融类公司 |
| 成本层级 | 营业总成本、营业成本、利息支出、手续费及佣金支出、退保金、赔付支出 | 金融/保险公司分析需要 |
| 税金与费用 | 税金及附加、销售费用、管理费用、研发费用、财务费用、资产减值损失、信用减值损失 | 利润质量、费用率、减值分析 |
| 投资与公允价值 | 投资收益、公允价值变动收益、资产处置收益、其他收益 | 非经常性收益和利润可持续性 |
| 利润层级 | 营业利润、利润总额、净利润、归母净利润、少数股东损益、扣非净利润 | 盈利能力和归母口径 |
| 每股指标 | 基本 EPS、稀释 EPS | 与估值和增长变量连接 |

### 4.2 资产负债表 `financial_balance_raw`

当前字段覆盖资产、负债、权益主干。建议补强以下字段组：

| 字段组 | 建议字段方向 | 用途 |
|---|---|---|
| 流动资产 | 货币资金、交易性金融资产、应收票据、应收账款、预付款项、其他应收款、存货、合同资产、流动资产合计 | 流动性、营运资本、存货和应收质量 |
| 非流动资产 | 长期股权投资、投资性房地产、固定资产、在建工程、使用权资产、无形资产、开发支出、商誉、递延所得税资产、非流动资产合计 | 资产结构、商誉风险、资本开支 |
| 流动负债 | 短期借款、应付票据、应付账款、预收款项、合同负债、应付职工薪酬、应交税费、一年内到期非流动负债、流动负债合计 | 短债压力、经营占款 |
| 非流动负债 | 长期借款、应付债券、租赁负债、长期应付款、递延收益、递延所得税负债、非流动负债合计 | 长债压力和资本结构 |
| 所有者权益 | 股本、资本公积、盈余公积、未分配利润、归母权益、少数股东权益、权益合计 | ROE、杠杆、权益质量 |

### 4.3 现金流量表 `financial_cashflow_raw`

当前字段覆盖现金流三大类主干。建议补强以下字段组：

| 字段组 | 建议字段方向 | 用途 |
|---|---|---|
| 经营流入 | 销售商品提供劳务收到现金、收到税费返还、收到其他与经营活动有关现金、经营流入小计 | 收现质量 |
| 经营流出 | 购买商品接受劳务支付现金、支付职工现金、支付税费、支付其他经营现金、经营流出小计 | 成本现金化、经营效率 |
| 经营净额 | 经营活动现金流量净额 | 利润含金量 |
| 投资流入 | 收回投资、取得投资收益、处置固定/无形资产收回现金、投资流入小计 | 投资收益和资产处置 |
| 投资流出 | 购建固定/无形资产支付现金、投资支付现金、取得子公司支付现金、投资流出小计 | CAPEX 和扩张强度 |
| 筹资流入 | 吸收投资、取得借款、发行债券、筹资流入小计 | 外部融资 |
| 筹资流出 | 偿还债务、分红付息、筹资流出小计 | 债务压力和股东回报 |
| 现金首尾 | 期初现金、现金净增加、期末现金、汇率影响 | 现金流勾稽 |

### 4.4 财务指标 `financial_indicator_raw`

当前 151 个字段较丰富，优先做中文名和用途校准，不建议盲目扩字段。重点分为：

| 字段组 | 代表字段 | 用途 |
|---|---|---|
| 每股指标 | EPS、BPS、OCFPS、CFPS、FCFF_PS、FCFE_PS | 估值和股东回报 |
| 盈利能力 | gross_margin、netprofit_margin、ROE、ROA、ROIC | 质量和盈利能力 |
| 偿债能力 | current_ratio、quick_ratio、cash_ratio、debt_to_assets | 财务风险 |
| 周转效率 | ar_turn、ca_turn、assets_turn、turn_days | 经营效率 |
| 现金流质量 | ocf_to_profit、ocf_to_debt、salescash_to_or | 利润含金量 |
| 成长指标 | tr_yoy、or_yoy、netprofit_yoy、ocf_yoy、q_*_yoy/qoq | 成长和边际变化 |
| 单季指标 | q_opincome、q_eps、q_roe、q_netprofit_margin | 单季趋势 |

## 5. 点时安全和版本规则

财务数据必须按“公告后可用”处理，不能按报告期直接泄漏未来信息。

推荐规则：

1. `effective_date = coalesce(first_ann_date, ann_date, end_date)`，其中 `end_date` 只能作为兜底缺失处理，不应视为真实公告可得日。
2. 同一 `ts_code + end_date` 有多条记录时，默认选择 `effective_date <= trade_date` 且 `effective_date` 最大的一条。
3. 若同一 `effective_date` 仍有多版本，优先级建议为：更正/正式披露优先于预披露；字段完整度高者优先；`updated_at` 新者优先。
4. Phase 3 日频衍生变量只能依赖 as-of 视图，不直接依赖 raw 表。
5. 超过 10 个交易日的历史财务修复仍按你的要求显式确认后触发。

## 6. payload_json 与结构化表的取舍

### 6.1 payload_json 优点

- 能完整保留 Tushare 原始返回。
- 字段新增时无需立刻迁移 schema。
- 审计和回放友好。
- 对稀疏事件类数据尤其合适。

### 6.2 payload_json 缺点

- 字段中文名、单位、含义不直观。
- 查询性能和类型校验弱。
- 衍生变量公式不透明。
- 后续 Excel 数据字典很难清晰展示字段来源。

### 6.3 结构化表优点

- 字段类型稳定，便于质量校验。
- 衍生变量可以直接写公式。
- 查询性能更好。
- 更适合维护中文数据字典。

### 6.4 结构化表缺点

- schema 维护成本更高。
- Tushare 字段变化时需要迁移。
- 对大量稀疏事件可能产生很多空列。

### 6.5 推荐

财务报表和财务指标采用 **结构化字段为主、payload_json 保底**。  
财务事件采用 **raw payload 全保留 + 高价值事件结构化视图/表**。

这和当前项目方向一致，但需要把“结构化字段为主”做得更彻底。

## 7. 实施步骤

### Step 1：财务字段审计

输出 `reports/phase2_financial_field_audit.md`：

- 对比 `schema_registry.json`、`base_variables.json`、DuckDB 实际表字段。
- 列出四张财务报表已结构化字段、payload 中存在但未结构化字段。
- 识别字段中文名缺失、英文 label、单位缺失、字段含义不明确的问题。

### Step 2：财务报表字段补强

修改：

- `config/schema_registry.json`
- `config/variables/base_variables.json`
- `src/stock_maintainance/ingest.py` rename/mapping 逻辑
- 必要时修改 `views.py`

原则：

- 优先补三大报表高价值字段。
- 保持原主键不变。
- 不删除 `payload_json`。
- 不破坏现有视图和 Phase 3 依赖。

### Step 3：财务事件结构化增强

优先增强：

1. `financial_forecast`
2. `financial_express`
3. `financial_audit_opinion`
4. `financial_main_business`
5. `financial_holder_number`
6. `financial_top10_holders`
7. `financial_top10_float_holders`
8. `financial_share_float`

这些对象先做视图，若后续查询性能不足再物化为表。

### Step 4：财务 as-of 标准层

新增或增强：

- `financial_statement_latest`
- `financial_statement_asof`
- `financial_indicator_asof`
- `financial_event_asof`

这些视图是 Phase 3 财务衍生变量的唯一推荐入口。

### Step 5：质量审计增强

新增审计项：

- 财报表按年覆盖率。
- 股票覆盖率，含上市、退市、北交所。
- `ann_date`、`first_ann_date`、`effective_date` 缺失率。
- 同一报告期多版本数量。
- 关键字段缺失率：收入、归母净利润、总资产、归母权益、经营现金流、ROE、毛利率。
- as-of 可用率。

### Step 6：数据字典同步

重新生成：

- `outputs/variable_dictionary/global_variable_dictionary.xlsx`

并保证：

- 财务字段中文名为中文叙述。
- 来源 API、来源字段准确。
- as-of 视图和衍生变量公式能明确引用来源。

## 8. 验收标准

Phase 2 财务补强完成后，需要满足：

1. 四张核心财务表的结构化字段覆盖比当前明显提升。
2. 财务字段中文名、字段含义、来源 API、来源字段在全局数据字典中可读。
3. `payload_json` 仍完整保留。
4. 所有财务主键重复检查为 0。
5. 核心日期字段缺失率为 0 或有明确例外清单。
6. 关键字段缺失率报告清晰，不把源数据自然缺失误判为工程失败。
7. as-of 视图满足点时安全。
8. Phase 3 财务衍生变量可以只依赖标准化/as-of 入口，不需要直接解析 raw payload。

## 9. 需要你确认的问题

在进入实现前，我建议你确认以下三点：

1. 财务报表字段是否按“尽量完整结构化”推进，即三大报表从当前精选字段扩展为高覆盖字段，而不是只补几个核心字段。
2. 财务事件是否先采用“结构化视图”方案，等性能确有问题再物化为实体表。
3. 是否同意财务 as-of 标准层作为 Phase 3 财务衍生变量的唯一入口，避免衍生变量直接读取 raw 表。
