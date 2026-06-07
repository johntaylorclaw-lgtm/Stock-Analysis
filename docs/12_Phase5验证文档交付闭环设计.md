# 12 Phase 5 验证文档交付闭环设计

更新日期：2026-06-07

## 1. Phase 5 定位

Phase 5 定义为：

**验证、文档、交付闭环与日常运行固化。**

Phase 4 已证明增量构建能够保持与近期全量参照一致。Phase 5 的目标是把这种能力固化成稳定运行模式、标准验证命令、自动化文档门禁、样本审查材料和下游交付指南。

## 2. 运行模式

### 2.1 daily-light

daily-light 用于每日运行，维护范围包括：

1. 每日基础数据；
2. 核心衍生变量；
3. 视图衍生变量；
4. light 质量验证。
5. 证券主数据刷新，用于及时引入新股、退市状态和公司基础信息变化。

运行原则：

1. 只做增量补充，缺几个交易日补几个交易日。
2. 自动补充窗口最多 10 个交易日。
3. 若缺口不超过 10 个交易日，允许额外选择 1 个历史验证日，用于验证本次跑批与历史交付是否一致或高度相近。
4. 验证日只用于对照，不作为最终补数写入目标窗口，避免用验证行为污染最终数据库。
5. 每次正式补数前先运行 `sync-master`，确保 `stock_basic_info`、`stock_company_info` 和 `stock_status_history` 已覆盖最新全 A 股范围。
6. 新股上市后，先由主数据刷新捕捉证券代码、上市日期和市场信息，再由日行情、复权、涨跌停、daily_basic、资金等基础表补齐交易日记录。
7. 若新股的首个应覆盖交易日超出 10 个交易日自动窗口，应纳入历史修复确认，而不是由 daily-light 静默大范围回补。

示例：

数据库截至 2026-06-01，最近交易日为 2026-06-05，则 daily-light 可使用：

| 类型 | 日期 | 用途 |
|---|---|---|
| 验证日 | 2026-06-01 | 检查本次跑批与历史结果是否一致或高度相近 |
| 增量日 | 2026-06-02 至 2026-06-05 | 真实补数和衍生构建 |

### 2.2 weekly-full

weekly-full 用于周度复核，执行近期全量参照窗口与增量窗口对照。

建议内容：

1. 选择最近 20 至 40 个自然日作为近期全量参照；
2. 选择最近 5 至 10 个交易日作为增量窗口；
3. 比较基础表、核心衍生表、缓存表、统一出口视图；
4. 输出字段级差异报告。

### 2.3 repair-confirmed

repair-confirmed 用于历史修复。

规则：

1. 超过 10 个交易日的修复必须显式确认。
2. 修复前先生成计划和影响表清单。
3. 修复后必须运行 full 或 targeted compare。
4. 涉及财务、公司行动、行业概念、指数权重等事件型数据时，应优先按受影响股票和日期范围构建。

## 3. 验证命令建议

Phase 5 建议新增或固化以下命令：

| 命令 | 用途 |
|---|---|
| `daily-light` | 日批编排入口，串联主数据刷新、precheck、基础增量、衍生构建、视图刷新和 postcheck。已完成首版 |
| `weekly-full` | 周度复核入口，串联近期参照窗口、快照共同窗口对齐和字段级增量一致性对照。已完成首版 |
| `validate-daily` | daily-light 窗口判断、行数、日期、缺失、重复键、股票级衍生覆盖验证。已完成首版 |
| `compare-incremental-window` | 增量窗口与近期全量参照字段级对照。已完成首版 |
| `sample-stock` | 输出单股票基础、衍生、质量报告三类 Excel 样本。已完成首版 |
| `sample-module` | 输出指定模块或表的抽样审查材料 |
| `refresh-dictionary` | 同步统一出口 schema、刷新 generated docs、重建全局 Excel 数据字典。已完成首版 |
| `docs-check` | 文档、字典、注册表同步门禁 |

### 3.1 daily-light

首版命令：

```bash
stock-maintain daily-light \
  --as-of-date 2026-06-07 \
  --dry-run \
  --output-prefix phase5_daily_light_dry_run_20260607
```

首版编排顺序：

1. `sync-master`：刷新证券主数据、公司信息、状态历史、交易日历和指数基础信息；dry-run 中仅计划，不实际调用 Tushare。
2. `validate-daily-precheck`：判断最新交易日、锚点日期、验证日和待增量日期。
3. `base-incremental`：待增量交易日存在时，刷新 `daily`、`daily_basic`、`stk_limit`、`adj_factor`、资金流、融资融券、北向、龙虎榜和指数日行情。
4. 可选 `index-weight`：通过 `--include-index-weight` 触发月度指数权重补充。
5. 可选 `financial-incremental`：通过 `--include-financial` 触发财务报表和高价值财务事件的公告窗口补拉。
6. `feature-build`：使用验证日作为计算校验起点、待增量最后一日作为结束日，执行衍生变量增量构建。
7. `create-views`：刷新分析视图和三档统一出口视图。
8. `validate-daily-postcheck`：执行日批后验收。

安全边界：

1. 待增量交易日超过 `--max-auto-trade-days` 时默认 blocked。
2. 只有显式传入 `--allow-confirmed-history` 后，才允许超过默认窗口的历史修复式执行。
3. dry-run 不调用 Tushare、不写基础数据、不写衍生数据，仅生成计划和 precheck 报告。

实测记录：

| 截至日期 | 模式 | 待增量交易日 | 结果 | 报告 |
|---|---|---:|---|---|
| 2026-06-07 | dry-run | 0 | pass | `reports/phase5_daily_light_dry_run_20260607.md` |
| 2026-06-07 | execute | 0 | pass | `reports/phase5_daily_light_execute_20260607.md` |

execute 实测中，`sync-master` 已刷新证券主数据、公司信息、状态历史、交易日历和指数基础信息。刷新后证券主数据为 5,851 只，其中当前上市 5,525 只、退市 326 只；本次无待增量交易日，因此基础日频补数和衍生构建均跳过。

### 3.2 weekly-full

### 3.3 compare-incremental-window

首版命令：

```bash
stock-maintain weekly-full \
  --as-of-date 2026-06-07 \
  --output-prefix phase5_weekly_full_compare_20260607
```

首版实现逻辑：

1. 默认取最近 40 个开放交易日作为参照窗口，最近 10 个开放交易日作为请求比较窗口。
2. 默认复用已有 `audit_tmp_phase4_full_` 全量参照快照，不自动覆盖主库、不自动重建生产表。
3. 若快照缺失，报告状态为 `blocked`。
4. 若请求比较窗口与快照共同窗口不完全一致，自动取交集作为实际比较窗口，避免因快照范围较短产生假失败。
5. 字段级对照复用 `compare-incremental-window` 的数值容忍、主键和字段差异逻辑。
6. `--create-snapshot-from-current` 仅用于从当前主库裁剪比较窗口生成快照基线，不等同于独立全量重建参照；如需真正的影子全量重建，应后续引入影子库方案。

实测记录：

| 截至日期 | 参照窗口 | 请求比较窗口 | 实际比较窗口 | 表数 | 通过表 | 键差异 | 字段差异 | 结果 | 报告 |
|---|---|---|---|---:|---:|---:|---:|---|---|
| 2026-06-07 | 2026-04-08 至 2026-06-05 | 2026-05-25 至 2026-06-05 | 2026-05-27 至 2026-06-05 | 24 | 24 | 0 | 0 | pass | `reports/phase5_weekly_full_compare_20260607.md` |

首版命令：

```bash
stock-maintain compare-incremental-window \
  --start-date 2026-05-27 \
  --end-date 2026-06-05 \
  --output-prefix phase5_compare_incremental_20260607 \
  --fail-on-diff
```

默认比较 Phase 4 验收使用的 24 张衍生和缓存表，默认快照前缀为 `audit_tmp_phase4_full_`。

本命令职责是比较当前数据库目标窗口与已存在的近期全量参照快照，不负责创建快照或重建数据。这样它可以作为 daily-light、weekly-full 和历史修复后的统一验收门禁。

实测记录：

| 窗口 | 表数 | 通过表 | 键差异 | 字段差异 | 报告 |
|---|---:|---:|---:|---:|---|
| 2026-05-27 至 2026-06-05 | 24 | 24 | 0 | 0 | `reports/phase5_compare_incremental_20260607.md` |

### 3.4 validate-daily

首版命令：

```bash
stock-maintain validate-daily \
  --as-of-date 2026-06-07 \
  --output-prefix phase5_validate_daily_20260607
```

首版实现逻辑：

1. 使用 `trade_calendar` 中 `is_open = 1` 且不晚于 `--as-of-date` 的最大日期作为最新交易日，避免把预加载到未来的交易日历误判为需要补数。
2. 使用 `derived_daily_spine` 的最大 `trade_date` 作为当前日批锚点；若该表不存在，则回退到 `stock_daily`。
3. 若锚点日期早于最新交易日，则生成待增量日期列表；待增量交易日超过 `--max-auto-trade-days` 时，报告状态为 `blocked`，需要显式确认后才能进入历史修复或大窗口补数。
4. 默认抽取 1 个锚点侧历史验证日，用于检查已有交付结果；增量日期只包含锚点之后至最新交易日之间的开放交易日。
5. 对基础日频表、Phase 4 验收用衍生表、统一出口视图执行目标日期覆盖、重复键、空 `ts_code` 和股票级衍生表相对 `derived_daily_spine` 的行数覆盖检查。
6. `index_weight` 等周期性基础表不按每日目标日期强制要求有数据，但仍记录最大日期和重复键检查结果。

实测记录：

| 截至日期 | 最新交易日 | 锚点日期 | 校验日期 | 待增量交易日 | 表数 | 问题表 | 结果 | 报告 |
|---|---|---|---|---:|---:|---:|---|---|
| 2026-06-07 | 2026-06-05 | 2026-06-05 | 2026-06-05 | 0 | 39 | 0 | pass | `reports/phase5_validate_daily_20260607.md` |
| 2026-06-07 | 2026-06-05 | 2026-06-05 | 2026-06-05 | 0 | 39 | 0 | pass | `reports/phase5_validate_daily_after_feature_expand_20260607.md` |
| 2026-06-07 | 2026-06-05 | 2026-06-05 | 2026-06-05 | 0 | 39 | 0 | pass | `reports/phase5_validate_daily_light_feature_views_20260607.md` |

## 4. 样本 Excel

样本 Excel 默认分为三类：

| 类别 | 内容 |
|---|---|
| 基础数据样本 | 行情、复权、涨跌停、资金、指数、财务原始结构化字段 |
| 衍生变量样本 | 核心衍生表、缓存表、统一出口视图字段 |
| 质量报告样本 | 缺失、特殊值、重复键、inf/NaN、增量一致性、字段覆盖率 |

### 4.1 sample-stock

首版命令：

```bash
stock-maintain sample-stock \
  --ts-code 000001.SZ \
  --start-date 2026-05-27 \
  --end-date 2026-06-05 \
  --rows 5 \
  --output-prefix phase5_sample_stock_20260607
```

首版实现内容：

1. 输出结构化 JSON 至 `reports/`，作为可追溯中间产物。
2. 输出 Excel 至 `outputs/phase5/`。
3. 基础数据样本覆盖股票基础信息、公司信息、上市状态、日行情、每日指标、复权因子、涨跌停、资金流、融资融券、北向持股、龙虎榜、财务三表、财务指标、分红、披露计划和质押统计。
4. 衍生变量样本覆盖日频 spine、交易技术、估值规模、财务 asof/quality/growth、资金流、行业概念、指数市场、横截面、公司行为、股权治理、综合事实状态以及 `stock_features_core/plus/full`。
5. 质量报告页按表记录是否存在、是否有 `ts_code`、日期列、样本股票行数、最小/最大日期和重复日期键数量。
6. 由于本工程优先在 WSL 中运行，Excel 首版采用 WSL Python `openpyxl` 生成；此前项目中的 artifact-tool 脚本保留，但不作为 WSL CLI 的强依赖。

实测记录：

| 股票 | 窗口 | 每表行数 | 基础对象 | 衍生对象 | 质量对象 | Sheet 数 | 报告 |
|---|---|---:|---:|---:|---:|---:|---|
| 000001.SZ | 2026-05-27 至 2026-06-05 | 5 | 19 | 20 | 39 | 43 | `outputs/phase5/phase5_sample_stock_20260607_000001_SZ.xlsx` |
| 000001.SZ | 2026-06-03 至 2026-06-05 | 2 | 19 | 20 | 39 | 43 | `outputs/phase5/phase5_sample_stock_expanded_20260607_000001_SZ.xlsx` |

## 4.2 refresh-dictionary

首版命令：

```bash
stock-maintain refresh-dictionary \
  --output-prefix phase5_refresh_dictionary_20260607
```

首版实现内容：

1. 同步 `stock_features_core/plus/full` 实际视图列至 `config/schema_registry.json`。
2. 重新生成 `docs/generated/generated_schema_dictionary.md`、`generated_variable_dictionary.md` 和 `generated_source_dictionary.md`。
3. 通过 Windows bundled Node 重建 `outputs/variable_dictionary/global_variable_dictionary.xlsx`。
4. 运行 `docs-check`，确认文档和主 Excel 数据字典存在且同步。

实测记录：

| 日期 | core列数 | plus列数 | full列数 | Excel | 结果 | 报告 |
|---|---:|---:|---:|---|---|---|
| 2026-06-07 | 318 | 1,198 | 1,602 | `outputs/variable_dictionary/global_variable_dictionary.xlsx` | pass | `reports/phase5_refresh_dictionary_20260607.json` |

## 5. 统一出口扩充

Phase 5 需要重新扩充并正式验收：

1. `stock_features_core`
2. `stock_features_plus`
3. `stock_features_full`

Phase 5 已生成覆盖率审计：

| 报告 | 当前结论 |
|---|---|
| `reports/phase5_feature_view_coverage_audit.md` | 当前 `core/plus/full` 分别为 318/1,198/1,602 列；`full` 已覆盖全部股票级 Phase 3 模块字段并补充基础 enriched 字段 |

扩充原则：

1. `core` 面向高频稳定使用，列数适中，字段必须质量稳定。
2. `plus` 面向研究扩展，纳入更多财务、行业、资金、公司行动和横截面变量。
3. `full` 面向全量研究和审计，尽量覆盖已注册核心衍生变量和关键基础变量。
4. 三类视图都必须进入 schema registry、Excel 数据字典和 docs-check。

已执行扩充边界：

| 视图 | 建议边界 |
|---|---|
| `core` | 扩充为 318 列，覆盖高频稳定核心事实字段 |
| `plus` | 扩充为 1,198 列，覆盖除横截面全量字段外的主要事实模块 |
| `full` | 扩充为 1,602 列，接受千列级全量事实出口，并对重名字段使用模块前缀，且过滤 `score` 字段 |

维护命令：

```bash
stock-maintain create-views
python scripts/sync_feature_view_schema_registry.py
```

数据字典同步：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' scripts\build_global_variable_dictionary.mjs
```

扩充后实测：

| 视图 | 列数 | 样本 Excel 页 |
|---|---:|---|
| `stock_features_core` | 318 | `D_stock_features_core` |
| `stock_features_plus` | 1,198 | `D_stock_features_plus` |
| `stock_features_full` | 1,602 | `D_stock_features_full` |

注意：`stock_features_full` 为千列级视图，适合 weekly-full、审计和全量研究。daily-light 已改为对 feature view 做轻量键覆盖检查，避免每日运行时对 full 视图做不必要的重型扫描；2026-06-07 实测约 1 分 50 秒完成。

## 6. Phase 5 验收标准

Phase 5 建议验收标准：

1. `validate-config` 通过；
2. `docs-check` 通过；
3. `pytest` 通过；
4. `validate-daily` 通过；首版已完成并通过 2026-06-07 截至日真实库验证；
5. `compare-incremental-window` 通过；首版已完成并通过 2026-05-27 至 2026-06-05 真实窗口验证；
6. 样本 Excel 可生成，且包含基础、衍生、质量报告三类；首版 `sample-stock` 已完成并通过 000001.SZ 真实样本验证；
7. `stock_features_core/plus/full` 完成扩充、注册、字典同步；
8. 迁移指南和运行手册完成。

当前总验收报告：

`reports/phase5_final_acceptance_report.md`
