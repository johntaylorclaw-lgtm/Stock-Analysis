# Daily-Light 运行报告

生成时间：2026-06-11T22:26:07
截至日期：`2026-06-11`
运行模式：`execute`
结果：`warning`

## 窗口

- 最新交易日：`2026-06-11`
- 当前锚点日期：`2026-06-10`
- 验证日期：2026-06-10
- 待增量日期：2026-06-11
- 待增量交易日数：1

## 步骤

| 步骤 | 状态 | 说明 |
|---|---|---|
| `sync-master` | done | {"stock_basic_info": 5854, "stock_company_info": 6294, "stock_status_history": 6264, "trade_calendar": 7467, "index_basic_info": 7821} |
| `validate-daily-precheck` | warning | {"json": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/fable_fix_daily_20260611_precheck.json", "markdown": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/fable_fix_daily_20260611_precheck.md", "status": "warning", "latest_trade_date": "2026-06-11", "anchor_data_date": "2026-06-10", "validation_dates": ["2026-06-10"], "incremental_dates": ["2026-06-11"], "requires_confirmation": false} |
| `base-incremental` | done | {"daily": {"stock_daily": 5511, "stock_daily_basic": 5511, "stock_limit_price": 7651, "trade_dates": 1}, "adj_factor": {"stock_adj_factor": 5529, "trade_dates": 1}, "market_behavior": {"stock_moneyflow_daily": 5193, "margin_detail": 0, "northbound_daily": 1, "northbound_holding": 0, "top_list_daily": 104, "top_inst_detail": 957, "trade_dates": 1}, "index_daily": {"index_daily": 14, "index_count": 14}} |
| `feature-build` | done | {"start_date": "2026-06-10", "end_date": "2026-06-11", "elapsed_seconds": 256.705, "module_count": 17} |
| `create-views` | done | created analytical views |
| `validate-daily-postcheck` | pass | {"json": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/fable_fix_daily_20260611_postcheck.json", "markdown": "/mnt/d/Opencode Workspace/Stock_Maintainance/reports/fable_fix_daily_20260611_postcheck.md", "status": "pass", "latest_trade_date": "2026-06-11", "anchor_data_date": "2026-06-11", "validation_dates": ["2026-06-11"], "incremental_dates": [], "requires_confirmation": false} |
