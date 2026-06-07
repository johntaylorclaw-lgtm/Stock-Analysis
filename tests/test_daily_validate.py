from __future__ import annotations

import duckdb

from stock_maintainance import daily_validate


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
        ('2026-06-05', 1),
        ('2026-12-31', 1)
        """
    )
    for table in ["stock_daily", "derived_daily_spine"]:
        con.execute(f"CREATE TABLE {table}(ts_code VARCHAR, trade_date DATE, close DOUBLE)")
        con.execute(
            f"""
            INSERT INTO {table} VALUES
            ('000001.SZ', '2026-06-01', 1.0),
            ('000002.SZ', '2026-06-01', 2.0),
            ('000001.SZ', '2026-06-02', 1.1),
            ('000002.SZ', '2026-06-02', 2.1)
            """
        )
    con.close()


def test_validate_daily_uses_as_of_date_not_future_calendar(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    _seed_db(db_path)
    monkeypatch.setattr(daily_validate, "REPORTS_DIR", reports_dir)

    result = daily_validate.validate_daily(
        as_of_date="2026-06-02",
        tables=["stock_daily", "derived_daily_spine"],
        db_path=db_path,
    )

    assert result.report["latest_trade_date"] == "2026-06-02"
    assert result.report["anchor_data_date"] == "2026-06-02"
    assert result.report["validation_dates"] == ["2026-06-02"]
    assert result.report["incremental_dates"] == []
    assert result.report["summary"]["status"] == "pass"
    assert result.json_path.exists()
    assert result.markdown_path.exists()


def test_validate_daily_blocks_large_incremental_gap(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    _seed_db(db_path)
    monkeypatch.setattr(daily_validate, "REPORTS_DIR", reports_dir)

    result = daily_validate.validate_daily(
        as_of_date="2026-06-05",
        max_auto_trade_days=2,
        tables=["stock_daily", "derived_daily_spine"],
        db_path=db_path,
    )

    assert result.report["latest_trade_date"] == "2026-06-05"
    assert result.report["anchor_data_date"] == "2026-06-02"
    assert result.report["incremental_dates"] == ["2026-06-03", "2026-06-04", "2026-06-05"]
    assert result.report["summary"]["requires_confirmation"] is True
    assert result.report["summary"]["status"] == "blocked"
