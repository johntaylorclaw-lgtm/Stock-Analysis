from __future__ import annotations

import json

from stock_maintainance import run_summary


def test_summarize_daily_from_report(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    source = reports_dir / "phase5_daily_light_execute_test.json"
    source.write_text(
        json.dumps(
            {
                "as_of_date": "2026-06-07",
                "dry_run": False,
                "precheck": {
                    "latest_trade_date": "2026-06-05",
                    "anchor_data_date": "2026-06-05",
                    "validation_dates": ["2026-06-05"],
                    "incremental_dates": [],
                },
                "postcheck": {"status": "pass", "markdown": "post.md"},
                "steps": [
                    {"name": "sync-master", "status": "done"},
                    {"name": "validate-daily-postcheck", "status": "pass"},
                ],
                "summary": {"status": "pass"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_summary, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(run_summary, "SUMMARY_DIR", reports_dir / "summaries")

    result = run_summary.summarize_run(mode="daily", run_id="phase5_daily_light_execute_test")

    assert result.passed
    assert result.markdown_path.exists()
    assert "日报汇总" in result.markdown_path.read_text(encoding="utf-8")


def test_summarize_weekly_from_report(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    source = reports_dir / "phase5_weekly_full_compare_test.json"
    source.write_text(
        json.dumps(
            {
                "as_of_date": "2026-06-07",
                "reference_start_date": "2026-04-08",
                "reference_end_date": "2026-06-05",
                "requested_compare_start_date": "2026-05-25",
                "requested_compare_end_date": "2026-06-05",
                "snapshot_common_start_date": "2026-05-27",
                "snapshot_common_end_date": "2026-06-05",
                "compare_start_date": "2026-05-27",
                "compare_end_date": "2026-06-05",
                "compare_report": {
                    "summary": {
                        "table_count": 24,
                        "pass_table_count": 24,
                        "fail_table_count": 0,
                        "missing_or_extra_key_rows": 0,
                        "mismatch_column_count": 0,
                        "mismatch_cell_count": 0,
                    }
                },
                "summary": {"status": "pass", "table_count": 24},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_summary, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(run_summary, "SUMMARY_DIR", reports_dir / "summaries")

    result = run_summary.summarize_run(mode="weekly", run_id="phase5_weekly_full_compare_test")

    assert result.passed
    text = result.markdown_path.read_text(encoding="utf-8")
    assert "周报汇总" in text
    assert "2026-05-27" in text


def test_summarize_status_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(run_summary, "SUMMARY_DIR", tmp_path)
    monkeypatch.setattr(
        run_summary,
        "_status_payload",
        lambda as_of_date: {
            "as_of_date": as_of_date,
            "latest_trade_date": "2026-06-05",
            "anchor_data_date": "2026-06-05",
            "incremental_trade_day_count": 0,
            "stock_basic_info_rows": 5851,
            "stock_active": 5525,
            "stock_delisted": 326,
            "stock_daily_rows": 15339845,
            "stock_daily_distinct": 5813,
            "derived_spine_rows": 15339845,
            "derived_spine_distinct": 5813,
            "feature_view_field_counts": {
                "stock_features_core": 318,
                "stock_features_plus": 1198,
                "stock_features_full": 1602,
            },
        },
    )

    result = run_summary.summarize_run(mode="status", as_of_date="2026-06-07")

    assert result.passed
    assert "状态汇总报告" in result.markdown_path.read_text(encoding="utf-8")
