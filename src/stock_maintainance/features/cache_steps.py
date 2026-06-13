from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import time

from .modules import _load_phase3_script


REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports"


@dataclass(frozen=True)
class CacheStepResult:
    name: str
    phase: str
    status: str
    rows_written: int = 0
    message: str = ""
    summary: dict[str, int] | None = None
    elapsed_seconds: float | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "phase": self.phase,
            "status": self.status,
            "rows_written": self.rows_written,
            "message": self.message,
            "summary": self.summary or {},
            "elapsed_seconds": self.elapsed_seconds,
            "details": self.details or {},
        }


def _write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sum_rows(summary: dict[str, int]) -> int:
    return int(sum(summary.values()))


def _insert_sql_to_temp(sql: str, table_name: str, temp_name: str) -> str:
    marker = f"INSERT INTO {table_name}"
    if marker not in sql:
        raise ValueError(f"cannot convert insert SQL for {table_name}")
    return sql.replace(marker, f"CREATE OR REPLACE TEMP TABLE {temp_name} AS", 1)


def _temp_columns(con: duckdb.DuckDBPyConnection, temp_name: str) -> list[str]:
    return [str(row[1]) for row in con.execute(f"PRAGMA table_info({temp_name})").fetchall()]


def _upsert_daily_cache_from_temp(
    con: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    temp_name: str,
    key_columns: list[str],
    qfunc,
) -> None:
    columns = _temp_columns(con, temp_name)
    value_columns = [col for col in columns if col not in set(key_columns)]
    set_sql = ", ".join(f"{qfunc(col)} = d.{qfunc(col)}" for col in value_columns)
    join_sql = " AND ".join(f"c.{qfunc(col)} = d.{qfunc(col)}" for col in key_columns)
    changed_sql = " OR ".join(f"c.{qfunc(col)} IS DISTINCT FROM d.{qfunc(col)}" for col in value_columns)
    con.execute(
        f"""
        UPDATE {qfunc(table_name)} AS c
        SET {set_sql}
        FROM {qfunc(temp_name)} AS d
        WHERE {join_sql}
          AND ({changed_sql})
        """
    )
    col_sql = ", ".join(qfunc(col) for col in columns)
    select_sql = ", ".join("d." + qfunc(col) for col in columns)
    con.execute(
        f"""
        INSERT INTO {qfunc(table_name)} ({col_sql})
        SELECT {select_sql}
        FROM {qfunc(temp_name)} AS d
        LEFT JOIN {qfunc(table_name)} AS c
          ON {join_sql}
        WHERE c.{qfunc(key_columns[0])} IS NULL
        """
    )


def dry_run_cache_step(name: str, phase: str, start: str, end: str, message: str) -> CacheStepResult:
    return CacheStepResult(
        name=name,
        phase=phase,
        status="dry_run",
        rows_written=0,
        message=f"would refresh {name} from {start} to {end}; {message}",
    )


def refresh_capital_flow_caches(con: duckdb.DuckDBPyConnection, start: str, end: str) -> CacheStepResult:
    stage_seconds: dict[str, float] = {}
    stage_started = time.perf_counter()
    backend = _load_phase3_script("build_phase3_capital_flow_caches.py")
    stage_seconds["load_backend"] = round(time.perf_counter() - stage_started, 3)
    started_at = datetime.now().isoformat(timespec="seconds")
    context_days = 520
    stage_started = time.perf_counter()
    read_start = backend.resolve_read_start(con, start, context_days)
    stage_seconds["resolve_read_start"] = round(time.perf_counter() - stage_started, 3)
    jobs = [
        ("derived_northbound_flow_cache", backend.north_cache_sql(start, end, read_start)),
        ("derived_capital_flow_event_cache", backend.event_cache_sql(start, end, read_start)),
    ]
    summary: dict[str, int] = {}
    for table, sql in jobs:
        con.execute("BEGIN TRANSACTION")
        try:
            stage_started = time.perf_counter()
            backend.delete_table_window(con, table, start, end)
            stage_seconds[f"{table}.delete"] = round(time.perf_counter() - stage_started, 3)
            stage_started = time.perf_counter()
            con.execute(sql)
            stage_seconds[f"{table}.insert"] = round(time.perf_counter() - stage_started, 3)
            stage_started = time.perf_counter()
            con.execute("COMMIT")
            stage_seconds[f"{table}.commit"] = round(time.perf_counter() - stage_started, 3)
        except Exception:
            con.execute("ROLLBACK")
            raise
        stage_started = time.perf_counter()
        summary[table] = backend.table_count(con, table, start, end)
        stage_seconds[f"{table}.count"] = round(time.perf_counter() - stage_started, 3)
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "window",
        "start_date": start,
        "end_date": end,
        "read_start_date": read_start,
        "context_days": context_days,
        "summary": summary,
        "trigger": "build-features",
        "stage_seconds": stage_seconds,
    }
    _write_json_report(REPORTS_DIR / "phase3_capital_flow_cache_run.json", payload)
    return CacheStepResult(
        "capital_flow_caches",
        "post",
        "success",
        _sum_rows(summary),
        summary=summary,
        details={"stage_seconds": stage_seconds},
    )


def refresh_sector_index_caches(
    con: duckdb.DuckDBPyConnection,
    start: str,
    end: str,
    *,
    profile: str = "daily-core",
) -> CacheStepResult:
    stage_seconds: dict[str, float] = {}
    stage_started = time.perf_counter()
    backend = _load_phase3_script("build_phase3_sector_index_caches.py")
    stage_seconds["load_backend"] = round(time.perf_counter() - stage_started, 3)
    started_at = datetime.now().isoformat(timespec="seconds")
    context_days = 260 if profile == "daily-core" else 260
    stage_started = time.perf_counter()
    read_start = backend.resolve_read_start(con, start, context_days)
    stage_seconds["resolve_read_start"] = round(time.perf_counter() - stage_started, 3)
    if profile == "daily-core":
        saved_full_periods = list(backend.FULL_PERIODS)
        saved_vol_periods = list(backend.VOL_PERIODS)
        try:
            backend.FULL_PERIODS = [5, 20, 60, 120]
            sector_sql = backend.sector_cache_sql(start, end, read_start)
            backend.FULL_PERIODS = [20]
            concept_sql = backend.concept_cache_sql(start, end, read_start)
            backend.FULL_PERIODS = [5, 20, 60, 120]
            backend.VOL_PERIODS = [5, 20, 60, 120]
            index_sql = backend.index_daily_cache_sql(start, end, read_start)
        finally:
            backend.FULL_PERIODS = saved_full_periods
            backend.VOL_PERIODS = saved_vol_periods
        jobs = [
            ("derived_sector_daily_cache", "sector_delta", sector_sql, ["industry_level", "industry_code", "trade_date"]),
            ("derived_concept_daily_cache", "concept_delta", concept_sql, ["concept_id", "trade_date"]),
            ("derived_index_daily_cache", "index_delta", index_sql, ["index_code", "trade_date"]),
            ("derived_index_membership_cache", "index_membership_delta", backend.index_membership_cache_sql(start, end, read_start), ["ts_code", "trade_date"]),
        ]
    else:
        jobs = [
            ("derived_sector_daily_cache", None, backend.sector_cache_sql(start, end, read_start), []),
            ("derived_concept_daily_cache", None, backend.concept_cache_sql(start, end, read_start), []),
            ("derived_index_daily_cache", None, backend.index_daily_cache_sql(start, end, read_start), []),
            ("derived_index_membership_cache", None, backend.index_membership_cache_sql(start, end, read_start), []),
        ]
    summary: dict[str, int] = {}
    for table, temp_name, sql, key_columns in jobs:
        if profile == "daily-core" and temp_name is not None:
            stage_started = time.perf_counter()
            con.execute(_insert_sql_to_temp(sql, table, temp_name))
            stage_seconds[f"{table}.delta"] = round(time.perf_counter() - stage_started, 3)
        con.execute("BEGIN TRANSACTION")
        try:
            if profile == "daily-core" and temp_name is not None:
                stage_started = time.perf_counter()
                _upsert_daily_cache_from_temp(
                    con,
                    table_name=table,
                    temp_name=temp_name,
                    key_columns=key_columns,
                    qfunc=backend.q,
                )
                stage_seconds[f"{table}.upsert"] = round(time.perf_counter() - stage_started, 3)
            else:
                stage_started = time.perf_counter()
                backend.delete_table_window(con, table, start, end)
                stage_seconds[f"{table}.delete"] = round(time.perf_counter() - stage_started, 3)
                stage_started = time.perf_counter()
                con.execute(sql)
                stage_seconds[f"{table}.insert"] = round(time.perf_counter() - stage_started, 3)
            stage_started = time.perf_counter()
            con.execute("COMMIT")
            stage_seconds[f"{table}.commit"] = round(time.perf_counter() - stage_started, 3)
        except Exception:
            con.execute("ROLLBACK")
            raise
        stage_started = time.perf_counter()
        summary[table] = backend.table_count(con, table, start, end)
        stage_seconds[f"{table}.count"] = round(time.perf_counter() - stage_started, 3)
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "window",
        "profile": profile,
        "start_date": start,
        "end_date": end,
        "read_start_date": read_start,
        "context_days": context_days,
        "summary": summary,
        "trigger": "build-features",
        "stage_seconds": stage_seconds,
    }
    _write_json_report(REPORTS_DIR / "phase3_sector_index_cache_run.json", payload)
    return CacheStepResult(
        "sector_index_caches",
        "pre",
        "success",
        _sum_rows(summary),
        summary=summary,
        details={"profile": profile, "stage_seconds": stage_seconds},
    )


def refresh_concept_stock_context_cache(
    con: duckdb.DuckDBPyConnection,
    start: str,
    end: str,
    *,
    profile: str = "daily-core",
) -> CacheStepResult:
    stage_seconds: dict[str, float] = {}
    stage_started = time.perf_counter()
    backend = _load_phase3_script("build_phase3_concept_stock_context_cache.py")
    stage_seconds["load_backend"] = round(time.perf_counter() - stage_started, 3)
    started_at = datetime.now().isoformat(timespec="seconds")
    table = "derived_concept_stock_context_cache"
    if profile == "daily-core":
        columns = backend.daily_core_columns()
        stage_seconds["table_fields"] = 0.0
    else:
        stage_started = time.perf_counter()
        columns = backend.table_fields(table)
        stage_seconds["table_fields"] = round(time.perf_counter() - stage_started, 3)

    def timed(stage: str, sql: str) -> None:
        stage_started = time.perf_counter()
        con.execute(sql)
        stage_seconds[stage] = round(time.perf_counter() - stage_started, 3)

    timed("concept_static", backend.static_temp_sql(start, end))
    if profile == "daily-core":
        timed("concept_period_all", backend.combined_period_temp_sql(start, end, backend.DAILY_CORE_PERIODS))
        timed("core_delta", backend.core_delta_temp_sql(start, end))
    else:
        timed("concept_period_all", backend.combined_period_temp_sql(start, end))
    con.execute("BEGIN TRANSACTION")
    try:
        if profile == "daily-core":
            timed("update_core", backend.update_daily_core_sql(columns))
            timed("insert_missing_core", backend.insert_missing_daily_core_sql(columns))
        else:
            stage_started = time.perf_counter()
            backend.delete_table_window(con, table, start, end)
            stage_seconds["delete_window"] = round(time.perf_counter() - stage_started, 3)
            timed("insert_cache", backend.insert_combined_sql(start, end, columns))
        stage_started = time.perf_counter()
        con.execute("COMMIT")
        stage_seconds["commit"] = round(time.perf_counter() - stage_started, 3)
    except Exception:
        con.execute("ROLLBACK")
        raise
    stage_started = time.perf_counter()
    rows = backend.count_table_window(con, table, start, end)
    stage_seconds["count_rows"] = round(time.perf_counter() - stage_started, 3)
    summary = {table: rows}
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "window",
        "profile": profile,
        "start_date": start,
        "end_date": end,
        "summary": summary,
        "trigger": "build-features",
        "stage_seconds": stage_seconds,
    }
    stage_started = time.perf_counter()
    _write_json_report(REPORTS_DIR / "phase3_concept_stock_context_cache_run.json", payload)
    stage_seconds["write_report"] = round(time.perf_counter() - stage_started, 3)
    return CacheStepResult(
        "concept_stock_context_cache",
        "pre",
        "success",
        rows,
        summary=summary,
        details={"profile": profile, "stage_seconds": stage_seconds},
    )


def refresh_valuation_percentile_cache(
    con: duckdb.DuckDBPyConnection,
    start: str,
    end: str,
    *,
    profile: str = "daily-core",
) -> CacheStepResult:
    backend = _load_phase3_script("backfill_valuation_percentile_cache.py")
    started_at = datetime.now().isoformat(timespec="seconds")
    active_sources = backend.DAILY_CORE_SOURCES if profile == "daily-core" else backend.SOURCES
    active_windows = backend.DAILY_CORE_WINDOWS if profile == "daily-core" else backend.WINDOWS
    context_days = max(active_windows.values()) * 2
    read_start = backend.resolve_read_start(con, start, context_days)
    stage_seconds: dict[str, float] = {}
    if profile == "daily-core":
        pct_columns = ["pe_ttm_pct_5y", "pb_pct_5y", "ps_ttm_pct_5y", "total_mv_pct_5y"]
        stage_started = time.perf_counter()
        con.execute(
            """
            CREATE OR REPLACE TEMP TABLE valuation_percentile_cache_df AS
            WITH context AS (
                SELECT
                    ts_code,
                    trade_date,
                    pe_ttm,
                    pb,
                    ps_ttm,
                    total_mv,
                    row_number() OVER (PARTITION BY ts_code ORDER BY trade_date) AS rn
                FROM derived_valuation_size
                WHERE trade_date BETWEEN ? AND ?
            ),
            targets AS (
                SELECT *
                FROM context
                WHERE trade_date BETWEEN ? AND ?
            )
            SELECT
                t.ts_code,
                t.trade_date,
                CASE WHEN t.pe_ttm > 0 AND count(CASE WHEN c.pe_ttm > 0 THEN c.pe_ttm END) >= 60
                     THEN (
                         sum(CASE WHEN c.pe_ttm > 0 AND c.pe_ttm < t.pe_ttm THEN 1 ELSE 0 END)
                       + (sum(CASE WHEN c.pe_ttm > 0 AND c.pe_ttm = t.pe_ttm THEN 1 ELSE 0 END) + 1) / 2.0
                     ) / count(CASE WHEN c.pe_ttm > 0 THEN c.pe_ttm END) ELSE NULL END AS pe_ttm_pct_5y,
                CASE WHEN t.pb > 0 AND count(CASE WHEN c.pb > 0 THEN c.pb END) >= 60
                     THEN (
                         sum(CASE WHEN c.pb > 0 AND c.pb < t.pb THEN 1 ELSE 0 END)
                       + (sum(CASE WHEN c.pb > 0 AND c.pb = t.pb THEN 1 ELSE 0 END) + 1) / 2.0
                     ) / count(CASE WHEN c.pb > 0 THEN c.pb END) ELSE NULL END AS pb_pct_5y,
                CASE WHEN t.ps_ttm > 0 AND count(CASE WHEN c.ps_ttm > 0 THEN c.ps_ttm END) >= 60
                     THEN (
                         sum(CASE WHEN c.ps_ttm > 0 AND c.ps_ttm < t.ps_ttm THEN 1 ELSE 0 END)
                       + (sum(CASE WHEN c.ps_ttm > 0 AND c.ps_ttm = t.ps_ttm THEN 1 ELSE 0 END) + 1) / 2.0
                     ) / count(CASE WHEN c.ps_ttm > 0 THEN c.ps_ttm END) ELSE NULL END AS ps_ttm_pct_5y,
                CASE WHEN t.total_mv > 0 AND count(CASE WHEN c.total_mv > 0 THEN c.total_mv END) >= 60
                     THEN (
                         sum(CASE WHEN c.total_mv > 0 AND c.total_mv < t.total_mv THEN 1 ELSE 0 END)
                       + (sum(CASE WHEN c.total_mv > 0 AND c.total_mv = t.total_mv THEN 1 ELSE 0 END) + 1) / 2.0
                     ) / count(CASE WHEN c.total_mv > 0 THEN c.total_mv END) ELSE NULL END AS total_mv_pct_5y
            FROM targets t
            JOIN context c
              ON t.ts_code = c.ts_code
             AND c.rn BETWEEN t.rn - 1249 AND t.rn
            GROUP BY t.ts_code, t.trade_date, t.pe_ttm, t.pb, t.ps_ttm, t.total_mv
            """,
            [read_start, end, start, end],
        )
        stage_seconds["compute_daily_core_sql"] = round(time.perf_counter() - stage_started, 3)
    else:
        stage_started = time.perf_counter()
        df = backend.load_valuation_frame(con, read_start, end, active_sources)
        grouped = df.groupby("ts_code", sort=False)
        pct_columns = []
        for source in active_sources:
            for alias, window in active_windows.items():
                target = f"{source}_pct_{alias}"
                df[target] = grouped[source].transform(lambda series, w=window: series.where(series > 0).rolling(w, min_periods=backend.MIN_PERCENTILE_OBS).rank(pct=True))
                pct_columns.append(target)
        write_mask = (df["trade_date"] >= start) & (df["trade_date"] <= end)
        cache_df = df.loc[write_mask, ["ts_code", "trade_date", *pct_columns]].copy()
        con.register("valuation_percentile_cache_df", cache_df)
        stage_seconds["compute_full_pandas"] = round(time.perf_counter() - stage_started, 3)
    columns = ["ts_code", "trade_date", *pct_columns]
    con.execute("BEGIN TRANSACTION")
    try:
        if profile == "daily-core":
            if not backend.table_exists(con, "derived_valuation_percentile_cache"):
                raise ValueError("daily-core requires existing derived_valuation_percentile_cache; run full cache first")
            set_sql = ", ".join(f"{backend.q(col)} = p.{backend.q(col)}" for col in pct_columns)
            stage_started = time.perf_counter()
            con.execute(
                f"""
                UPDATE derived_valuation_percentile_cache AS c
                SET {set_sql}, updated_at = CURRENT_TIMESTAMP
                FROM valuation_percentile_cache_df AS p
                WHERE c.ts_code = p.ts_code
                  AND c.trade_date = p.trade_date
                  AND (
                    c.pe_ttm_pct_5y IS DISTINCT FROM p.pe_ttm_pct_5y
                    OR c.pb_pct_5y IS DISTINCT FROM p.pb_pct_5y
                    OR c.ps_ttm_pct_5y IS DISTINCT FROM p.ps_ttm_pct_5y
                    OR c.total_mv_pct_5y IS DISTINCT FROM p.total_mv_pct_5y
                  )
                """
            )
            stage_seconds["update_daily_core"] = round(time.perf_counter() - stage_started, 3)
            stage_started = time.perf_counter()
            con.execute(
                f"""
                INSERT INTO derived_valuation_percentile_cache ({", ".join(backend.q(col) for col in columns)}, updated_at)
                SELECT {", ".join("p." + backend.q(col) for col in columns)}, CURRENT_TIMESTAMP AS updated_at
                FROM valuation_percentile_cache_df AS p
                LEFT JOIN derived_valuation_percentile_cache AS c
                  ON p.ts_code = c.ts_code
                 AND p.trade_date = c.trade_date
                WHERE c.ts_code IS NULL
                """
            )
            stage_seconds["insert_missing_daily_core"] = round(time.perf_counter() - stage_started, 3)
        else:
            con.execute(
                f"""
                CREATE TABLE IF NOT EXISTS derived_valuation_percentile_cache AS
                SELECT *, CURRENT_TIMESTAMP AS updated_at
                FROM valuation_percentile_cache_df
                WHERE false
                """
            )
            con.execute("DELETE FROM derived_valuation_percentile_cache WHERE trade_date BETWEEN ? AND ?", [start, end])
            con.execute(
                f"""
                INSERT INTO derived_valuation_percentile_cache ({", ".join(backend.q(col) for col in columns)}, updated_at)
                SELECT {", ".join(backend.q(col) for col in columns)}, CURRENT_TIMESTAMP AS updated_at
                FROM valuation_percentile_cache_df
                """
            )
        stage_started = time.perf_counter()
        con.execute(
            """
            UPDATE derived_valuation_size AS v
            SET
                pe_ttm_pct_5y = c.pe_ttm_pct_5y,
                pb_pct_5y = c.pb_pct_5y,
                ps_ttm_pct_5y = c.ps_ttm_pct_5y,
                total_mv_pct_5y = c.total_mv_pct_5y
            FROM derived_valuation_percentile_cache AS c
            WHERE v.ts_code = c.ts_code
              AND v.trade_date = c.trade_date
              AND v.trade_date BETWEEN ? AND ?
            """,
            [start, end],
        )
        stage_seconds["update_valuation_size"] = round(time.perf_counter() - stage_started, 3)
        stage_started = time.perf_counter()
        con.execute("COMMIT")
        stage_seconds["commit"] = round(time.perf_counter() - stage_started, 3)
    except Exception:
        con.execute("ROLLBACK")
        raise
    summary_row = con.execute(
        """
        SELECT
            count(*) AS rows,
            count(pe_ttm_pct_5y) AS pe_ttm_pct_5y_non_null,
            count(pb_pct_5y) AS pb_pct_5y_non_null,
            count(ps_ttm_pct_5y) AS ps_ttm_pct_5y_non_null,
            count(total_mv_pct_5y) AS total_mv_pct_5y_non_null
        FROM derived_valuation_percentile_cache
        WHERE trade_date BETWEEN ? AND ?
        """,
        [start, end],
    ).fetchone()
    summary = {
        "derived_valuation_percentile_cache": int(summary_row[0]),
        "pe_ttm_pct_5y_non_null": int(summary_row[1]),
        "pb_pct_5y_non_null": int(summary_row[2]),
        "ps_ttm_pct_5y_non_null": int(summary_row[3]),
        "total_mv_pct_5y_non_null": int(summary_row[4]),
    }
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "window",
        "start_date": start,
        "end_date": end,
        "read_start_date": read_start,
        "context_days": context_days,
        "profile": profile,
        "computed_fields": pct_columns,
        "summary": summary,
        "trigger": "build-features",
        "stage_seconds": stage_seconds,
    }
    _write_json_report(REPORTS_DIR / "phase4_valuation_percentile_cache_run.json", payload)
    return CacheStepResult(
        "valuation_percentile_cache",
        "post",
        "success",
        int(summary_row[0]),
        summary=summary,
        details={"profile": profile, "stage_seconds": stage_seconds},
    )
