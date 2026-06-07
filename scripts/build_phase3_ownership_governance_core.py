from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
REPORT_PATH = ROOT / "reports" / "phase3_ownership_governance_core_run.jsonl"
TABLE_NAME = "derived_ownership_governance"


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_fields() -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return [field["name"] for item in schema["tables"] if item["name"] == TABLE_NAME for field in item["fields"]]


def ratio(num: str, den: str) -> str:
    return f"CASE WHEN {den} > 0 THEN {num} / {den} ELSE NULL END"


def build_insert_sql(start: str, end: str) -> str:
    fields = table_fields()
    column_list = ", ".join(q(name) for name in fields)
    select_list = ",\n        ".join(q(name) for name in fields)
    return f"""
    INSERT INTO {q(TABLE_NAME)} ({column_list})
    WITH days_window AS (
        SELECT
            ds.ts_code,
            ds.trade_date,
            sdb.total_share,
            sdb.float_share,
            sdb.free_share
        FROM derived_daily_spine ds
        LEFT JOIN stock_daily_basic sdb
          ON ds.ts_code = sdb.ts_code AND ds.trade_date = sdb.trade_date
        WHERE ds.trade_date BETWEEN DATE '{start}' - INTERVAL 365 DAY AND DATE '{end}'
    ),
    days AS (
        SELECT *
        FROM days_window
        WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    ),
    pledge_versions AS (
        SELECT
            ts_code,
            end_date,
            pledge_count,
            unrest_pledge,
            rest_pledge,
            total_share,
            pledge_ratio,
            pledge_ratio - lag(pledge_ratio, 1) OVER (PARTITION BY ts_code ORDER BY end_date) AS pledge_ratio_chg_1report,
            pledge_ratio - lag(pledge_ratio, 4) OVER (PARTITION BY ts_code ORDER BY end_date) AS pledge_ratio_chg_4report,
            pledge_count - lag(pledge_count, 1) OVER (PARTITION BY ts_code ORDER BY end_date) AS pledge_count_chg_1report
        FROM financial_pledge_stat
        WHERE end_date IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, end_date
            ORDER BY pledge_count DESC NULLS LAST, pledge_ratio DESC NULLS LAST
        ) = 1
    ),
    holder_versions AS (
        SELECT
            ts_code,
            ann_date,
            end_date,
            holder_num,
            holder_num - lag(holder_num, 1) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date) AS holder_num_chg_1report,
            {ratio("holder_num - lag(holder_num, 1) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date)", "lag(holder_num, 1) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date)")} AS holder_num_chg_rate_1report,
            holder_num - lag(holder_num, 4) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date) AS holder_num_chg_4report,
            {ratio("holder_num - lag(holder_num, 4) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date)", "lag(holder_num, 4) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date)")} AS holder_num_chg_rate_4report
        FROM financial_holder_number
        WHERE ann_date IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, ann_date
            ORDER BY end_date DESC NULLS LAST, record_key DESC NULLS LAST
        ) = 1
    ),
    top10_ranked AS (
        SELECT
            *,
            row_number() OVER (
                PARTITION BY ts_code, ann_date, end_date
                ORDER BY hold_ratio DESC NULLS LAST, hold_amount DESC NULLS LAST, holder_name
            ) AS holder_rank
        FROM financial_top10_holders
        WHERE ann_date IS NOT NULL
    ),
    top10_versions AS (
        SELECT
            ts_code,
            ann_date,
            end_date,
            count(*)::INTEGER AS top10_holder_count_latest,
            max(CASE WHEN holder_rank = 1 THEN hold_ratio END) AS top1_holder_ratio_latest,
            sum(CASE WHEN holder_rank <= 3 THEN coalesce(hold_ratio, 0) ELSE 0 END) AS top3_holder_ratio_latest,
            sum(CASE WHEN holder_rank <= 5 THEN coalesce(hold_ratio, 0) ELSE 0 END) AS top5_holder_ratio_latest,
            sum(coalesce(hold_ratio, 0)) AS top10_holder_ratio_latest,
            sum(power(coalesce(hold_ratio, 0) / 100.0, 2)) AS top10_holder_hhi_latest
        FROM top10_ranked
        GROUP BY ts_code, ann_date, end_date
    ),
    top10_versions_lagged AS (
        SELECT
            *,
            top10_holder_ratio_latest - lag(top10_holder_ratio_latest, 1) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date) AS top10_holder_ratio_chg_1report,
            top1_holder_ratio_latest - lag(top1_holder_ratio_latest, 1) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date) AS top1_holder_ratio_chg_1report
        FROM top10_versions
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, ann_date
            ORDER BY end_date DESC NULLS LAST
        ) = 1
    ),
    top10_float_ranked AS (
        SELECT
            *,
            row_number() OVER (
                PARTITION BY ts_code, ann_date, end_date
                ORDER BY hold_float_ratio DESC NULLS LAST, hold_amount DESC NULLS LAST, holder_name
            ) AS holder_rank
        FROM financial_top10_float_holders
        WHERE ann_date IS NOT NULL
    ),
    top10_float_versions AS (
        SELECT
            ts_code,
            ann_date,
            end_date,
            count(*)::INTEGER AS top10_float_holder_count_latest,
            max(CASE WHEN holder_rank = 1 THEN hold_float_ratio END) AS top1_float_holder_ratio_latest,
            sum(CASE WHEN holder_rank <= 3 THEN coalesce(hold_float_ratio, 0) ELSE 0 END) AS top3_float_holder_ratio_latest,
            sum(CASE WHEN holder_rank <= 5 THEN coalesce(hold_float_ratio, 0) ELSE 0 END) AS top5_float_holder_ratio_latest,
            sum(coalesce(hold_float_ratio, 0)) AS top10_float_holder_ratio_latest,
            sum(power(coalesce(hold_float_ratio, 0) / 100.0, 2)) AS top10_float_holder_hhi_latest
        FROM top10_float_ranked
        GROUP BY ts_code, ann_date, end_date
    ),
    top10_float_versions_lagged AS (
        SELECT
            *,
            top10_float_holder_ratio_latest - lag(top10_float_holder_ratio_latest, 1) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date) AS top10_float_holder_ratio_chg_1report,
            top1_float_holder_ratio_latest - lag(top1_float_holder_ratio_latest, 1) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date) AS top1_float_holder_ratio_chg_1report
        FROM top10_float_versions
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, ann_date
            ORDER BY end_date DESC NULLS LAST
        ) = 1
    ),
    event_days AS (
        SELECT ts_code, end_date AS event_date, count(*) AS event_count
        FROM financial_pledge_stat
        WHERE end_date IS NOT NULL
        GROUP BY ts_code, end_date
        UNION ALL
        SELECT ts_code, ann_date AS event_date, count(*) AS event_count
        FROM financial_holder_number
        WHERE ann_date IS NOT NULL
        GROUP BY ts_code, ann_date
        UNION ALL
        SELECT ts_code, ann_date AS event_date, count(DISTINCT coalesce(CAST(end_date AS VARCHAR), '') || ':' || coalesce(record_key, '')) AS event_count
        FROM financial_top10_holders
        WHERE ann_date IS NOT NULL
        GROUP BY ts_code, ann_date
        UNION ALL
        SELECT ts_code, ann_date AS event_date, count(DISTINCT coalesce(CAST(end_date AS VARCHAR), '') || ':' || coalesce(record_key, '')) AS event_count
        FROM financial_top10_float_holders
        WHERE ann_date IS NOT NULL
        GROUP BY ts_code, ann_date
    ),
    event_day_sum AS (
        SELECT ts_code, event_date, sum(event_count) AS event_count
        FROM event_days
        GROUP BY ts_code, event_date
    ),
    event_roll AS (
        SELECT
            d.ts_code,
            d.trade_date,
            sum(coalesce(e.event_count, 0)) OVER (
                PARTITION BY d.ts_code ORDER BY d.trade_date
                RANGE BETWEEN INTERVAL 365 DAY PRECEDING AND CURRENT ROW
            )::INTEGER AS ownership_event_count_365d
        FROM days_window d
        LEFT JOIN event_day_sum e
          ON d.ts_code = e.ts_code AND d.trade_date = e.event_date
    ),
    joined AS (
        SELECT
            d.ts_code,
            d.trade_date,
            er.ownership_event_count_365d,
            p.end_date AS latest_pledge_end_date,
            p.pledge_count AS pledge_count_asof,
            p.unrest_pledge AS pledge_unreleased_share_asof,
            p.rest_pledge AS pledge_released_share_asof,
            p.total_share AS pledge_total_share_base_asof,
            p.pledge_ratio AS pledge_ratio_asof,
            p.pledge_ratio_chg_1report,
            p.pledge_ratio_chg_4report,
            p.pledge_count_chg_1report,
            {ratio("p.unrest_pledge + p.rest_pledge", "d.total_share")} AS pledge_share_to_total_share_asof,
            CASE WHEN p.end_date IS NOT NULL THEN (d.trade_date - p.end_date)::INTEGER ELSE NULL END AS pledge_stat_staleness_days,
            h.ann_date AS latest_holder_ann_date,
            h.end_date AS latest_holder_end_date,
            h.holder_num AS holder_num_asof,
            h.holder_num_chg_1report,
            h.holder_num_chg_rate_1report,
            h.holder_num_chg_4report,
            h.holder_num_chg_rate_4report,
            {ratio("d.total_share", "h.holder_num")} AS shares_per_holder_asof,
            {ratio("d.free_share", "h.holder_num")} AS free_shares_per_holder_asof,
            {ratio("h.holder_num", "d.total_share")} AS holder_num_to_total_share,
            {ratio("h.holder_num", "d.free_share")} AS holder_num_to_free_share,
            CASE WHEN h.ann_date IS NOT NULL THEN (d.trade_date - h.ann_date)::INTEGER ELSE NULL END AS holder_num_staleness_days,
            t.ann_date AS latest_top10_holder_ann_date,
            t.end_date AS latest_top10_holder_end_date,
            t.top10_holder_count_latest,
            t.top1_holder_ratio_latest,
            t.top3_holder_ratio_latest,
            t.top5_holder_ratio_latest,
            t.top10_holder_ratio_latest,
            t.top10_holder_hhi_latest,
            t.top10_holder_ratio_chg_1report,
            t.top1_holder_ratio_chg_1report,
            CASE WHEN t.ann_date IS NOT NULL THEN (d.trade_date - t.ann_date)::INTEGER ELSE NULL END AS top10_holder_staleness_days,
            tf.ann_date AS latest_top10_float_ann_date,
            tf.end_date AS latest_top10_float_end_date,
            tf.top10_float_holder_count_latest,
            tf.top1_float_holder_ratio_latest,
            tf.top3_float_holder_ratio_latest,
            tf.top5_float_holder_ratio_latest,
            tf.top10_float_holder_ratio_latest,
            tf.top10_float_holder_hhi_latest,
            tf.top10_float_holder_ratio_chg_1report,
            tf.top1_float_holder_ratio_chg_1report,
            CASE WHEN tf.ann_date IS NOT NULL THEN (d.trade_date - tf.ann_date)::INTEGER ELSE NULL END AS top10_float_staleness_days
        FROM days d
        LEFT JOIN event_roll er
          ON d.ts_code = er.ts_code AND d.trade_date = er.trade_date
        ASOF LEFT JOIN pledge_versions p
          ON d.ts_code = p.ts_code AND d.trade_date >= p.end_date
        ASOF LEFT JOIN holder_versions h
          ON d.ts_code = h.ts_code AND d.trade_date >= h.ann_date
        ASOF LEFT JOIN top10_versions_lagged t
          ON d.ts_code = t.ts_code AND d.trade_date >= t.ann_date
        ASOF LEFT JOIN top10_float_versions_lagged tf
          ON d.ts_code = tf.ts_code AND d.trade_date >= tf.ann_date
    )
    SELECT
        {select_list}
    FROM (
        SELECT
            j.ts_code,
            j.trade_date,
            (
                j.latest_pledge_end_date IS NOT NULL
                OR j.latest_holder_ann_date IS NOT NULL
                OR j.latest_top10_holder_ann_date IS NOT NULL
                OR j.latest_top10_float_ann_date IS NOT NULL
            ) AS ownership_available_flag,
            NULLIF(greatest(
                coalesce(j.latest_pledge_end_date, DATE '1900-01-01'),
                coalesce(j.latest_holder_ann_date, DATE '1900-01-01'),
                coalesce(j.latest_top10_holder_ann_date, DATE '1900-01-01'),
                coalesce(j.latest_top10_float_ann_date, DATE '1900-01-01')
            ), DATE '1900-01-01') AS latest_ownership_event_date,
            CASE
                WHEN latest_ownership_event_date IS NOT NULL THEN (j.trade_date - latest_ownership_event_date)::INTEGER
                ELSE NULL
            END AS days_since_latest_ownership_event,
            coalesce(j.ownership_event_count_365d, 0) AS ownership_event_count_365d,
            j.latest_pledge_end_date,
            j.pledge_count_asof,
            j.pledge_unreleased_share_asof,
            j.pledge_released_share_asof,
            j.pledge_total_share_base_asof,
            j.pledge_ratio_asof,
            j.pledge_ratio_chg_1report,
            j.pledge_ratio_chg_4report,
            j.pledge_count_chg_1report,
            j.pledge_share_to_total_share_asof,
            j.pledge_stat_staleness_days,
            CASE WHEN j.pledge_ratio_asof IS NULL THEN NULL ELSE j.pledge_ratio_asof >= 10 END AS pledge_ratio_ge_10_flag,
            CASE WHEN j.pledge_ratio_asof IS NULL THEN NULL ELSE j.pledge_ratio_asof >= 30 END AS pledge_ratio_ge_30_flag,
            CASE WHEN j.pledge_ratio_asof IS NULL THEN NULL ELSE j.pledge_ratio_asof >= 50 END AS pledge_ratio_ge_50_flag,
            j.latest_pledge_end_date IS NOT NULL AS pledge_data_available_flag,
            j.latest_holder_ann_date,
            j.latest_holder_end_date,
            j.holder_num_asof,
            j.holder_num_chg_1report,
            j.holder_num_chg_rate_1report,
            j.holder_num_chg_4report,
            j.holder_num_chg_rate_4report,
            j.shares_per_holder_asof,
            j.free_shares_per_holder_asof,
            j.holder_num_to_total_share,
            j.holder_num_to_free_share,
            j.holder_num_staleness_days,
            j.latest_holder_ann_date IS NOT NULL AS holder_data_available_flag,
            j.latest_top10_holder_ann_date,
            j.latest_top10_holder_end_date,
            j.top10_holder_count_latest,
            j.top1_holder_ratio_latest,
            j.top3_holder_ratio_latest,
            j.top5_holder_ratio_latest,
            j.top10_holder_ratio_latest,
            j.top10_holder_hhi_latest,
            j.top10_holder_ratio_chg_1report,
            j.top1_holder_ratio_chg_1report,
            j.top10_holder_staleness_days,
            j.latest_top10_float_ann_date,
            j.latest_top10_float_end_date,
            j.top10_float_holder_count_latest,
            j.top1_float_holder_ratio_latest,
            j.top3_float_holder_ratio_latest,
            j.top5_float_holder_ratio_latest,
            j.top10_float_holder_ratio_latest,
            j.top10_float_holder_hhi_latest,
            j.top10_float_holder_ratio_chg_1report,
            j.top1_float_holder_ratio_chg_1report,
            j.top10_float_staleness_days,
            coalesce(j.top10_holder_ratio_latest, j.top10_float_holder_ratio_latest) AS ownership_concentration_ratio_latest,
            coalesce(j.top10_holder_ratio_chg_1report, j.top10_float_holder_ratio_chg_1report) AS ownership_concentration_chg_1report,
            j.top10_float_holder_ratio_latest - j.top10_holder_ratio_latest AS float_concentration_premium_latest,
            {ratio("j.pledge_ratio_asof", "j.top10_holder_ratio_latest")} AS pledge_to_concentration_ratio,
            (
                CASE WHEN j.latest_pledge_end_date IS NOT NULL THEN 1 ELSE 0 END
                + CASE WHEN j.latest_holder_ann_date IS NOT NULL THEN 1 ELSE 0 END
                + CASE WHEN j.latest_top10_holder_ann_date IS NOT NULL THEN 1 ELSE 0 END
                + CASE WHEN j.latest_top10_float_ann_date IS NOT NULL THEN 1 ELSE 0 END
            )::INTEGER AS ownership_data_completeness_count,
            (
                CASE WHEN j.latest_pledge_end_date IS NOT NULL THEN 1 ELSE 0 END
                + CASE WHEN j.latest_holder_ann_date IS NOT NULL THEN 1 ELSE 0 END
                + CASE WHEN j.latest_top10_holder_ann_date IS NOT NULL THEN 1 ELSE 0 END
                + CASE WHEN j.latest_top10_float_ann_date IS NOT NULL THEN 1 ELSE 0 END
            ) / 4.0 AS ownership_data_completeness_ratio,
            current_timestamp AS updated_at
        FROM joined j
    ) payload
    """


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2006)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--no-delete", action="store_true")
    args = parser.parse_args()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(DB_PATH) as con, REPORT_PATH.open("a", encoding="utf-8") as report:
        if not args.no_delete:
            con.execute(f"DELETE FROM {q(TABLE_NAME)}")
        for year in range(args.start_year, args.end_year + 1):
            start = f"{year}-01-01"
            end = f"{year}-12-31"
            started_at = datetime.now().isoformat(timespec="seconds")
            con.execute(build_insert_sql(start, end))
            rows = con.execute(
                f"SELECT count(*) FROM {q(TABLE_NAME)} WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}'"
            ).fetchone()[0]
            payload = {
                "year": year,
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "rows": rows,
            }
            line = json.dumps(payload, ensure_ascii=False)
            report.write(line + "\n")
            report.flush()
            print(line)


if __name__ == "__main__":
    main()
