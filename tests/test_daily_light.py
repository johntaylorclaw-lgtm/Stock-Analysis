from __future__ import annotations

from pathlib import Path

from stock_maintainance import daily_light


class FakeValidationResult:
    def __init__(self, *, incremental_dates, requires_confirmation=False):
        self.json_path = Path("/tmp/precheck.json")
        self.markdown_path = Path("/tmp/precheck.md")
        self.report = {
            "latest_trade_date": "2026-06-05",
            "anchor_data_date": "2026-06-01",
            "validation_dates": ["2026-06-01"],
            "incremental_dates": incremental_dates,
            "summary": {
                "status": "blocked" if requires_confirmation else "pass",
                "requires_confirmation": requires_confirmation,
            },
        }


def test_daily_light_dry_run_plans_incremental_window(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_light, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(
        daily_light,
        "validate_daily",
        lambda **_: FakeValidationResult(incremental_dates=["2026-06-02", "2026-06-03"]),
    )
    monkeypatch.setattr(
        daily_light,
        "build_features",
        lambda **kwargs: {"elapsed_seconds": 0.1, "results": [{"module": "daily_spine"}], "kwargs": kwargs},
    )

    result = daily_light.run_daily_light(as_of_date="2026-06-05", dry_run=True, output_prefix="test_daily_light")

    assert result.report["summary"]["status"] == "pass"
    assert result.report["summary"]["incremental_trade_day_count"] == 2
    assert [step["name"] for step in result.report["steps"]] == [
        "sync-master",
        "validate-daily-precheck",
        "base-incremental",
        "feature-build",
        "create-views",
        "validate-daily-postcheck",
    ]
    assert result.json_path.exists()
    assert result.markdown_path.exists()


def test_daily_light_default_as_of_uses_latest_open_trade_date(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_light, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(daily_light, "_latest_open_trade_date", lambda requested: "2026-06-05")

    seen: dict[str, str] = {}

    def fake_validate_daily(**kwargs):
        seen["as_of_date"] = kwargs["as_of_date"]
        return FakeValidationResult(incremental_dates=[])

    monkeypatch.setattr(daily_light, "validate_daily", fake_validate_daily)

    result = daily_light.run_daily_light(dry_run=True, output_prefix="resolved_as_of")

    assert seen["as_of_date"] == "2026-06-05"
    assert result.report["as_of_date"] == "2026-06-05"
    assert any(step["name"] == "resolve-as-of-date" and step["status"] == "done" for step in result.report["steps"])


def test_daily_light_default_as_of_warns_when_calendar_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_light, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(daily_light, "_latest_open_trade_date", lambda requested: None)
    monkeypatch.setattr(
        daily_light,
        "validate_daily",
        lambda **_: FakeValidationResult(incremental_dates=[]),
    )

    result = daily_light.run_daily_light(dry_run=True, output_prefix="missing_calendar")

    assert result.report["summary"]["status"] == "warning"
    assert any(step["name"] == "resolve-as-of-date" and step["status"] == "warning" for step in result.report["steps"])


def test_daily_light_blocks_large_window_without_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_light, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(
        daily_light,
        "validate_daily",
        lambda **_: FakeValidationResult(
            incremental_dates=[f"2026-06-{day:02d}" for day in range(2, 15)],
            requires_confirmation=True,
        ),
    )

    result = daily_light.run_daily_light(as_of_date="2026-06-20", dry_run=True, output_prefix="blocked")

    assert result.report["summary"]["status"] == "blocked"
    assert "allow-confirmed-history" in result.report["summary"]["blocked_reason"]


def test_daily_light_reports_optional_market_behavior_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_light, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(
        daily_light,
        "validate_daily",
        lambda **_: FakeValidationResult(incremental_dates=["2026-06-05"]),
    )
    monkeypatch.setattr(daily_light, "sync_daily_range", lambda *_, **__: {"stock_daily": 1})
    monkeypatch.setattr(daily_light, "sync_adj_factor_range", lambda *_, **__: {"stock_adj_factor": 1})
    monkeypatch.setattr(
        daily_light,
        "sync_market_behavior_range",
        lambda *_, **__: {"stock_moneyflow_daily": 1, "optional_failures": [{"api": "top_list", "error": "temporary"}]},
    )
    monkeypatch.setattr(daily_light, "sync_index_daily_range", lambda *_, **__: {"index_daily": 1})
    monkeypatch.setattr(
        daily_light,
        "build_features",
        lambda **kwargs: {"elapsed_seconds": 0.1, "results": [{"module": "daily_spine"}], "kwargs": kwargs},
    )
    monkeypatch.setattr(daily_light, "create_views", lambda: None)

    result = daily_light.run_daily_light(as_of_date="2026-06-05", output_prefix="optional_warning")

    base_step = next(step for step in result.report["steps"] if step["name"] == "base-incremental")
    assert base_step["status"] == "warning"
    assert result.report["summary"]["status"] == "warning"


def test_daily_light_precheck_warning_clears_when_postcheck_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_light, "REPORTS_DIR", tmp_path)
    calls = {"count": 0}

    def fake_validate_daily(**_):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeValidationResult(incremental_dates=["2026-06-05"])
        return FakeValidationResult(incremental_dates=[])

    monkeypatch.setattr(daily_light, "validate_daily", fake_validate_daily)
    monkeypatch.setattr(daily_light, "sync_daily_range", lambda *_, **__: {"stock_daily": 1})
    monkeypatch.setattr(daily_light, "sync_adj_factor_range", lambda *_, **__: {"stock_adj_factor": 1})
    monkeypatch.setattr(daily_light, "sync_market_behavior_range", lambda *_, **__: {"stock_moneyflow_daily": 1})
    monkeypatch.setattr(daily_light, "sync_index_daily_range", lambda *_, **__: {"index_daily": 1})
    monkeypatch.setattr(
        daily_light,
        "build_features",
        lambda **kwargs: {"elapsed_seconds": 0.1, "results": [{"module": "daily_spine"}], "kwargs": kwargs},
    )
    monkeypatch.setattr(daily_light, "create_views", lambda: None)

    result = daily_light.run_daily_light(as_of_date="2026-06-05", output_prefix="precheck_cleared")

    precheck_step = next(step for step in result.report["steps"] if step["name"] == "validate-daily-precheck")
    assert precheck_step["status"] == "pass"
    assert result.report["summary"]["status"] == "pass"
