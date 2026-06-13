# Fable 审计修复报告 Batch 21

生成时间：2026-06-12

## 修复范围

本批次处理 Fable 审计中的 L15：统一出口视图的评分字段过滤规则使用 `"score" in column` 子串匹配，可能误删合法的 `*_zscore_*` 字段；同时基础 enriched 列未复用该过滤规则。

## 已修复问题

| 审计项 | 判断 | 修复结论 |
|---|---|---|
| L15 `score` 子串过滤过宽 | 客观 | 新增 `_is_score_field`，仅过滤 `score` 或以 `_score` 结尾的字段 |
| L15 base/enriched 列未统一过滤 | 客观 | `stock_base_daily_enriched` 进入 `stock_features_full` 时也使用同一评分字段过滤规则 |

## 验证

| 命令 | 结果 |
|---|---|
| `.venv-wsl/bin/pytest -q tests/test_views_compat.py` | 3 passed |
| `.venv-wsl/bin/stock-maintain create-views` | created analytical views |
| `.venv-wsl/bin/pytest -q` | 90 passed |

## 说明

该修复保留事实型标准化字段如 `north_money_zscore_20`，同时继续排除评价型 `*_score` 字段，符合本工程“事实层而非评分层”的原则。
