# Phase 3 行业概念与指数市场上下文模块设计

生成日期：2026-06-02

状态：已实施。行业概念核心表、指数市场核心表、增强行业成员、行业/概念/指数缓存、个股概念多周期缓存和完整视图已生成。

实施结果：

1. `derived_sw_industry_member_enhanced`：5,847 行，包含申万 L1/L2/L3 成员字段。
2. `derived_sector_daily_cache`：762,770 行，97 列。
3. `derived_concept_daily_cache`：4,265,393 行，89 列。
4. `derived_concept_stock_context_cache`：15,295,776 行，224 列。
5. `derived_sector_concept_context`：15,295,776 行，104 列。
6. `derived_sector_concept_context_full_v`：15,295,776 行，356 列。
7. `derived_index_daily_cache`：63,767 行，29 列。
8. `derived_index_membership_cache`：15,295,776 行，19 列。
9. `derived_index_market_context`：15,295,776 行，105 列。
10. `derived_index_market_context_full_v`：15,295,776 行，260 列。
11. 审计报告：`reports/phase3_sector_index_context_audit.md`。

工程边界记录：概念多口径 20 日字段已落入核心表；完整视图已扩展行业、概念和指数多周期。概念多周期列表不在视图中即时展开，而是通过 `derived_concept_stock_context_cache` 物理缓存承接 `ts_code + trade_date` 粒度的多概念聚合，避免查询时触发超大规模概念-股票-日期多对多计算。

## 1. 设计目标

本阶段优先完成两个上下文模块：

1. `sector_concept_context`：把申万行业、概念板块、行业/概念表现、行业内位置、概念暴露等事实变量映射到个股日频主干。
2. `index_market_context`：把指数成分、指数行情、指数相对收益、市场宽度、市场风格环境等事实变量映射到个股日频主干。

两个模块不生成主观评分，不做选股结论，只提供股票分析模型需要的事实型上下文变量。

## 2. 可用基础数据

| 来源表/视图 | 用途 | 当前口径 |
|---|---|---|
| `derived_daily_spine` | 个股日频主干、行情、市场、交易所 | 全 A 股日频基础 |
| `derived_return_momentum` | 个股收益和动量 | 后复权收益，用于连续收益比较 |
| `derived_volume_liquidity` | 个股成交额、成交量、换手 | 不复权成交事实 |
| `derived_valuation_size` | 市值、估值、规模 | 不复权事实 |
| `derived_capital_flow` | 个股资金流、两融、北向持仓 | 不复权交易事实 |
| `sw_industry_classify` | 申万行业分类 | SW2021 分类 |
| `sw_industry_member` | 申万行业成分历史 | 通过 `in_date/out_date` 做时点映射 |
| `concept_basic` | 概念基础信息 | Tushare 概念 |
| `concept_member` | 概念成分 | 概念成分，可能缺少精确历史进出日期 |
| `industry_daily` | 行业日频聚合视图 | 由成分股聚合 |
| `concept_daily` | 概念日频聚合视图 | 由成分股聚合 |
| `index_basic_info` | 指数基础信息 | SSE/SZSE/CSI/CNI/SW |
| `index_daily` | 指数日行情 | 默认指数池行情 |
| `index_weight` | 指数成分权重 | 月度维护 |
| `market_breadth_daily` | 市场宽度 | 全市场涨跌、涨跌停、成交统计 |

## 3. 周期体系

```text
完整滚动周期：2, 3, 5, 10, 20, 30, 60, 120, 250
核心落库锚点周期：5, 20, 60, 120
指数成分权重刷新周期：按月
概念成员口径：以可得成员表为准，若缺少进出日期则默认静态暴露
```

说明：

1. 行业、概念、指数收益使用后复权股票收益或指数自身收盘价收益，适合连续历史比较。
2. 成交额、换手率、资金流、市值等上下文使用不复权事实口径。
3. 核心物理表保留常用锚点周期，完整视图展开全部周期。
4. 概念变量容易变宽，不把每个概念单独展开为一列；采用“全量多概念聚合、领涨概念、领跌概念、热度概念、窄口径主题概念”的方式进入核心表和视图。

## 4. 模块结构

### 4.1 物理核心表

1. `derived_sector_concept_context`
   - 粒度：`ts_code + trade_date`
   - 定位：个股行业/概念归属、行业表现、概念表现、行业内位置的核心变量。
   - 预计字段数：110-140。

2. `derived_index_market_context`
   - 粒度：`ts_code + trade_date`
   - 定位：个股指数成员关系、指数相对收益、市场宽度和风格市场环境核心变量。
   - 预计字段数：80-110。

### 4.2 物理缓存表

1. `derived_sector_daily_cache`
   - 粒度：`industry_code + trade_date`
   - 保存行业日频表现、行业估值中位数、行业资金流、行业宽度、行业排名等聚合。

2. `derived_concept_daily_cache`
   - 粒度：`concept_id + trade_date`
   - 保存概念日频表现、概念成交热度、概念资金流、概念宽度等聚合。

3. `derived_concept_stock_context_cache`
   - 粒度：`ts_code + trade_date`
   - 保存个股所属多个概念的全量列表、领涨列表、领跌列表、活跃列表、窄口径领涨列表和统计聚合。
   - 周期：`2, 3, 5, 10, 20, 30, 60, 120, 250`。
   - 实现：用 `concept_member × derived_concept_daily_cache` 先聚合成物理缓存，再供完整视图连接，避免视图运行期重复展开。

4. `derived_index_daily_cache`
   - 粒度：`index_code + trade_date`
   - 保存指数收益、波动、成交额、市场指数相对强弱等。

5. `derived_index_membership_cache`
   - 粒度：`ts_code + trade_date`
   - 保存指数成分映射、权重和主要指数成员标记，避免完整视图反复按月度权重做 asof join。

### 4.3 完整视图

1. `derived_sector_concept_context_full_v`
   - 核心表 + 行业缓存 + 个股概念多周期缓存扩展周期。
   - 实际字段数：356。

2. `derived_index_market_context_full_v`
   - 核心表 + 指数缓存 + 市场宽度扩展周期。
   - 实际字段数：260。

## 5. `derived_sector_concept_context` 核心表设计

### 5.1 行业归属字段

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `ts_code` | 股票代码 | 主键 |
| `trade_date` | 交易日期 | 主键 |
| `sw_l1_code` | 申万一级行业代码 | `sw_industry_member.industry_code` asof join，或由基础库字段映射 |
| `sw_l1_name` | 申万一级行业名称 | `sw_industry_member.industry_name` |
| `sw_l2_code` | 申万二级行业代码 | 由 `sw_industry_classify` 层级关系和成员表映射；若基础库暂缺则先保留字段为空 |
| `sw_l2_name` | 申万二级行业名称 | 同上 |
| `has_sw_industry` | 是否有申万行业归属 | 行业成员是否匹配 |
| `industry_member_days` | 行业归属持续天数 | `trade_date - in_date` |
| `industry_member_is_current` | 是否当前行业成员 | `out_date IS NULL OR out_date > trade_date` |

说明：第一阶段同时设计申万一级和二级行业字段。若当前基础库只能稳定落一级行业，二级字段先注册并保留为空，实施前会审计 `sw_industry_classify/sw_industry_member` 是否足以还原二级归属；三级行业后续补齐。

### 5.2 行业表现字段

核心周期：`5, 20, 60, 120`。

| 字段模式 | 中文名 | 衍生逻辑 | 复权口径 |
|---|---|---|---|
| `industry_ret_N` | N日行业收益率 | 行业内成分股 `ret_N_hfq` 等权平均，或行业指数收益 | 后复权 |
| `industry_ret_excess_stock_N` | 个股相对行业N日超额收益 | `stock_ret_N_hfq - industry_ret_N` | 后复权 |
| `industry_ret_rank_all_N` | 行业N日收益全市场排名 | `rank(industry_ret_N) over trade_date` | 后复权 |
| `industry_ret_pct_all_N` | 行业N日收益全市场分位 | `percent_rank(industry_ret_N) over trade_date` | 后复权 |
| `industry_volume_amount_N` | N日行业成交额均值 | 行业内 `amount` 聚合 | 不复权 |
| `industry_amount_chg_N` | N日行业成交额变化率 | `industry_amount_ma_N / lag(industry_amount_ma_N,N)-1` | 不复权 |
| `industry_turnover_N` | N日行业平均换手 | 行业内 `turnover_rate` 等权平均 | 不复权 |
| `industry_up_ratio_N` | N日行业上涨比例 | 行业内上涨股票数/行业股票数 | 不复权事实 |
| `industry_limit_up_count_N` | N日行业涨停数累计 | 行业内涨停标记累计 | 不复权事实 |
| `industry_main_flow_sum_N` | N日行业主力净流入累计 | 行业内 `main_net_amount` 累计 | 不复权事实 |
| `industry_main_flow_to_mv_N` | N日行业主力净流入占市值 | `industry_main_flow_sum_N / industry_total_mv` | 不复权事实 |

### 5.3 行业内个股位置字段

核心周期：`20, 60`；完整视图扩展到全部周期。

| 字段模式 | 中文名 | 衍生逻辑 |
|---|---|---|
| `stock_ret_rank_industry_N` | 个股N日收益行业内排名 | 行业内按 `ret_N_hfq` 排名 |
| `stock_ret_pct_industry_N` | 个股N日收益行业内分位 | 行业内 `percent_rank(ret_N_hfq)` |
| `stock_amount_rank_industry_N` | 个股N日成交额行业内排名 | 行业内按 `amount_ma_N` 排名 |
| `stock_turnover_rank_industry_N` | 个股N日换手行业内排名 | 行业内按 `turnover_rate_ma_N` 排名 |
| `stock_mv_rank_industry` | 个股总市值行业内排名 | 行业内按 `total_mv` 排名 |
| `stock_pe_ttm_pct_industry` | 个股PE_TTM行业内分位 | 行业内按 `pe_ttm` 分位，负值和空值单独处理 |
| `stock_pb_pct_industry` | 个股PB行业内分位 | 行业内按 `pb` 分位，负值和空值单独处理 |
| `stock_main_flow_rank_industry_N` | 个股主力净流入行业内排名 | 行业内按 `main_flow_sum_N` 排名 |

### 5.4 概念暴露字段

一个股票可以同时从属于多个概念，设计上不能只保留一个“最强概念”。本工程采用以下事实口径：

1. 全量暴露：记录概念数量、概念ID列表、概念名称列表、概念成员覆盖状态。
2. 聚合表现：对股票所属全部概念计算平均、最大、最小、中位数、分位数量等。
3. 方向拆分：分别识别领涨概念和领跌概念，避免只关注上涨主题。
4. 规模约束：对概念宽泛度进行显式字段刻画，避免宽泛概念因成交额绝对值大而长期占据 Top。
5. 窄口径主题：额外识别成员数较少但表现突出的概念，保留“主题纯度”信息。

#### 5.4.1 概念排序口径

概念 Top N 不采用单一成交额排序。核心表保留 5 个概念，分别按不同事实口径输出：

| 排序口径 | 字段前缀 | 排序逻辑 | 解决的问题 |
|---|---|---|---|
| 领涨概念 | `concept_leading_*_N` | 所属概念中 `concept_ret_N` 从高到低 | 捕捉正向主题 |
| 领跌概念 | `concept_lagging_*_N` | 所属概念中 `concept_ret_N` 从低到高 | 捕捉负向主题和拖累来源 |
| 放量活跃概念 | `concept_active_*_N` | 所属概念中 `concept_amount_pct_all_N` 从高到低 | 捕捉交易热度 |
| 窄口径领涨概念 | `concept_narrow_leading_*_N` | 先筛选 `concept_stock_count` 处于合理区间，再按 `concept_ret_N` 排序 | 避免宽泛大概念垄断 |
| 综合展示列表 | `concept_ids_top_N/concept_names_top_N` | 默认使用领涨概念口径，另保留领跌和活跃列表 | 便于人工查看 |

宽泛度控制建议：

```text
concept_member_share = concept_stock_count / all_stock_count
窄口径概念候选：concept_stock_count >= 5 且 concept_member_share <= 0.10
过宽概念标记：concept_member_share > 0.10
过窄概念标记：concept_stock_count < 5
```

成交额排序不直接用绝对成交额，而使用全概念横截面分位：

```text
concept_amount_pct_all_N = percent_rank(concept_amount_ma_N) over trade_date
concept_active_rank_N = rank(concept_amount_pct_all_N desc)
```

这样不会让成分股很多的宽泛概念仅凭绝对成交额长期排在前面。收益排序也不只看领涨，同时输出领跌概念和概念收益分布。

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `concept_count` | 概念数量 | 个股匹配概念数 |
| `concept_ids_all` | 全部概念ID列表 | 所属概念ID按名称排序后 `string_agg` |
| `concept_names_all` | 全部概念名称列表 | 所属概念名称按名称排序后 `string_agg` |
| `concept_ids_top_20` | 20日领涨概念ID列表 | 所属概念按 `concept_ret_20 DESC` 取前5，`string_agg` |
| `concept_names_top_20` | 20日领涨概念名称列表 | 同上 |
| `concept_lagging_ids_20` | 20日领跌概念ID列表 | 所属概念按 `concept_ret_20 ASC` 取前5，`string_agg` |
| `concept_lagging_names_20` | 20日领跌概念名称列表 | 同上 |
| `concept_active_ids_20` | 20日活跃概念ID列表 | 所属概念按 `concept_amount_pct_all_20 DESC` 取前5 |
| `concept_active_names_20` | 20日活跃概念名称列表 | 同上 |
| `concept_narrow_leading_ids_20` | 20日窄口径领涨概念ID列表 | 窄口径候选中按 `concept_ret_20 DESC` 取前5 |
| `concept_narrow_leading_names_20` | 20日窄口径领涨概念名称列表 | 同上 |
| `concept_best_id_20` | 20日领涨概念ID | 个股所属概念中 `concept_ret_20` 最大 |
| `concept_best_name_20` | 20日领涨概念名称 | 同上 |
| `concept_best_ret_20` | 20日领涨概念收益 | `max(concept_ret_20)` |
| `concept_worst_id_20` | 20日领跌概念ID | 个股所属概念中 `concept_ret_20` 最小 |
| `concept_worst_name_20` | 20日领跌概念名称 | 同上 |
| `concept_worst_ret_20` | 20日领跌概念收益 | `min(concept_ret_20)` |
| `concept_avg_ret_20` | 所属概念20日平均收益 | 个股所属概念 `concept_ret_20` 平均 |
| `concept_median_ret_20` | 所属概念20日中位收益 | 个股所属概念 `concept_ret_20` 中位数 |
| `concept_max_ret_20` | 所属概念20日最大收益 | 个股所属概念 `concept_ret_20` 最大 |
| `concept_min_ret_20` | 所属概念20日最小收益 | 个股所属概念 `concept_ret_20` 最小 |
| `concept_ret_spread_20` | 所属概念20日收益跨度 | `concept_max_ret_20 - concept_min_ret_20` |
| `concept_positive_count_20` | 20日正收益概念数量 | 所属概念中 `concept_ret_20 > 0` 的数量 |
| `concept_negative_count_20` | 20日负收益概念数量 | 所属概念中 `concept_ret_20 < 0` 的数量 |
| `concept_avg_amount_20` | 所属概念20日平均成交额 | 个股所属概念成交额均值 |
| `concept_main_flow_sum_20` | 所属概念20日主力净流入均值 | 个股所属概念主力净流入均值 |
| `concept_hot_count_20` | 20日高热概念数量 | 所属概念中收益或成交额进入全市场概念前20%的数量 |
| `concept_broad_count` | 宽泛概念数量 | 所属概念中 `concept_member_share > 0.10` 的数量 |
| `concept_narrow_count` | 窄口径概念数量 | 所属概念中 `concept_stock_count >= 5 AND concept_member_share <= 0.10` 的数量 |

完整视图把 `20` 扩展为 `2,3,5,10,20,30,60,120,250`。

注意：`concept_hot_count_N` 是事实型“进入前分位数量”，不是综合评分；`concept_best_*` 更名语义上表示“领涨概念”，不表示该概念一定是股票上涨的因果原因。

### 5.5 质量字段

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `has_concept` | 是否有概念归属 | 概念成员是否匹配 |
| `sector_context_missing_reason` | 行业概念缺失原因 | `missing_industry/missing_concept/missing_price/null` |
| `updated_at` | 更新时间 | `CURRENT_TIMESTAMP` |

## 6. `derived_sector_daily_cache` 设计

| 字段模式 | 中文名 | 衍生逻辑 |
|---|---|---|
| `industry_code` | 行业代码 | 主键 |
| `trade_date` | 交易日期 | 主键 |
| `industry_name` | 行业名称 | `sw_industry_member.industry_name` |
| `industry_stock_count` | 行业股票数量 | 当日行业成分数 |
| `industry_ret_N` | N日行业收益率 | 成分股 `ret_N_hfq` 等权平均 |
| `industry_ret_rank_all_N` | 行业收益全行业排名 | 对行业收益排名 |
| `industry_ret_pct_all_N` | 行业收益全行业分位 | 对行业收益分位 |
| `industry_amount_ma_N` | N日行业成交额均值 | 成分股成交额汇总后滚动均值 |
| `industry_turnover_ma_N` | N日行业换手均值 | 成分股换手均值后滚动均值 |
| `industry_up_ratio_N` | N日行业上涨比例均值 | 行业内上涨比例滚动均值 |
| `industry_limit_up_count_N` | N日行业涨停数累计 | 行业内涨停数量滚动累计 |
| `industry_main_flow_sum_N` | N日行业主力净流入累计 | 行业内主力净流入滚动累计 |
| `industry_total_mv` | 行业总市值 | 成分股总市值汇总 |
| `updated_at` | 更新时间 | `CURRENT_TIMESTAMP` |

## 7. `derived_concept_daily_cache` 设计

| 字段模式 | 中文名 | 衍生逻辑 |
|---|---|---|
| `concept_id` | 概念ID | 主键 |
| `trade_date` | 交易日期 | 主键 |
| `concept_name` | 概念名称 | `concept_basic.concept_name` |
| `concept_stock_count` | 概念股票数量 | 概念成分数 |
| `concept_ret_N` | N日概念收益率 | 成分股 `ret_N_hfq` 等权平均 |
| `concept_ret_rank_all_N` | 概念收益全概念排名 | 对概念收益排名 |
| `concept_ret_pct_all_N` | 概念收益全概念分位 | 对概念收益分位 |
| `concept_amount_ma_N` | N日概念成交额均值 | 成分股成交额汇总滚动均值 |
| `concept_up_ratio_N` | N日概念上涨比例 | 概念内上涨比例滚动均值 |
| `concept_limit_up_count_N` | N日概念涨停数累计 | 概念内涨停数量滚动累计 |
| `concept_main_flow_sum_N` | N日概念主力净流入累计 | 概念内主力净流入累计 |
| `concept_hot_flag_N` | N日概念是否高热 | `concept_ret_pct_all_N >= 0.8 OR concept_amount_pct_all_N >= 0.8` |
| `concept_member_share` | 概念成员占全市场比例 | `concept_stock_count / market_stock_count` |
| `concept_broad_flag` | 是否宽泛概念 | `concept_member_share > 0.10` |
| `concept_narrow_flag` | 是否窄口径概念 | `concept_stock_count >= 5 AND concept_member_share <= 0.10` |
| `concept_amount_pct_all_N` | 概念成交额全概念分位 | `percent_rank(concept_amount_ma_N)` |
| `updated_at` | 更新时间 | `CURRENT_TIMESTAMP` |

## 8. `derived_index_market_context` 核心表设计

### 8.1 指数成员字段

默认核心指数池来自 `config/pipeline.json`：

```text
000001.SH 上证指数
000016.SH 上证50
000688.SH 科创50
000300.SH 沪深300
000906.SH 中证800
000903.SH 中证100
000985.CSI 中证全指
000905.SH 中证500
000852.SH 中证1000
399001.SZ 深证成指
399006.SZ 创业板指
399317.SZ 国证A指
399311.SZ 国证1000
399673.SZ 创业板50
```

核心表建议显式维护下列主要指数标记：

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `is_hs300_member` | 是否沪深300成分 | `index_weight.index_code='000300.SH'` asof |
| `hs300_weight` | 沪深300权重 | 最近月度 `index_weight.weight` |
| `is_zz500_member` | 是否中证500成分 | `000905.SH` asof |
| `zz500_weight` | 中证500权重 | 最近月度权重 |
| `is_zz1000_member` | 是否中证1000成分 | `000852.SH` asof |
| `zz1000_weight` | 中证1000权重 | 最近月度权重 |
| `is_sse50_member` | 是否上证50成分 | `000016.SH` asof |
| `sse50_weight` | 上证50权重 | 最近月度权重 |
| `is_star50_member` | 是否科创50成分 | `000688.SH` asof |
| `star50_weight` | 科创50权重 | 最近月度权重 |
| `is_chinext_member` | 是否创业板指成分 | `399006.SZ` asof |
| `chinext_weight` | 创业板指权重 | 最近月度权重 |
| `index_member_count` | 所属核心指数数量 | 上述成分标记合计 |
| `primary_index_code` | 主要指数归属 | 按优先级选择一个主指数 |
| `primary_index_name` | 主要指数名称 | 主指数名称 |

主指数优先级建议：

```text
上证50/科创50/创业板指 > 沪深300 > 中证500 > 中证1000 > 中证全指/国证A指
```

### 8.2 指数收益与相对收益字段

核心周期：`5, 20, 60, 120`。

| 字段模式 | 中文名 | 衍生逻辑 | 复权口径 |
|---|---|---|---|
| `hs300_ret_N` | 沪深300 N日收益 | `index_daily.close / lag(close,N) - 1` | 指数原始收盘 |
| `zz500_ret_N` | 中证500 N日收益 | 同上 | 指数原始收盘 |
| `zz1000_ret_N` | 中证1000 N日收益 | 同上 | 指数原始收盘 |
| `sse50_ret_N` | 上证50 N日收益 | 同上 | 指数原始收盘 |
| `stock_excess_hs300_N` | 个股相对沪深300超额收益 | `ret_N_hfq - hs300_ret_N` | 个股后复权 |
| `stock_excess_zz500_N` | 个股相对中证500超额收益 | `ret_N_hfq - zz500_ret_N` | 个股后复权 |
| `stock_excess_primary_index_N` | 个股相对主指数超额收益 | `ret_N_hfq - primary_index_ret_N` | 个股后复权 |
| `primary_index_ret_N` | 主指数N日收益 | 根据 `primary_index_code` 取指数收益 | 指数原始收盘 |

### 8.3 市场宽度字段

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `market_stock_count` | 全市场股票数量 | `market_breadth_daily.stock_count` |
| `market_up_ratio` | 全市场上涨比例 | `up_count / stock_count` |
| `market_down_ratio` | 全市场下跌比例 | `down_count / stock_count` |
| `market_limit_up_count` | 全市场涨停数量 | `market_breadth_daily.limit_up_count` |
| `market_limit_down_count` | 全市场跌停数量 | `market_breadth_daily.limit_down_count` |
| `market_limit_up_ratio` | 全市场涨停比例 | `limit_up_count / stock_count` |
| `market_limit_down_ratio` | 全市场跌停比例 | `limit_down_count / stock_count` |
| `market_amount` | 全市场成交额 | `market_breadth_daily.amount` |
| `market_amount_ma_N` | N日全市场成交额均值 | `avg(market_amount,N)` |
| `market_amount_chg_N` | N日市场成交额变化率 | `market_amount_ma_N / lag(market_amount_ma_N,N)-1` |
| `market_up_ratio_ma_N` | N日上涨比例均值 | `avg(market_up_ratio,N)` |

### 8.4 风格环境字段

风格环境仍是事实型相对表现，不做评分。

| 字段模式 | 中文名 | 衍生逻辑 |
|---|---|---|
| `large_vs_small_ret_N` | 大盘相对小盘N日收益差 | `hs300_ret_N - zz1000_ret_N` |
| `mid_vs_large_ret_N` | 中盘相对大盘N日收益差 | `zz500_ret_N - hs300_ret_N` |
| `growth_vs_broad_ret_N` | 创业板相对宽基N日收益差 | `chinext_ret_N - hs300_ret_N` |
| `star_vs_broad_ret_N` | 科创50相对宽基N日收益差 | `star50_ret_N - hs300_ret_N` |
| `market_breadth_chg_N` | 市场宽度N日变化 | `market_up_ratio - lag(market_up_ratio,N)` |

## 9. `derived_index_daily_cache` 设计

| 字段模式 | 中文名 | 衍生逻辑 |
|---|---|---|
| `index_code` | 指数代码 | 主键 |
| `trade_date` | 交易日期 | 主键 |
| `index_name` | 指数名称 | `index_basic_info.index_name` |
| `index_close` | 指数收盘价 | `index_daily.close` |
| `index_ret_N` | N日指数收益 | `close / lag(close,N) - 1` |
| `index_vol_N` | N日指数波动 | `stddev(log_ret_1,N) * sqrt(242)` |
| `index_amount_ma_N` | N日指数成交额均值 | `avg(index_daily.amount,N)` |
| `index_amount_chg_N` | N日指数成交额变化 | `amount_ma_N / lag(amount_ma_N,N)-1` |
| `updated_at` | 更新时间 | `CURRENT_TIMESTAMP` |

## 10. `derived_index_membership_cache` 设计

| 字段 | 中文名 | 衍生逻辑 |
|---|---|---|
| `ts_code` | 股票代码 | 主键 |
| `trade_date` | 交易日期 | 主键 |
| `is_hs300_member` | 是否沪深300成分 | `index_weight` 最近月度权重是否存在 |
| `hs300_weight` | 沪深300权重 | 最近月度权重 |
| `is_zz500_member` | 是否中证500成分 | 同上 |
| `zz500_weight` | 中证500权重 | 同上 |
| `is_zz1000_member` | 是否中证1000成分 | 同上 |
| `zz1000_weight` | 中证1000权重 | 同上 |
| `is_sse50_member` | 是否上证50成分 | 同上 |
| `sse50_weight` | 上证50权重 | 同上 |
| `is_star50_member` | 是否科创50成分 | 同上 |
| `star50_weight` | 科创50权重 | 同上 |
| `is_chinext_member` | 是否创业板指成分 | 同上 |
| `chinext_weight` | 创业板指权重 | 同上 |
| `index_member_count` | 所属核心指数数量 | 成分标记合计 |
| `primary_index_code` | 主要指数代码 | 按优先级选择 |
| `primary_index_name` | 主要指数名称 | 映射指数名称 |
| `updated_at` | 更新时间 | `CURRENT_TIMESTAMP` |

## 11. `derived_index_market_context` 核心表字段

核心表保留：

1. 主要指数成分标记和权重。
2. 核心指数 `5/20/60/120` 收益。
3. 个股相对沪深300、中证500、中证1000、主指数 `5/20/60/120` 超额收益。
4. 市场宽度当日值和 `5/20/60/120` 均值。
5. 大小盘、成长宽基、科创宽基等 `5/20/60/120` 相对收益事实。

完整视图扩展到 `2/3/5/10/20/30/60/120/250`。

## 12. 缺失与质量策略

| 场景 | 处理 |
|---|---|
| 股票无申万行业 | `has_sw_industry=false`，行业字段为空，缺失原因 `missing_industry` |
| 股票无概念 | `has_concept=false`，概念数量为0，概念表现为空，缺失原因 `missing_concept` |
| 概念缺少进出日期 | 默认静态暴露，使用 `concept_member` 现有成员关系 |
| 指数权重月度缺口 | 使用最近可得月度权重 asof，最长向前回看 90 天 |
| 指数行情缺口 | 指数收益为空，不用个股收益填补 |
| 北交所/退市股不在指数或行业覆盖 | 明确保留个股行，成员标记为 false，相关上下文字段为空 |
| 市场宽度缺失 | 市场字段为空，不影响个股行 |

## 13. 字段规模与核心列明细

### 13.1 `derived_sector_concept_context` 核心表列明细

预计 128 列左右。

```text
主键与行业归属：
ts_code, trade_date,
sw_l1_code, sw_l1_name, sw_l2_code, sw_l2_name,
has_sw_industry, industry_member_days, industry_member_is_current

行业核心周期字段，N in 5,20,60,120：
industry_ret_N,
industry_ret_excess_stock_N,
industry_ret_rank_all_N,
industry_ret_pct_all_N,
industry_amount_ma_N,
industry_amount_chg_N,
industry_turnover_ma_N,
industry_up_ratio_N,
industry_limit_up_count_N,
industry_main_flow_sum_N,
industry_main_flow_to_mv_N

行业内个股位置字段，N in 20,60：
stock_ret_rank_industry_N,
stock_ret_pct_industry_N,
stock_amount_rank_industry_N,
stock_turnover_rank_industry_N,
stock_main_flow_rank_industry_N

行业内估值与规模位置：
stock_mv_rank_industry,
stock_mv_pct_industry,
stock_pe_ttm_pct_industry,
stock_pb_pct_industry,
stock_ps_ttm_pct_industry

概念静态暴露：
concept_count,
concept_ids_all,
concept_names_all,
concept_broad_count,
concept_narrow_count

概念20日核心表现与列表：
concept_ids_top_20,
concept_names_top_20,
concept_lagging_ids_20,
concept_lagging_names_20,
concept_active_ids_20,
concept_active_names_20,
concept_narrow_leading_ids_20,
concept_narrow_leading_names_20,
concept_best_id_20,
concept_best_name_20,
concept_best_ret_20,
concept_worst_id_20,
concept_worst_name_20,
concept_worst_ret_20,
concept_avg_ret_20,
concept_median_ret_20,
concept_max_ret_20,
concept_min_ret_20,
concept_ret_spread_20,
concept_positive_count_20,
concept_negative_count_20,
concept_avg_amount_20,
concept_main_flow_sum_20,
concept_hot_count_20

质量与元数据：
has_concept,
sector_context_missing_reason,
updated_at
```

### 13.2 `derived_sector_concept_context_full_v` 完整视图列明细

预计 300-340 列。继承核心表全部字段，并扩展下列完整周期字段：

```text
N in 2,3,5,10,20,30,60,120,250：
industry_ret_N,
industry_ret_excess_stock_N,
industry_ret_rank_all_N,
industry_ret_pct_all_N,
industry_amount_ma_N,
industry_amount_chg_N,
industry_turnover_ma_N,
industry_up_ratio_N,
industry_limit_up_count_N,
industry_main_flow_sum_N,
industry_main_flow_to_mv_N,
stock_ret_rank_industry_N,
stock_ret_pct_industry_N,
stock_amount_rank_industry_N,
stock_turnover_rank_industry_N,
stock_main_flow_rank_industry_N,
concept_ids_top_N,
concept_names_top_N,
concept_lagging_ids_N,
concept_lagging_names_N,
concept_active_ids_N,
concept_active_names_N,
concept_narrow_leading_ids_N,
concept_narrow_leading_names_N,
concept_best_id_N,
concept_best_name_N,
concept_best_ret_N,
concept_worst_id_N,
concept_worst_name_N,
concept_worst_ret_N,
concept_avg_ret_N,
concept_median_ret_N,
concept_max_ret_N,
concept_min_ret_N,
concept_ret_spread_N,
concept_positive_count_N,
concept_negative_count_N,
concept_avg_amount_N,
concept_main_flow_sum_N,
concept_hot_count_N
```

### 13.3 `derived_sector_daily_cache` 缓存表列明细

预计 85-95 列。

```text
industry_code, trade_date, industry_name, industry_stock_count,
N in 2,3,5,10,20,30,60,120,250：
industry_ret_N,
industry_ret_rank_all_N,
industry_ret_pct_all_N,
industry_amount_ma_N,
industry_amount_pct_all_N,
industry_turnover_ma_N,
industry_up_ratio_N,
industry_limit_up_count_N,
industry_main_flow_sum_N,
industry_main_flow_to_mv_N,
industry_total_mv,
updated_at
```

### 13.4 `derived_concept_daily_cache` 缓存表列明细

预计 110-125 列。

```text
concept_id, trade_date, concept_name,
concept_stock_count,
concept_member_share,
concept_broad_flag,
concept_narrow_flag,
N in 2,3,5,10,20,30,60,120,250：
concept_ret_N,
concept_ret_rank_all_N,
concept_ret_pct_all_N,
concept_amount_ma_N,
concept_amount_pct_all_N,
concept_up_ratio_N,
concept_limit_up_count_N,
concept_main_flow_sum_N,
concept_hot_flag_N,
updated_at
```

### 13.5 `derived_index_market_context` 核心表列明细

预计 92 列左右。

```text
主键：
ts_code, trade_date

指数成分与权重：
is_hs300_member, hs300_weight,
is_zz500_member, zz500_weight,
is_zz1000_member, zz1000_weight,
is_sse50_member, sse50_weight,
is_star50_member, star50_weight,
is_chinext_member, chinext_weight,
index_member_count,
primary_index_code,
primary_index_name

核心指数收益，N in 5,20,60,120：
hs300_ret_N,
zz500_ret_N,
zz1000_ret_N,
sse50_ret_N,
star50_ret_N,
chinext_ret_N,
primary_index_ret_N

个股相对指数超额收益，N in 5,20,60,120：
stock_excess_hs300_N,
stock_excess_zz500_N,
stock_excess_zz1000_N,
stock_excess_primary_index_N

市场宽度：
market_stock_count,
market_up_ratio,
market_down_ratio,
market_limit_up_count,
market_limit_down_count,
market_limit_up_ratio,
market_limit_down_ratio,
market_amount

市场宽度核心周期，N in 5,20,60,120：
market_amount_ma_N,
market_amount_chg_N,
market_up_ratio_ma_N,
market_breadth_chg_N

风格环境核心周期，N in 5,20,60,120：
large_vs_small_ret_N,
mid_vs_large_ret_N,
growth_vs_broad_ret_N,
star_vs_broad_ret_N

质量与元数据：
has_index_weight,
has_market_breadth,
index_context_missing_reason,
updated_at
```

### 13.6 `derived_index_market_context_full_v` 完整视图列明细

预计 220-260 列。继承核心表全部字段，并扩展：

```text
完整周期 N in 2,3,5,10,20,30,60,120,250：
hs300_ret_N,
zz500_ret_N,
zz1000_ret_N,
sse50_ret_N,
star50_ret_N,
chinext_ret_N,
primary_index_ret_N,
stock_excess_hs300_N,
stock_excess_zz500_N,
stock_excess_zz1000_N,
stock_excess_primary_index_N,
market_amount_ma_N,
market_amount_chg_N,
market_up_ratio_ma_N,
market_breadth_chg_N,
large_vs_small_ret_N,
mid_vs_large_ret_N,
growth_vs_broad_ret_N,
star_vs_broad_ret_N

指数波动与成交，N in 5,20,60,120,250：
hs300_vol_N,
zz500_vol_N,
zz1000_vol_N,
sse50_vol_N,
star50_vol_N,
chinext_vol_N,
hs300_amount_ma_N,
zz500_amount_ma_N,
zz1000_amount_ma_N
```

### 13.7 `derived_index_daily_cache` 缓存表列明细

预计 35-45 列。

```text
index_code, trade_date, index_name, index_close,
N in 2,3,5,10,20,30,60,120,250：
index_ret_N,
N in 5,20,60,120,250：
index_vol_N,
index_amount_ma_N,
index_amount_chg_N,
updated_at
```

### 13.8 `derived_index_membership_cache` 缓存表列明细

预计 20-25 列。

```text
ts_code, trade_date,
is_hs300_member, hs300_weight,
is_zz500_member, zz500_weight,
is_zz1000_member, zz1000_weight,
is_sse50_member, sse50_weight,
is_star50_member, star50_weight,
is_chinext_member, chinext_weight,
index_member_count,
primary_index_code,
primary_index_name,
has_index_weight,
updated_at
```

## 14. 实施步骤

### 阶段 A：覆盖和口径实证

1. 检查 `sw_industry_member` 对全 A 股覆盖率。
2. 检查 `concept_member` 覆盖率和 `in_date/out_date` 可用性。
3. 检查默认指数池 `index_daily/index_weight` 覆盖日期和成分覆盖。
4. 检查 `market_breadth_daily` 日期覆盖。

### 阶段 B：注册与核心表

1. 注册 `derived_sector_daily_cache`、`derived_concept_daily_cache`、`derived_sector_concept_context`、`derived_sector_concept_context_full_v`。
2. 注册 `derived_index_daily_cache`、`derived_index_membership_cache`、`derived_index_market_context`、`derived_index_market_context_full_v`。
3. 实现核心物理表构建。

### 阶段 C：缓存和完整视图

1. 构建行业日频缓存。
2. 构建概念日频缓存。
3. 构建指数日频缓存。
4. 构建指数成分缓存。
5. 创建两个完整视图。

### 阶段 D：审计和字典

1. 生成 `reports/phase3_sector_index_context_audit.md`。
2. 审计覆盖率、字段非空率、指数成分 asof 质量、概念静态暴露比例。
3. 刷新全局 Excel 数据字典。
4. 跑 `validate-config`、`docs-check`、`create-views`、`pytest`。

## 15. 待确认边界问题

1. 已修正：申万一级、二级行业一起设计；三级行业后续补齐。
2. 已确认：概念成员第一阶段接受静态暴露处理。
3. 已修正：概念 Top N 不采用单一排序，改为领涨、领跌、活跃、窄口径领涨四套列表，核心表取前 5。
4. 已确认：第一阶段只对默认指数池中的核心指数做显式成分标记和权重字段，其他指数保留在缓存或视图中。
5. 已确认：指数权重 asof 最多向前回看 90 天。
6. 已确认：行业/概念收益第一阶段使用等权成分股收益，市值加权后续增强。
7. 已确认：北交所和退市股票保留行并显式标记缺失，不做外推补齐。
8. 待确认：按上述修正后，是否接受字段规模：
   - `derived_sector_concept_context` 核心表约 128 列。
   - `derived_sector_concept_context_full_v` 完整视图约 300-340 列。
   - `derived_index_market_context` 核心表约 92 列。
   - `derived_index_market_context_full_v` 完整视图约 220-260 列。
   - 四张缓存表合计约 250-290 列。
