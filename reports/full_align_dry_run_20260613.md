# Daily-Full 运行报告

生成时间：2026-06-13T10:09:03
截至日期：`2026-06-13`
运行模式：`dry-run`
结果：`warning`

## 全量窗口

- 重拉交易日：2026-06-12
- 重拉交易日数：1

## 步骤

| 步骤 | 状态 | 说明 |
|---|---|---|
| `sync-master` | planned | refresh stock_basic/company/status/trade_calendar/index_basic before full daily reload |
| `resolve-target-window` | done | {"reload_trade_days": 1, "target_dates": ["2026-06-12"]} |
| `validate-daily-precheck` | warning | {"json": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/full_align_dry_run_20260613_precheck.json", "markdown": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/full_align_dry_run_20260613_precheck.md", "status": "warning", "latest_trade_date": "2026-06-12", "anchor_data_date": "2026-06-12", "validation_dates": ["2026-06-12"], "incremental_dates": [], "requires_confirmation": false} |
| `base-full-reload` | planned | {"start_date": "20260612", "end_date": "20260612", "resume": false, "force_market_behavior": true, "apis": ["daily", "daily_basic", "stk_limit", "adj_factor", "moneyflow", "margin_detail", "moneyflow_hsgt", "hk_hold", "top_list", "top_inst", "index_daily"]} |
| `feature-build` | planned | {"start_date": "2026-06-12", "end_date": "2026-06-12", "mode": "daily", "note": "daily-full dry-run keeps feature planning lightweight; execute mode rebuilds all feature modules for the target window"} |
| `create-views` | planned | refresh stock_features_core/plus/full and analytical views |
| `validate-daily-postcheck` | planned | run after execution |
