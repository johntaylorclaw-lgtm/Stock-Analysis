from __future__ import annotations

import duckdb

from stock_maintainance import sample_stock


def test_sample_stock_payload_json_only(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    reports_dir = tmp_path / "reports"
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE stock_basic_info(ts_code VARCHAR, name VARCHAR, market VARCHAR, exchange VARCHAR)")
    con.execute("CREATE TABLE stock_daily(ts_code VARCHAR, trade_date DATE, close DOUBLE)")
    con.execute("CREATE TABLE derived_daily_spine(ts_code VARCHAR, trade_date DATE, is_trade INTEGER)")
    con.execute("INSERT INTO stock_basic_info VALUES ('000001.SZ', '平安银行', '主板', 'SZSE')")
    con.execute("INSERT INTO stock_daily VALUES ('000001.SZ', '2026-06-05', 12.3)")
    con.execute("INSERT INTO derived_daily_spine VALUES ('000001.SZ', '2026-06-05', 1)")
    con.close()
    monkeypatch.setattr(sample_stock, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(sample_stock, "BASE_SAMPLE_TABLES", ["stock_basic_info", "stock_daily"])
    monkeypatch.setattr(sample_stock, "DERIVED_SAMPLE_TABLES", ["derived_daily_spine"])

    result = sample_stock.sample_stock(ts_code="000001.SZ", row_limit=5, build_excel=False, db_path=db_path)

    assert result.payload["stock"]["name"] == "平安银行"
    assert result.payload["base_tables"][1]["rows"][0]["close"] == 12.3
    assert result.payload["quality_report"][1]["row_count"] == 1
    assert result.json_path.exists()
    assert result.xlsx_path is None
