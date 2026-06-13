from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_phase3_sector_index_caches.py"
    spec = importlib.util.spec_from_file_location("build_phase3_sector_index_caches", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_concept_cache_uses_explicit_limit_up_ratio_alias() -> None:
    module = _load_script()

    sql = module.concept_cache_sql("2026-06-01", "2026-06-11", "2025-01-01")

    assert "AS limit_up_ratio" in sql
    assert "avg(limit_up_ratio) OVER" in sql
    assert "AS up_ratio" not in sql
