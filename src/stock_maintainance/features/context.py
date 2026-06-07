from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class FeatureBuildContext:
    con: duckdb.DuckDBPyConnection | None
    module: str
    read_start_date: str
    write_start_date: str
    write_end_date: str
    dry_run: bool = False
