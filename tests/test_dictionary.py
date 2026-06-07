from __future__ import annotations

import json

from stock_maintainance import dictionary


def test_to_windows_path_converts_wsl_mount() -> None:
    assert dictionary._to_windows_path(dictionary.Path("/mnt/d/Opencode Workspace/Stock_Maintainance")).startswith(
        "D:\\"
    )


def test_refresh_dictionary_skip_excel(tmp_path, monkeypatch) -> None:
    schema_path = tmp_path / "schema_registry.json"
    schema_path.write_text(
        json.dumps(
            {
                "tables": [
                    {"name": "stock_features_core", "fields": [], "primary_key": [], "table_type": "view"},
                    {"name": "stock_features_plus", "fields": [], "primary_key": [], "table_type": "view"},
                    {"name": "stock_features_full", "fields": [], "primary_key": [], "table_type": "view"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dictionary, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(dictionary, "SCHEMA_PATH", schema_path)
    monkeypatch.setattr(dictionary, "GLOBAL_DICTIONARY_PATH", tmp_path / "global_variable_dictionary.xlsx")
    monkeypatch.setattr(dictionary, "sync_feature_view_schema_registry", lambda: {"stock_features_core": 1})
    monkeypatch.setattr(dictionary, "generate_docs", lambda: [tmp_path / "generated_schema_dictionary.md"])
    monkeypatch.setattr(dictionary, "check_docs", lambda: [])

    result = dictionary.refresh_dictionary(build_excel=False, output_prefix="refresh")

    assert result.passed
    assert result.report["feature_view_field_counts"] == {"stock_features_core": 1}
    assert result.report["summary"]["build_excel"] is False
    assert result.json_path.exists()
