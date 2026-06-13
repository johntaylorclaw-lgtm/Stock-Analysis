# Daily-Full 运行报告

生成时间：2026-06-13T10:11:28
截至日期：`2026-06-13`
运行模式：`execute`
结果：`warning`

## 全量窗口

- 重拉交易日：2026-06-12
- 重拉交易日数：1

## 步骤

| 步骤 | 状态 | 说明 |
|---|---|---|
| `sync-master` | done | {"stock_basic_info": 5854, "stock_company_info": 6294, "stock_status_history": 6264, "trade_calendar": 7469, "index_basic_info": 7821} |
| `resolve-target-window` | done | {"reload_trade_days": 1, "target_dates": ["2026-06-12"]} |
| `validate-daily-precheck` | warning | {"json": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/full_align_execute_20260613_precheck.json", "markdown": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/full_align_execute_20260613_precheck.md", "status": "warning", "latest_trade_date": "2026-06-12", "anchor_data_date": "2026-06-12", "validation_dates": ["2026-06-12"], "incremental_dates": [], "requires_confirmation": false} |
| `base-full-reload` | done | {"daily": {"stock_daily": 5512, "stock_daily_basic": 5512, "stock_limit_price": 7651, "trade_dates": 1, "dates_done": 1, "dates_failed": 0, "dates_skipped": 0}, "adj_factor": {"stock_adj_factor": 5529, "trade_dates": 1}, "market_behavior": {"stock_moneyflow_daily": 5194, "margin_detail": 1980, "northbound_daily": 1, "northbound_holding": 944, "top_list_daily": 95, "top_inst_detail": 897, "trade_dates": 1}, "index_daily": {"index_daily": 14, "index_count": 14}} |
| `feature-build` | done | {"start_date": "2026-06-12", "end_date": "2026-06-12", "elapsed_seconds": 313.189, "module_count": 17} |
| `create-views` | done | created analytical views |
| `validate-daily-postcheck` | warning | {"json": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/full_align_execute_20260613_postcheck.json", "markdown": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/full_align_execute_20260613_postcheck.md", "status": "warning", "latest_trade_date": "2026-06-12", "anchor_data_date": "2026-06-12", "validation_dates": ["2026-06-12"], "incremental_dates": [], "requires_confirmation": false} |
| `refresh-weekly-snapshot` | snapshot_created | {"json": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/full_align_execute_20260613_weekly_snapshot.json", "markdown": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/full_align_execute_20260613_weekly_snapshot.md", "status": "snapshot_created", "table_count": 25, "blocked_reason": "snapshot refreshed from current data; rerun weekly-full without --create-snapshot-from-current to perform an independent comparison"} |
