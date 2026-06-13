from __future__ import annotations

from stock_maintainance.features.planner import build_feature_plan


def _registry() -> dict:
    return {
        "variables": [
            {
                "name": "trade_date",
                "table": "derived_daily_spine",
                "module": "daily_spine",
                "read_window": 10,
                "write_window": 10,
                "min_history": 1,
            }
        ]
    }


def test_feature_plan_defaults_to_recent_trading_days_when_calendar_available() -> None:
    trade_dates = [
        "2026-06-01",
        "2026-06-02",
        "2026-06-03",
        "2026-06-04",
        "2026-06-05",
        "2026-06-08",
        "2026-06-09",
        "2026-06-10",
        "2026-06-11",
        "2026-06-12",
    ]

    plan = build_feature_plan(
        _registry(),
        modules=["daily_spine"],
        end_date="2026-06-12",
        trade_dates=trade_dates,
    )

    assert plan.write_start_date == "2026-06-01"
    assert plan.write_end_date == "2026-06-12"
    assert plan.requires_confirmation is False


def test_feature_plan_confirmation_uses_trading_day_count_when_available() -> None:
    trade_dates = [
        "2026-06-01",
        "2026-06-02",
        "2026-06-03",
        "2026-06-04",
        "2026-06-05",
        "2026-06-08",
        "2026-06-09",
        "2026-06-10",
        "2026-06-11",
        "2026-06-12",
        "2026-06-15",
    ]

    plan = build_feature_plan(
        _registry(),
        modules=["daily_spine"],
        start_date="2026-06-01",
        end_date="2026-06-15",
        trade_dates=trade_dates,
    )

    assert plan.requires_confirmation is True
    assert "11 trading days" in plan.confirmation_reason


def test_feature_plan_expands_read_context_when_trade_calendar_unavailable() -> None:
    registry = {
        "variables": [
            {
                "name": "dividend_year_count_5y",
                "table": "derived_corporate_action",
                "module": "corporate_action",
                "read_window": 1250,
                "write_window": 10,
                "min_history": 1250,
            }
        ]
    }

    plan = build_feature_plan(
        registry,
        modules=["corporate_action"],
        start_date="2026-06-01",
        end_date="2026-06-11",
        trade_dates=[],
    )
    module = next(item for item in plan.module_plans if item.module == "corporate_action")

    assert module.read_window == 1250
    assert module.read_start_date < "2023-01-01"
