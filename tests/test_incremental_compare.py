from __future__ import annotations

import duckdb

from stock_maintainance import incremental_compare


def _make_test_db(path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            CREATE TABLE derived_daily_spine (
                ts_code VARCHAR,
                trade_date DATE,
                value DOUBLE,
                label VARCHAR,
                updated_at TIMESTAMP
            )
            """
        )
        con.execute(
            """
            CREATE TABLE snap_derived_daily_spine AS
            SELECT *
            FROM derived_daily_spine
            """
        )
        rows = [
            ("000001.SZ", "2026-06-01", 1.0, "a"),
            ("000002.SZ", "2026-06-01", 2.0, "b"),
        ]
        con.executemany(
            "INSERT INTO derived_daily_spine (ts_code, trade_date, value, label, updated_at) VALUES (?, ?, ?, ?, current_timestamp)",
            rows,
        )
        con.executemany(
            "INSERT INTO snap_derived_daily_spine (ts_code, trade_date, value, label, updated_at) VALUES (?, ?, ?, ?, current_timestamp)",
            rows,
        )
    finally:
        con.close()


def test_compare_incremental_window_passes(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    _make_test_db(db_path)
    monkeypatch.setattr(incremental_compare, "REPORTS_DIR", reports_dir)

    result = incremental_compare.compare_incremental_window(
        start_date="2026-06-01",
        end_date="2026-06-01",
        tables=["derived_daily_spine"],
        snapshot_prefix="snap_",
        output_prefix="cmp",
        db_path=db_path,
    )

    assert result.passed
    assert result.json_path.exists()
    assert result.markdown_path.exists()
    assert result.report["summary"]["pass_table_count"] == 1


def test_compare_incremental_window_reports_mismatch(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    _make_test_db(db_path)
    con = duckdb.connect(str(db_path))
    try:
        con.execute("UPDATE derived_daily_spine SET value = 9 WHERE ts_code = '000002.SZ'")
    finally:
        con.close()
    monkeypatch.setattr(incremental_compare, "REPORTS_DIR", reports_dir)

    result = incremental_compare.compare_incremental_window(
        start_date="2026-06-01",
        end_date="2026-06-01",
        tables=["derived_daily_spine"],
        snapshot_prefix="snap_",
        output_prefix="cmp",
        db_path=db_path,
    )

    assert not result.passed
    assert result.report["tables"][0]["mismatch_columns"] == {"value": 1}


def test_compare_incremental_window_filters_snapshot_to_window(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    _make_test_db(db_path)
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO snap_derived_daily_spine
            VALUES ('000003.SZ', DATE '2026-05-31', 3.0, 'outside', current_timestamp)
            """
        )
    finally:
        con.close()
    monkeypatch.setattr(incremental_compare, "REPORTS_DIR", reports_dir)

    result = incremental_compare.compare_incremental_window(
        start_date="2026-06-01",
        end_date="2026-06-01",
        tables=["derived_daily_spine"],
        snapshot_prefix="snap_",
        output_prefix="cmp",
        db_path=db_path,
    )

    assert result.passed
    assert result.report["tables"][0]["snapshot_rows"] == 2
