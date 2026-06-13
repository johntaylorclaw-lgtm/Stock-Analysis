# 13 Agent Skill 运行手册与自动报告设计

更新日期：2026-06-07

## 1. 目标与确认结论

本阶段目标不是重写数据维护逻辑，而是为已完成的 CLI 和报告体系增加一层薄封装。

用户确认的实施边界如下：

1. Agent Skill 创建到项目内 `Skill/` 路径，即 `D:\Opencode Workspace\Stock_Maintainance\Skill`。
2. 每日报告是接续 `daily-light` 后的执行检查和总结，由 Hermes Agent 执行。
3. 周报告是接续 `weekly-full` 后的执行检查和总结，由 Hermes Agent 执行。
4. 自动报告采用 Markdown 形式；当前实现同时保留 CLI 内部可读取的结构化事实来源，但 Hermes 对外输出以 Markdown 为准。
5. 2026-06-08 首日日加载审计后，Hermes 日加载默认运行时间调整为北京时间 20:00，以覆盖 Tushare 晚间 T+0 API 发布窗口。
6. 项目内 Hermes 调度配置记录在 `config/hermes_agent.json`，用于把运行手册、Skill 和自动化设置保持一致。

本阶段交付包括：

1. Agent Skill：让 Codex 在本工程中稳定知道如何执行状态检查、日批、周检、字典刷新、抽样和修复建议。
2. 运行手册：给人工维护者一份低歧义、可复现的操作入口。
3. 自动报告汇总：把每日、每周运行结果聚合成统一 Markdown 报告，减少手工翻找多个 `reports/phase5_*` 文件。

设计原则：

1. 以现有 CLI 为唯一执行入口，不在 Skill 中嵌入复杂业务逻辑。
2. Skill 只做流程导航、边界提醒和命令选择，不直接替代代码。
3. 自动报告只汇总事实，不生成投资观点、评分或策略建议。
4. 每日/每周报告必须能被人工快速阅读，报告中的状态、窗口、执行步骤和异常必须可追溯到原始运行报告。
5. 优先 WSL 运行；涉及 Excel 数据字典时允许通过 WSL 调 Windows bundled Node。

## 2. Agent Skill 薄封装设计

### 2.1 Skill 名称

已创建 Skill：

`stock-maintenance-ops`

建议触发描述：

当用户要求在 `Stock_Maintainance` 工程中执行或规划股票数据维护、日批、周检、质量验证、数据字典刷新、样本抽查、报告汇总、历史修复或交付验收时使用。

### 2.2 Skill 文件结构

已创建在项目内 Skill 目录：

```text
Skill/stock-maintenance-ops/
  SKILL.md
  references/
    commands.md
    operations.md
    reports.md
    hermes_agent.md
```

说明：

1. `SKILL.md` 只保留最短工作流和安全边界。
2. `references/commands.md` 保存 CLI 命令清单。
3. `references/operations.md` 保存日批、周检、修复、抽样的流程说明。
4. `references/reports.md` 保存报告路径、字段含义和验收口径。

### 2.3 SKILL.md 核心内容

建议 Skill 主体只包含：

1. 工作目录：

```bash
cd "/mnt/d/Opencode Workspace/Stock_Maintainance"
```

2. Python/CLI 入口：

```bash
.venv-wsl/bin/stock-maintain <command>
```

3. 默认流程：

| 用户意图 | 首选命令 |
|---|---|
| 查看当前状态 | `stock-maintain summarize-run --mode status` |
| 执行日批前计划 | `stock-maintain daily-light --dry-run` |
| 执行日批 | `stock-maintain daily-light` |
| 强制日频重拉 | `stock-maintain daily-full` |
| 执行周检 | `stock-maintain weekly-full` |
| 刷新字典 | `stock-maintain refresh-dictionary` |
| 抽样单股 | `stock-maintain sample-stock` |
| 汇总日报 | `stock-maintain summarize-run --mode daily` |
| 汇总周报 | `stock-maintain summarize-run --mode weekly` |

4. 安全边界：

| 场景 | 规则 |
|---|---|
| 超过 10 个交易日补数 | 不自动执行，必须显式确认 |
| 新股/退市状态 | 日批必须先跑 `sync-master`，由 `daily-light` / `daily-full` 自动完成 |
| 全量重建参照 | 不在 Skill 中直接触发，需进入影子库设计 |
| Excel 数据字典 | 使用 `refresh-dictionary`，不手写底层 Node 命令 |
| 投资建议/评分 | 不生成，工程只维护事实数据 |

### 2.4 Skill 与运行手册的区别

| 对象 | 面向对象 | 内容粒度 | 是否进入 Codex 上下文 |
|---|---|---|---|
| Agent Skill | Codex/Agent | 极简流程和边界 | 会触发加载 |
| 运行手册 | 人工维护者 | 详细命令、报告、故障处理 | 默认不加载，按需阅读 |
| 自动报告 | 人和程序 | 本次运行事实 | 由 CLI 生成 |

## 3. 运行手册设计

已新增主文档：

`14_运行手册.md`

运行手册建议包含以下章节：

1. 环境入口
2. 日批 daily-light
3. 周检 weekly-full
4. 数据字典 refresh-dictionary
5. 样本抽检 sample-stock
6. 历史修复 repair-confirmed
7. 常见故障
8. 报告路径索引

### 3.1 环境入口

固定使用：

```bash
cd "/mnt/d/Opencode Workspace/Stock_Maintainance"
.venv-wsl/bin/stock-maintain --help
```

### 3.2 日批操作

推荐：

```bash
.venv-wsl/bin/stock-maintain daily-light \
  --as-of-date <YYYY-MM-DD> \
  --dry-run \
  --output-prefix <run_id>

.venv-wsl/bin/stock-maintain daily-light \
  --as-of-date <YYYY-MM-DD> \
  --output-prefix <run_id>
```

若日频源数据晚到或需要强制重拉最近窗口：

```bash
.venv-wsl/bin/stock-maintain daily-full \
  --as-of-date <YYYY-MM-DD> \
  --reload-trade-days 1 \
  --output-prefix <run_id>
```

验收：

1. 日批报告 status 为 `pass`。
2. precheck/postcheck 均为 `pass`。
3. 若待增量交易日数为 0，应确认 `sync-master` 已执行。
4. 若出现 blocked，不继续补数，先确认是否超过 10 个交易日。

### 3.3 周检操作

推荐：

```bash
.venv-wsl/bin/stock-maintain weekly-full \
  --as-of-date <YYYY-MM-DD> \
  --dry-run \
  --output-prefix <run_id>

.venv-wsl/bin/stock-maintain weekly-full \
  --as-of-date <YYYY-MM-DD> \
  --auto-create-missing-snapshot \
  --output-prefix <run_id>
```

验收：

1. 表数为 25。
2. 通过表为 25。
3. 键差异为 0。
4. 字段差异为 0。
5. 若结果为 `snapshot_created`，需要再跑一次 weekly-full 完成 compare。
5. 若请求比较窗口与快照共同窗口不一致，报告必须明确实际比较窗口。

### 3.4 字典刷新

推荐：

```bash
.venv-wsl/bin/stock-maintain refresh-dictionary \
  --output-prefix <run_id>
```

验收：

1. `schema_registry.json` 与实际视图列同步。
2. `docs/generated/*` 已刷新。
3. `global_variable_dictionary.xlsx` 存在。
4. `docs-check` 通过。

## 4. 自动报告汇总设计

已新增 CLI：

`stock-maintain summarize-run`

### 4.1 设计目标

`summarize-run` 负责把多个底层报告汇总为一个稳定入口：

| 模式 | 用途 | 输出 |
|---|---|---|
| `status` | 当前库状态快照 | `reports/summaries/status_summary_<date>.md` |
| `daily` | 汇总最近一次或指定 run_id 的日批 | `reports/summaries/daily_summary_<run_id>.md` |
| `weekly` | 汇总最近一次或指定 run_id 的周检 | `reports/summaries/weekly_summary_<run_id>.md` |
| `phase` | 汇总阶段验收状态 | `reports/summaries/phase_summary_<phase>.md` |

### 4.2 status 报告字段

建议字段：

| 字段 | 来源 |
|---|---|
| 证券主数据股票数 | `stock_basic_info` |
| 当前上市股票数 | `stock_basic_info.list_status = 'L'` |
| 已退市股票数 | `stock_basic_info.list_status = 'D'` |
| 日行情覆盖股票数 | `stock_daily` |
| 日频核心行数 | `derived_daily_spine` |
| 最新交易日 | `trade_calendar` |
| 当前数据锚点 | `derived_daily_spine.max(trade_date)` |
| 待增量交易日数 | `validate-daily` |
| core/plus/full 列数 | `PRAGMA table_info` |
| 最近门禁结果 | 最近 `phase5_*` 报告 |

### 4.3 daily 报告字段

建议字段：

| 字段 | 来源 |
|---|---|
| run_id | 参数或文件名 |
| as_of_date | `daily-light` report |
| dry_run/execute | `daily-light` report |
| latest_trade_date | precheck |
| anchor_data_date | precheck |
| validation_dates | precheck |
| incremental_dates | precheck |
| sync-master 结果 | daily-light steps |
| base-incremental 结果 | daily-light steps |
| feature-build 模块数 | daily-light steps |
| postcheck 状态 | daily-light postcheck |
| 总状态 | daily-light summary |

### 4.4 weekly 报告字段

建议字段：

| 字段 | 来源 |
|---|---|
| reference window | weekly-full report |
| requested compare window | weekly-full report |
| snapshot common window | weekly-full report |
| effective compare window | weekly-full report |
| table_count | weekly-full summary |
| pass/fail table count | compare report |
| key diff rows | compare report |
| mismatch columns/cells | compare report |
| fail tables | compare report |

### 4.5 输出路径

建议路径：

```text
reports/summaries/
  status_summary_YYYYMMDD.md
  daily_summary_<run_id>.md
  weekly_summary_<run_id>.md
  phase_summary_<phase>.md
```

### 4.6 报告状态枚举

| 状态 | 含义 |
|---|---|
| `pass` | 所有关键门禁通过 |
| `warning` | 有非阻塞异常，例如 optional 数据域缺失、窗口自动对齐 |
| `blocked` | 超过 10 个交易日、缺失快照、缺失必要报告 |
| `fail` | 字段级对照失败、配置校验失败或测试失败 |

## 5. 实施结果

### 5.1 自动报告汇总

已新增：

1. `src/stock_maintainance/run_summary.py`
2. CLI：`summarize-run`
3. 测试：`tests/test_run_summary.py`

已实现：

1. `--mode status`
2. `--mode daily --run-id <prefix>`
3. `--mode weekly --run-id <prefix>`
4. `--mode phase --phase <phase>`

### 5.2 运行手册

已新增：

1. `docs/14_运行手册.md`
2. 更新 `docs/00_文档索引.md`
3. 更新 `docs.py` 的 `MAIN_DOCS`

### 5.3 Agent Skill

已新增项目本地 Skill：

```text
Skill/stock-maintenance-ops/
  SKILL.md
  references/
    commands.md
    operations.md
    reports.md
    hermes_agent.md
```

Skill 内容保持短，只记录工作目录、CLI 入口、运行边界和 Hermes Agent 报告职责；详细命令和报告口径放在 references 与 `docs/14_运行手册.md`。

### 5.4 已生成的 Markdown 报告样例

本轮已实际生成：

| 报告 | 路径 |
|---|---|
| 当前状态汇总 | `reports/summaries/status_summary_20260607.md` |
| 日批后 Hermes 汇总 | `reports/summaries/daily_summary_phase5_daily_light_execute_20260607.md` |
| 周检后 Hermes 汇总 | `reports/summaries/weekly_summary_phase5_weekly_full_compare_20260607.md` |

## 6. 验收标准

| 项目 | 标准 |
|---|---|
| `summarize-run --mode status` | 生成 status summary，包含当前股票数、日期、锚点和出口列数 |
| `summarize-run --mode daily` | 能读取 `daily-light` 报告并生成日报 |
| `summarize-run --mode weekly` | 能读取 `weekly-full` 和 compare 报告并生成周报 |
| 运行手册 | 编号文档存在，命令和报告路径可执行 |
| Agent Skill | Skill 简洁、触发描述明确、引用稳定 CLI |
| 门禁 | `pytest`、`validate-config`、`docs-check` 通过 |

## 7. 后续维护规则

1. `daily-light` 和 `weekly-full` 的执行逻辑仍由 CLI 负责，Hermes Agent 只做后续检查和总结。
2. 每次新增或调整运行命令，应同步更新 `Skill/stock-maintenance-ops/references/commands.md` 与 `docs/14_运行手册.md`。
3. 每次调整报告字段，应同步更新 `src/stock_maintainance/run_summary.py`、`tests/test_run_summary.py` 与本设计文档。
4. 报告若出现乱码，优先检查文件是否以 UTF-8 写入；本工程 Markdown 文档和报告统一使用 UTF-8。
5. Hermes 日加载时间若再调整，必须同步更新 `config/pipeline.json`、`Skill/stock-maintenance-ops/` 和 `docs/14_运行手册.md`。
