from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .database import connect
from .docs import check_docs, generate_docs
from .paths import REPORTS_DIR, ROOT
from .schema import quote_ident


FEATURE_VIEWS = [
    "stock_features_core",
    "stock_features_plus",
    "stock_features_full",
]

SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
GLOBAL_DICTIONARY_PATH = ROOT / "outputs" / "variable_dictionary" / "global_variable_dictionary.xlsx"
DEFAULT_WINDOWS_NODE_PATH = Path("/mnt/c/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe")


@dataclass(frozen=True)
class RefreshDictionaryResult:
    report: dict[str, Any]
    json_path: Path

    @property
    def passed(self) -> bool:
        return self.report["summary"]["status"] == "pass"


def _to_windows_path(path: Path) -> str:
    resolved = path.resolve()
    text = str(resolved)
    if text.startswith("/mnt/") and len(text) > 6:
        drive = text[5].upper()
        rest = text[7:].replace("/", "\\")
        return f"{drive}:\\{rest}"
    return text


def sync_feature_view_schema_registry() -> dict[str, int]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    tables = {table["name"]: table for table in schema["tables"]}
    counts: dict[str, int] = {}
    with connect() as con:
        for view in FEATURE_VIEWS:
            if view not in tables:
                raise ValueError(f"{view} is not registered in schema_registry.json")
            registered = tables[view]
            old_fields = {field["name"]: field for field in registered.get("fields", [])}
            new_fields = []
            for _, name, dtype, nullable, *_ in con.execute(f"PRAGMA table_info({quote_ident(view)})").fetchall():
                if name in old_fields:
                    field = {**old_fields[name], "dtype": str(dtype), "nullable": bool(nullable)}
                else:
                    field = {
                        "name": name,
                        "dtype": str(dtype),
                        "nullable": bool(nullable),
                        "description": f"{view}.{name} 统一出口字段",
                    }
                new_fields.append(field)
            registered["fields"] = new_fields
            registered["primary_key"] = ["ts_code", "trade_date"]
            registered["table_type"] = "view"
            registered["description"] = f"{view} unified feature export view"
            counts[view] = len(new_fields)
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return counts


def _run_global_dictionary_builder(*, node_path: Path = DEFAULT_WINDOWS_NODE_PATH) -> dict[str, Any]:
    script = ROOT / "scripts" / "build_global_variable_dictionary.mjs"
    if not node_path.exists():
        raise ValueError(f"Windows Node executable not found: {node_path}")
    command = (
        f"Set-Location '{_to_windows_path(ROOT)}'; "
        f"& '{_to_windows_path(node_path)}' '{_to_windows_path(script)}'"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "path": str(GLOBAL_DICTIONARY_PATH),
        "exists": GLOBAL_DICTIONARY_PATH.exists(),
    }


def refresh_dictionary(
    *,
    build_excel: bool = True,
    skip_feature_schema_sync: bool = False,
    output_prefix: str = "refresh_dictionary",
) -> RefreshDictionaryResult:
    steps: list[dict[str, Any]] = []
    if skip_feature_schema_sync:
        steps.append({"name": "sync-feature-view-schema", "status": "skipped"})
        feature_counts = {}
    else:
        feature_counts = sync_feature_view_schema_registry()
        steps.append({"name": "sync-feature-view-schema", "status": "done", "detail": feature_counts})

    generated = generate_docs()
    steps.append({"name": "docs-generate", "status": "done", "detail": [str(path) for path in generated]})

    excel_payload = None
    if build_excel:
        excel_payload = _run_global_dictionary_builder()
        steps.append({"name": "build-global-variable-dictionary", "status": "done", "detail": excel_payload})
    else:
        steps.append({"name": "build-global-variable-dictionary", "status": "skipped"})

    docs_diffs = check_docs()
    steps.append({"name": "docs-check", "status": "pass" if not docs_diffs else "fail", "detail": docs_diffs})

    status = "pass" if not docs_diffs and (not build_excel or GLOBAL_DICTIONARY_PATH.exists()) else "fail"
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "feature_view_field_counts": feature_counts,
        "global_dictionary_path": str(GLOBAL_DICTIONARY_PATH),
        "steps": steps,
        "summary": {
            "status": status,
            "build_excel": build_excel,
            "docs_diff_count": len(docs_diffs),
            "global_dictionary_exists": GLOBAL_DICTIONARY_PATH.exists(),
        },
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"{output_prefix}.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return RefreshDictionaryResult(report=report, json_path=json_path)
