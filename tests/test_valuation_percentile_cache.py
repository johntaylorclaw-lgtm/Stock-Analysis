from __future__ import annotations

from pathlib import Path


def test_valuation_percentile_cache_requires_min_observations_and_positive_values() -> None:
    script = (Path("scripts") / "backfill_valuation_percentile_cache.py").read_text(encoding="utf-8")
    cache_steps = (Path("src") / "stock_maintainance" / "features" / "cache_steps.py").read_text(encoding="utf-8")

    assert "MIN_PERCENTILE_OBS = 60" in script
    assert "min_periods=MIN_PERCENTILE_OBS" in script
    assert "min_periods=1" not in script
    assert "count(CASE WHEN c.pe_ttm > 0 THEN c.pe_ttm END) >= 60" in cache_steps
    assert "t.pe_ttm > 0" in cache_steps
