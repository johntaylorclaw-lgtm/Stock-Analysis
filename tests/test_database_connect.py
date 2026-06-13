from __future__ import annotations

import duckdb

from stock_maintainance import database


def test_connect_retries_duckdb_io_errors(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}
    real_connect = duckdb.connect

    def flaky_connect(path):
        calls["count"] += 1
        if calls["count"] == 1:
            raise duckdb.IOException("database is locked")
        return real_connect(path)

    monkeypatch.setattr(database.duckdb, "connect", flaky_connect)
    monkeypatch.setattr(database, "CONNECT_RETRY_SLEEP_SECONDS", 0)

    con = database.connect(tmp_path / "test.duckdb")
    try:
        assert calls["count"] == 2
        assert con.execute("SELECT 1").fetchone()[0] == 1
    finally:
        con.close()
