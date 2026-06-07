# Phase 3 持有人治理模块执行记录

生成日期：2026-06-05

## 1. 完成范围

已完成 `ownership_governance` 第一阶段全量历史构建，覆盖：

1. 股权质押统计：`financial_pledge_stat`
2. 股权质押明细：`financial_pledge_detail`
3. 股东户数：`financial_holder_number`
4. 十大股东：`financial_top10_holders`
5. 十大流通股东：`financial_top10_float_holders`

暂不纳入实控人、董监高、管理层数据；该部分待基础库稳定后进入后续扩展。

## 2. 产出对象

| 对象 | 类型 | 列数 | 行数/状态 |
|---|---|---:|---:|
| `derived_ownership_governance` | 物理表 | 63 | 15,295,776 |
| `derived_ownership_governance_full_v` | 视图 | 98 | 15,295,776 |
| `ownership_holder_concentration_v` | 视图 | 10 | 477,251 |
| `ownership_governance_event_timeline_v` | 视图 | 12 | 7,156,042 |

## 3. 核心口径

1. `financial_pledge_stat` 无公告日，使用 `end_date` 作为 as-of 有效日。
2. 股东户数、十大股东、十大流通股东使用 `ann_date <= trade_date` 做 point-in-time 映射。
3. 高质押事实标记采用 10/30/50 三档，不生成主观评分。
4. Tushare 比例字段保留来源口径；HHI 内部按百分数除以 100 后计算。
5. 股东类型归一化和股东名单变动在完整视图层维护，不进入核心物理表。
6. 持有人分散度代理同时提供总股本和自由流通股本口径。

## 4. 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/register_phase3_ownership_governance.py` | 注册表结构和变量字典 |
| `scripts/reset_phase3_ownership_governance_table.py` | 重建核心物理表 |
| `scripts/build_phase3_ownership_governance_core.py` | 分年构建核心日频快照 |
| `scripts/create_phase3_ownership_governance_views.py` | 创建完整视图、事件时间线和集中度视图 |
| `scripts/generate_phase3_ownership_governance_audit.py` | 生成审计报告 |

## 5. 验收

审计报告：`reports/phase3_ownership_governance_audit.md`

验收结果：

| 检查项 | 结果 |
|---|---:|
| 主键重复组数 | 0 |
| 股东户数公告日晚于交易日行数 | 0 |
| 十大股东公告日晚于交易日行数 | 0 |
| 质押统计有效日晚于交易日行数 | 0 |
| 质押阈值三档非单调行数 | 0 |
| 名单变动字段非0/1行数 | 0 |

测试结果：`python -m pytest`，8 项通过。

新增 ownership 专项测试覆盖：

1. `derived_ownership_governance`、`derived_ownership_governance_full_v`、`ownership_governance_event_timeline_v`、`ownership_holder_concentration_v` 的注册列数。
2. 高质押阈值 10/30/50 三档字段存在，旧的单一 `high_pledge_ratio_flag` 不再进入核心表。
3. 股东户数分散度同时保留总股本和自由流通股本两种口径。
4. ownership 模块变量注册与 schema registry 对齐。
5. 名单变动字段口径为“是否变动”而不是“变动数量”。

## 6. 数据字典

已刷新全局 Excel 数据字典：

`outputs/variable_dictionary/global_variable_dictionary.xlsx`

由于 Excel sheet 名长度限制，ownership 相关 sheet 名被自动截短：

| 物理/视图对象 | Excel sheet |
|---|---|
| `derived_ownership_governance` | `d_ownership_governance` |
| `derived_ownership_governance_full_v` | `d_ownership_governance_full_v` |
| `ownership_governance_event_timeline_v` | `ownership_governance_event_time` |
| `ownership_holder_concentration_v` | `ownership_holder_concentration_` |
