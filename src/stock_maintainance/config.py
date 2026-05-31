from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import CONFIG_DIR


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources() -> dict[str, Any]:
    return load_json(CONFIG_DIR / "sources.json")


def load_pipeline() -> dict[str, Any]:
    return load_json(CONFIG_DIR / "pipeline.json")


def load_schema_registry() -> dict[str, Any]:
    return load_json(CONFIG_DIR / "schema_registry.json")


def load_variable_registry() -> dict[str, Any]:
    variables: list[dict[str, Any]] = []
    for path in sorted((CONFIG_DIR / "variables").glob("*.json")):
        payload = load_json(path)
        variables.extend(payload.get("variables", []))
    return {"variables": variables}
