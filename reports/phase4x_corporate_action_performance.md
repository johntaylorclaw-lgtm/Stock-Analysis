# Phase 4.x corporate_action 性能专项报告

- 生成日期：2026-06-07
- 测试窗口：2026-05-27 至 2026-06-05
- 目标模块：`corporate_action`

## 1. 结论

`corporate_action` 性能专项通过。

本次优化后，正式 CLI 路径下 `corporate_action` 单模块耗时由此前约 467 秒下降至约 53 秒；包含依赖 `financial_asof` 的总耗时约 60 秒。优化后结果与优化前参照快照字段级一致，无键缺失、无字段差异。

## 2. 优化前瓶颈

阶段计时显示：

| 阶段 | 优化前耗时 |
|---|---:|
| 主 SQL 插入 | 约 17 秒 |
| `share_float_update` | 约 311 秒 |
| commit | 约 4 秒 |

瓶颈集中在股本变动字段更新。旧逻辑使用 pandas 按股票遍历 `financial_share_float` 全历史事件，并用 Fenwick 树计算最近解禁、365 日累计和未来解禁窗口。该逻辑口径正确，但对日批窗口过重。

## 3. 本次改动

1. 将 `build_insert_sql` 拆为 `days_context` 和 `days`：
   - `days_context` 仅用于 20 日股本变化和滚动上下文；
   - 主 ASOF 和事件宽表只对 write-window 输出日执行。
2. 将 `update_share_float_fields` 改为 DuckDB SQL：
   - `sf_daily` 聚合 `financial_share_float` 到 `ts_code + float_date`；
   - `sf_latest` 使用 ASOF 获取最近解禁事件；
   - `sf_roll` 使用区间 join 计算 365 日事件数、解禁股份和比例；
   - `sf_future` 计算已公告未实施的 30/90 日未来解禁窗口。
3. 保留既有 NULL 口径：
   - 股票从未出现解禁事件时，365 日字段保持 NULL；
   - 股票有解禁历史但近 365 日无事件时，365 日字段为 0。

## 4. 性能结果

阶段计时：

| 阶段 | 优化后耗时 |
|---|---:|
| delete window | 0.26 秒 |
| 主 SQL 插入 | 约 17.5 秒 |
| SQL 股本变动更新 | 约 12.5 秒 |
| commit | 约 4.0 秒 |

正式 CLI 结果：

| 命令 | 模块 | 行数 | 耗时 |
|---|---|---:|---:|
| `stock-maintain build-features --module corporate_action --start-date 2026-05-27 --end-date 2026-06-05` | `financial_asof` | 44069 | 约 5 秒 |
| 同上 | `corporate_action` | 44069 | 约 53 秒 |

## 5. 一致性验证

对优化前参照快照 `audit_tmp_phase4x_corporate_action_ref` 与优化后 `derived_corporate_action` 做字段级比较：

| 项目 | 结果 |
|---|---|
| 键缺失/额外 | 0 |
| 差异字段 | 0 |
| 结论 | pass |

## 6. 验证命令

```bash
.venv-wsl/bin/pytest -q
.venv-wsl/bin/stock-maintain validate-config
.venv-wsl/bin/stock-maintain docs-check
```

结果：

| 验证项 | 结果 |
|---|---|
| pytest | 27 passed |
| validate-config | passed |
| docs-check | passed |

## 7. 后续建议

`corporate_action` 已不再是 Phase 4 的阻塞项。后续若继续优化，可考虑：

1. 为 `financial_share_float` 建立持久化日聚合表，进一步减少每次构建的临时聚合成本。
2. 将分红、回购、业绩预告、业绩快报、审计意见等事件也拆成可复用事件缓存。
3. 在 Phase 5 的 light/full 验证中加入 `corporate_action` 专项抽样，覆盖无事件、有历史事件、近 365 日事件、未来 30/90 日事件四类样本。
