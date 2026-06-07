from __future__ import annotations

import duckdb

from stock_maintainance import weekly_full


def _seed_db(path):
    con = duckdb.connect(path)
    con.execute("CREATE TABLE trade_calendar(cal_date DATE, is_open INTEGER)")
    con.execute(
        """
        INSERT INTO trade_calendar VALUES
        ('2026-06-01', 1),
        ('2026-06-02', 1),
        ('2026-06-03', 1),
        ('2026-06-04', 1),
        ('2026-06-05', 1)
        """
    )
    con.execute(
        """
        CREATE TABLE derived_daily_spine(
            ts_code VARCHAR,
            trade_date DATE,
            value DOUBLE,
            updated_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        INSERT INTO derived_daily_spine VALUES
        ('000001.SZ', '2026-06-03', 1.0, current_timestamp),
        ('000001.SZ', '2026-06-04', 1.1, current_timestamp),
        ('000001.SZ', '2026-06-05', 1.2, current_timestamp)
        """
    )
    con.close()


def test_weekly_full_dry_run_builds_windows(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    _seed_db(db_path)
    monkeypatch.setattr(weekly_full, "REPORTS_DIR", tmp_path)

    result = weekly_full.run_weekly_full(
        as_of_date="2026-06-05",
        reference_days=5,
        compare_days=2,
        tables=["derived_daily_spine"],
        dry_run=True,
        db_path=db_path,
    )

    assert result.report["reference_start_date"] == "2026-06-01"
    assert result.report["compare_start_date"] == "2026-06-04"
    assert result.report["summary"]["status"] == "pass"


def test_weekly_full_blocks_when_snapshot_missing(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    _seed_db(db_path)
    monkeypatch.setattr(weekly_full, "REPORTS_DIR", tmp_path)

    result = weekly_full.run_weekly_full(
        as_of_date="2026-06-05",
        tables=["derived_daily_spine"],
        db_path=db_path,
    )

    assert result.report["summary"]["status"] == "blocked"
    assert result.report["missing_snapshot_tables"] == ["derived_daily_spine"]


def test_weekly_full_can_compare_created_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    _seed_db(db_path)
    monkeypatch.setattr(weekly_full, "REPORTS_DIR", tmp_path)

    result = weekly_full.run_weekly_full(
        as_of_date="2026-06-05",
        reference_days=3,
        compare_days=2,
        tables=["derived_daily_spine"],
        snapshot_prefix="snap_",
        output_prefix="weekly",
        create_snapshot_from_current=True,
        db_path=db_path,
    )

    assert result.report["summary"]["status"] == "pass"
    assert result.report["compare_report"]["summary"]["pass_table_count"] == 1


def test_weekly_full_aligns_compare_window_to_snapshot_bounds(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    _seed_db(db_path)
    con = duckdb.connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE snap_derived_daily_spine AS
            SELECT *
            FROM derived_daily_spine
            WHERE trade_date BETWEEN DATE '2026-06-04' AND DATE '2026-06-05'
            """
        )
    finally:
        con.close()
    monkeypatch.setattr(weekly_full, "REPORTS_DIR", tmp_path)

    result = weekly_full.run_weekly_full(
        as_of_date="2026-06-05",
        reference_days=5,
        compare_days=5,
        tables=["derived_daily_spine"],
        snapshot_prefix="snap_",
        output_prefix="weekly_aligned",
        db_path=db_path,
    )

    assert result.report["requested_compare_start_date"] == "2026-06-01"
    assert result.report["compare_start_date"] == "2026-06-04"
    assert result.report["summary"]["status"] == "pass"
