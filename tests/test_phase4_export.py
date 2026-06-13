from pathlib import Path

import duckdb
import pytest

from stock_maintainance import export as export_module


def test_export_parquet_dry_run_supports_date_partitions_and_column_pruning(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE stock_features_core (
            ts_code VARCHAR,
            trade_date DATE,
            close_hfq DOUBLE,
            ma_20_hfq DOUBLE
        )
        """
    )
    con.execute(
        """
        INSERT INTO stock_features_core VALUES
        ('000001.SZ', DATE '2026-05-25', 10.0, 9.8),
        ('000002.SZ', DATE '2026-05-25', 11.0, 10.8),
        ('000001.SZ', DATE '2026-05-26', 10.2, 9.9)
        """
    )
    con.close()

    def connect_test():
        return duckdb.connect(str(db_path))

    monkeypatch.setattr(export_module, "connect", connect_test)
    result = export_module.export_parquet(
        source="stock_features_core",
        start_date="2026-05-25",
        end_date="2026-05-26",
        columns=["close_hfq"],
        output_dir=tmp_path / "parquet" / "features",
        dry_run=True,
    )

    payload = result.to_dict()
    assert payload["columns"] == ["ts_code", "trade_date", "close_hfq"]
    assert [item["trade_date"] for item in payload["partitions"]] == ["2026-05-25", "2026-05-26"]
    assert [item["rows"] for item in payload["partitions"]] == [2, 1]
    assert not Path(payload["partitions"][0]["path"]).exists()


def test_export_parquet_writes_atomically_without_ts_code(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE market_features (
            trade_date DATE,
            market_ret DOUBLE
        )
        """
    )
    con.execute("INSERT INTO market_features VALUES (DATE '2026-05-25', 0.01)")
    con.close()

    def connect_test():
        return duckdb.connect(str(db_path))

    monkeypatch.setattr(export_module, "connect", connect_test)
    result = export_module.export_parquet(
        source="market_features",
        start_date="2026-05-25",
        end_date="2026-05-25",
        output_dir=tmp_path / "parquet" / "market",
    )

    output_file = Path(result.partitions[0]["path"])
    assert output_file.exists()
    assert not output_file.with_suffix(output_file.suffix + ".tmp").exists()


def test_export_parquet_rejects_non_iso_dates(tmp_path) -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        export_module.export_parquet(
            source="stock_features_core",
            start_date="20260525",
            end_date="2026-05-26",
            output_dir=tmp_path / "parquet",
            dry_run=True,
        )
