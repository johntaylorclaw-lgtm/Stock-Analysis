from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import ceil
from typing import Any


MODULE_ORDER = [
    "daily_spine",
    "price_technical",
    "volume_liquidity",
    "return_momentum",
    "volatility_risk",
    "trading_constraint",
    "valuation_size",
    "financial_asof",
    "financial_quality",
    "financial_growth",
    "capital_flow",
    "sector_concept_context",
    "index_market_context",
    "cross_sectional",
    "corporate_action",
    "ownership_governance",
    "composite_state",
]


MODULE_DEPENDENCIES = {
    "daily_spine": [],
    "price_technical": ["daily_spine"],
    "volume_liquidity": ["daily_spine"],
    "return_momentum": ["daily_spine"],
    "volatility_risk": ["daily_spine", "return_momentum"],
    "trading_constraint": ["daily_spine"],
    "valuation_size": ["daily_spine"],
    "financial_asof": [],
    "financial_quality": ["financial_asof"],
    "financial_growth": ["financial_asof"],
    "capital_flow": ["daily_spine"],
    "sector_concept_context": ["daily_spine", "return_momentum"],
    "index_market_context": ["daily_spine", "return_momentum"],
    "cross_sectional": [
        "daily_spine",
        "price_technical",
        "volume_liquidity",
        "return_momentum",
        "volatility_risk",
        "trading_constraint",
        "valuation_size",
        "financial_quality",
        "financial_growth",
        "capital_flow",
        "sector_concept_context",
        "index_market_context",
    ],
    "corporate_action": ["financial_asof"],
    "ownership_governance": ["financial_asof"],
    "composite_state": [
        "price_technical",
        "volume_liquidity",
        "return_momentum",
        "volatility_risk",
        "valuation_size",
        "financial_quality",
        "capital_flow",
        "sector_concept_context",
        "index_market_context",
        "cross_sectional",
    ],
}


@dataclass(frozen=True)
class FeatureModulePlan:
    module: str
    variables: int
    tables: list[str]
    read_start_date: str
    write_start_date: str
    write_end_date: str
    read_window: int
    write_window: int
    max_min_history: int
    dependencies: list[str]


@dataclass(frozen=True)
class FeaturePlan:
    mode: str
    requested_modules: list[str]
    execution_order: list[str]
    write_start_date: str
    write_end_date: str
    requires_confirmation: bool
    confirmation_reason: str
    module_plans: list[FeatureModulePlan]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "requested_modules": self.requested_modules,
            "execution_order": self.execution_order,
            "write_start_date": self.write_start_date,
            "write_end_date": self.write_end_date,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_reason": self.confirmation_reason,
            "module_plans": [item.__dict__ for item in self.module_plans],
        }


def parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid date: {value}")


def format_date(value: date) -> str:
    return value.isoformat()


def _normalize_trade_dates(values: list[str | date] | None) -> list[date]:
    if not values:
        return []
    return sorted({parse_date(value.isoformat() if isinstance(value, date) else str(value)) for value in values})


def _trade_window_start(end: date, window_size: int, trade_dates: list[date]) -> date | None:
    eligible = [item for item in trade_dates if item <= end]
    if len(eligible) < window_size:
        return None
    return eligible[-window_size]


def _trade_day_count(start: date, end: date, trade_dates: list[date]) -> int | None:
    if not trade_dates:
        return None
    return sum(1 for item in trade_dates if start <= item <= end)


def _calendar_context_days(trading_context_days: int, trade_dates: list[date]) -> int:
    if trade_dates:
        return trading_context_days
    return int(ceil(trading_context_days * 7 / 5) + 14)


def expand_modules(modules: list[str] | None) -> list[str]:
    if not modules:
        return MODULE_ORDER.copy()
    unknown = sorted(set(modules) - set(MODULE_ORDER))
    if unknown:
        raise ValueError(f"unknown feature modules: {', '.join(unknown)}")
    needed: set[str] = set()

    def add_with_dependencies(module: str) -> None:
        if module in needed:
            return
        for dep in MODULE_DEPENDENCIES.get(module, []):
            add_with_dependencies(dep)
        needed.add(module)

    for module in modules:
        add_with_dependencies(module)
    return [module for module in MODULE_ORDER if module in needed]


def variables_by_module(variable_registry: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for variable in variable_registry.get("variables", []):
        module = variable.get("module")
        if module in MODULE_ORDER:
            grouped.setdefault(module, []).append(variable)
    return grouped


def build_feature_plan(
    variable_registry: dict[str, Any],
    *,
    modules: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    mode: str = "daily",
    default_write_window: int = 10,
    trade_dates: list[str | date] | None = None,
) -> FeaturePlan:
    end = parse_date(end_date)
    normalized_trade_dates = _normalize_trade_dates(trade_dates)
    if start_date:
        write_start = parse_date(start_date)
        write_day_count = _trade_day_count(write_start, end, normalized_trade_dates)
    else:
        write_start = _trade_window_start(end, default_write_window, normalized_trade_dates)
        if write_start is None:
            write_start = end - timedelta(days=default_write_window - 1)
            write_day_count = None
        else:
            write_day_count = default_write_window

    execution_order = expand_modules(modules)
    grouped = variables_by_module(variable_registry)
    module_plans: list[FeatureModulePlan] = []
    for module in execution_order:
        variables = grouped.get(module, [])
        read_window = max([int(item.get("read_window") or 0) for item in variables] or [default_write_window])
        write_window = max([int(item.get("write_window") or 0) for item in variables] or [default_write_window])
        min_history = max([int(item.get("min_history") or 0) for item in variables] or [0])
        context_days = max(read_window, min_history, default_write_window)
        fallback_context_days = _calendar_context_days(context_days, normalized_trade_dates)
        read_start = write_start - timedelta(days=fallback_context_days)
        tables = sorted({item.get("table", "") for item in variables if item.get("table")})
        module_plans.append(
            FeatureModulePlan(
                module=module,
                variables=len(variables),
                tables=tables,
                read_start_date=format_date(read_start),
                write_start_date=format_date(write_start),
                write_end_date=format_date(end),
                read_window=context_days,
                write_window=write_window,
                max_min_history=min_history,
                dependencies=MODULE_DEPENDENCIES.get(module, []),
            )
        )

    calendar_days = (end - write_start).days + 1
    effective_write_days = write_day_count if write_day_count is not None else calendar_days
    requires_confirmation = mode == "history" or effective_write_days > default_write_window
    reason = ""
    if requires_confirmation:
        day_unit = "trading days" if write_day_count is not None else "calendar days"
        reason = (
            f"write range spans {effective_write_days} {day_unit}; "
            f"Phase 3 daily mode defaults to {default_write_window} recent trading days"
        )
    return FeaturePlan(
        mode=mode,
        requested_modules=modules or MODULE_ORDER.copy(),
        execution_order=execution_order,
        write_start_date=format_date(write_start),
        write_end_date=format_date(end),
        requires_confirmation=requires_confirmation,
        confirmation_reason=reason,
        module_plans=module_plans,
    )


def render_plan_markdown(plan: FeaturePlan) -> str:
    lines = [
        "# Phase 3 Feature Plan",
        "",
        f"- Mode: `{plan.mode}`",
        f"- Write window: `{plan.write_start_date}` to `{plan.write_end_date}`",
        f"- Requires confirmation: `{str(plan.requires_confirmation).lower()}`",
    ]
    if plan.confirmation_reason:
        lines.append(f"- Confirmation reason: {plan.confirmation_reason}")
    lines.extend(["", "## Execution Order", "", " -> ".join(f"`{item}`" for item in plan.execution_order), ""])
    lines.extend(
        [
            "## Module Plan",
            "",
            "| module | variables | tables | read_start | write_start | write_end | read_window | write_window | dependencies |",
            "|---|---:|---|---|---|---|---:|---:|---|",
        ]
    )
    for item in plan.module_plans:
        tables = ", ".join(item.tables)
        deps = ", ".join(item.dependencies)
        lines.append(
            "| "
            + " | ".join(
                [
                    item.module,
                    str(item.variables),
                    tables,
                    item.read_start_date,
                    item.write_start_date,
                    item.write_end_date,
                    str(item.read_window),
                    str(item.write_window),
                    deps,
                ]
            )
            + " |"
        )
    return "\n".join(lines).rstrip() + "\n"
