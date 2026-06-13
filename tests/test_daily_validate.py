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


def test_validate_daily_dedupes_multi_exchange_trade_calendar(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE trade_calendar(cal_date DATE, exchange VARCHAR, is_open INTEGER)")
    con.execute(
        """
        INSERT INTO trade_calendar VALUES
        ('2026-06-01', 'SSE', 1),
        ('2026-06-01', 'SZSE', 1),
        ('2026-06-02', 'SSE', 1),
        ('2026-06-02', 'SZSE', 1)
        """
    )
    con.execute("CREATE TABLE derived_daily_spine(ts_code VARCHAR, trade_date DATE)")
    con.execute("CREATE TABLE stock_daily(ts_code VARCHAR, trade_date DATE)")
    con.execute(
        """
        INSERT INTO derived_daily_spine VALUES
        ('000001.SZ', '2026-06-01'),
        ('000001.SZ', '2026-06-02')
        """
    )
    con.execute(
        """
        INSERT INTO stock_daily VALUES
        ('000001.SZ', '2026-06-01'),
        ('000001.SZ', '2026-06-02')
        """
    )
    con.close()
    monkeypatch.setattr(daily_validate, "REPORTS_DIR", reports_dir)

    result = daily_validate.validate_daily(
        as_of_date="2026-06-02",
        validation_days=2,
        tables=["stock_daily", "derived_daily_spine"],
        db_path=db_path,
    )

    assert result.report["validation_dates"] == ["2026-06-01", "2026-06-02"]
    assert result.report["summary"]["status"] == "pass"


def test_validate_daily_blocks_empty_anchor_database(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE trade_calendar(cal_date DATE, is_open INTEGER)")
    con.execute("INSERT INTO trade_calendar VALUES ('2026-06-01', 1)")
    con.execute("CREATE TABLE stock_daily(ts_code VARCHAR, trade_date DATE)")
    con.close()
    monkeypatch.setattr(daily_validate, "REPORTS_DIR", reports_dir)

    result = daily_validate.validate_daily(
        as_of_date="2026-06-01",
        tables=["stock_daily"],
        db_path=db_path,
    )

    assert result.report["summary"]["status"] == "blocked"
    assert result.report["summary"]["empty_anchor"] is True
    assert result.report["summary"]["blocked_empty_anchor"] is True
    assert "base initialization" in result.report["summary"]["blocked_reason"]


def test_validate_daily_clamps_anchor_to_as_of_latest_trade_date(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE trade_calendar(cal_date DATE, is_open INTEGER)")
    con.execute(
        """
        INSERT INTO trade_calendar VALUES
        ('2026-06-11', 1),
        ('2026-06-12', 1)
        """
    )
    con.execute("CREATE TABLE derived_daily_spine(ts_code VARCHAR, trade_date DATE)")
    con.execute("CREATE TABLE stock_daily(ts_code VARCHAR, trade_date DATE)")
    con.execute("INSERT INTO derived_daily_spine VALUES ('000001.SZ', '2026-06-11')")
    con.execute("INSERT INTO derived_daily_spine VALUES ('000001.SZ', '2026-06-12')")
    con.execute("INSERT INTO stock_daily VALUES ('000001.SZ', '2026-06-11')")
    con.close()
    monkeypatch.setattr(daily_validate, "REPORTS_DIR", reports_dir)

    result = daily_validate.validate_daily(
        as_of_date="2026-06-11",
        tables=["stock_daily", "derived_daily_spine"],
        db_path=db_path,
    )

    assert result.report["latest_trade_date"] == "2026-06-11"
    assert result.report["anchor_data_date"] == "2026-06-11"
    assert result.report["validation_dates"] == ["2026-06-11"]


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


def test_validate_daily_treats_next_day_tables_as_expected_delay(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    _seed_db(db_path)
    monkeypatch.setattr(daily_validate, "REPORTS_DIR", reports_dir)
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE margin_detail(ts_code VARCHAR, trade_date DATE)")
    con.execute("INSERT INTO margin_detail VALUES ('000001.SZ', '2026-06-02')")
    con.close()

    result = daily_validate.validate_daily(
        as_of_date="2026-06-03",
        validation_days=1,
        tables=["margin_detail"],
        db_path=db_path,
    )

    item = result.report["tables"][0]
    assert item["status"] == "warning"
    assert item["expected_delay_missing"] is True
    assert result.report["summary"]["status"] == "pass"
    assert result.report["summary"]["expected_delay_table_count"] == 1


def test_validate_daily_warns_on_row_count_drop(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE trade_calendar(cal_date DATE, is_open INTEGER)")
    for day in range(1, 7):
        con.execute("INSERT INTO trade_calendar VALUES (?, 1)", [f"2026-06-{day:02d}"])
    con.execute("CREATE TABLE derived_daily_spine(ts_code VARCHAR, trade_date DATE)")
    con.execute("CREATE TABLE margin_detail(ts_code VARCHAR, trade_date DATE)")
    for day in range(1, 6):
        for idx in range(10):
            con.execute("INSERT INTO margin_detail VALUES (?, ?)", [f"{idx:06d}.SZ", f"2026-06-{day:02d}"])
    con.execute("INSERT INTO margin_detail VALUES ('000001.SZ', '2026-06-06')")
    con.close()
    monkeypatch.setattr(daily_validate, "REPORTS_DIR", reports_dir)

    result = daily_validate.validate_daily(
        as_of_date="2026-06-06",
        validation_days=1,
        tables=["margin_detail"],
        db_path=db_path,
    )

    item = result.report["tables"][0]
    assert item["status"] == "warning"
    assert "prior_5_day_avg" in item["row_count_warning"]
    assert result.report["summary"]["status"] == "pass"
    assert result.report["summary"]["row_count_warning_table_count"] == 1


def test_validate_daily_warns_on_hidden_table_lag_when_anchor_is_current(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE trade_calendar(cal_date DATE, is_open INTEGER)")
    for day in range(1, 4):
        con.execute("INSERT INTO trade_calendar VALUES (?, 1)", [f"2026-06-{day:02d}"])
    con.execute("CREATE TABLE derived_daily_spine(ts_code VARCHAR, trade_date DATE)")
    con.execute("CREATE TABLE stock_daily(ts_code VARCHAR, trade_date DATE)")
    con.execute("INSERT INTO derived_daily_spine VALUES ('000001.SZ', '2026-06-03')")
    con.execute("INSERT INTO stock_daily VALUES ('000001.SZ', '2026-06-01')")
    con.close()
    monkeypatch.setattr(daily_validate, "REPORTS_DIR", reports_dir)

    result = daily_validate.validate_daily(
        as_of_date="2026-06-03",
        validation_days=0,
        tables=["stock_daily", "derived_daily_spine"],
        db_path=db_path,
    )

    item = next(item for item in result.report["tables"] if item["table"] == "stock_daily")
    assert item["hidden_lag_dates"] == ["2026-06-02", "2026-06-03"]
    assert item["status"] == "warning"
    assert result.report["summary"]["table_lag_issue_count"] == 1
    assert result.report["summary"]["status"] == "warning"


def test_validate_daily_reports_new_stock_missing_from_base_table(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE trade_calendar(cal_date DATE, is_open INTEGER)")
    for day in range(1, 4):
        con.execute("INSERT INTO trade_calendar VALUES (?, 1)", [f"2026-06-{day:02d}"])
    con.execute("CREATE TABLE derived_daily_spine(ts_code VARCHAR, trade_date DATE)")
    con.execute("CREATE TABLE stock_daily(ts_code VARCHAR, trade_date DATE)")
    con.execute("CREATE TABLE stock_basic_info(ts_code VARCHAR, list_date DATE, list_status VARCHAR, delist_date DATE)")
    con.execute("INSERT INTO derived_daily_spine VALUES ('000001.SZ', '2026-06-03')")
    con.execute("INSERT INTO stock_daily VALUES ('000001.SZ', '2026-06-03')")
    con.execute("INSERT INTO stock_basic_info VALUES ('000001.SZ', '2026-06-01', 'L', NULL)")
    con.execute("INSERT INTO stock_basic_info VALUES ('000002.SZ', '2026-06-01', 'L', NULL)")
    con.close()
    monkeypatch.setattr(daily_validate, "REPORTS_DIR", reports_dir)

    result = daily_validate.validate_daily(
        as_of_date="2026-06-03",
        validation_days=0,
        tables=["stock_daily", "derived_daily_spine"],
        db_path=db_path,
    )

    issues = result.report["new_stock_coverage_issues"]
    assert issues == [
        {
            "table": "stock_daily",
            "missing_stock_count": 1,
            "sample": [{"ts_code": "000002.SZ", "list_date": "2026-06-01"}],
        }
    ]
    assert result.report["summary"]["new_stock_coverage_issue_count"] == 1
    assert result.report["summary"]["status"] == "warning"


def test_ownership_governance_registered_for_stock_level_validation():
    assert "derived_ownership_governance" in daily_validate.STOCK_LEVEL_DERIVED_TABLES
