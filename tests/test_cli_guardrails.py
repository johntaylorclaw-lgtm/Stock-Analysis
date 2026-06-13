from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from stock_maintainance import cli
from stock_maintainance import ingest
from stock_maintainance.tushare_source import RateLimitPolicy, TushareClient


class _BlockedValidation:
    json_path = "blocked.json"
    markdown_path = "blocked.md"
    passed = False
    report = {
        "summary": {
            "status": "blocked",
            "requires_confirmation": True,
        }
    }


def test_validate_daily_blocked_returns_nonzero_even_without_fail_on_warning(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "validate_daily", lambda **_: _BlockedValidation())

    status = cli.cmd_validate_daily(
        SimpleNamespace(
            as_of_date="2026-06-12",
            max_auto_trade_days=10,
            validation_days=1,
            table=None,
            output_prefix="x",
            fail_on_warning=False,
        )
    )

    assert status == 2
    assert '"status": "blocked"' in capsys.readouterr().out


def test_direct_sync_range_guard_blocks_large_unconfirmed_calendar_window(monkeypatch) -> None:
    monkeypatch.setattr(cli, "connect", lambda: (_ for _ in ()).throw(RuntimeError("no db")))

    blocked = cli._sync_range_guard(
        "20260601",
        "20260620",
        allow_confirmed_history=False,
    )

    assert blocked is not None
    assert blocked["status"] == "blocked"
    assert "calendar days" in str(blocked["reason"])


def test_direct_sync_range_guard_allows_explicit_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(cli, "connect", lambda: (_ for _ in ()).throw(RuntimeError("no db")))

    assert (
        cli._sync_range_guard(
            "20260601",
            "20260620",
            allow_confirmed_history=True,
        )
        is None
    )


def test_cross_sectional_sentinel_threshold_keeps_real_large_negative_values() -> None:
    from pathlib import Path

    core_script = Path("scripts/build_phase3_cross_sectional_core.py").read_text(encoding="utf-8")
    view_script = Path("scripts/create_phase3_cross_sectional_full_view.py").read_text(encoding="utf-8")

    assert "<= -9000000" in core_script
    assert "<= -9000000" in view_script
    assert "<= -900000 THEN NULL" not in core_script
    assert "<= -900000 THEN NULL" not in view_script


def test_tushare_call_paged_concatenates_until_short_page(monkeypatch) -> None:
    client = TushareClient.__new__(TushareClient)
    client._rate_limit = RateLimitPolicy(default_sleep_seconds=0, financial_sleep_seconds=0, max_retries=1)

    calls: list[dict[str, int]] = []

    class _FakePro:
        def demo(self, **params):
            calls.append(params)
            offset = params["offset"]
            if offset == 0:
                return pd.DataFrame({"x": [1, 2]})
            return pd.DataFrame({"x": [3]})

    client._pro = _FakePro()

    df = client.call_paged("demo", page_size=2, ts_code="000001.SZ")

    assert df["x"].tolist() == [1, 2, 3]
    assert calls == [
        {"ts_code": "000001.SZ", "limit": 2, "offset": 0},
        {"ts_code": "000001.SZ", "limit": 2, "offset": 2},
    ]


def test_sync_daily_range_records_per_date_failure(monkeypatch) -> None:
    states: list[tuple[str, str, str]] = []
    failures: list[tuple[str, str]] = []

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(ingest, "open_trade_dates", lambda *_: ["20260610", "20260611"])
    monkeypatch.setattr(ingest, "connect", lambda: _Conn())
    monkeypatch.setattr(ingest, "init_database", lambda con: None)
    monkeypatch.setattr(ingest, "fetch_task_state", lambda con, task, key: None)
    monkeypatch.setattr(
        ingest,
        "record_task_state",
        lambda con, task, key, status, **_: states.append((task, key, status)),
    )
    monkeypatch.setattr(
        ingest,
        "record_task_failure",
        lambda con, task, key, error, **_: failures.append((task, key)),
    )

    def _sync_one(trade_date: str):
        if trade_date == "20260611":
            raise RuntimeError("boom")
        return {"stock_daily": 1, "stock_daily_basic": 1, "stock_limit_price": 1}

    monkeypatch.setattr(ingest, "sync_daily_for_date", _sync_one)

    result = ingest.sync_daily_range("20260610", "20260611")

    assert result["dates_done"] == 1
    assert result["dates_failed"] == 1
    assert failures == [("sync_daily_date", "20260611")]
    assert ("sync_daily_date", "20260610", "success") in states
    assert ("sync_daily_date", "20260611", "failed") in states


def test_sector_concept_sql_protects_null_industry_rank_groups() -> None:
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path

    path = Path("scripts/build_phase3_sector_concept_core.py")
    spec = spec_from_file_location("build_phase3_sector_concept_core", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    expr = module.rank_desc_expr("v.total_mv")

    assert "m.sw_l2_code IS NOT NULL" in expr
    assert "count(v.total_mv) FILTER" in expr
    assert ">= 2" in expr


def test_reconcile_schema_refuses_to_recreate_nonempty_growth_table(monkeypatch) -> None:
    from stock_maintainance import database

    class _Conn:
        def execute(self, sql, *_):
            class _Result:
                def fetchone(self_inner):
                    if "count(*)" in sql:
                        return [1]
                    return [None]

            return _Result()

    registry = {
        "tables": [
            {
                "name": "derived_financial_growth",
                "fields": [{"name": f"col_{i}", "dtype": "DOUBLE"} for i in range(101)],
            }
        ]
    }
    monkeypatch.setattr(database, "table_columns", lambda con, table: [])

    try:
        database.reconcile_schema(_Conn(), registry)
    except RuntimeError as exc:
        assert "schema is incompatible" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("expected RuntimeError")
