from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_phase3_capital_flow_caches.py"
    spec = importlib.util.spec_from_file_location("build_phase3_capital_flow_caches", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_north_money_zscore_requires_full_window_observations() -> None:
    module = _load_script()

    sql = module.north_cache_sql("2026-01-01", "2026-06-30", "2025-01-01")

    for period in module.ZSCORE_PERIODS:
        assert f"count(north_money) OVER (ORDER BY trade_date ROWS BETWEEN {period - 1} PRECEDING AND CURRENT ROW) >= {period}" in sql
        assert f"AS north_money_zscore_{period}" in sql


def test_capital_flow_core_aggregates_northbound_ratio_consistently() -> None:
    source = (Path("src") / "stock_maintainance" / "features" / "modules.py").read_text(encoding="utf-8")

    assert "sum(hold_shares) AS north_hold_shares" in source
    assert "sum(hold_ratio) AS north_hold_ratio" in source
    assert "max(hold_ratio) AS north_hold_ratio" not in source
