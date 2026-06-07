# 基础变量覆盖核对

生成日期：2026-05-29

## 1. Excel 字典

基础变量 Excel 数据字典已生成：

`outputs/phase2/base_variable_dictionary.xlsx`

工作表：

1. `Summary`：变量数量、表覆盖和缺口摘要。
2. `Registered_Base`：当前已登记基础变量。
3. `Schema_Candidates`：根据已建 schema 推导出的基础变量候选。
4. `Coverage_Gaps`：尚未登记到 `base_variables.json` 的候选变量。
5. `Module_Summary`：按建议模块统计候选变量。

## 2. 覆盖结论

当前 `config/variables/base_variables.json` 仅登记 7 个基础变量，不能完整覆盖 Phase 2 已建成的数据域。

根据 `config/schema_registry.json` 推导：

- Schema 候选基础变量：341 个。
- 未登记候选变量：322 个。
- 当前登记表覆盖明显不足，尤其是行情、估值、指数、行业/概念、财务 raw、财务事件 raw 等已建表字段。

这不是数据缺失，而是“变量注册表尚未扩展”。底层数据和 schema 已经远多于当前变量 registry。

## 3. 建议处理

基础变量注册应分两步补齐：

1. 优先补齐 P0 高价值变量：
   - 股票主数据字段。
   - OHLCV 行情字段。
   - 日估值和市值字段。
   - 复权因子和涨跌停字段。
   - 指数基础、指数日线、指数成分字段。
   - 四大财务表标准字段。
2. 再补齐 P1 扩展变量：
   - 申万行业和概念字段。
   - 财务事件结构化视图字段。
   - 财务 raw 宽表中的长尾字段。

## 4. 当前处理原则

本次不直接把 300+ 个候选字段全部写回 `base_variables.json`，避免把未经人工确认的字段名、中文标签和单位固化进正式变量注册表。

Excel 中的 `Coverage_Gaps` 作为下一轮变量注册的审阅清单。审阅后再将确认字段批量写入 registry，比较稳。

补充：自动生成的基础变量注册草案位于 `outputs/phase2/base_variables_draft.json`。该草案不放入 `config/variables/`，避免被正式配置校验当作已生效变量。
