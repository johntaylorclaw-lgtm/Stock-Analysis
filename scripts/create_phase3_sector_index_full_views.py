from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("STOCK_DB_PATH", ROOT / "data" / "duckdb" / "stock_data.duckdb"))
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"

FULL_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
CORE_PERIODS = [5, 20, 60, 120]
NON_CORE = [n for n in FULL_PERIODS if n not in CORE_PERIODS]
CONCEPT_VIEW_PERIODS = [n for n in FULL_PERIODS if n != 20]
INDEX_CODES = {
    "hs300": "000300.SH",
    "zz500": "000905.SH",
    "zz1000": "000852.SH",
    "sse50": "000016.SH",
    "star50": "000688.SH",
    "chinext": "399006.SZ",
}


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def update_view_schema(con: duckdb.DuckDBPyConnection, view_name: str, desc: str) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    desc_by_name = {
        field["name"]: field.get("description", field["name"])
        for table in schema.get("tables", [])
        for field in table.get("fields", [])
    }
    cols = con.execute(f"PRAGMA table_info('{view_name}')").fetchall()
    fields = [
        {
            "name": row[1],
            "dtype": row[2],
            "nullable": row[3] is False,
            "description": desc_by_name.get(row[1], row[1]),
            "source_api": "local_derived",
        }
        for row in cols
    ]
    for field in fields:
        if field["name"] in {"ts_code", "trade_date"}:
            field["nullable"] = False
    payload = {
        "name": view_name,
        "phase": "P3",
        "description": desc,
        "table_type": "view",
        "primary_key": ["ts_code", "trade_date"],
        "fields": fields,
    }
    for idx, table in enumerate(schema["tables"]):
        if table["name"] == view_name:
            schema["tables"][idx] = payload
            break
    else:
        schema["tables"].append(payload)
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sector_view_sql() -> str:
    extra = []
    for n in NON_CORE:
        for level, alias in [("sw_l1", "l1"), ("sw_l2", "l2")]:
            extra.extend(
                [
                    f"{alias}.industry_ret_{n} AS {level}_ret_{n}",
                    f"r.ret_{n}_hfq - {alias}.industry_ret_{n} AS stock_excess_{level}_{n}",
                    f"{alias}.industry_ret_rank_all_{n} AS {level}_ret_rank_all_{n}",
                    f"{alias}.industry_ret_pct_all_{n} AS {level}_ret_pct_all_{n}",
                    f"{alias}.industry_amount_ma_{n} AS {level}_amount_ma_{n}",
                    f"{alias}.industry_main_flow_sum_{n} AS {level}_main_flow_sum_{n}",
                ]
            )
    for n in CONCEPT_VIEW_PERIODS:
        extra.extend(
            [
                f"cfull.concept_ids_top_{n} AS concept_ids_top_{n}",
                f"cfull.concept_names_top_{n} AS concept_names_top_{n}",
                f"cfull.concept_lagging_ids_{n} AS concept_lagging_ids_{n}",
                f"cfull.concept_lagging_names_{n} AS concept_lagging_names_{n}",
                f"cfull.concept_active_ids_{n} AS concept_active_ids_{n}",
                f"cfull.concept_active_names_{n} AS concept_active_names_{n}",
                f"cfull.concept_narrow_leading_ids_{n} AS concept_narrow_leading_ids_{n}",
                f"cfull.concept_narrow_leading_names_{n} AS concept_narrow_leading_names_{n}",
                f"cfull.concept_best_id_{n} AS concept_best_id_{n}",
                f"cfull.concept_best_name_{n} AS concept_best_name_{n}",
                f"cfull.concept_best_ret_{n} AS concept_best_ret_{n}",
                f"cfull.concept_worst_id_{n} AS concept_worst_id_{n}",
                f"cfull.concept_worst_name_{n} AS concept_worst_name_{n}",
                f"cfull.concept_worst_ret_{n} AS concept_worst_ret_{n}",
                f"cfull.concept_avg_ret_{n} AS concept_avg_ret_{n}",
                f"cfull.concept_median_ret_{n} AS concept_median_ret_{n}",
                f"cfull.concept_max_ret_{n} AS concept_max_ret_{n}",
                f"cfull.concept_min_ret_{n} AS concept_min_ret_{n}",
                f"cfull.concept_ret_spread_{n} AS concept_ret_spread_{n}",
                f"cfull.concept_positive_count_{n} AS concept_positive_count_{n}",
                f"cfull.concept_negative_count_{n} AS concept_negative_count_{n}",
                f"cfull.concept_avg_amount_{n} AS concept_avg_amount_{n}",
                f"cfull.concept_main_flow_sum_{n} AS concept_main_flow_sum_{n}",
                f"cfull.concept_hot_count_{n} AS concept_hot_count_{n}",
            ]
        )
    return f"""
    CREATE OR REPLACE VIEW derived_sector_concept_context_full_v AS
    WITH ret_ext AS (
        SELECT
            ds.ts_code,
            ds.trade_date,
            r.ret_2_hfq,
            CASE WHEN ds.close_hfq > 0 AND lag(ds.close_hfq, 3) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0
                 THEN ds.close_hfq / lag(ds.close_hfq, 3) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) - 1 ELSE NULL END AS ret_3_hfq,
            r.ret_5_hfq,
            r.ret_10_hfq,
            r.ret_20_hfq,
            CASE WHEN ds.close_hfq > 0 AND lag(ds.close_hfq, 30) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0
                 THEN ds.close_hfq / lag(ds.close_hfq, 30) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) - 1 ELSE NULL END AS ret_30_hfq,
            r.ret_60_hfq,
            r.ret_120_hfq,
            r.ret_250_hfq
        FROM derived_daily_spine ds
        LEFT JOIN derived_return_momentum r USING (ts_code, trade_date)
    )
    SELECT
        sc.*,
        {", ".join(extra)}
    FROM derived_sector_concept_context sc
    LEFT JOIN ret_ext r USING (ts_code, trade_date)
    LEFT JOIN derived_sector_daily_cache l1
      ON sc.sw_l1_code = l1.industry_code AND l1.industry_level = 'L1' AND sc.trade_date = l1.trade_date
    LEFT JOIN derived_sector_daily_cache l2
      ON sc.sw_l2_code = l2.industry_code AND l2.industry_level = 'L2' AND sc.trade_date = l2.trade_date
    LEFT JOIN derived_concept_stock_context_cache cfull
      ON sc.ts_code = cfull.ts_code AND sc.trade_date = cfull.trade_date
    """


def index_view_sql() -> str:
    idx_select = ["trade_date"]
    for p, code in INDEX_CODES.items():
        for n in FULL_PERIODS:
            idx_select.append(f"max(CASE WHEN index_code = '{code}' THEN index_ret_{n} END) AS {p}_ret_{n}")
        for n in [5, 20, 60, 120, 250]:
            idx_select.append(f"max(CASE WHEN index_code = '{code}' THEN index_vol_{n} END) AS {p}_vol_{n}")
            idx_select.append(f"max(CASE WHEN index_code = '{code}' THEN index_amount_ma_{n} END) AS {p}_amount_ma_{n}")
    market = []
    for n in NON_CORE:
        market.extend(
            [
                f"avg(amount_total) OVER w{n} AS market_amount_ma_{n}",
                f"avg(up_count::DOUBLE / nullif(stock_count,0)) OVER w{n} AS market_up_ratio_ma_{n}",
                f"up_count::DOUBLE / nullif(stock_count,0) - lag(up_count::DOUBLE / nullif(stock_count,0), {n}) OVER ord AS market_breadth_chg_{n}",
            ]
        )
    market_final = ["trade_date"]
    for n in NON_CORE:
        market_final.extend(
            [
                f"market_amount_ma_{n}",
                f"CASE WHEN lag(market_amount_ma_{n}, {n}) OVER (ORDER BY trade_date) > 0 THEN market_amount_ma_{n} / lag(market_amount_ma_{n}, {n}) OVER (ORDER BY trade_date) - 1 ELSE NULL END AS market_amount_chg_{n}",
                f"market_up_ratio_ma_{n}",
                f"market_breadth_chg_{n}",
            ]
        )
    extra = []
    for n in NON_CORE:
        for p in INDEX_CODES:
            extra.append(f"idx.{p}_ret_{n} AS {p}_ret_{n}")
        primary_case = "CASE " + " ".join(f"WHEN im.primary_index_code = '{code}' THEN idx.{p}_ret_{n}" for p, code in INDEX_CODES.items()) + " ELSE NULL END"
        extra.append(f"{primary_case} AS primary_index_ret_{n}")
        for p in ["hs300", "zz500", "zz1000"]:
            extra.append(f"r.ret_{n}_hfq - idx.{p}_ret_{n} AS stock_excess_{p}_{n}")
        extra.append(f"r.ret_{n}_hfq - ({primary_case}) AS stock_excess_primary_index_{n}")
        extra.extend(
            [
                f"mb.market_amount_ma_{n}",
                f"mb.market_amount_chg_{n}",
                f"mb.market_up_ratio_ma_{n}",
                f"mb.market_breadth_chg_{n}",
                f"idx.hs300_ret_{n} - idx.zz1000_ret_{n} AS large_vs_small_ret_{n}",
                f"idx.zz500_ret_{n} - idx.hs300_ret_{n} AS mid_vs_large_ret_{n}",
                f"idx.chinext_ret_{n} - idx.hs300_ret_{n} AS growth_vs_broad_ret_{n}",
                f"idx.star50_ret_{n} - idx.hs300_ret_{n} AS star_vs_broad_ret_{n}",
            ]
        )
    for p in INDEX_CODES:
        for n in [5, 20, 60, 120, 250]:
            extra.append(f"idx.{p}_vol_{n} AS {p}_vol_{n}")
        for n in [5, 20, 60, 120, 250]:
            extra.append(f"idx.{p}_amount_ma_{n} AS {p}_amount_ma_{n}")
    windows = ", ".join([f"w{n} AS (ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)" for n in NON_CORE] + ["ord AS (ORDER BY trade_date)"])
    return f"""
    CREATE OR REPLACE VIEW derived_index_market_context_full_v AS
    WITH idx AS (
        SELECT {", ".join(idx_select)}
        FROM derived_index_daily_cache
        GROUP BY trade_date
    ),
    ret_ext AS (
        SELECT
            ds.ts_code,
            ds.trade_date,
            r.ret_2_hfq,
            CASE WHEN ds.close_hfq > 0 AND lag(ds.close_hfq, 3) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0
                 THEN ds.close_hfq / lag(ds.close_hfq, 3) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) - 1 ELSE NULL END AS ret_3_hfq,
            r.ret_5_hfq,
            r.ret_10_hfq,
            r.ret_20_hfq,
            CASE WHEN ds.close_hfq > 0 AND lag(ds.close_hfq, 30) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) > 0
                 THEN ds.close_hfq / lag(ds.close_hfq, 30) OVER (PARTITION BY ds.ts_code ORDER BY ds.trade_date) - 1 ELSE NULL END AS ret_30_hfq,
            r.ret_60_hfq,
            r.ret_120_hfq,
            r.ret_250_hfq
        FROM derived_daily_spine ds
        LEFT JOIN derived_return_momentum r USING (ts_code, trade_date)
    ),
    mb_raw AS (
        SELECT trade_date, {", ".join(market)}
        FROM market_breadth_daily
        WINDOW {windows}
    ),
    mb AS (
        SELECT {", ".join(market_final)}
        FROM mb_raw
    )
    SELECT
        im.*,
        {", ".join(extra)}
    FROM derived_index_market_context im
    LEFT JOIN idx ON im.trade_date = idx.trade_date
    LEFT JOIN ret_ext r ON im.ts_code = r.ts_code AND im.trade_date = r.trade_date
    LEFT JOIN mb ON im.trade_date = mb.trade_date
    """


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    con.execute(sector_view_sql())
    con.execute(index_view_sql())
    update_view_schema(con, "derived_sector_concept_context_full_v", "Phase 3 行业概念上下文完整视图")
    update_view_schema(con, "derived_index_market_context_full_v", "Phase 3 指数市场上下文完整视图")
    print({
        "derived_sector_concept_context_full_v": len(con.execute("PRAGMA table_info('derived_sector_concept_context_full_v')").fetchall()),
        "derived_index_market_context_full_v": len(con.execute("PRAGMA table_info('derived_index_market_context_full_v')").fetchall()),
    })


if __name__ == "__main__":
    main()
