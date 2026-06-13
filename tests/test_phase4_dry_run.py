from stock_maintainance.features import build as feature_build


def test_build_features_dry_run_does_not_open_database(monkeypatch) -> None:
    def fail_connect():
        raise AssertionError("dry-run must not open DuckDB")

    monkeypatch.setattr(feature_build, "connect", fail_connect)

    result = feature_build.build_features(
        modules=["daily_spine"],
        end_date="2026-05-26",
        dry_run=True,
    )

    assert result["plan"]["execution_order"] == ["daily_spine"]
    assert result["results"][0]["status"] == "dry_run"


def test_low_frequency_modules_dry_run_use_unified_builder_without_database(monkeypatch) -> None:
    def fail_connect():
        raise AssertionError("dry-run must not open DuckDB")

    monkeypatch.setattr(feature_build, "connect", fail_connect)

    result = feature_build.build_features(
        modules=["corporate_action", "ownership_governance"],
        end_date="2026-05-26",
        dry_run=True,
    )

    by_module = {item["module"]: item for item in result["results"]}
    assert by_module["corporate_action"]["status"] == "dry_run"
    assert "build_phase3_corporate_action_core.py" in by_module["corporate_action"]["message"]
    assert by_module["ownership_governance"]["status"] == "dry_run"
    assert "build_phase3_ownership_governance_core.py" in by_module["ownership_governance"]["message"]


def test_context_modules_dry_run_use_phase3_backends_without_database(monkeypatch) -> None:
    def fail_connect():
        raise AssertionError("dry-run must not open DuckDB")

    monkeypatch.setattr(feature_build, "connect", fail_connect)

    result = feature_build.build_features(
        modules=["sector_concept_context", "index_market_context", "cross_sectional"],
        end_date="2026-05-26",
        dry_run=True,
    )

    by_module = {item["module"]: item for item in result["results"]}
    assert by_module["sector_concept_context"]["status"] == "dry_run"
    assert "build_phase3_sector_concept_core.py" in by_module["sector_concept_context"]["message"]
    assert by_module["index_market_context"]["status"] == "dry_run"
    assert "build_phase3_index_market_core.py" in by_module["index_market_context"]["message"]
    assert by_module["cross_sectional"]["status"] == "dry_run"
    assert "build_phase3_cross_sectional_core.py" in by_module["cross_sectional"]["message"]


def test_composite_state_dry_run_uses_phase3_backend_without_database(monkeypatch) -> None:
    def fail_connect():
        raise AssertionError("dry-run must not open DuckDB")

    monkeypatch.setattr(feature_build, "connect", fail_connect)

    result = feature_build.build_features(
        modules=["composite_state"],
        end_date="2026-05-26",
        dry_run=True,
    )

    by_module = {item["module"]: item for item in result["results"]}
    assert by_module["composite_state"]["status"] == "dry_run"
    assert "build_phase3_composite_state_core.py" in by_module["composite_state"]["message"]


def test_sector_context_dry_run_reports_required_cache_steps_without_database(monkeypatch) -> None:
    def fail_connect():
        raise AssertionError("dry-run must not open DuckDB")

    monkeypatch.setattr(feature_build, "connect", fail_connect)

    result = feature_build.build_features(
        modules=["sector_concept_context"],
        end_date="2026-05-26",
        dry_run=True,
    )

    cache_names = [item["name"] for item in result["cache_results"]]
    assert cache_names == ["sector_index_caches", "concept_stock_context_cache"]
    assert all(item["status"] == "dry_run" for item in result["cache_results"])


def test_shared_cache_step_is_reported_once_in_dry_run(monkeypatch) -> None:
    def fail_connect():
        raise AssertionError("dry-run must not open DuckDB")

    monkeypatch.setattr(feature_build, "connect", fail_connect)

    result = feature_build.build_features(
        modules=["sector_concept_context", "index_market_context"],
        end_date="2026-05-26",
        dry_run=True,
    )

    cache_names = [item["name"] for item in result["cache_results"]]
    assert cache_names.count("sector_index_caches") == 1
    assert "concept_stock_context_cache" in cache_names


def test_cache_steps_can_be_skipped_in_dry_run(monkeypatch) -> None:
    def fail_connect():
        raise AssertionError("dry-run must not open DuckDB")

    monkeypatch.setattr(feature_build, "connect", fail_connect)

    result = feature_build.build_features(
        modules=["valuation_size"],
        end_date="2026-05-26",
        dry_run=True,
        run_cache_steps=False,
    )

    assert result["cache_results"] == []


def test_required_cache_steps_cannot_be_skipped_for_real_build(monkeypatch) -> None:
    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            raise RuntimeError("calendar unavailable")

    monkeypatch.setattr(feature_build, "connect", lambda: _Conn())
    monkeypatch.setattr(feature_build, "init_database", lambda con: None)

    try:
        feature_build.build_features(
            modules=["valuation_size"],
            end_date="2026-05-26",
            run_cache_steps=False,
        )
    except ValueError as exc:
        assert "cannot skip required cache steps" in str(exc)
        assert "valuation_size" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("expected ValueError")


def test_feature_build_results_do_not_use_built_status() -> None:
    from pathlib import Path

    source = Path("src/stock_maintainance/features/modules.py").read_text(encoding="utf-8")

    assert 'status="built"' not in source
    assert "status='built'" not in source
