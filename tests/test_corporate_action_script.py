from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_phase3_corporate_action_core.py"
    spec = importlib.util.spec_from_file_location("build_phase3_corporate_action_core", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dividend_announced_flag_counts_matched_events_only():
    module = _load_script()
    sql = module.build_insert_sql("2025-12-27", "2026-12-31", write_start="2026-01-01")

    assert "count(e.ts_code) > 0 AS has_dividend_announced_not_executed" in sql
    assert "FROM dividend_latest e" in sql
    assert "min(d.trade_date)" in sql
    assert "d.trade_date >= e.event_date" in sql
    assert "WHERE ds.trade_date BETWEEN DATE '2025-12-27' AND DATE '2026-12-31'" in sql
    assert "WHERE trade_date BETWEEN DATE '2026-01-01' AND DATE '2026-12-31'" in sql
