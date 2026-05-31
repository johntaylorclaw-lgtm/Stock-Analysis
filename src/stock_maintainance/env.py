from __future__ import annotations

import os
from pathlib import Path

from .config import load_sources
from .paths import ROOT


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_project_env() -> dict[str, str]:
    values = _read_env_file(ROOT / ".env")
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return values


def get_tushare_token() -> str:
    sources = load_sources()
    token_env = sources["tushare"].get("token_env", "TUSHARE_TOKEN")
    load_project_env()
    token = os.environ.get(token_env)
    if token:
        return token

    fallback = sources["tushare"].get("token_file_fallback")
    if fallback:
        fallback_values = _read_env_file((ROOT / fallback).resolve())
        token = fallback_values.get(token_env)
        if token:
            return token
    raise RuntimeError(f"{token_env} is not configured in project .env")
