from __future__ import annotations

from pathlib import Path

from stock_maintainance import daily_full


class FakeValidationResult:
    def __init__(self, *, incremental_dates=None, status="pass"):
        self.json_path = Path("/tmp/check.json")
        self.markdown_path = Path("/tmp/check.md")
        self.report = {
            "latest_trade_date": "2026-06-12",
            "anchor_data_date": "2026-06-11",
            "validation_dates": ["2026-06-12"],
            "incremental_dates": incremental_dates or [],
            "summary": {
                "status": status,
                "requires_confirmation": False,
            },
        }


def test_daily_full_dry_run_plans_forced_full_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_full, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(daily_full, "_open_trade_dates", lambda *_, **__: ["2026-06-12"])
    monkeypatch.setattr(daily_full, "validate_daily", lambda **_: FakeValidationResult())
    monkeypatch.setattr(
        daily_full,
        "build_features",
        lambda **kwargs: {"elapsed_seconds": 0.1, "results": [{"module": "daily_spine"}], "kwargs": kwargs},
    )

    result = daily_full.run_daily_full(
        as_of_date="2026-06-12",
        dry_run=True,
        output_prefix="daily_full_plan",
    )

    assert result.report["summary"]["status"] == "pass"
    assert result.report["target_dates"] == ["2026-06-12"]
    base_step = next(step for step in result.report["steps"] if step["name"] == "base-full-reload")
    assert base_step["status"] == "planned"
    assert base_step["detail"]["resume"] is False
    assert base_step["detail"]["force_market_behavior"] is True


def test_daily_full_execute_disables_resume_and_forces_market_behavior(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_full, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(daily_full, "_open_trade_dates", lambda *_, **__: ["2026-06-11", "2026-06-12"])
    monkeypatch.setattr(daily_full, "validate_daily", lambda **_: FakeValidationResult())
    for name in [
        "sync_stock_basic",
        "sync_stock_company",
        "sync_stock_status_history",
        "sync_trade_calendar",
        "sync_index_basic",
    ]:
        monkeypatch.setattr(daily_full, name, lambda *_, **__: {name: 1})

    seen: dict[str, object] = {}

    def fake_sync_daily_range(start_date, end_date, *, resume=True, **_):
        seen["daily"] = (start_date, end_date, resume)
        return {"stock_daily": 2}

    def fake_market_behavior(start_date, end_date, *, force=False, **_):
        seen["market"] = (start_date, end_date, force)
        return {"stock_moneyflow_daily": 2}

    monkeypatch.setattr(daily_full, "sync_daily_range", fake_sync_daily_range)
    monkeypatch.setattr(daily_full, "sync_adj_factor_range", lambda *_, **__: {"stock_adj_factor": 2})
    monkeypatch.setattr(daily_full, "sync_market_behavior_range", fake_market_behavior)
    monkeypatch.setattr(daily_full, "sync_index_daily_range", lambda *_, **__: {"index_daily": 2})
    monkeypatch.setattr(
        daily_full,
        "build_features",
        lambda **kwargs: {"elapsed_seconds": 0.1, "results": [{"module": "daily_spine"}], "kwargs": kwargs},
    )
    monkeypatch.setattr(daily_full, "create_views", lambda: None)

    result = daily_full.run_daily_full(
        as_of_date="2026-06-12",
        reload_trade_days=2,
        output_prefix="daily_full_execute",
    )

    assert result.report["summary"]["status"] == "pass"
    assert seen["daily"] == ("20260611", "20260612", False)
    assert seen["market"] == ("20260611", "20260612", True)


def test_daily_full_precheck_warning_clears_when_postcheck_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_full, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(daily_full, "_open_trade_dates", lambda *_, **__: ["2026-06-12"])
    calls = {"count": 0}

    def fake_validate_daily(**_):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeValidationResult(incremental_dates=["2026-06-12"], status="warning")
        return FakeValidationResult(incremental_dates=[], status="pass")

    monkeypatch.setattr(daily_full, "validate_daily", fake_validate_daily)
    for name in [
        "sync_stock_basic",
        "sync_stock_company",
        "sync_stock_status_history",
        "sync_trade_calendar",
        "sync_index_basic",
    ]:
        monkeypatch.setattr(daily_full, name, lambda *_, **__: {name: 1})
    monkeypatch.setattr(daily_full, "sync_daily_range", lambda *_, **__: {"stock_daily": 1})
    monkeypatch.setattr(daily_full, "sync_adj_factor_range", lambda *_, **__: {"stock_adj_factor": 1})
    monkeypatch.setattr(daily_full, "sync_market_behavior_range", lambda *_, **__: {"stock_moneyflow_daily": 1})
    monkeypatch.setattr(daily_full, "sync_index_daily_range", lambda *_, **__: {"index_daily": 1})
    monkeypatch.setattr(
        daily_full,
        "build_features",
        lambda **kwargs: {"elapsed_seconds": 0.1, "results": [{"module": "daily_spine"}], "kwargs": kwargs},
    )
    monkeypatch.setattr(daily_full, "create_views", lambda: None)

    result = daily_full.run_daily_full(as_of_date="2026-06-12", output_prefix="daily_full_cleared")

    precheck_step = next(step for step in result.report["steps"] if step["name"] == "validate-daily-precheck")
    assert precheck_step["status"] == "warning"
    assert result.report["summary"]["status"] == "pass"
