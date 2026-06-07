from __future__ import annotations

from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"

CORE_NO_UPDATED = [
    "ts_code", "trade_date",
    "pe", "pe_ttm", "pb", "ps", "ps_ttm", "dv_ratio", "dv_ttm",
    "total_share", "float_share", "free_share",
    "total_mv", "circ_mv", "free_float_mv",
    "log_total_mv", "log_circ_mv", "log_free_float_mv",
    "float_share_ratio", "free_share_ratio",
    "earnings_yield_ttm", "book_to_price", "sales_yield_ttm", "dividend_yield_ttm",
    "pe_ttm_pct_5y", "pb_pct_5y", "ps_ttm_pct_5y", "total_mv_pct_5y",
    "pe_ttm_valid_flag", "pb_valid_flag", "ps_ttm_valid_flag", "mv_valid_flag",
    "valuation_missing_reason",
]
PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
MA_PERIODS = [20, 60, 120, 250]


def win(alias: str, n: int) -> str:
    return f"{alias}.ts_code ORDER BY {alias}.trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW"


def avg_expr(expr: str, n: int, alias: str = "b") -> str:
    return f"avg({expr}) OVER (PARTITION BY {win(alias, n)})"


def chg_expr(source: str, n: int) -> str:
    lag_value = f"lag({source}, {n}) OVER (PARTITION BY ts_code ORDER BY trade_date)"
    return (
        f"CASE WHEN {source} > 0 AND {lag_value} > 0 THEN {source} / {lag_value} - 1 "
        f"ELSE NULL END AS {source}_chg_{n}"
    )


def create_sql() -> str:
    pct_sources = ["pe", "pe_ttm", "pb", "ps", "ps_ttm", "dv_ratio", "dv_ttm", "total_mv", "circ_mv", "free_float_mv"]
    pct_aliases = ["1y", "3y", "5y", "10y"]
    base_fields = [f"v.{field}" for field in CORE_NO_UPDATED] + [
        "v.updated_at",
        "ds.close_raw",
        "ds.amount",
        "q.roe_asof",
        "q.bps_asof",
        "q.eps_asof",
        "q.ocfps_asof",
        "g.parent_net_profit_yoy_1y_calc_asof",
        "g.parent_net_profit_single_quarter_value_asof",
        *[
            f"pc.{source}_pct_{alias} AS cache_{source}_pct_{alias}"
            for source in pct_sources
            for alias in pct_aliases
        ],
    ]
    select_fields = [
        *CORE_NO_UPDATED,
        "CASE WHEN pe > 0 THEN 1.0 / pe ELSE NULL END AS earnings_yield",
        "CASE WHEN ps > 0 THEN 1.0 / ps ELSE NULL END AS sales_yield",
        "dv_ratio / 100.0 AS dividend_yield",
        "CASE WHEN pe_ttm > 0 THEN ln(pe_ttm) ELSE NULL END AS log_pe_ttm",
        "CASE WHEN pb > 0 THEN ln(pb) ELSE NULL END AS log_pb",
        "CASE WHEN ps_ttm > 0 THEN ln(ps_ttm) ELSE NULL END AS log_ps_ttm",
        "dv_ratio IS NOT NULL OR dv_ttm IS NOT NULL AS dv_valid_flag",
    ]
    for source in pct_sources:
        for alias in pct_aliases:
            if (source, alias) in {("pe_ttm", "5y"), ("pb", "5y"), ("ps_ttm", "5y"), ("total_mv", "5y")}:
                continue
            select_fields.append(f"cache_{source}_pct_{alias} AS {source}_pct_{alias}")
    for source in ["pe_ttm", "pb", "ps_ttm", "total_mv", "circ_mv", "free_float_mv"]:
        for n in PERIODS:
            select_fields.append(chg_expr(source, n))
    for source in ["pe_ttm", "pb", "ps_ttm", "total_mv", "circ_mv"]:
        for n in MA_PERIODS:
            select_fields.append(f"{avg_expr(source, n)} AS {source}_ma_{n}")
    select_fields.extend(
        [
            "CASE WHEN total_share > 0 THEN float_share / total_share ELSE NULL END AS float_to_total_share_ratio",
            "CASE WHEN total_share > 0 THEN free_share / total_share ELSE NULL END AS free_to_total_share_ratio",
            "CASE WHEN float_share > 0 THEN free_share / float_share ELSE NULL END AS free_to_float_share_ratio",
            "CASE WHEN total_mv > 0 THEN circ_mv / total_mv ELSE NULL END AS circ_mv_to_total_mv_ratio",
            "CASE WHEN total_mv > 0 THEN free_float_mv / total_mv ELSE NULL END AS free_float_mv_to_total_mv_ratio",
            "CASE WHEN total_mv > 0 THEN (amount / 10.0) / total_mv ELSE NULL END AS amount_to_total_mv",
            "CASE WHEN circ_mv > 0 THEN (amount / 10.0) / circ_mv ELSE NULL END AS amount_to_circ_mv",
            "CASE WHEN pe_ttm > 0 AND parent_net_profit_yoy_1y_calc_asof > 0 THEN pe_ttm / parent_net_profit_yoy_1y_calc_asof ELSE NULL END AS peg_ttm",
            "CASE WHEN pb > 0 AND roe_asof > 0 THEN pb / roe_asof ELSE NULL END AS pb_to_roe",
            "CASE WHEN pe_ttm > 0 AND roe_asof > 0 THEN pe_ttm / roe_asof ELSE NULL END AS pe_to_roe",
            "CASE WHEN close_raw > 0 AND bps_asof > 0 THEN close_raw / bps_asof ELSE NULL END AS price_to_bps_asof",
            "CASE WHEN close_raw > 0 AND eps_asof > 0 THEN close_raw / eps_asof ELSE NULL END AS price_to_eps_asof",
            "CASE WHEN close_raw > 0 AND ocfps_asof > 0 THEN close_raw / ocfps_asof ELSE NULL END AS price_to_ocfps_asof",
            "CASE WHEN total_mv > 0 AND parent_net_profit_single_quarter_value_asof > 0 THEN total_mv * 10000.0 / parent_net_profit_single_quarter_value_asof ELSE NULL END AS market_cap_to_parent_profit",
            "updated_at",
        ]
    )
    return f"""
    CREATE OR REPLACE VIEW derived_valuation_size_full_v AS
    WITH b AS (
        SELECT
            {",\n            ".join(base_fields)}
        FROM derived_valuation_size v
        LEFT JOIN derived_daily_spine ds USING (ts_code, trade_date)
        LEFT JOIN derived_financial_quality q USING (ts_code, trade_date)
        LEFT JOIN derived_financial_growth g USING (ts_code, trade_date)
        LEFT JOIN derived_valuation_percentile_cache pc USING (ts_code, trade_date)
    )
    SELECT
        {",\n        ".join(select_fields)}
    FROM b
    """


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    con.execute(create_sql())
    columns = len(con.execute("PRAGMA table_info('derived_valuation_size_full_v')").fetchall())
    print({"view": "derived_valuation_size_full_v", "columns": columns})


if __name__ == "__main__":
    main()
