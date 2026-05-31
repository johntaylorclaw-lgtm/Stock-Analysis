from __future__ import annotations

from typing import Any

from .context import FeatureBuildContext
from .modules import BUILDERS, FeatureBuildResult
from .planner import build_feature_plan
from ..config import load_variable_registry
from ..database import connect, init_database


def build_features(
    *,
    modules: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    mode: str = "daily",
    dry_run: bool = False,
    allow_confirmed_history: bool = False,
) -> dict[str, Any]:
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
    with connect() as con:
        init_database(con)
        for item in plan.module_plans:
            builder = BUILDERS[item.module]
            ctx = FeatureBuildContext(
                con=con,
                module=item.module,
                read_start_date=item.read_start_date,
                write_start_date=item.write_start_date,
                write_end_date=item.write_end_date,
                dry_run=dry_run,
            )
            results.append(builder(ctx))
    return {
        "plan": plan.to_dict(),
        "results": [result.__dict__ for result in results],
    }
