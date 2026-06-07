from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import datetime
from typing import Any

from .cache_steps import (
    CacheStepResult,
    dry_run_cache_step,
    refresh_capital_flow_caches,
    refresh_concept_stock_context_cache,
    refresh_sector_index_caches,
    refresh_valuation_percentile_cache,
)
from .context import FeatureBuildContext
from .modules import BUILDERS, FeatureBuildResult
from .planner import build_feature_plan
from ..config import load_variable_registry
from ..database import connect, init_database
from ..paths import REPORTS_DIR


PRE_CACHE_STEPS = {
    "sector_concept_context": ["sector_index_caches", "concept_stock_context_cache"],
    "index_market_context": ["sector_index_caches"],
}

POST_CACHE_STEPS = {
    "valuation_size": ["valuation_percentile_cache"],
    "capital_flow": ["capital_flow_caches"],
}


def _resolve_trade_calendar_read_start(con: Any, write_start_date: str, context_days: int, fallback: str) -> str:
    """Convert a requested context size into trading-calendar context at runtime."""
    if context_days <= 0:
        return fallback
    try:
        row = con.execute(
            """
            SELECT cal_date
            FROM (
                SELECT
                    cal_date,
                    row_number() OVER (ORDER BY cal_date DESC) AS rn
                FROM trade_calendar
                WHERE is_open = true
                  AND cal_date <= CAST(? AS DATE)
            )
            WHERE rn = ?
            """,
            [write_start_date, context_days + 1],
        ).fetchone()
    except Exception:  # noqa: BLE001 - missing/partial calendars should fall back to planner output.
        return fallback
    if not row or row[0] is None:
        return fallback
    return row[0].isoformat()


def _run_cache_step(name: str, phase: str, ctx: FeatureBuildContext) -> CacheStepResult:
    started = time.perf_counter()
    if ctx.dry_run:
        messages = {
            "valuation_percentile_cache": "daily-core profile updates four 5y compatibility fields",
            "capital_flow_caches": "refreshes northbound and event cache tables",
            "sector_index_caches": "refreshes sector, concept, index and index membership daily caches",
            "concept_stock_context_cache": "daily-core profile updates static concept fields and 20-day concept context",
        }
        result = dry_run_cache_step(name, phase, ctx.write_start_date, ctx.write_end_date, messages.get(name, ""))
        return replace(result, elapsed_seconds=round(time.perf_counter() - started, 3))
    if ctx.con is None:
        raise ValueError("feature build context has no database connection")
    if name == "valuation_percentile_cache":
        result = refresh_valuation_percentile_cache(ctx.con, ctx.write_start_date, ctx.write_end_date, profile="daily-core")
        return replace(result, elapsed_seconds=round(time.perf_counter() - started, 3))
    if name == "capital_flow_caches":
        result = refresh_capital_flow_caches(ctx.con, ctx.write_start_date, ctx.write_end_date)
        return replace(result, elapsed_seconds=round(time.perf_counter() - started, 3))
    if name == "sector_index_caches":
        result = refresh_sector_index_caches(ctx.con, ctx.write_start_date, ctx.write_end_date)
        return replace(result, elapsed_seconds=round(time.perf_counter() - started, 3))
    if name == "concept_stock_context_cache":
        result = refresh_concept_stock_context_cache(ctx.con, ctx.write_start_date, ctx.write_end_date)
        return replace(result, elapsed_seconds=round(time.perf_counter() - started, 3))
    raise ValueError(f"unknown cache step: {name}")


def _run_pre_cache_steps(
    ctx: FeatureBuildContext,
    *,
    enabled: bool,
    executed: set[str],
) -> list[CacheStepResult]:
    if not enabled:
        return []
    results: list[CacheStepResult] = []
    for name in PRE_CACHE_STEPS.get(ctx.module, []):
        if name in executed:
            continue
        results.append(_run_cache_step(name, "pre", ctx))
        executed.add(name)
    return results


def _run_post_cache_steps(
    ctx: FeatureBuildContext,
    *,
    enabled: bool,
    executed: set[str],
) -> list[CacheStepResult]:
    if not enabled:
        return []
    results: list[CacheStepResult] = []
    for name in POST_CACHE_STEPS.get(ctx.module, []):
        if name in executed:
            continue
        results.append(_run_cache_step(name, "post", ctx))
        executed.add(name)
    return results


def build_features(
    *,
    modules: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    mode: str = "daily",
    dry_run: bool = False,
    allow_confirmed_history: bool = False,
    run_cache_steps: bool = True,
) -> dict[str, Any]:
    run_started_at = datetime.now().isoformat(timespec="seconds")
    run_started = time.perf_counter()
    registry = load_variable_registry()
    plan = build_feature_plan(
        registry,
        modules=modules,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
    )
    if plan.requires_confirmation and not (dry_run or allow_confirmed_history):
        raise ValueError(
            "feature build requires explicit confirmation: "
            f"{plan.confirmation_reason}; rerun with --allow-confirmed-history after review"
        )
    results: list[FeatureBuildResult] = []
    cache_results: list[CacheStepResult] = []
    executed_cache_steps: set[str] = set()
    if dry_run:
        for item in plan.module_plans:
            builder = BUILDERS[item.module]
            ctx = FeatureBuildContext(
                con=None,
                module=item.module,
                read_start_date=item.read_start_date,
                write_start_date=item.write_start_date,
                write_end_date=item.write_end_date,
                dry_run=True,
            )
            cache_results.extend(
                _run_pre_cache_steps(ctx, enabled=run_cache_steps, executed=executed_cache_steps)
            )
            module_started = time.perf_counter()
            results.append(replace(builder(ctx), elapsed_seconds=round(time.perf_counter() - module_started, 3)))
            cache_results.extend(
                _run_post_cache_steps(ctx, enabled=run_cache_steps, executed=executed_cache_steps)
            )
        return {
            "started_at": run_started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "elapsed_seconds": round(time.perf_counter() - run_started, 3),
            "plan": plan.to_dict(),
            "results": [result.__dict__ for result in results],
            "cache_results": [result.to_dict() for result in cache_results],
        }

    with connect() as con:
        init_database(con)
        runtime_module_plans = []
        for item in plan.module_plans:
            read_start_date = _resolve_trade_calendar_read_start(
                con,
                item.write_start_date,
                item.read_window,
                item.read_start_date,
            )
            runtime_module_plans.append(replace(item, read_start_date=read_start_date))
            builder = BUILDERS[item.module]
            ctx = FeatureBuildContext(
                con=con,
                module=item.module,
                read_start_date=read_start_date,
                write_start_date=item.write_start_date,
                write_end_date=item.write_end_date,
                dry_run=dry_run,
            )
            cache_results.extend(
                _run_pre_cache_steps(ctx, enabled=run_cache_steps, executed=executed_cache_steps)
            )
            module_started = time.perf_counter()
            results.append(replace(builder(ctx), elapsed_seconds=round(time.perf_counter() - module_started, 3)))
            cache_results.extend(
                _run_post_cache_steps(ctx, enabled=run_cache_steps, executed=executed_cache_steps)
            )
    payload = {
        "started_at": run_started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": round(time.perf_counter() - run_started, 3),
        "plan": {**plan.to_dict(), "module_plans": [item.__dict__ for item in runtime_module_plans]},
        "results": [result.__dict__ for result in results],
        "cache_results": [result.to_dict() for result in cache_results],
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "phase4_last_build_features_run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload
