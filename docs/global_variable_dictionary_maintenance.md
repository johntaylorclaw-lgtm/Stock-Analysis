# 全局变量数据字典维护说明

生成日期：2026-05-31

## 1. 文件位置

全局变量数据字典：
`outputs/variable_dictionary/global_variable_dictionary.xlsx`

该文件是后续理解项目全局变量设计的主要依据。它按物理表拆分 sheet，覆盖基础变量表和衍生变量表。

## 2. 工作簿结构

| Sheet | 说明 |
|---|---|
| `Summary` | 全局概览，包含基础表、衍生表、字段数和注册变量数 |
| `Summary` 表目录 | 从 `Sheet名` 单元格直接跳转到每张物理表 sheet |
| `Table_Index` | sheet 名、中文物理表名、英文表名、主键和字段数量的索引 |
| 每个物理表一个 sheet | 字段级数据字典 |

由于 Excel sheet 名最多 31 个字符，较长表名会被缩写。面向阅读和审阅时以 `物理表名` 的中文描述为主；真实英文表名以 `英文表名` 列为准。

## 3. 字段级信息

每张表 sheet 均采用中文说明优先的列顺序。前置核心列为：

1. `字段名`
2. `中文名`
3. `字段含义`
4. `衍生逻辑`
5. `复权口径`
6. `用途`
7. `物理表名`
8. `英文表名`

基础变量表的 `中文名` 优先来自变量注册文件，其次来自项目维护的 Tushare 常用字段中文映射。  
衍生变量表的 `衍生逻辑` 应尽量维护为公式形式，例如：

```text
close_hfq = stock_daily.close * stock_adj_factor.adj_factor
log_ret_1_hfq = ln(close_hfq / lag(close_hfq, 1))
```

如果当前变量注册尚未提供精确公式，生成脚本会用依赖字段生成占位形式 `字段名 = f(依赖字段)`，后续扩展变量时必须逐步补齐为可审阅公式。

## 4. 维护机制

后续新增、删除或修改变量时，应同步更新：

1. `config/schema_registry.json`
2. `config/variables/*.json`
3. 对应构建器或视图
4. `scripts/build_global_variable_dictionary.mjs` 中必要的中文名或公式映射
5. 重新生成 `outputs/variable_dictionary/global_variable_dictionary.xlsx`

生成命令：

```powershell
$env:NODE_PATH='C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' scripts\build_global_variable_dictionary.mjs
```

如果主 Excel 文件正在被打开占用，脚本会自动生成带时间戳的副本，避免生成失败。

## 5. 当前注意事项

1. `adj_factor`、`up_limit`、`down_limit` 在基础变量注册表中已有同名变量；`derived_daily_spine` 中作为镜像字段落库，但未重复注册为新变量。
2. `latest_adj_factor_asof` 和 `*_qfq` 为当前数据库尺度展示口径，不是严格点时安全口径。
3. 当前 Phase 3 除 `derived_daily_spine` 外，其余衍生表仍是第一批代表变量，字段数量后续会继续扩展。
