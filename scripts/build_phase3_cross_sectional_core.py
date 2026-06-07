from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from phase3_cross_sectional_config import (
    EXPOSURES,
    MIN_GROUP_RANK_N,
    MIN_GROUP_ZSCORE_N,
    PHYSICAL_VARIABLES,
    RESIDUAL_VARIABLES,
    WINSOR_LOWER,
    WINSOR_UPPER,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
REPORT_PATH = ROOT / "reports" / "phase3_cross_sectional_core_run.jsonl"

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


def table_fields(table: str) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return [field["name"] for item in schema["tables"] if item["name"] == table for field in item["fields"]]


def valid_expr(var, alias: str | None = None, universe_expr: str = "xs_universe_flag") -> str:
    prefix = alias or SOURCE_ALIASES[var.source_table]
    expr = f"{prefix}.{q(var.source_field)}"
    base = f"CASE WHEN NOT ({universe_expr}) THEN NULL WHEN {expr} IS NULL THEN NULL WHEN {expr} <= -900000 THEN NULL"
    if var.valid_rule == "positive":
        base += f" WHEN {expr} <= 0 THEN NULL"
    elif var.valid_rule == "non_negative":
        base += f" WHEN {expr} < 0 THEN NULL"
    return base + f" ELSE {expr} END"


def insert_metadata_sql(start: str, end: str) -> str:
    valid_terms = []
    missing_terms = []
    joins = "\n        ".join(
        f"LEFT JOIN {table} {alias} ON ds.ts_code = {alias}.ts_code AND ds.trade_date = {alias}.trade_date"
        for table, alias in SOURCE_ALIASES.items()
    )
    for var in PHYSICAL_VARIABLES:
        expr = valid_expr(var, universe_expr="ds.is_listed_asof AND ds.has_price AND ds.price_valid_flag")
        valid_terms.append(f"CASE WHEN ({expr}) IS NOT NULL THEN 1 ELSE 0 END")
        missing_terms.append(f"CASE WHEN ({expr}) IS NULL THEN '{var.name}' ELSE NULL END")
    return f"""
    INSERT INTO derived_cross_sectional (
        ts_code, trade_date,
        xs_universe_flag, xs_market, xs_exchange, xs_sw_l1_code, xs_sw_l2_code,
        xs_sample_all_count, xs_sample_market_count, xs_sample_sw_l1_count, xs_sample_sw_l2_count,
        xs_core_available_count, xs_core_available_ratio, xs_missing_fields,
        xs_winsor_lower_pct, xs_winsor_upper_pct, xs_min_group_zscore_n, xs_min_group_rank_n,
        updated_at
    )
    WITH base AS (
        SELECT
            ds.ts_code,
            ds.trade_date,
            ds.is_listed_asof AND ds.has_price AND ds.price_valid_flag AS xs_universe_flag,
            ds.market AS xs_market,
            ds.exchange AS xs_exchange,
            sc.sw_l1_code AS xs_sw_l1_code,
            sc.sw_l2_code AS xs_sw_l2_code,
            {' + '.join(valid_terms)} AS xs_core_available_count,
            concat_ws(';', {', '.join(missing_terms)}) AS xs_missing_fields
        FROM derived_daily_spine ds
        {joins}
        WHERE ds.trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    )
    SELECT
        ts_code,
        trade_date,
        xs_universe_flag,
        xs_market,
        xs_exchange,
        xs_sw_l1_code,
        xs_sw_l2_code,
        count(*) FILTER (WHERE xs_universe_flag) OVER (PARTITION BY trade_date)::INTEGER AS xs_sample_all_count,
        count(*) FILTER (WHERE xs_universe_flag) OVER (PARTITION BY trade_date, xs_market)::INTEGER AS xs_sample_market_count,
        count(*) FILTER (WHERE xs_universe_flag) OVER (PARTITION BY trade_date, xs_sw_l1_code)::INTEGER AS xs_sample_sw_l1_count,
        count(*) FILTER (WHERE xs_universe_flag) OVER (PARTITION BY trade_date, xs_sw_l2_code)::INTEGER AS xs_sample_sw_l2_count,
        xs_core_available_count::INTEGER,
        xs_core_available_count::DOUBLE / {len(PHYSICAL_VARIABLES)} AS xs_core_available_ratio,
        xs_missing_fields,
        {WINSOR_LOWER}::DOUBLE,
        {WINSOR_UPPER}::DOUBLE,
        {MIN_GROUP_ZSCORE_N}::INTEGER,
        {MIN_GROUP_RANK_N}::INTEGER,
        CURRENT_TIMESTAMP
    FROM base
    """


def rank_expr(value: str, partition: str) -> str:
    count_sql = f"count({q(value)}) OVER (PARTITION BY {partition})"
    order_value = f"round({q(value)}, 10)"
    return f"CASE WHEN {q(value)} IS NULL OR {count_sql} < {MIN_GROUP_RANK_N} THEN NULL ELSE rank() OVER (PARTITION BY {partition} ORDER BY {order_value} DESC NULLS LAST)::INTEGER END"


def pct_expr(value: str, partition: str) -> str:
    count_sql = f"count({q(value)}) OVER (PARTITION BY {partition})"
    order_value = f"round({q(value)}, 10)"
    rank_sql = f"rank() OVER (PARTITION BY {partition} ORDER BY {order_value} DESC NULLS LAST)"
    return f"CASE WHEN {q(value)} IS NULL OR {count_sql} < {MIN_GROUP_RANK_N} THEN NULL ELSE ({count_sql} - {rank_sql})::DOUBLE / nullif({count_sql} - 1, 0) END"


def z_expr(value: str, partition: str = "trade_date") -> str:
    w = q(value + "_w")
    count_sql = f"count({w}) OVER (PARTITION BY {partition})"
    avg_sql = f"avg({w}) OVER (PARTITION BY {partition})"
    std_sql = f"stddev_samp({w}) OVER (PARTITION BY {partition})"
    return f"CASE WHEN {w} IS NULL OR {count_sql} < {MIN_GROUP_ZSCORE_N} OR {std_sql} = 0 THEN NULL ELSE ({w} - {avg_sql}) / {std_sql} END"


def update_variable_sql(var, start: str, end: str) -> str:
    alias = SOURCE_ALIASES[var.source_table]
    fields = [
        f"{var.name}_rank_all_desc",
        f"{var.name}_pct_all_desc",
        f"{var.name}_z_all",
        f"{var.name}_rank_market_desc",
        f"{var.name}_pct_market_desc",
        f"{var.name}_rank_sw_l2_desc",
        f"{var.name}_pct_sw_l2_desc",
    ]
    set_sql = ", ".join(f"{q(field)} = x.{q(field)}" for field in fields)
    return f"""
    CREATE OR REPLACE TEMP TABLE xs_var AS
    WITH base AS (
        SELECT
            t.ts_code,
            t.trade_date,
            t.xs_market,
            t.xs_sw_l2_code,
            t.xs_universe_flag AS xs_universe_flag,
            {valid_expr(var, alias)} AS {q(var.name)}
        FROM derived_cross_sectional t
        LEFT JOIN {var.source_table} {alias}
          ON t.ts_code = {alias}.ts_code AND t.trade_date = {alias}.trade_date
        WHERE t.trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    ),
    bounds AS (
        SELECT
            trade_date,
            quantile_cont({q(var.name)}, {WINSOR_LOWER}) AS lo,
            quantile_cont({q(var.name)}, {WINSOR_UPPER}) AS hi
        FROM base
        GROUP BY trade_date
    ),
    clipped AS (
        SELECT
            b.*,
            CASE WHEN b.{q(var.name)} IS NULL THEN NULL ELSE least(greatest(b.{q(var.name)}, bd.lo), bd.hi) END AS {q(var.name + '_w')}
        FROM base b
        LEFT JOIN bounds bd USING (trade_date)
    )
    SELECT
        ts_code,
        trade_date,
        {rank_expr(var.name, 'trade_date')} AS {q(fields[0])},
        {pct_expr(var.name, 'trade_date')} AS {q(fields[1])},
        {z_expr(var.name)} AS {q(fields[2])},
        {rank_expr(var.name, 'trade_date, xs_market')} AS {q(fields[3])},
        {pct_expr(var.name, 'trade_date, xs_market')} AS {q(fields[4])},
        {rank_expr(var.name, 'trade_date, xs_sw_l2_code')} AS {q(fields[5])},
        {pct_expr(var.name, 'trade_date, xs_sw_l2_code')} AS {q(fields[6])}
    FROM clipped;

    UPDATE derived_cross_sectional AS t
    SET {set_sql}
    FROM xs_var x
    WHERE t.ts_code = x.ts_code AND t.trade_date = x.trade_date;
    """


def avg_components(components: list[tuple[str, int]]) -> str:
    terms = []
    counts = []
    for name, sign in components:
        col = q(f"{name}_z_all")
        terms.append(f"coalesce({sign} * {col}, 0)")
        counts.append(f"CASE WHEN {col} IS NOT NULL THEN 1 ELSE 0 END")
    min_count = (len(components) + 1) // 2
    count_expr = " + ".join(counts)
    return f"CASE WHEN ({count_expr}) < {min_count} THEN NULL ELSE ({' + '.join(terms)}) / nullif(({count_expr}), 0) END"


def update_exposure_sql(start: str, end: str) -> str:
    assignments = ", ".join(f"{q(name)} = {avg_components(components)}" for name, (_, components) in EXPOSURES.items())
    return f"""
    UPDATE derived_cross_sectional
    SET {assignments}, updated_at = CURRENT_TIMESTAMP
    WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    """


def update_residual_variable_sql(name: str, start: str, end: str) -> str:
    y = q(name + "_z_all")
    x = q("log_free_float_mv_z_all")
    y_dm = q("y_dm")
    x_dm = q("x_dm")
    raw = q("resid_raw")
    out = q(name + "_resid_size_sw_l2_z")
    beta = f"sum({x_dm} * {y_dm}) OVER (PARTITION BY trade_date) / nullif(sum({x_dm} * {x_dm}) OVER (PARTITION BY trade_date), 0)"
    std = f"stddev_samp({raw}) OVER (PARTITION BY trade_date)"
    return f"""
    CREATE OR REPLACE TEMP TABLE xs_resid_one AS
    WITH demeaned AS (
        SELECT
            ts_code,
            trade_date,
            {y} - avg({y}) OVER (PARTITION BY trade_date, xs_sw_l2_code) AS {y_dm},
            {x} - avg({x}) OVER (PARTITION BY trade_date, xs_sw_l2_code) AS {x_dm}
        FROM derived_cross_sectional
        WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    ),
    residual_raw AS (
        SELECT
            ts_code,
            trade_date,
            {y_dm} - ({beta}) * {x_dm} AS {raw}
        FROM demeaned
    )
    SELECT
        ts_code,
        trade_date,
        CASE WHEN {raw} IS NULL OR {std} = 0 THEN NULL ELSE {raw} / {std} END AS {out}
    FROM residual_raw;

    UPDATE derived_cross_sectional AS t
    SET {out} = r.{out}, updated_at = CURRENT_TIMESTAMP
    FROM xs_resid_one r
    WHERE t.ts_code = r.ts_code AND t.trade_date = r.trade_date;
    """


def update_residuals_pandas(con: duckdb.DuckDBPyConnection, start: str, end: str) -> None:
    y_cols = [f"{name}_z_all" for name in RESIDUAL_VARIABLES]
    out_cols = [f"{name}_resid_size_sw_l2_z" for name in RESIDUAL_VARIABLES]
    cols = ["ts_code", "trade_date", "xs_sw_l2_code", "log_free_float_mv_z_all"] + y_cols
    df = con.execute(
        f"""
        SELECT {", ".join(q(col) for col in cols)}
        FROM derived_cross_sectional
        WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}'
        """
    ).fetchdf()
    if df.empty:
        return
    size_dm = df["log_free_float_mv_z_all"] - df.groupby(["trade_date", "xs_sw_l2_code"], dropna=False)["log_free_float_mv_z_all"].transform("mean")
    for name, y_col, out_col in zip(RESIDUAL_VARIABLES, y_cols, out_cols, strict=True):
        y_dm = df[y_col] - df.groupby(["trade_date", "xs_sw_l2_code"], dropna=False)[y_col].transform("mean")
        work = pd.DataFrame({"trade_date": df["trade_date"], "x": size_dm, "y": y_dm})
        beta = work.assign(xy=work["x"] * work["y"], xx=work["x"] * work["x"]).groupby("trade_date")[["xy", "xx"]].sum()
        beta["beta"] = beta["xy"] / beta["xx"].replace(0, pd.NA)
        resid = y_dm - size_dm * df["trade_date"].map(beta["beta"])
        resid_std = resid.groupby(df["trade_date"]).transform("std")
        df[out_col] = resid / resid_std.replace(0, pd.NA)
    payload = df[["ts_code", "trade_date"] + out_cols].copy()
    con.register("xs_resid_payload", payload)
    set_sql = ", ".join(f"{q(col)} = p.{q(col)}" for col in out_cols)
    con.execute(
        f"""
        UPDATE derived_cross_sectional AS t
        SET {set_sql}, updated_at = CURRENT_TIMESTAMP
        FROM xs_resid_payload p
        WHERE t.ts_code = p.ts_code AND t.trade_date = p.trade_date
        """
    )
    con.unregister("xs_resid_payload")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2006)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--no-delete", action="store_true")
    args = parser.parse_args()

    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    if not args.no_delete:
        con.execute("DELETE FROM derived_cross_sectional")
        if REPORT_PATH.exists():
            REPORT_PATH.unlink()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    for year in range(args.start_year, args.end_year + 1):
        start = f"{year}-01-01"
        end = "2026-05-26" if year == 2026 else f"{year}-12-31"
        started = datetime.now().isoformat(timespec="seconds")
        con.execute("DELETE FROM derived_cross_sectional WHERE trade_date BETWEEN ? AND ?", [start, end])
        con.execute(insert_metadata_sql(start, end))
        for var in PHYSICAL_VARIABLES:
            con.execute(update_variable_sql(var, start, end))
        con.execute(update_exposure_sql(start, end))
        update_residuals_pandas(con, start, end)
        rows = con.execute(
            "SELECT count(*) FROM derived_cross_sectional WHERE trade_date BETWEEN ? AND ?",
            [start, end],
        ).fetchone()[0]
        payload = {"year": year, "started_at": started, "finished_at": datetime.now().isoformat(timespec="seconds"), "rows": int(rows)}
        with REPORT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        if year == 2026:
            break


if __name__ == "__main__":
    main()
