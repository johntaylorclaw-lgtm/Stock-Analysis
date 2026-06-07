# Phase 3 财务成长表第二阶段执行记录

生成日期：2026-06-01

## 执行边界

第二阶段最初按“完整注册、分批落库”的方式执行：完整注册 `derived_financial_growth` 的二阶段字段，并按年度分片完成历史构建。用户随后指出全宽物理表占用空间过大，因此本阶段已调整为“核心物理表 + 完整视图”的混合结构。

## 当前结构

| 对象 | 类型 | 字段数 | 用途 |
|---|---|---:|---|
| `derived_financial_growth` | 物理表 | 255 | 高频使用的核心成长字段，支持日常增量加载和常规分析 |
| `derived_financial_growth_full_v` | 视图 | 1,196 | 二阶段完整字段设计，按需从基础表、财务 asof 表和质量表计算 |

混合结构的原因：

1. 完整宽表 1,196 列、15,295,776 行会显著放大 DuckDB 文件体积。
2. 成长字段中大量变量是低频核查字段，不适合全部长期物理化。
3. 核心字段物理化可以保留日增量效率；完整视图可以保留设计完整性和可追溯性。
4. 后续如果某些视图字段被频繁使用，可按字段组升级为物理表或物化子集。

## 字段注册

注册脚本：

```text
scripts/register_phase3_financial_growth_hybrid.py
```

辅助配置：

```text
scripts/financial_growth_hybrid_config.py
```

注册结果：

| 项目 | 数量 |
|---|---:|
| `derived_financial_growth` 物理字段 | 255 |
| `derived_financial_growth_full_v` 视图字段 | 1,196 |
| `derived_financial_growth` 变量注册 | 252 |

变量注册目前只注册核心物理表字段，避免同名变量在核心表和完整视图之间重复。完整视图字段通过 `config/schema_registry.json` 进入全局 Excel 数据字典。

## 落库过程

重置核心物理表：

```text
scripts/reset_phase3_financial_growth_core_table.py
```

核心成长字段年度全量构建：

```text
scripts/run_phase3_financial_growth_batch1.py
```

核心质量变化字段更新：

```text
scripts/run_phase3_financial_growth_quality_batch.py
```

完整视图创建：

```text
scripts/create_phase3_financial_growth_full_view.py
```

## 全历史结果

| 对象 | 行数/样本 | 股票数 | 日期范围 | 字段数 |
|---|---:|---:|---|---:|
| `derived_financial_growth` | 15,295,776 | 5,809 | 2006-01-04 至 2026-05-26 | 255 |
| `derived_financial_growth_full_v` | 近期样本 27,511 | 5,656 | 2026-05-20 至 2026-05-26 | 1,196 |

## 审计报告

| 报告 | 用途 |
|---|---|
| `reports/phase3_financial_growth_hybrid_audit.md` | 混合结构表级覆盖、核心字段覆盖、完整视图字段抽检 |
| `reports/phase3_financial_growth_batch1_audit.md` | 第一批金额增长、单季倒推、特殊值编码审计 |
| `reports/phase3_financial_growth_full_audit.md` | 历史全宽物理实现审计，保留作迁移前记录 |

## 运行机制

日常增量加载只写入 `derived_financial_growth` 核心物理表。完整字段不在日常任务中物理落库，需要时查询 `derived_financial_growth_full_v`。若未来某类完整视图字段成为稳定高频需求，应单独建立物化子表，而不是恢复 1,196 列单一宽表。

## 注意事项

1. DuckDB 删除宽表后，数据库文件不一定立即释放磁盘空间；如果需要真实回收空间，应安排单独的数据库压缩或重写任务。
2. 所有新文档和审计报告必须以 UTF-8 写入。
3. 所有比率和增长率字段继续使用 `docs/ratio_special_value_policy.md` 中的 `-9ABCDEF` 特殊值规则。
