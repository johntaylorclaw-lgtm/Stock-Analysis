from __future__ import annotations

import json
import argparse
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
REPORT_PATH = ROOT / "reports" / "phase3_sector_concept_core_run.json"

CORE_PERIODS = [5, 20, 60, 120]
RANK_PERIODS = [20, 60]


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_fields(table: str) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for item in schema["tables"]:
        if item["name"] == table:
            return [field["name"] for field in item["fields"]]
    raise KeyError(table)


def build_sql(start_date: str, end_date: str, columns: list[str]) -> str:
    select: dict[str, str] = {
        "ts_code": "ds.ts_code",
        "trade_date": "ds.trade_date",
        "sw_l1_code": "m.sw_l1_code",
        "sw_l1_name": "m.sw_l1_name",
        "sw_l2_code": "m.sw_l2_code",
        "sw_l2_name": "m.sw_l2_name",
        "has_sw_industry": "m.ts_code IS NOT NULL",
        "industry_member_days": "CASE WHEN m.in_date IS NOT NULL THEN date_diff('day', m.in_date, ds.trade_date)::INTEGER ELSE NULL END",
        "industry_member_is_current": "m.ts_code IS NOT NULL AND (m.out_date IS NULL OR ds.trade_date <= m.out_date)",
        "stock_mv_rank_industry": "rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY v.total_mv DESC NULLS LAST)::INTEGER",
        "stock_mv_pct_industry": "percent_rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY v.total_mv)",
        "stock_pe_ttm_pct_industry": "percent_rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY CASE WHEN v.pe_ttm > 0 THEN v.pe_ttm END)",
        "stock_pb_pct_industry": "percent_rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY CASE WHEN v.pb > 0 THEN v.pb END)",
        "stock_ps_ttm_pct_industry": "percent_rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY CASE WHEN v.ps_ttm > 0 THEN v.ps_ttm END)",
        "concept_count": "coalesce(c.concept_count, 0)",
        "concept_ids_all": "c.concept_ids_all",
        "concept_names_all": "c.concept_names_all",
        "concept_broad_count": "coalesce(c.concept_broad_count, 0)",
        "concept_narrow_count": "coalesce(c.concept_narrow_count, 0)",
        "has_concept": "coalesce(c.concept_count, 0) > 0",
        "sector_context_missing_reason": "CASE WHEN m.ts_code IS NULL THEN 'missing_industry' WHEN coalesce(c.concept_count,0)=0 THEN 'missing_concept' ELSE NULL END",
        "updated_at": "CURRENT_TIMESTAMP",
    }
    for n in CORE_PERIODS:
        for level, alias in [("sw_l1", "l1"), ("sw_l2", "l2")]:
            select[f"{level}_ret_{n}"] = f"{alias}.industry_ret_{n}"
            select[f"stock_excess_{level}_{n}"] = f"r.ret_{n}_hfq - {alias}.industry_ret_{n}"
            select[f"{level}_ret_rank_all_{n}"] = f"{alias}.industry_ret_rank_all_{n}"
            select[f"{level}_ret_pct_all_{n}"] = f"{alias}.industry_ret_pct_all_{n}"
            select[f"{level}_amount_ma_{n}"] = f"{alias}.industry_amount_ma_{n}"
            select[f"{level}_main_flow_sum_{n}"] = f"{alias}.industry_main_flow_sum_{n}"
    for n in RANK_PERIODS:
        select[f"stock_ret_rank_industry_{n}"] = f"rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY r.ret_{n}_hfq DESC NULLS LAST)::INTEGER"
        select[f"stock_ret_pct_industry_{n}"] = f"percent_rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY r.ret_{n}_hfq)"
        amount_expr = "vl.amount_ma_20" if n == 20 else "vl.amount_ma_60"
        select[f"stock_amount_rank_industry_{n}"] = f"rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY {amount_expr} DESC NULLS LAST)::INTEGER"
        select[f"stock_turnover_rank_industry_{n}"] = "rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY b.turnover_rate DESC NULLS LAST)::INTEGER"
        flow_expr = "cf.main_flow_sum_20" if n == 20 else "cf.main_flow_sum_60"
        select[f"stock_main_flow_rank_industry_{n}"] = f"rank() OVER (PARTITION BY m.sw_l2_code, ds.trade_date ORDER BY {flow_expr} DESC NULLS LAST)::INTEGER"
    concept_fields = [
        "concept_ids_top_20", "concept_names_top_20", "concept_lagging_ids_20", "concept_lagging_names_20",
        "concept_active_ids_20", "concept_active_names_20", "concept_narrow_leading_ids_20", "concept_narrow_leading_names_20",
        "concept_best_id_20", "concept_best_name_20", "concept_best_ret_20", "concept_worst_id_20", "concept_worst_name_20",
        "concept_worst_ret_20", "concept_avg_ret_20", "concept_median_ret_20", "concept_max_ret_20", "concept_min_ret_20",
        "concept_ret_spread_20", "concept_positive_count_20", "concept_negative_count_20", "concept_avg_amount_20",
        "concept_main_flow_sum_20", "concept_hot_count_20",
    ]
    for field in concept_fields:
        select[field] = f"c.{field}"
    select_sql = ",\n            ".join(f"{select[col]} AS {q(col)}" for col in columns)
    col_sql = ", ".join(q(col) for col in columns)
    return f"""
    INSERT INTO derived_sector_concept_context ({col_sql})
    WITH member_asof AS (
        SELECT
            ds.ts_code,
            ds.trade_date,
            m.sw_l1_code,
            m.sw_l1_name,
            m.sw_l2_code,
            m.sw_l2_name,
            m.in_date,
            m.out_date,
            row_number() OVER (PARTITION BY ds.ts_code, ds.trade_date ORDER BY m.in_date DESC) AS rn
        FROM derived_daily_spine ds
        LEFT JOIN derived_sw_industry_member_enhanced m
          ON ds.ts_code = m.ts_code
         AND ds.trade_date >= m.in_date
         AND (m.out_date IS NULL OR ds.trade_date <= m.out_date)
        WHERE ds.trade_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
    ),
    concept_ranked AS (
        SELECT
            ds.ts_code,
            ds.trade_date,
            cm.concept_id,
            coalesce(cm.concept_name, cc.concept_name) AS concept_name,
            cc.concept_ret_20,
            cc.concept_amount_pct_all_20,
            cc.concept_amount_ma_20,
            cc.concept_main_flow_sum_20,
            cc.concept_hot_flag_20,
            cc.concept_broad_flag,
            cc.concept_narrow_flag,
            row_number() OVER (PARTITION BY ds.ts_code, ds.trade_date ORDER BY cc.concept_ret_20 DESC NULLS LAST, cm.concept_id) AS rn_lead,
            row_number() OVER (PARTITION BY ds.ts_code, ds.trade_date ORDER BY cc.concept_ret_20 ASC NULLS LAST, cm.concept_id) AS rn_lag,
            row_number() OVER (PARTITION BY ds.ts_code, ds.trade_date ORDER BY cc.concept_amount_pct_all_20 DESC NULLS LAST, cm.concept_id) AS rn_active,
            row_number() OVER (
                PARTITION BY ds.ts_code, ds.trade_date
                ORDER BY CASE WHEN cc.concept_narrow_flag THEN cc.concept_ret_20 ELSE NULL END DESC NULLS LAST, cm.concept_id
            ) AS rn_narrow
        FROM derived_daily_spine ds
        JOIN concept_member cm ON ds.ts_code = cm.ts_code
        LEFT JOIN derived_concept_daily_cache cc
          ON cm.concept_id = cc.concept_id
         AND ds.trade_date = cc.trade_date
        WHERE ds.trade_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
    ),
    concept_agg AS (
        SELECT
            ts_code,
            trade_date,
            count(DISTINCT concept_id)::INTEGER AS concept_count,
            string_agg(DISTINCT concept_id, ';' ORDER BY concept_id) AS concept_ids_all,
            string_agg(DISTINCT concept_name, ';' ORDER BY concept_name) AS concept_names_all,
            sum(CASE WHEN concept_broad_flag THEN 1 ELSE 0 END)::INTEGER AS concept_broad_count,
            sum(CASE WHEN concept_narrow_flag THEN 1 ELSE 0 END)::INTEGER AS concept_narrow_count,
            string_agg(concept_id, ';' ORDER BY rn_lead) FILTER (WHERE rn_lead <= 5 AND concept_ret_20 IS NOT NULL) AS concept_ids_top_20,
            string_agg(concept_name, ';' ORDER BY rn_lead) FILTER (WHERE rn_lead <= 5 AND concept_ret_20 IS NOT NULL) AS concept_names_top_20,
            string_agg(concept_id, ';' ORDER BY rn_lag) FILTER (WHERE rn_lag <= 5 AND concept_ret_20 IS NOT NULL) AS concept_lagging_ids_20,
            string_agg(concept_name, ';' ORDER BY rn_lag) FILTER (WHERE rn_lag <= 5 AND concept_ret_20 IS NOT NULL) AS concept_lagging_names_20,
            string_agg(concept_id, ';' ORDER BY rn_active) FILTER (WHERE rn_active <= 5 AND concept_amount_pct_all_20 IS NOT NULL) AS concept_active_ids_20,
            string_agg(concept_name, ';' ORDER BY rn_active) FILTER (WHERE rn_active <= 5 AND concept_amount_pct_all_20 IS NOT NULL) AS concept_active_names_20,
            string_agg(concept_id, ';' ORDER BY rn_narrow) FILTER (WHERE rn_narrow <= 5 AND concept_narrow_flag) AS concept_narrow_leading_ids_20,
            string_agg(concept_name, ';' ORDER BY rn_narrow) FILTER (WHERE rn_narrow <= 5 AND concept_narrow_flag) AS concept_narrow_leading_names_20,
            max(concept_id) FILTER (WHERE rn_lead = 1 AND concept_ret_20 IS NOT NULL) AS concept_best_id_20,
            max(concept_name) FILTER (WHERE rn_lead = 1 AND concept_ret_20 IS NOT NULL) AS concept_best_name_20,
            max(concept_ret_20) AS concept_best_ret_20,
            max(concept_id) FILTER (WHERE rn_lag = 1 AND concept_ret_20 IS NOT NULL) AS concept_worst_id_20,
            max(concept_name) FILTER (WHERE rn_lag = 1 AND concept_ret_20 IS NOT NULL) AS concept_worst_name_20,
            min(concept_ret_20) AS concept_worst_ret_20,
            avg(concept_ret_20) AS concept_avg_ret_20,
            median(concept_ret_20) AS concept_median_ret_20,
            max(concept_ret_20) AS concept_max_ret_20,
            min(concept_ret_20) AS concept_min_ret_20,
            max(concept_ret_20) - min(concept_ret_20) AS concept_ret_spread_20,
            sum(CASE WHEN concept_ret_20 > 0 THEN 1 ELSE 0 END)::INTEGER AS concept_positive_count_20,
            sum(CASE WHEN concept_ret_20 < 0 THEN 1 ELSE 0 END)::INTEGER AS concept_negative_count_20,
            avg(concept_amount_ma_20) AS concept_avg_amount_20,
            avg(concept_main_flow_sum_20) AS concept_main_flow_sum_20,
            sum(CASE WHEN concept_hot_flag_20 THEN 1 ELSE 0 END)::INTEGER AS concept_hot_count_20
        FROM concept_ranked
        GROUP BY ts_code, trade_date
    )
    SELECT
        {select_sql}
    FROM derived_daily_spine ds
    LEFT JOIN member_asof m ON ds.ts_code = m.ts_code AND ds.trade_date = m.trade_date AND m.rn = 1
    LEFT JOIN derived_sector_daily_cache l1 ON m.sw_l1_code = l1.industry_code AND l1.industry_level = 'L1' AND ds.trade_date = l1.trade_date
    LEFT JOIN derived_sector_daily_cache l2 ON m.sw_l2_code = l2.industry_code AND l2.industry_level = 'L2' AND ds.trade_date = l2.trade_date
    LEFT JOIN derived_return_momentum r ON ds.ts_code = r.ts_code AND ds.trade_date = r.trade_date
    LEFT JOIN derived_volume_liquidity vl ON ds.ts_code = vl.ts_code AND ds.trade_date = vl.trade_date
    LEFT JOIN stock_daily_basic b ON ds.ts_code = b.ts_code AND ds.trade_date = b.trade_date
    LEFT JOIN derived_valuation_size v ON ds.ts_code = v.ts_code AND ds.trade_date = v.trade_date
    LEFT JOIN derived_capital_flow cf ON ds.ts_code = cf.ts_code AND ds.trade_date = cf.trade_date
    LEFT JOIN concept_agg c ON ds.ts_code = c.ts_code AND ds.trade_date = c.trade_date
    WHERE ds.trade_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
    """


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2006)
    parser.add_argument("--no-delete", action="store_true")
    args = parser.parse_args()
    started_at = datetime.now().isoformat(timespec="seconds")
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    columns = table_fields("derived_sector_concept_context")
    if not args.no_delete:
        con.execute("DELETE FROM derived_sector_concept_context")
    years = range(args.start_year, 2027)
    summary = []
    for year in years:
        start = f"{year}-01-01"
        end = "2026-05-26" if year == 2026 else f"{year}-12-31"
        con.execute(
            "DELETE FROM derived_sector_concept_context WHERE trade_date BETWEEN ? AND ?",
            [start, end],
        )
        con.execute(build_sql(start, end, columns))
        rows = con.execute(
            "SELECT count(*) FROM derived_sector_concept_context WHERE trade_date BETWEEN ? AND ?",
            [start, end],
        ).fetchone()[0]
        summary.append({"year": year, "rows": int(rows)})
        print(json.dumps(summary[-1], ensure_ascii=False))
        if year == 2026:
            break
    total = con.execute("SELECT count(*) FROM derived_sector_concept_context").fetchone()[0]
    payload = {"started_at": started_at, "finished_at": datetime.now().isoformat(timespec="seconds"), "rows": int(total), "batches": summary}
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
