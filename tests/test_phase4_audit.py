from pathlib import Path

from stock_maintainance import phase4_audit


def test_phase4_audit_generates_reports(tmp_path, monkeypatch) -> None:
    reports_dir = tmp_path / "reports"
    classification = reports_dir / "phase4_phase3_script_classification.csv"
    classification.parent.mkdir(parents=True)
    classification.write_text(
        "script,classification,notes\n"
        "build_phase3_example.py,windowized_cache_script,ok\n"
        "reset_phase3_example.py,full_rebuild_only,ok\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(phase4_audit, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(phase4_audit, "SCRIPT_CLASSIFICATION_PATH", classification)
    monkeypatch.setattr(phase4_audit, "MODULE_WINDOW_SPEC_PATH", reports_dir / "phase4_module_window_spec.csv")
    monkeypatch.setattr(phase4_audit, "check_docs", lambda: [])

    paths = phase4_audit.run_phase4_audit(end_date="2026-05-26", output_prefix="test_phase4_audit")

    assert paths["json"].exists()
    assert paths["markdown"].exists()
    assert (reports_dir / "phase4_module_window_spec.csv").exists()
    assert "Phase 4 增量性能审计报告" in paths["markdown"].read_text(encoding="utf-8")
