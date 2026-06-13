from __future__ import annotations

from pathlib import Path
from datetime import UTC, datetime
import time
from typing import Any

import duckdb
import pandas as pd

from .config import load_schema_registry, load_sources
from .paths import DATA_DIR, LOGS_DIR, REPORTS_DIR
from .schema import all_create_table_sql, create_table_sql, field_sql, quote_ident


DB_PATH = DATA_DIR / "duckdb" / "stock_data.duckdb"
CONNECT_RETRY_ATTEMPTS = 5
CONNECT_RETRY_SLEEP_SECONDS = 0.5


def ensure_runtime_dirs() -> None:
    for path in [
        DATA_DIR,
        DATA_DIR / "duckdb",
        DATA_DIR / "parquet",
        DATA_DIR / "snapshots",
        LOGS_DIR,
        REPORTS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    ensure_runtime_dirs()
    last_error: Exception | None = None
    for attempt in range(CONNECT_RETRY_ATTEMPTS):
        try:
            con = duckdb.connect(str(db_path))
            break
        except duckdb.IOException as exc:
            last_error = exc
            if attempt == CONNECT_RETRY_ATTEMPTS - 1:
                raise
            time.sleep(CONNECT_RETRY_SLEEP_SECONDS * (attempt + 1))
    else:
        raise last_error or RuntimeError("failed to connect to DuckDB")
    try:
        con.execute("SET lock_timeout='30s'")
    except duckdb.CatalogException:
        pass
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    return con


def init_database(con: duckdb.DuckDBPyConnection | None = None) -> None:
    close = con is None
    con = con or connect()
    try:
        registry = load_schema_registry()
        con.execute(all_create_table_sql(registry))
        reconcile_schema(con, registry)
        _seed_source_api(con)
    finally:
        if close:
            con.close()


def _seed_source_api(con: duckdb.DuckDBPyConnection) -> None:
    existing = {
        row[0]: row[1]
        for row in con.execute(
            """
            SELECT api_name, status
            FROM metadata_source_api
            WHERE source_name = 'tushare'
            """
        ).fetchall()
    }
    rows = []
    for api in load_sources()["tushare"]["apis"]:
        rows.append(
            {
                "source_name": "tushare",
                "api_name": api["name"],
                "domain": api["domain"],
                "phase": api["phase"],
                "status": existing.get(api["name"], "planned"),
            }
        )
    df = pd.DataFrame(rows)
    upsert_dataframe(con, "metadata_source_api", df, ["source_name", "api_name"])


def reconcile_schema(con: duckdb.DuckDBPyConnection, registry: dict[str, Any] | None = None) -> None:
    registry = registry or load_schema_registry()
    for table in registry.get("tables", []):
        if table.get("table_type") == "view":
            continue
        table_name = table["name"]
        current = set(table_columns(con, table_name))
        missing = [field for field in table.get("fields", []) if field["name"] not in current]
        if table_name == "derived_financial_growth" and len(missing) > 100:
            row_count = con.execute(f"SELECT count(*) FROM {quote_ident(table_name)}").fetchone()[0]
            if row_count:
                raise RuntimeError(
                    "derived_financial_growth schema is incompatible with registry "
                    f"({len(missing)} missing columns, {row_count} existing rows). "
                    "Run the explicit financial growth rebuild/migration instead of init-time reconcile."
                )
            con.execute(f"DROP TABLE IF EXISTS {quote_ident(table_name)}")
            con.execute(create_table_sql(table))
            continue
        for field in table.get("fields", []):
            name = field["name"]
            if name in current:
                continue
            if not field.get("nullable", True) and not field.get("default"):
                raise ValueError(f"cannot add NOT NULL field without default: {table_name}.{name}")
            con.execute(f"ALTER TABLE {quote_ident(table_name)} ADD COLUMN {field_sql(field)}")


def refresh_source_api_status(con: duckdb.DuckDBPyConnection) -> None:
    registry = load_schema_registry()
    api_tables: dict[str, set[str]] = {}
    for table in registry.get("tables", []):
        for field in table.get("fields", []):
            api_name = field.get("source_api")
            if api_name and api_name != "local_derived":
                api_tables.setdefault(api_name, set()).add(table["name"])

    financial_event_apis = {
        row[0]
        for row in con.execute(
            """
            SELECT DISTINCT api_name
            FROM financial_event_raw
            WHERE api_name IS NOT NULL
            """
        ).fetchall()
    }
    failed_tasks = {
        row[0]
        for row in con.execute(
            """
            SELECT DISTINCT task_name
            FROM metadata_task_failure
            """
        ).fetchall()
    }

    rows = []
    for api in load_sources()["tushare"]["apis"]:
        api_name = api["name"]
        status = "planned"
        if api_name in financial_event_apis or any(_table_has_rows(con, table) for table in api_tables.get(api_name, [])):
            status = "success"
        elif any(api_name in task for task in failed_tasks):
            status = "failure"
        rows.append(
            {
                "source_name": "tushare",
                "api_name": api_name,
                "domain": api["domain"],
                "phase": api["phase"],
                "status": status,
            }
        )
    upsert_dataframe(con, "metadata_source_api", pd.DataFrame(rows), ["source_name", "api_name"])


def _table_has_rows(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    try:
        return bool(con.execute(f"SELECT EXISTS(SELECT 1 FROM {quote_ident(table_name)} LIMIT 1)").fetchone()[0])
    except duckdb.CatalogException:
        return False


def table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
    rows = con.execute(f"PRAGMA table_info({quote_ident(table_name)})").fetchall()
    return [row[1] for row in rows]


def upsert_dataframe(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    df: pd.DataFrame,
    primary_key: list[str],
) -> int:
    if df.empty:
        return 0
    columns = table_columns(con, table_name)
    payload = df[[col for col in columns if col in df.columns]].copy()
    if payload.empty:
        return 0
    payload = payload.drop_duplicates(subset=primary_key, keep="last")

    temp_name = f"tmp_{table_name}"
    con.register(temp_name, payload)
    try:
        quoted_table = quote_ident(table_name)
        quoted_temp = quote_ident(temp_name)
        key_join = " AND ".join(f"t.{quote_ident(col)} = s.{quote_ident(col)}" for col in primary_key)
        col_sql = ", ".join(quote_ident(col) for col in payload.columns)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"DELETE FROM {quoted_table} t USING {quoted_temp} s WHERE {key_join}")
            con.execute(f"INSERT INTO {quoted_table} ({col_sql}) SELECT {col_sql} FROM {quoted_temp}")
        except Exception:
            con.execute("ROLLBACK")
            raise
        else:
            con.execute("COMMIT")
    finally:
        con.unregister(temp_name)
    return len(payload)


def fetch_task_state(
    con: duckdb.DuckDBPyConnection,
    task_name: str,
    task_key: str,
) -> dict[str, Any] | None:
    rows = con.execute(
        """
        SELECT task_name, task_key, status, checkpoint_value, row_count, error_message
        FROM metadata_task_state
        WHERE task_name = ? AND task_key = ?
        """,
        [task_name, task_key],
    ).fetchall()
    if not rows:
        return None
    keys = ["task_name", "task_key", "status", "checkpoint_value", "row_count", "error_message"]
    return dict(zip(keys, rows[0]))


def record_task_state(
    con: duckdb.DuckDBPyConnection,
    task_name: str,
    task_key: str,
    status: str,
    checkpoint_value: str | None = None,
    row_count: int = 0,
    error_message: str | None = None,
) -> None:
    df = pd.DataFrame(
        [
            {
                "task_name": task_name,
                "task_key": task_key,
                "status": status,
                "checkpoint_value": checkpoint_value,
                "row_count": row_count,
                "error_message": error_message,
            }
        ]
    )
    upsert_dataframe(con, "metadata_task_state", df, ["task_name", "task_key"])


def record_task_failure(
    con: duckdb.DuckDBPyConnection,
    task_name: str,
    task_key: str,
    error_message: str,
    retryable: bool = True,
) -> None:
    failed_at = datetime.now(UTC).replace(tzinfo=None)
    df = pd.DataFrame(
        [
            {
                "task_name": task_name,
                "task_key": task_key,
                "failed_at": failed_at,
                "error_message": error_message[:4000],
                "retryable": retryable,
            }
        ]
    )
    upsert_dataframe(con, "metadata_task_failure", df, ["task_name", "task_key", "failed_at"])
