# 审计报告：Stock_Maintainance 工程

**审计日期**：2026-06-06  
**目标工程**：`D:\Opencode Workspace\Stock_Maintainance`  
**当前阶段**：Phase 3 已验收完成，Phase 4 正在进行中  
**审计范围**：Phase 3 交付物完整性、Phase 4 执行进展、质量门禁、安全性、架构合规性  
**审计依据**：`Data Quality Check Rules.md`、项目 `AGENTS.md` 标准、设计文档 `docs/`  

---

## 1. 总体摘要

### 1.1 裁定声明

工程 Phase 3 主体已高质量完成，Phase 4 启动基础扎实，但存在**1 个 MAJOR 安全配置问题**（`.env` 中硬编码生产 Token）和 **3 个 MINOR 架构合规性问题**（缺少 `design/` 目录、日志基础设施未建立、schema 注册表 phase 标记格式不一致），建议修复后进入 Phase 4 深度推进。

### 1.2 项目背景

Stock_Maintainance 是一个 A 股日频数据库维护工程，覆盖 5,809 只股票、4,951 个交易日（2006-01-04 至 2026-05-26）。工程通过 Tushare API 同步原始数据（37 个 API 端点），再通过 17 个衍生特征模块构建分析就绪的变量库。工程坚持事实变量原则：不生成评分、不生成买卖信号、不生成未来收益标签。

### 1.3 审计行为统计

| 审计维度 | 数量 |
|---|---|
| 检查源文件 | 45+ 个文件 |
| 审查代码行 | ~13,000 行 Python 源码 |
| 验证注册表条目 | 81 个表/视图 |
| 验证变量定义 | 2,757 个变量（543 基础 + 2,214 衍生） |
| 交叉引用文档 | 11 份设计文档 |
| 分析脚本 | 56 个 Phase 3 相关脚本 |
| 检查测试 | 7 个测试文件（21 个测试用例） |
| 审查审计报告 | 18 份已有模块审计报告 |

---

## 2. 问题清单

### 问题 1：`.env` 文件中硬编码生产级 API Token

| 属性 | 内容 |
|---|---|
| **严重性** | `MAJOR` |
| **类别** | `security` |
| **证据** | `.env:1` — 包含完整有效的 Tushare Pro API Token 字符串（40 位十六进制） |
| **描述** | `TUSHARE_TOKEN` 的值以明文形式持久化在项目根目录的 `.env` 文件中。虽然 `.gitignore:1` 排除了该文件使其不被 Git 跟踪，但 Token 仍以明文形式存在于文件系统中，任何可以读取该工作空间的进程或用户均可获取该 Token。此外，Token 未设置轮换机制，属于长期不变凭据。 |
| **缓解因素** | 源代码（`env.py:32-36`）从环境变量动态读取 Token，采用正确的读取模式；`sources.json` 中通过 `token_env` 字段引用环境变量名，符合安全配置架构；`.gitignore` 提供了版本控制隔离。 |

### 问题 2：Schema Registry 中 Phase 标记格式不一致

| 属性 | 内容 |
|---|---|
| **严重性** | `MINOR` |
| **类别** | `data-integrity` |
| **证据** | `config/schema_registry.json:15051` — 唯一一个 `"phase": "phase3"` 的条目（`derived_financial_growth_full_v`），而其余 44 个 P3 条目均使用 `"phase": "P3"` 格式 |
| **描述** | 这是注册表中唯一的格式不一致项。当前 `validate-config` 命令（`validate.py:25-46`）不校验 `phase` 字段，因此该问题未被自动检测。如果下游代码对 `phase` 字段做精确字符串匹配（如 `== "P3"`），此视图将被遗漏于 P3 范围的统计、过滤或遍历逻辑之外。 |

### 问题 3：缺少 `design/` 目录

| 属性 | 内容 |
|---|---|
| **严重性** | `MINOR` |
| **类别** | `documentation` |
| **证据** | 项目根目录下无 `design/` 目录（glob 搜索确认） |
| **描述** | 工程 `AGENTS.md` 第 1 条标准要求项目必须包含 `design/` 目录用于存放设计文档。虽然 `docs/` 目录包含 11 份主要设计（`00-11`）和实现文档，且 `docs/99_archive/` 保留了历史快照，但未按工程标准建立独立的 `design/` 目录。 |

### 问题 4：日志基础设施未建立

| 属性 | 内容 |
|---|---|
| **严重性** | `MINOR` |
| **类别** | `maintainability` |
| **证据** | `logs/` 目录为空（glob 搜索 `logs/**/*` 无任何文件） |
| **描述** | 工程 `AGENTS.md` 第 6 条（Data Processing Log Standard）要求所有 `src/` 数据处理代码必须实现统一日志机制，包含时间戳、级别、模块名和处理结果，日志仅存储在 `logs/` 目录。当前所有源码模块（`ingest.py`、`modules.py`、`views.py`、`build.py`、`database.py` 等）均未集成日志基础设施，运行状态和关键指标不可追溯。 |

### 问题 5：DuckDB 残留的过期 WAL 文件

| 属性 | 内容 |
|---|---|
| **严重性** | `INFO` |
| **类别** | `maintainability` |
| **证据** | `data/duckdb/` 中存在两个过期 WAL 文件：`stock_data.duckdb.wal.stale_20260603_2157` 和 `stock_data.duckdb.wal.stale_20260604_2159` |
| **描述** | 这些残留文件表明近期（6 月 3 日、6 月 4 日）存在 DuckDB 未正常关闭的情况。虽然 DuckDB 已自动将它们标记为 `stale` 并生成了新的 WAL，不影响当前数据完整性，但反映了连接管理层面的不稳定性。`database.py` 的 `connect()` 函数需要确保在进程退出时正确关闭连接。此外存在一个 `recovery_20260531_174050/` 恢复快照目录，印证了 5 月 31 日曾发生过需要恢复的问题。 |

### 问题 6：空数据子目录

| 属性 | 内容 |
|---|---|
| **严重性** | `INFO` |
| **类别** | `cross-reference` |
| **证据** | `data/parquet/` 和 `data/snapshots/` 均为空目录 |
| **描述** | Phase 4 计划（`docs/09:75`）中包含 Parquet 导出（P1 优先级）任务。当前两个目录已创建但无内容，表明 Parquet 导出和快照功能尚未实施。目录存在但为空，说明设计已为这些功能预留了位置，但实现尚未完成。 |

### 问题 7：`validate-config` 缺少 `phase` 和 `table_type` 字段校验

| 属性 | 内容 |
|---|---|
| **严重性** | `INFO` |
| **类别** | `correctness` |
| **证据** | `validate.py:25-46` — schema registry 校验只检查重复表名、重复字段名、主键字段存在性和必需字段属性（name、dtype、description），不检查 `phase` 和 `table_type` 字段 |
| **描述** | 此校验缺口直接导致了问题 2（phase 格式不一致）未被自动检测。建议扩展 schema 校验以覆盖 `phase` 值的合法格式和一致性，以及 `table_type` 分类的合法性校验（如仅允许 `table` 和 `view` 两种类型）。 |

### 问题 8：部分模块统一 builder 通过外部脚本代理，耦合度较高

| 属性 | 内容 |
|---|---|
| **严重性** | `INFO` |
| **类别** | `maintainability` |
| **证据** | `modules.py:43-61` — `_load_phase3_script()` 函数；6 个 builder（`corporate_action`、`ownership_governance`、`sector_concept_context`、`index_market_context`、`cross_sectional`、`composite_state`）通过动态 `importlib` 加载外部 `scripts/` 目录中的独立脚本 |
| **描述** | 这种架构允许这些模块运行独立的完整 SQL，但引入了以下风险：(1) 统一 builder 对这些模块的可观测性不如内联实现（SQL 错误堆栈跨越进程边界），(2) 外部脚本与 builder 之间的接口契约（如 `build_insert_sql()` 函数签名）未在任何地方正式声明。当前 6 个脚本已在 `docs/11:105-116` 中记录，但接口契约缺少形式化定义。 |

---

## 3. 影响评估

| 问题编号 | 潜在影响 |
|---|---|
| 问题 1（.env Token） | 若工作空间被未经授权访问（如备份泄露、文件共享、快照导出），Token 可能被滥用，导致 Tushare API 额度耗尽或数据泄露。Token 长期不变增加泄露窗口期 |
| 问题 2（phase 格式不一致） | 基于 phase 字段做下游过滤或统计（如列出所有 P3 视图）的逻辑可能遗漏 `derived_financial_growth_full_v` 这一个视图，影响自动化管理脚本的完整性 |
| 问题 3（缺少 design 目录） | 不影响功能性，但降低工程标准化程度，新加入的开发者可能不知道设计文档的查找入口 |
| 问题 4（缺少日志） | 日批运行时无法追溯错误根因；当数据出现异常时，只能通过事后审计报告查找问题，缺少实时运行日志；违反 AGENTS.md 强制性要求 |
| 问题 5（过期 WAL） | 不影响当前数据完整性，DuckDB 已正确恢复。仅反映历史连接管理不稳定问题 |
| 问题 6（空数据目录） | 无功能影响，仅表明尚未完成 Phase 4 全部计划产出 |
| 问题 7（校验缺口） | 降低自动质量门禁的有效性；类似问题 2 的异常无法在 `validate-config` 阶段被拦截，可能在运行时才暴露 |
| 问题 8（外部脚本耦合） | 模块可观测性和调试效率降低；脚本接口变更可能在构建时而非校验阶段才暴露 |

---

## 4. 建议

### 问题 1 建议：轮换 Token 并加固安全配置

1. **立即**：在 Tushare 控制面板轮换当前 Token，并将新 Token 写入 `.env`
2. 确认 `.env` 文件仍在 `.gitignore` 中且**从未**提交到 Git（运行 `git log -- .env` 确认）
3. 生产环境部署时使用系统级环境变量（systemd `Environment=` 或 Docker secrets），移除 `.env` 文件依赖
4. 建立 Token 轮换策略（建议每季度轮换一次）

### 问题 2 建议：统一 Phase 标记格式

将 `config/schema_registry.json` 第 15051 行的 `"phase": "phase3"` 改为 `"phase": "P3"`，与其他 44 个 P3 条目保持一致。

### 问题 3 建议：建立 design 目录

创建 `design/` 目录，放入 `README.md` 说明设计文档入口位于 `docs/` 目录。或直接将 `docs/` 中与设计直接相关的文档（`02_项目整体设计.md`、`05_衍生变量Phase3总览.md`、`06_Phase3模块设计合订本.md`、`10_统一出口视图设计.md`）链接到 `design/` 目录。

### 问题 4 建议：建立统一日志模块

在 Phase 4 中建立 `src/stock_maintainance/logging.py` 统一日志模块，遵循 AGENTS.md 第 6 条规范：

```
{timestamp} | {LEVEL} | {module} | {message}
```

在以下关键操作点集成日志：
- 数据同步开始/结束、行数、耗时（`ingest.py`）
- 特征构建模块开始/结束、写入行数、异常（`features/build.py`、`features/modules.py`）
- 视图创建/刷新（`views.py`）
- 数据库连接/关闭、schema 对账（`database.py`）
- 质量审计执行（`audit.py`）

### 问题 5 建议：加固 DuckDB 连接管理

在 `database.py` 中增强 `connect()` 函数的正确关闭逻辑：
- 确保 `con.close()` 在 `finally` 块中执行
- 添加进程退出时的 atexit 钩子关闭连接
- 清理当前残留的两个过期 WAL 文件和 recovery 快照目录

### 问题 6 建议

Phase 4 计划中 Parquet 导出为 P1 优先级，按计划推进即可，不阻塞当前阶段。

### 问题 7 建议：扩展 validate-config 校验

在 `validate.py` 的 `validate_schema_registry()` 函数中增加：
- `phase` 字段值合法格式校验（仅允许 `P0`、`P1`、`P3`、`P4` 等 `P+数字` 格式）
- `table_type` 字段值合法性校验（仅允许 `table` 和 `view` 两种类型）

### 问题 8 建议：形式化外部脚本接口

为 6 个外部 builder 脚本定义明确的接口契约，至少在 `modules.py` 中添加文档字符串说明每个外部脚本必须暴露的函数签名（如 `build_insert_sql(start_date, end_date) -> str`）。

---

## 5. Phase 3 / Phase 4 执行评估

### 5.1 Phase 3 验收清单

| 检查项 | 状态 | 证据 |
|---|---|---|
| 19 个核心衍生变量物理表全部构建 | **通过** | 每表 15,295,776 行。`docs/05` 模块清单 + `docs/08` 级联验收 |
| 17 个统一 builder 全部实现 | **通过** | `modules.py:2263-2280` — `BUILDERS` 注册表中全部 17 个条目均绑定了实际 builder 函数，无 `placeholder_builder` 残留 |
| 19 个完整视图（`_full_v`）创建 | **通过** | `views.py` 包含所有 `_full_v` 视图定义 |
| 81 个 schema 注册条目 | **通过** | `config/schema_registry.json` 共 81 个注册条目，其中 45 个 P3、3 个 P4、33 个 P0/P1 |
| 2,757 个变量注册 | **通过** | `config/variables/` 中 543 个基础变量 + 2,214 个衍生变量 |
| 18 份模块审计报告 | **通过** | `reports/phase3_*_audit.md` 覆盖所有模块 |
| 无评分字段 | **通过** | `derived_composite_state` 92 列中无 `score` 字段（`test_phase3_composite_state.py:33-34` 测试验证） |
| 数据字典 Excel | **通过** | `outputs/variable_dictionary/global_variable_dictionary.xlsx` |
| 测试 | **通过** | 21 个测试用例，覆盖 schema 校验、Phase 3 关键模块、Phase 4 dry-run、统一出口视图 |
| 统一出口视图 `stock_features_*` | **通过**（P4 前置） | 三个视图均已实现（`views.py:717-888`）和注册（schema_registry.json P4 条目） |

### 5.2 Phase 4 P0 任务执行状态

| P0 任务（`docs/09:69-76`） | 状态 | 证据 |
|---|---|---|
| 1. docs-check / validate-config 修复 | **完成** | `docs/09:93-94` 声明完成 + `test_docs.py` 和 `test_schema_registry.py` 验证 |
| 2. 统一出口视图注册与正式设计 | **完成** | `schema_registry.json` 三个 P4 条目（119/151/185 列）+ `views.py:717-888` 实现 + `docs/10` 设计文档 |
| 3. 增量运行计划 | **完成初版** | `docs/11` 窗口规格文档 + `reports/phase4_module_window_spec.csv` + `reports/phase4_phase3_script_classification.csv` |
| 4. 核心模块迁移至统一 builder | **部分完成** | 6 个已迁移（`docs/11:105-116`）：corporate_action、ownership_governance、sector_concept_context、cross_sectional、composite_state、index_market_context。11 个原生实现 |
| 5. 财务 ASOF 映射优化 | **待启动** | 未在源码中发现相关优化实现 |
| 6. 长窗口/递归指标优化 | **部分完成** | `valuation_size` 从 2510 天降至 20 天，`financial_growth` 从 1300 天降至 260 天（`docs/11:205-209`） |
| 7. Parquet 导出 | **待启动** | `data/parquet/` 为空 |
| 8. 性能基准测试 | **待启动** | 未发现基准测试相关代码或报告文件 |

### 5.3 统一出口视图验证

| 视图 | 注册列数 | 实现位置 | 连接表数 | 无 score 字段 | 主键 |
|---|---|---|---|---|---|
| `stock_features_core` | 119 | `views.py:717-804` | 13 张 LEFT JOIN | **通过**（`test_phase4_feature_exports.py:31-33`） | `(ts_code, trade_date)` |
| `stock_features_plus` | 151 | `views.py:806-845` | core + 3 张 LEFT JOIN | **通过** | `(ts_code, trade_date)` |
| `stock_features_full` | 185 | `views.py:847-888` | plus + 1 张 LEFT JOIN | **通过** | `(ts_code, trade_date)` |

### 5.4 脚本迁移进度

| 分类 | 数量 | 日批状态 |
|---|---|---|
| `unified_builder_backend` | 6 | 已接入 `build-features` |
| `windowized_cache_script` | 4 | 支持 `--start-date/--end-date` 窗口刷新 |
| `external_full_sync` | 1 | **日批禁止**（需 `--confirm-full-refresh`） |
| `full_rebuild_only` | 6 | **日批禁止**（仅结构变更/全量重建） |
| `view_rebuild_only` | 9 | 可由 `create-views` 或模块 post-step 调用 |
| `audit_report` | 13 | 独立审计脚本，不进日批 |
| `registry_maintenance` | 10 | 注册表维护，不进日批 |
| `review_needed` | 7 | 待人工复核用途和边界 |

### 5.5 增量窗口降窗验证

| 模块 | 原读取窗口 | 新读取窗口 | 降窗方式 | 验证结果 |
|---|---|---|---|---|
| `valuation_size` | 2510 天 | 20 天 | 核心表仅维护近端字段；5 年分位由独立缓存回填 | `2026-05-26` 核心表 + 缓存各 5,504 行 |
| `financial_growth` | 1300 天 | 260 天 | 日频窗口降至 asof 同级；SQL 内部按股票构造报告序列 | `2026-05-26` 写入 5,504 行 |

### 5.6 数据质量抽样检查

| 检查维度 | 结果 |
|---|---|
| 日频覆盖交易日数 | 4,951 天（2006-01-04 至 2026-05-26），各表一致 |
| 日频覆盖股票数 | 5,809 只 |
| 主键重复 | 0（`docs/08` 审计验收确认所有模块） |
| PIT 违规 | 0（公司行为、持有人治理模块审计确认） |
| 空值比率 | PE_TTM 82.69% 非空、PB 98.57% 非空（估值审计报告） |
| 估值单位校准 | 市值/流通市值单位为元，自由流通市值单位为万元，已在字典中标明 |
| 质押分档 | 10/30/50 三档，边界检查通过 |
| 枚举非法值 | 0（composite_state 审计确认） |

---

## 6. 数据质量规则合规性（对照 Data Quality Check Rules.md）

| 规则类别 | 检查项 | 状态 |
|---|---|---|
| 基础数据画像 | 列空值比率计算 | `audit.py` 已实现（`quality_null_checks.csv`） |
| 基础数据画像 | 列名与 schema 一致性 | `validate.py` `validate_variable_schema_alignment` 已实现 |
| 基础数据画像 | 必需列存在性 | `validate.py` `REQUIRED_VARIABLE_KEYS` 检查已实现 |
| 数值范围合理性 | 硬上下边界校验 | `config/variables/derived_variables.json` 中定义了 `min_value: 0`，但**运行时未强制执行** |
| 数值范围合理性 | 衍生指标与源列数学一致性 | 测试中存在变量-schema 对齐检查，但**未对计算结果的数学正确性做抽样验证** |
| 唯一性检测 | 主键唯一性 | `audit.py` 的 duplicate check 已实现，覆盖 5 个核心表 |
| 唯一性检测 | 全字段重复检测 | 仅做主键重复检测，**未做全字段重复记录检测** |
| 格式语法有效性 | 日期格式一致性 | `transform.py` 的 `parse_tushare_date` 已处理多种日期格式 |
| 格式语法有效性 | 枚举列值域校验 | composite_state 审计报告中确认"枚举非法值 0"，但**未建立自动化的枚举值域校验框架** |
| 业务逻辑一致性 | 跨列逻辑依赖 | **未实现**（如 `end_date >= start_date` 此类跨列校验未建立） |
| 跨表引用完整性 | 外键关系验证 | 统一出口视图使用 `LEFT JOIN`，天然允许缺失值，但**未建立表间引用完整性校验** |
| 时效性检查 | 最新数据点不晚于阈值 | Phase 4 计划中包含每日质量报告目标，**尚未实现自动化** |
| 异常值检测 | 统计离群值识别 | 截面转换模块使用了 winsorization，但**未建立独立的离群值检测报告** |
| 数据溯源 | 数据点来源可追溯 | 变量注册表包含 `source_api`/`source_field` 溯源信息，**满足要求** |
| 数据溯源 | 敏感数据处理 | **不适用**（无 PII 数据） |

---

## 7. 最终裁定

**裁定：APPROVED WITH NOTES**

### 通过项（核心）

Phase 3 的核心目标已经全部实现：
- 19 个衍生变量物理表全部完成全量历史构建，行数高度一致（15,295,776）
- 17 个统一 builder 全部实现，BUILDERS 注册表无 placeholder 残留
- 完整视图层（`_full_v`）和辅助视图（timeline、coverage 等）就位
- 2,757 个变量完成注册和字典录入
- 18 份模块审计报告覆盖全部模块
- 21 个测试用例验证关键质量属性

Phase 4 的启动准备扎实：
- `validate-config` 和 `docs-check` 门禁已修复并可作为例行验收
- `stock_features_core/plus/full` 三个统一出口视图已实现并注册（119/151/185 列）
- 17 个模块的 read-context/write-window 规格已生成并文档化
- 56 个独立脚本已完成迁移分类
- 两个 P0 长窗口模块完成降窗优化
- `build-features --dry-run` 使用只读连接，兼容并行审计

### 需关注的待办事项

不阻塞 Phase 4 继续推进，但建议优先解决：

1. **轮换 API Token 并确认安全配置**（问题 1）
2. **修复 `derived_financial_growth_full_v` 的 phase 标记格式**（问题 2）
3. **建立统一日志模块**，满足 AGENTS.md 强制标准（问题 4）
4. **在 `validate.py` 中增加 `phase` 和 `table_type` 字段校验**，防止类似异常再次出现（问题 7）
5. **清理残留的过期 WAL 文件和 recovery 快照**，加固连接管理（问题 5）

### 下一阶段建议

Phase 4 的优先级路径建议为：
1. 完成问题 1-5 的修复（配置与合规类）
2. 实施财务 ASOF 增量优化（P0 任务 5）
3. 将已窗口化的 4 个缓存脚本纳入 `build-features` 统一编排
4. 实现 `phase4-audit` 统一命令，集成窗口计划 + 脚本分类 + 日批耗时 + 质量结果
5. 按 P1 → P2 顺序推进各模块性能优化
