from __future__ import annotations

from pathlib import Path

import duckdb

from phase3_cross_sectional_config import (
    MIN_GROUP_RANK_N,
    MIN_GROUP_ZSCORE_N,
    PHYSICAL_VARIABLES,
    VIEW_EXTRA_VARIABLES,
    WINSOR_LOWER,
    WINSOR_UPPER,
    view_extra_field_names,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"

SOURCE_ALIASES = {
    "derived_return_momentum": "rm",
    "derived_volume_liquidity": "vl",
    "derived_volatility_risk": "vr",
    "derived_valuation_size": "vs",
    "derived_financial_quality": "fq",
    "derived_financial_growth": "fg",
    "derived_capital_flow": "cf",
    "derived_sector_concept_context": "sc",
    "derived_index_market_context": "im",
}


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def valid_expr(var, alias: str | None = None) -> str:
    prefix = alias or SOURCE_ALIASES[var.source_table]
    expr = f"{prefix}.{q(var.source_field)}"
    base = f"CASE WHEN NOT xs.xs_universe_flag THEN NULL WHEN {expr} IS NULL THEN NULL WHEN {expr} <= -9000000 THEN NULL"
    if var.valid_rule == "positive":
        base += f" WHEN {expr} <= 0 THEN NULL"
    elif var.valid_rule == "non_negative":
        base += f" WHEN {expr} < 0 THEN NULL"
    return base + f" ELSE {expr} END"


def z_expr(value: str, partition: str) -> str:
    count_sql = f"count({q(value)}) OVER (PARTITION BY {partition})"
    avg_sql = f"avg({q(value)}) OVER (PARTITION BY {partition})"
    std_sql = f"stddev_samp({q(value)}) OVER (PARTITION BY {partition})"
    return (
        f"CASE WHEN {count_sql} >= {MIN_GROUP_ZSCORE_N} AND {std_sql} > 0 "
        f"THEN ({q(value)} - {avg_sql}) / {std_sql} ELSE NULL END"
    )


def rank_expr(value: str, partition: str) -> str:
    count_sql = f"count({q(value)}) OVER (PARTITION BY {partition})"
    return (
        f"CASE WHEN {count_sql} >= {MIN_GROUP_RANK_N} AND {q(value)} IS NOT NULL "
        f"THEN rank() OVER (PARTITION BY {partition} ORDER BY {q(value)} DESC NULLS LAST)::INTEGER ELSE NULL END"
    )


def pct_expr(value: str, partition: str) -> str:
    count_sql = f"count({q(value)}) OVER (PARTITION BY {partition})"
    rank_sql = f"rank() OVER (PARTITION BY {partition} ORDER BY {q(value)} DESC NULLS LAST)"
    return (
        f"CASE WHEN {count_sql} >= {MIN_GROUP_RANK_N} AND {q(value)} IS NOT NULL "
        f"THEN 1.0 - ({rank_sql} - 1)::DOUBLE / NULLIF({count_sql} - 1, 0) ELSE NULL END"
    )


def physical_extra_selects() -> list[str]:
    selects: list[str] = []
    for var in PHYSICAL_VARIABLES:
        base = f"{var.name}_z_all"
        selects.extend(
            [
                f"{z_expr(base, 'xs.trade_date, xs.xs_market')} AS {q(var.name + '_z_market')}",
                f"{rank_expr(base, 'xs.trade_date, xs.xs_sw_l1_code')} AS {q(var.name + '_rank_sw_l1_desc')}",
                f"{pct_expr(base, 'xs.trade_date, xs.xs_sw_l1_code')} AS {q(var.name + '_pct_sw_l1_desc')}",
                f"{z_expr(base, 'xs.trade_date, xs.xs_sw_l1_code')} AS {q(var.name + '_z_sw_l1')}",
                f"{z_expr(base, 'xs.trade_date, xs.xs_sw_l2_code')} AS {q(var.name + '_z_sw_l2')}",
                f"{rank_expr(base, 'xs.trade_date, xs.xs_exchange')} AS {q(var.name + '_rank_exchange_desc')}",
                f"{pct_expr(base, 'xs.trade_date, xs.xs_exchange')} AS {q(var.name + '_pct_exchange_desc')}",
                f"{z_expr(base, 'xs.trade_date, xs.xs_exchange')} AS {q(var.name + '_z_exchange')}",
            ]
        )
    return selects


def view_extra_ctes() -> tuple[list[str], list[str]]:
    joins = "\n        ".join(
        f"LEFT JOIN {table} {alias} ON xs.ts_code = {alias}.ts_code AND xs.trade_date = {alias}.trade_date"
        for table, alias in SOURCE_ALIASES.items()
    )
    raw_fields = [f"{valid_expr(var)} AS {q(var.name + '_raw')}" for var in VIEW_EXTRA_VARIABLES]
    ctes = [
        "extra_raw AS (\n"
        "    SELECT xs.ts_code, xs.trade_date,\n"
        f"           {', '.join(raw_fields)}\n"
        "    FROM derived_cross_sectional xs\n"
        f"    {joins}\n"
        ")",
    ]
    for var in VIEW_EXTRA_VARIABLES:
        raw = q(var.name + "_raw")
        ctes.append(
            f"{q(var.name + '_bounds')} AS (\n"
            f"    SELECT trade_date,\n"
            f"           quantile_cont({raw}, {WINSOR_LOWER}) AS lower_bound,\n"
            f"           quantile_cont({raw}, {WINSOR_UPPER}) AS upper_bound\n"
            f"    FROM extra_raw\n"
            f"    WHERE {raw} IS NOT NULL\n"
            f"    GROUP BY trade_date\n"
            f")"
        )
    clipped_select = ["er.ts_code", "er.trade_date"]
    clipped_joins = []
    for var in VIEW_EXTRA_VARIABLES:
        raw = q(var.name + "_raw")
        alias = "b_" + var.name
        clipped_select.append(
            f"CASE WHEN {raw} IS NULL THEN NULL "
            f"ELSE least(greatest({raw}, {alias}.lower_bound), {alias}.upper_bound) END AS {q(var.name)}"
        )
        clipped_joins.append(
            f"LEFT JOIN {q(var.name + '_bounds')} {alias} ON er.trade_date = {alias}.trade_date"
        )
    ctes.append(
        "extra_clipped AS (\n"
        f"    SELECT {', '.join(clipped_select)}\n"
        "    FROM extra_raw er\n"
        f"    {' '.join(clipped_joins)}\n"
        ")"
    )
    selects: list[str] = []
    for var in VIEW_EXTRA_VARIABLES:
        partitions = {
            "all": "xs.trade_date",
            "market": "xs.trade_date, xs.xs_market",
            "sw_l1": "xs.trade_date, xs.xs_sw_l1_code",
            "sw_l2": "xs.trade_date, xs.xs_sw_l2_code",
            "exchange": "xs.trade_date, xs.xs_exchange",
        }
        value = var.name
        selects.extend(
            [
                f"{rank_expr(value, partitions['all'])} AS {q(var.name + '_rank_all_desc')}",
                f"{pct_expr(value, partitions['all'])} AS {q(var.name + '_pct_all_desc')}",
                f"{z_expr(value, partitions['all'])} AS {q(var.name + '_z_all')}",
                f"{rank_expr(value, partitions['market'])} AS {q(var.name + '_rank_market_desc')}",
                f"{pct_expr(value, partitions['market'])} AS {q(var.name + '_pct_market_desc')}",
                f"{rank_expr(value, partitions['sw_l2'])} AS {q(var.name + '_rank_sw_l2_desc')}",
                f"{pct_expr(value, partitions['sw_l2'])} AS {q(var.name + '_pct_sw_l2_desc')}",
            ]
        )
        selects.extend(
            [
                f"{z_expr(value, partitions['market'])} AS {q(var.name + '_z_market')}",
                f"{rank_expr(value, partitions['sw_l1'])} AS {q(var.name + '_rank_sw_l1_desc')}",
                f"{pct_expr(value, partitions['sw_l1'])} AS {q(var.name + '_pct_sw_l1_desc')}",
                f"{z_expr(value, partitions['sw_l1'])} AS {q(var.name + '_z_sw_l1')}",
                f"{z_expr(value, partitions['sw_l2'])} AS {q(var.name + '_z_sw_l2')}",
                f"{rank_expr(value, partitions['exchange'])} AS {q(var.name + '_rank_exchange_desc')}",
                f"{pct_expr(value, partitions['exchange'])} AS {q(var.name + '_pct_exchange_desc')}",
                f"{z_expr(value, partitions['exchange'])} AS {q(var.name + '_z_exchange')}",
            ]
        )
    return ctes, selects


def avg_available(components: list[tuple[str, int]], min_count: int | None = None) -> str:
    min_required = min_count or max(1, (len(components) + 1) // 2)
    count_expr = " + ".join(f"CASE WHEN {q(name)} IS NOT NULL THEN 1 ELSE 0 END" for name, _sign in components)
    sum_expr = " + ".join(
        f"CASE WHEN {q(name)} IS NOT NULL THEN {sign} * {q(name)} ELSE 0 END" for name, sign in components
    )
    return f"CASE WHEN ({count_expr}) >= {min_required} THEN ({sum_expr}) / NULLIF(({count_expr}), 0) ELSE NULL END"


def extended_exposure_selects() -> list[str]:
    definitions = {
        "profitability_exposure_z": [
            ("roe_asof_z_all", 1),
            ("roa_asof_z_all", 1),
            ("roic_asof_z_all", 1),
            ("gross_margin_asof_z_all", 1),
            ("netprofit_margin_asof_z_all", 1),
        ],
        "cashflow_quality_exposure_z": [
            ("ocf_to_profit_asof_z_all", 1),
            ("accrual_ratio_asof_z_all", -1),
        ],
        "leverage_exposure_z": [
            ("debt_to_assets_asof_z_all", 1),
            ("liabilities_to_equity_asof_z_all", 1),
        ],
        "concept_heat_exposure_z": [
            ("concept_hot_count_20_z_all", 1),
            ("concept_avg_ret_20_z_all", 1),
        ],
        "index_relative_exposure_z": [
            ("stock_excess_hs300_20_z_all", 1),
            ("stock_excess_zz1000_20_z_all", 1),
        ],
    }
    return [f"{avg_available(components)} AS {q(name)}" for name, components in definitions.items()]


def build_view_sql() -> str:
    extra_ctes, extra_selects = view_extra_ctes()
    with_parts = ["base AS (SELECT xs.* FROM derived_cross_sectional xs)"]
    with_parts.extend(extra_ctes)
    all_selects = ["xs.*"]
    all_selects.extend(physical_extra_selects())
    all_selects.extend(extra_selects)
    wide_sql = (
        f"SELECT {', '.join(all_selects)}\n"
        "FROM base xs\n"
        "LEFT JOIN extra_clipped ec ON xs.ts_code = ec.ts_code AND xs.trade_date = ec.trade_date"
    )
    with_parts.append(f"wide AS ({wide_sql})")
    final_selects = ["wide.*"]
    final_selects.extend(extended_exposure_selects())
    return (
        "CREATE OR REPLACE VIEW derived_cross_sectional_full_v AS\n"
        f"WITH {', '.join(with_parts)}\n"
        f"SELECT {', '.join(final_selects)}\n"
        "FROM wide"
    )


def main() -> None:
    with duckdb.connect(DB_PATH) as con:
        con.execute(build_view_sql())
        cols = con.execute("SELECT count(*) FROM pragma_table_info('derived_cross_sectional_full_v')").fetchone()[0]
        print({"derived_cross_sectional_full_v": cols})


if __name__ == "__main__":
    main()
