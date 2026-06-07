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
