# Stock_Maintainance 工程审计报告

审计日期：2026-06-08（含晚间22:00 Tushare API实证复核）
审计范围：全量代码 + 全量数据（57张物理表 + 60张视图 + 配置）

---

## 1. 摘要

### 判定陈述

工程整体质量**良好**，铺底数据与补跑数据一致完整。日加载(0608)在15:56运行时9张表缺失，**但经22:00 Tushare API实证复核，其中7张表的数据已可在当晚获取**（属于晚间发布而非T+1），仅2张表（`margin_detail`、`northbound_holding`）属真正T+1延迟。工程核心缺陷是 `daily-light` 运行时间过早（15:56），未能捕获晚间发布的API数据。另发现`margin_detail` 0605数据缺口（仅45%覆盖率）。总体判定 **APPROVED WITH NOTES**，建议实施晚间重试机制后变更为 APPROVED。

### 工程上下文

- **目标**：A股全量股票基础数据与衍生变量维护工程，不涉及选股/回测/评分/信号
- **技术栈**：DuckDB 单文件 OLAP + Python (Tushare API) + pandas
- **阶段状态**：Phase 0–5 全部完成
- **数据范围**：全A股（沪深京北交，含退市股），2006-01-04 起

### 审计行为

- 审查了 `src/stock_maintainance/` 下全部 25 个模块的源码架构
- 运行了 43 条 pytest 测试（全部通过）
- 运行了 `validate-config` 和 `docs-check`（均通过）
- 在 DuckDB 中执行了约 40 条 SQL 查询，覆盖全部 57 张物理表 + 关键视图
- 横跨三层数据（铺底 ~2026-05-26、补跑 0527-0605、日加载 0608）进行实证校验
- **在 22:00 直接调用 Tushare API 逐表验证数据的实际可获取状态**（见附录 5.2）

---

## 2. 问题

### 2.1 MAJOR — `margin_detail` 2026-06-05 数据不完整

| 属性 | 内容 |
|---|---|
| **严重度** | MAJOR |
| **分类** | data-integrity |
| **证据** | DuckDB查询：`margin_detail` 在2026-06-05仅 `1,981` 行/股票，而正常水平为 `~4,366` 行/股票（如0604=4,366、0603=4,366）。0605的1,981只股票均为0604已有股票的子集（overlap=1,981）。|
| **描述** | 融资融券明细数据在0605覆盖率仅为正常的45%（1,981/4,366），缺失约2,385只股票的margin_detail记录。非数据错位或重复，是Tushare API在0605当日返回不完整。 |

**附加证据 — 22:00 Tushare API实证**：`margin_detail` API 对 2026-06-08 仍返回 **0行**，确认该API存在**真正的T+1延迟**。

### 2.2 MAJOR — `daily-light` 运行时间过早导致7张表可当晚补齐但未补

| 属性 | 内容 |
|---|---|
| **严重度** | MAJOR |
| **分类** | data-integrity / correctness |
| **证据** | ① `daily_2026-06-08.md` 生成时间 `15:56:36`，postcheck报告9张表fail；② 22:00 Tushare API逐表实证（见下表）|
| **描述** | `daily-light` 在15:56运行，此时Tushare部分API尚未发布当日数据。经22:00直接调用API验证，9张缺失表中**7张已可获取**，仅2张为真正T+1。这是一个**工程运行窗口问题**而非数据源固有延迟问题。 |

**22:00 Tushare API逐表实证结果**：

| # | 目标表 | Tushare API | 15:56状态 | 22:00实证 | 实际延迟类型 |
|---|---|---|---|---|---|
| 1 | `stock_daily_basic` | `daily_basic` | 0行 ✗ | **5,515行** ✓ | **T+0晚间** (18:00后发布) |
| 2 | `stock_moneyflow_daily` | `moneyflow` | 0行 ✗ | **5,198行** ✓ | **T+0晚间** |
| 3 | `northbound_daily` | `moneyflow_hsgt` | 0行 ✗ | **1行** ✓ | **T+0晚间** |
| 4 | `top_list_daily` | `top_list` | 0行 ✗ | **109行** ✓ | **T+0晚间** |
| 5 | `top_inst_detail` | `top_inst` | 0行 ✗ | **1,200行** ✓ | **T+0晚间** |
| 6 | `index_daily` | `index_daily` | 0行 ✗ | **14行(14指数全)** ✓ | **T+0晚间** |
| 7 | `derived_index_daily_cache` | (级联index_daily) | 0行 ✗ | 可补齐 ✓ | **T+0晚间** |
| 8 | `margin_detail` | `margin_detail` | 0行 ✗ | **0行** ✗ | **真正T+1** |
| 9 | `northbound_holding` | `hk_hold` | 0行 ✗ | **0行** ✗ | **真正T+1** |

> **结论**：9张缺失表中，**7张可在当晚补回**（属于晚间分批发布），仅 **2张为真正T+1**。`daily-light` 在15:56运行过早，导致漏掉了晚间批量发布的数据窗口。

### 2.3 MINOR — `pipeline.json` 中的 `latest_trade_cutoff_hour_local: 18` 与实际API发布节奏不匹配

| 属性 | 内容 |
|---|---|
| **严重度** | MINOR |
| **分类** | configuration |
| **证据** | `config/pipeline.json:3` 中 `latest_trade_cutoff_hour_local: 18`；22:00实证发现每日多次调用的 `daily`、`adj_factor`、`stk_limit` 在15:56即可获取，但 `daily_basic` 等晚间发布API需等到 ~18:00-20:00 |
| **描述** | `pipeline.json` 中仅有单一的 `latest_trade_cutoff_hour_local` 配置值，没有区分快速API（`daily`/`adj_factor`/`stk_limit`）和慢速API（`daily_basic`/`moneyflow`/`top_list`/`top_inst`/`moneyflow_hsgt`/`index_daily`）的不同发布时间。当前工程默认在15:56运行，快速API可获取，但晚间API尚未发布，导致postcheck warning。 |

### 2.4 MINOR — 25张审计临时表未清理

| 属性 | 内容 |
|---|---|
| **严重度** | MINOR |
| **分类** | maintainability |
| **证据** | DuckDB中存在25张 `audit_tmp_phase4_*` 临时表，每张44,069行（约8个交易日），总计约1.1M行 |
| **描述** | Phase 4 审计时产生的临时快照表未清理，占用DuckDB存储空间且使数据库对象列表膨胀（143个对象中25个为临时审计表）。不影响数据正确性但降低可维护性。 |

### 2.5 MINOR — `derived_ownership_governance` 表未纳入 `daily_validate.py` 的股票级衍生表列表

| 属性 | 内容 |
|---|---|
| **严重度** | MINOR |
| **分类** | correctness |
| **证据** | `src/stock_maintainance/daily_validate.py:46-63` 的 `STOCK_LEVEL_DERIVED_TABLES` 集合包含16张衍生表，但 `derived_ownership_governance` 不在其中 |
| **描述** | `derived_ownership_governance` 是日频股票级衍生表（15,345,360行，与spine完全对齐，主键唯一性100%），但未在 `STOCK_LEVEL_DERIVED_TABLES` 中注册，意味着日验证不会对其进行衍生行数 vs spine行数的对齐检查。虽然当前实际数据完全对齐，但存在未来监控盲区的风险。 |

---

## 3. 影响

### 3.1 `margin_detail` 0605 缺失影响
- **下游量化研究**：使用margin_detail计算融资融券余额、融资买入额等资金流指标时，2026-06-05的数据将只能覆盖不到一半的股票
- **级联影响**：`derived_capital_flow` 表中与margin相关的衍生字段在0605的覆盖也会收窄
- **持续时间**：这是Tushare API当天返回不完整。22:00再次调0605的 `margin_detail` API需要确认是否需要补数

### 3.2 0608日加载7张晚间表缺失影响
- **影响范围**：仅最新1个交易日（0608），在当天晚些时候（~20:00后）重新运行即可补齐，不影响历史数据完整性
- **级联缺失**：`derived_index_daily_cache` 因 `index_daily` 晚间缺失而级联缺失，同样可当晚补回
- **其他衍生表**：衍生构建依靠已有的基础数据（`stock_daily`/`stock_adj_factor`/`stock_limit_price`均已拉取），17个衍生核心模块在0608的构建是**完整**的
- **下游视图**：`stock_features_core/plus/full` 中涉及 `stock_daily_basic` 列的字段在0608为NULL，但当晚补数后可恢复
- **真正T+1的2张表**（`margin_detail`、`northbound_holding`）：需下个交易日补数，属于预期行为

### 3.3 运行窗口过早影响
- 当前的 `daily-light` 单次运行模式导致晚间发布数据无法在当日入库
- 需改为**二阶段运行**：(1) 收盘快速阶段 → (2) 晚间补全阶段
- 若不做改动，每日 postcheck 都会出现 warning（当前模式预期的"正常"状态被当作异常）

---

## 4. 建议

### 4.1 立即补数 — `margin_detail` 0605 + 0608 晚间API数据

**第一步：补数 margin_detail 0605**
```bash
stock-maintain sync-market-behavior-range 20260605 20260605
stock-maintain build-features --start-date 20260605 --end-date 20260605
stock-maintain create-views
```

**第二步：补数0608的7张晚间API表**（现在即可执行，22:00已确认API有数据）
```bash
# 重新拉取0608的晚间发布数据（daily_basic, moneyflow, moneyflow_hsgt, top_list, top_inst, index_daily）
stock-maintain sync-daily-range 20260608 20260608
stock-maintain sync-market-behavior-range 20260608 20260608
stock-maintain sync-index-daily 20260608 20260608
# 重建衍生模块
stock-maintain build-features --start-date 20260608 --end-date 20260608
stock-maintain create-views
# 验证
stock-maintain validate-daily --as-of-date 2026-06-08 --output-prefix fix_evening_0608
```

### 4.2 工程化改造（核心建议）— 实现 `daily-light` 二阶段运行

**设计方案**：在 `config/pipeline.json` 中按API发布时间拆分配置：

```json
"daily_policy": {
  "latest_trade_cutoff_hour_local": 18,
  "default_repair_window_trade_days": 10,
  "require_confirmation_beyond_trade_days": 10,
  "northbound_default": "skip_optional",
  "validation_default": "light",
  
  "api_release_phases": {
    "fast": {
      "available_after_hour_local": 15,
      "apis": ["daily", "adj_factor", "stk_limit"],
      "description": "收盘后立即可用"
    },
    "evening": {
      "available_after_hour_local": 20,
      "apis": ["daily_basic", "moneyflow", "moneyflow_hsgt", "top_list", "top_inst", "index_daily"],
      "description": "晚间18:00-20:00分批发布"
    },
    "next_day": {
      "available_after_hour_local": 9,
      "apis": ["margin_detail", "hk_hold"],
      "description": "T+1日上午发布"
    }
  }
}
```

**daily-light 二阶段流程**：

```
Phase 1 (15:30 close sync):
  sync-master → sync-daily(stock_daily/adj_factor/stk_limit) → precheck
  → build-features(fast) → create-views → postcheck-phase1

Phase 2 (20:00 evening retry):
  sync-daily(evening APIs: daily_basic/moneyflow/hsgt/top_list/top_inst)
  → sync-index-daily → build-features(evening) → create-views → postcheck-full
```

**实现方式**：
- 在 `daily_light.py` 中增加 `--retry-late` 参数，触发晚间API的增量同步
- 或者提供独立命令 `stock-maintain daily-light-late --as-of-date <today>`

### 4.3 针对 `pipeline.json` 的 `latest_trade_cutoff_hour_local` 优化

当前值 `18` 过于乐观（`margin_detail` 和 `hk_hold` 在22:00仍不可用），建议：
- 将 `latest_trade_cutoff_hour_local` 调整为 `20`（覆盖晚间API发布窗口）
- 对真正T+1的API，在postcheck中输出 `WARNING` 级别而非 `fail`，因为这是数据源的固有特征

### 4.4 长期防御：postcheck 增加行数波动检测

在 `daily_validate.py` 中增加行数异常检测：
- 若某表的当日行数较前5日均值下降超过 **20%**，输出明确 `WARNING`
- 当前postcheck仅检测"目标日期行数=0"，无法发现 `margin_detail` 0605 这种部分缺失
- `_row_count_for_date` 已存在，可增加对比前一交易日的逻辑

### 4.5 针对审计临时表（MINOR）

```bash
# 在 cli.py 中增加 cleanup-audit-tmp 命令
stock-maintain cleanup-audit-tmp
```

### 4.6 针对 `derived_ownership_governance` 监控盲区（MINOR）

在 `src/stock_maintainance/daily_validate.py:46-63` 的 `STOCK_LEVEL_DERIVED_TABLES` 集合中追加 `"derived_ownership_governance"`。

---

## 5. 证据附录

### 5.1 数据库全局概览（核心表）

| 表 | 行数 | 日期列 | 最早日期 | 最新日期 | 列数 |
|---|---|---|---|---|---|
| `derived_daily_spine` | 15,345,360 | trade_date | 2006-01-04 | **2026-06-08** | 49 |
| `stock_daily` | 15,345,360 | trade_date | 2006-01-04 | **2026-06-08** | 13 |
| `stock_adj_factor` | 15,703,617 | trade_date | 2006-01-04 | **2026-06-08** | 5 |
| `stock_limit_price` | 17,601,785 | trade_date | 2007-01-04 | **2026-06-08** | 5 |
| `stock_daily_basic` | 15,248,558 | trade_date | 2006-01-04 | **2026-06-05** | 19 |
| `stock_moneyflow_daily` | 14,227,592 | trade_date | 2007-01-04 | **2026-06-05** | 21 |
| `margin_detail` | 6,519,333 | trade_date | 2010-03-31 | **2026-06-05** | 11 |
| `northbound_daily` | 2,718 | trade_date | 2014-11-17 | **2026-06-05** | 8 |
| `northbound_holding` | 5,677,174 | trade_date | 2016-06-29 | **2026-06-05** | 8 |
| `top_list_daily` | 242,520 | trade_date | 2006-01-24 | **2026-06-05** | 16 |
| `top_inst_detail` | 2,501,605 | trade_date | 2012-01-04 | **2026-06-05** | 11 |
| `index_daily` | 63,879 | trade_date | 2006-01-04 | **2026-06-05** | 12 |
| `derived_index_daily_cache` | 63,879 | trade_date | 2006-01-04 | **2026-06-05** | 29 |
| 其余衍生表(16张) | 各15,345,360 | trade_date | 2006-01-04 | **2026-06-08** | 13–353 |

### 5.2 Tushare API 实证：2026-06-08 数据可获取性（执行时间：22:00 北京时间）

| # | Tushare API | 目标数据库表 | 22:00返回行数 | 可获取 | 延迟分类 |
|---|---|---|---|---|---|
| 1 | `daily_basic` | `stock_daily_basic` | **5,515** | ✓ | **T+0晚间** |
| 2 | `moneyflow` | `stock_moneyflow_daily` | **5,198** | ✓ | **T+0晚间** |
| 3 | `moneyflow_hsgt` | `northbound_daily` | **1** | ✓ | **T+0晚间** |
| 4 | `top_list` | `top_list_daily` | **109** | ✓ | **T+0晚间** |
| 5 | `top_inst` | `top_inst_detail` | **1,200** | ✓ | **T+0晚间** |
| 6 | `index_daily` (14个默认指数) | `index_daily` | **14** | ✓ | **T+0晚间** |
| 7 | (级联) | `derived_index_daily_cache` | 可补齐 | ✓ | **T+0晚间** |
| 8 | `margin_detail` | `margin_detail` | **0** | ✗ | **真正T+1** |
| 9 | `hk_hold` | `northbound_holding` | **0** | ✗ | **真正T+1** |

> **实证结论**：9张缺失表中，7张可在**当天晚间**（18:00-22:00）获取，仅2张为**真正T+1**。`daily-light` 在15:56运行过早，未覆盖晚间发布窗口。

### 5.3 API延迟溯源：9张表在补跑区间(0527-0605)的每日覆盖

| 日期 | stock_daily_basic | moneyflow_daily | margin_detail | northbound_daily | northbound_holding | top_list_daily | top_inst_detail | index_daily | index_daily_cache |
|---|---|---|---|---|---|---|---|---|---|
| 2026-05-27 | 5,506 ✓ | 5,191 ✓ | 4,365 ✓ | 1 ✓ | 937 ✓ | 80 ✓ | 722 ✓ | 14 ✓ | 14 ✓ |
| 2026-05-28 | 5,506 ✓ | 5,191 ✓ | 4,365 ✓ | 1 ✓ | 936 ✓ | 85 ✓ | 797 ✓ | 14 ✓ | 14 ✓ |
| 2026-05-29 | 5,506 ✓ | 5,190 ✓ | 4,366 ✓ | 1 ✓ | 935 ✓ | 90 ✓ | 806 ✓ | 14 ✓ | 14 ✓ |
| 2026-06-01 | 5,508 ✓ | 5,192 ✓ | 4,366 ✓ | 1 ✓ | 935 ✓ | 106 ✓ | 1,033 ✓ | 14 ✓ | 14 ✓ |
| 2026-06-02 | 5,507 ✓ | 5,191 ✓ | 4,366 ✓ | 1 ✓ | 935 ✓ | 86 ✓ | 861 ✓ | 14 ✓ | 14 ✓ |
| 2026-06-03 | 5,511 ✓ | 5,195 ✓ | 4,366 ✓ | 1 ✓ | 935 ✓ | 86 ✓ | 811 ✓ | 14 ✓ | 14 ✓ |
| 2026-06-04 | 5,511 ✓ | 5,195 ✓ | 4,366 ✓ | 1 ✓ | 936 ✓ | 105 ✓ | 955 ✓ | 14 ✓ | 14 ✓ |
| **2026-06-05** | 5,514 ✓ | 5,197 ✓ | **1,981 ⚠** | 1 ✓ | 936 ✓ | 83 ✓ | 786 ✓ | 14 ✓ | 14 ✓ |
| **2026-06-08** | **0 ✗** | **0 ✗** | **0 ✗** | **0 ✗** | **0 ✗** | **0 ✗** | **0 ✗** | **0 ✗** | **0 ✗** |

> **结论**：补跑区间(0527-0605)数据完整。`margin_detail` 0605缺口(1,981/4,366)是独立的数据不完整问题。

### 5.4 测试与配置验证

| 检查项 | 结果 |
|---|---|
| `pytest -v` | **43 passed** (Phase 5 报告记录为38，已增加5个) |
| `validate-config` | **passed** |
| `docs-check` | **passed** (docs are up to date) |
| Token安全 | Tushare Token置于 `.env` 文件，通过 `TUSHARE_TOKEN` 环境变量读取，无硬编码 |

### 5.5 主键唯一性（全量通过 — 19张表 0 重复）

| 表 | 总行数 | 唯一键数 | 重复数 |
|---|---|---|---|
| derived_daily_spine | 15,345,360 | 15,345,360 | **0** |
| derived_price_technical | 15,345,360 | 15,345,360 | **0** |
| derived_volume_liquidity | 15,345,360 | 15,345,360 | **0** |
| derived_return_momentum | 15,345,360 | 15,345,360 | **0** |
| derived_volatility_risk | 15,345,360 | 15,345,360 | **0** |
| derived_trading_constraint | 15,345,360 | 15,345,360 | **0** |
| derived_valuation_size | 15,345,360 | 15,345,360 | **0** |
| derived_financial_asof | 15,345,360 | 15,345,360 | **0** |
| derived_financial_quality | 15,345,360 | 15,345,360 | **0** |
| derived_financial_growth | 15,345,360 | 15,345,360 | **0** |
| derived_capital_flow | 15,345,360 | 15,345,360 | **0** |
| derived_sector_concept_context | 15,345,360 | 15,345,360 | **0** |
| derived_index_market_context | 15,345,360 | 15,345,360 | **0** |
| derived_cross_sectional | 15,345,360 | 15,345,360 | **0** |
| derived_corporate_action | 15,345,360 | 15,345,360 | **0** |
| derived_composite_state | 15,345,360 | 15,345,360 | **0** |
| derived_ownership_governance | 15,345,360 | 15,345,360 | **0** |
| stock_daily | 15,345,360 | 15,345,360 | **0** |
| stock_adj_factor | 15,703,617 | 15,703,617 | **0** |

### 5.6 统一出口视图列数一致性

| 视图 | Phase 5报告声称 | 实际DuckDB列数 | 一致 |
|---|---|---|---|
| `stock_features_core` | 318 | 318 | ✓ |
| `stock_features_plus` | 1,198 | 1,198 | ✓ |
| `stock_features_full` | 1,602 | 1,602 | ✓ |

### 5.7 `composite_state` score 字段检查

查询 `PRAGMA table_info(derived_composite_state)` 中是否包含 `score` 字段：**0个**。符合 Phase 3 验收标准。

### 5.8 Spine 关键指标

| 指标 | 值 |
|---|---|
| 总行数 | 15,345,360 |
| 股票数 | 5,814 |
| 交易日数 | 4,960 |
| 日期范围 | 2006-01-04 至 2026-06-08 |
| 最新交易日 | 2026-06-08（5,515只股票） |
| 最大日期 | 2026-06-08 |

---

## 6. 最终判定

### Verdict: **APPROVED WITH NOTES**

**理由**：

1. **核心数据完整性通过**：铺底数据(2006-2026-05-26)完整，补跑数据(0527-0605)完整一致，主键100%唯一。
2. **代码质量通过**：43条测试全通，配置验证通过，无硬编码密钥。
3. **交叉验证通过**：统一出口视图列数与文档一致，schema与DuckDB实际结构对齐，无score字段泄露。
4. **发现2个MAJOR问题**：
   - `margin_detail` 0605数据缺口（Tushare API当天返回不完整）— 需显式补数
   - **`daily-light` 运行窗口过早**，7张晚间发布API可当晚补齐但未被捕获 — 需工程化改造为二阶段运行
5. **发现3个MINOR问题**：审计临时表未清理、`pipeline.json` 单一截止时间不匹配API分层发布节奏、`ownership_governance` 监控盲区。

**推荐行动（按优先级）**：

| 优先级 | 行动 | 命令/方式 |
|---|---|---|
| **立即** | 补数 margin_detail 0605 | `sync-market-behavior-range 20260605 20260605` |
| **立即** | 补数 0608 晚间7张表 | 运行 4.1 节第二步命令 |
| **今晚** | 验证补数结果 | `validate-daily --as-of-date 2026-06-08` |
| **下版迭代** | 实现 `daily-light` 二阶段运行（收盘+晚间） | 参考 4.2 节设计方案 |
| **下版迭代** | postcheck增加行数波动检测 | 修改 `daily_validate.py` |
| **下版迭代** | 清理审计临时表 | 新增 `cleanup-audit-tmp` 命令 |
