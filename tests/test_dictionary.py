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


def test_resolve_node_path_prefers_env(monkeypatch, tmp_path) -> None:
    node = tmp_path / "node"
    node.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("STOCK_MAINTAIN_NODE", str(node))
    monkeypatch.setattr(dictionary.shutil, "which", lambda name: None)

    assert dictionary._resolve_node_path(tmp_path / "missing") == node


def test_global_dictionary_builder_error_mentions_skip_excel(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("STOCK_MAINTAIN_NODE", raising=False)
    monkeypatch.setattr(dictionary.shutil, "which", lambda name: None)

    try:
        dictionary._run_global_dictionary_builder(node_path=tmp_path / "missing-node")
    except ValueError as exc:
        assert "--skip-excel" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("expected ValueError")


def test_node_command_uses_powershell_for_windows_node() -> None:
    command = dictionary._node_command(
        dictionary.Path("/mnt/c/Users/Administrator/node.exe"),
        dictionary.Path("/mnt/d/project/scripts/build.mjs"),
    )

    assert command[0] == "powershell.exe"
    assert "node.exe" in command[-1]
