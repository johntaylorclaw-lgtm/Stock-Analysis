from __future__ import annotations

from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"


def holder_type_expr(column: str = "holder_type") -> str:
    return (
        "CASE "
        f"WHEN {column} IS NULL THEN 'unknown' "
        f"WHEN {column} LIKE '%个人%' OR {column} LIKE '%自然人%' THEN 'individual' "
        f"WHEN {column} LIKE '%机构%' OR {column} LIKE '%基金%' OR {column} LIKE '%证券%' "
        f"OR {column} LIKE '%券商%' OR {column} LIKE '%保险%' OR {column} LIKE '%银行%' "
        f"OR {column} LIKE '%信托%' OR {column} LIKE '%社保%' OR {column} LIKE '%QFII%' "
        f"OR {column} LIKE '%RQFII%' OR {column} LIKE '%公司%' OR {column} LIKE '%法人%' "
        f"OR {column} LIKE '%资管%' OR {column} LIKE '%投资%' THEN 'institution' "
        "ELSE 'unknown' END"
    )


def build_concentration_view_sql() -> str:
    return """
    CREATE OR REPLACE VIEW ownership_holder_concentration_v AS
    WITH scoped AS (
        SELECT
            'top10_total' AS holder_scope,
            ts_code,
            end_date,
            ann_date,
            holder_name,
            hold_ratio AS ratio_value,
            row_number() OVER (
                PARTITION BY ts_code, ann_date, end_date
                ORDER BY hold_ratio DESC NULLS LAST, hold_amount DESC NULLS LAST, holder_name
            ) AS holder_rank
        FROM financial_top10_holders
        WHERE ann_date IS NOT NULL
        UNION ALL
        SELECT
            'top10_float' AS holder_scope,
            ts_code,
            end_date,
            ann_date,
            holder_name,
            hold_float_ratio AS ratio_value,
            row_number() OVER (
                PARTITION BY ts_code, ann_date, end_date
                ORDER BY hold_float_ratio DESC NULLS LAST, hold_amount DESC NULLS LAST, holder_name
            ) AS holder_rank
        FROM financial_top10_float_holders
        WHERE ann_date IS NOT NULL
    )
    SELECT
        ts_code,
        end_date,
        ann_date,
        holder_scope,
        count(*)::INTEGER AS holder_count,
        max(CASE WHEN holder_rank = 1 THEN ratio_value END) AS top1_ratio,
        sum(CASE WHEN holder_rank <= 3 THEN coalesce(ratio_value, 0) ELSE 0 END) AS top3_ratio,
        sum(CASE WHEN holder_rank <= 5 THEN coalesce(ratio_value, 0) ELSE 0 END) AS top5_ratio,
        sum(coalesce(ratio_value, 0)) AS top10_ratio,
        sum(power(coalesce(ratio_value, 0) / 100.0, 2)) AS hhi
    FROM scoped
    GROUP BY ts_code, end_date, ann_date, holder_scope
    """


def build_timeline_view_sql() -> str:
    return """
    CREATE OR REPLACE VIEW ownership_governance_event_timeline_v AS
    SELECT
        ts_code,
        'pledge_stat' AS event_type,
        end_date AS event_date,
        end_date AS effective_date,
        end_date,
        NULL::VARCHAR AS record_key,
        NULL::VARCHAR AS holder_name,
        NULL::VARCHAR AS holder_type,
        pledge_ratio AS event_value_1,
        pledge_count AS event_value_2,
        NULL::VARCHAR AS event_text,
        'financial_pledge_stat' AS source_table
    FROM financial_pledge_stat
    UNION ALL
    SELECT
        ts_code,
        CASE
            WHEN lower(CAST(is_release AS VARCHAR)) IN ('true', '1', 'yes', 'y', 't') THEN 'pledge_release'
            ELSE 'pledge_detail'
        END AS event_type,
        coalesce(start_date, ann_date, end_date) AS event_date,
        coalesce(ann_date, start_date, end_date) AS effective_date,
        end_date,
        record_key,
        holder_name,
        NULL::VARCHAR AS holder_type,
        pledge_amount AS event_value_1,
        p_total_ratio AS event_value_2,
        pledgor AS event_text,
        'financial_pledge_detail' AS source_table
    FROM financial_pledge_detail
    UNION ALL
    SELECT
        ts_code,
        'holder_number' AS event_type,
        ann_date AS event_date,
        ann_date AS effective_date,
        end_date,
        record_key,
        NULL::VARCHAR AS holder_name,
        NULL::VARCHAR AS holder_type,
        holder_num AS event_value_1,
        NULL::DOUBLE AS event_value_2,
        NULL::VARCHAR AS event_text,
        'financial_holder_number' AS source_table
    FROM financial_holder_number
    UNION ALL
    SELECT
        ts_code,
        'top10_holder' AS event_type,
        ann_date AS event_date,
        ann_date AS effective_date,
        end_date,
        record_key,
        holder_name,
        holder_type,
        hold_ratio AS event_value_1,
        hold_amount AS event_value_2,
        hold_change AS event_text,
        'financial_top10_holders' AS source_table
    FROM financial_top10_holders
    UNION ALL
    SELECT
        ts_code,
        'top10_float_holder' AS event_type,
        ann_date AS event_date,
        ann_date AS effective_date,
        end_date,
        record_key,
        holder_name,
        holder_type,
        hold_float_ratio AS event_value_1,
        hold_amount AS event_value_2,
        hold_change AS event_text,
        'financial_top10_float_holders' AS source_table
    FROM financial_top10_float_holders
    """


def build_full_view_sql() -> str:
    holder_type = holder_type_expr("holder_type")
    return f"""
    CREATE OR REPLACE VIEW derived_ownership_governance_full_v AS
    WITH lagged AS (
        SELECT
            c.*,
            lag(pledge_ratio_asof, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) AS pledge_ratio_lag_20,
            lag(pledge_ratio_asof, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) AS pledge_ratio_lag_60,
            lag(pledge_ratio_asof, 120) OVER (PARTITION BY ts_code ORDER BY trade_date) AS pledge_ratio_lag_120,
            lag(pledge_ratio_asof, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS pledge_ratio_lag_250,
            lag(pledge_count_asof, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) AS pledge_count_lag_20,
            lag(pledge_count_asof, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) AS pledge_count_lag_60,
            lag(pledge_count_asof, 120) OVER (PARTITION BY ts_code ORDER BY trade_date) AS pledge_count_lag_120,
            lag(pledge_count_asof, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS pledge_count_lag_250,
            lag(holder_num_asof, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) AS holder_num_lag_20,
            lag(holder_num_asof, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) AS holder_num_lag_60,
            lag(holder_num_asof, 120) OVER (PARTITION BY ts_code ORDER BY trade_date) AS holder_num_lag_120,
            lag(holder_num_asof, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS holder_num_lag_250
        FROM derived_ownership_governance c
    ),
    top10_ranked AS (
        SELECT
            *,
            {holder_type} AS holder_type_norm,
            row_number() OVER (
                PARTITION BY ts_code, ann_date, end_date
                ORDER BY hold_ratio DESC NULLS LAST, hold_amount DESC NULLS LAST, holder_name
            ) AS holder_rank
        FROM financial_top10_holders
    ),
    top10_agg AS (
        SELECT
            ts_code,
            ann_date,
            end_date,
            max(CASE WHEN holder_rank = 1 THEN holder_name END) AS top1_holder_name_latest,
            max(CASE WHEN holder_rank = 1 THEN holder_type_norm END) AS top1_holder_type_latest,
            sum(CASE WHEN holder_type_norm = 'institution' THEN coalesce(hold_ratio, 0) ELSE 0 END) AS top10_institution_holder_ratio_latest,
            sum(CASE WHEN holder_type_norm = 'individual' THEN coalesce(hold_ratio, 0) ELSE 0 END) AS top10_individual_holder_ratio_latest,
            sum(try_cast(hold_change AS DOUBLE)) AS top10_holder_change_sum_latest,
            count(CASE WHEN try_cast(hold_change AS DOUBLE) > 0 THEN 1 END)::INTEGER AS top10_holder_positive_change_count,
            count(CASE WHEN try_cast(hold_change AS DOUBLE) < 0 THEN 1 END)::INTEGER AS top10_holder_negative_change_count,
            string_agg(holder_name, '|' ORDER BY holder_name) AS holder_name_set
        FROM top10_ranked
        GROUP BY ts_code, ann_date, end_date
    ),
    top10_agg_lagged AS (
        SELECT
            *,
            lag(holder_name_set, 1) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date) AS previous_holder_name_set
        FROM top10_agg
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, ann_date
            ORDER BY end_date DESC NULLS LAST
        ) = 1
    ),
    top10_float_ranked AS (
        SELECT
            *,
            {holder_type} AS holder_type_norm,
            row_number() OVER (
                PARTITION BY ts_code, ann_date, end_date
                ORDER BY hold_float_ratio DESC NULLS LAST, hold_amount DESC NULLS LAST, holder_name
            ) AS holder_rank
        FROM financial_top10_float_holders
    ),
    top10_float_agg AS (
        SELECT
            ts_code,
            ann_date,
            end_date,
            max(CASE WHEN holder_rank = 1 THEN holder_name END) AS top1_float_holder_name_latest,
            max(CASE WHEN holder_rank = 1 THEN holder_type_norm END) AS top1_float_holder_type_latest,
            sum(CASE WHEN holder_type_norm = 'institution' THEN coalesce(hold_float_ratio, 0) ELSE 0 END) AS top10_float_institution_ratio_latest,
            sum(CASE WHEN holder_type_norm = 'individual' THEN coalesce(hold_float_ratio, 0) ELSE 0 END) AS top10_float_individual_ratio_latest,
            sum(try_cast(hold_change AS DOUBLE)) AS top10_float_holder_change_sum_latest,
            count(CASE WHEN try_cast(hold_change AS DOUBLE) > 0 THEN 1 END)::INTEGER AS top10_float_holder_positive_change_count,
            count(CASE WHEN try_cast(hold_change AS DOUBLE) < 0 THEN 1 END)::INTEGER AS top10_float_holder_negative_change_count,
            string_agg(holder_name, '|' ORDER BY holder_name) AS holder_name_set
        FROM top10_float_ranked
        GROUP BY ts_code, ann_date, end_date
    ),
    top10_float_agg_lagged AS (
        SELECT
            *,
            lag(holder_name_set, 1) OVER (PARTITION BY ts_code ORDER BY ann_date, end_date) AS previous_holder_name_set
        FROM top10_float_agg
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, ann_date
            ORDER BY end_date DESC NULLS LAST
        ) = 1
    )
    SELECT
        l.* EXCLUDE (
            pledge_ratio_lag_20,
            pledge_ratio_lag_60,
            pledge_ratio_lag_120,
            pledge_ratio_lag_250,
            pledge_count_lag_20,
            pledge_count_lag_60,
            pledge_count_lag_120,
            pledge_count_lag_250,
            holder_num_lag_20,
            holder_num_lag_60,
            holder_num_lag_120,
            holder_num_lag_250,
            updated_at
        ),
        l.pledge_ratio_asof - l.pledge_ratio_lag_20 AS pledge_ratio_chg_20d,
        l.pledge_ratio_asof - l.pledge_ratio_lag_60 AS pledge_ratio_chg_60d,
        l.pledge_ratio_asof - l.pledge_ratio_lag_120 AS pledge_ratio_chg_120d,
        l.pledge_ratio_asof - l.pledge_ratio_lag_250 AS pledge_ratio_chg_250d,
        l.pledge_count_asof - l.pledge_count_lag_20 AS pledge_count_chg_20d,
        l.pledge_count_asof - l.pledge_count_lag_60 AS pledge_count_chg_60d,
        l.pledge_count_asof - l.pledge_count_lag_120 AS pledge_count_chg_120d,
        l.pledge_count_asof - l.pledge_count_lag_250 AS pledge_count_chg_250d,
        l.holder_num_asof - l.holder_num_lag_20 AS holder_num_chg_20d,
        l.holder_num_asof - l.holder_num_lag_60 AS holder_num_chg_60d,
        l.holder_num_asof - l.holder_num_lag_120 AS holder_num_chg_120d,
        l.holder_num_asof - l.holder_num_lag_250 AS holder_num_chg_250d,
        CASE WHEN l.holder_num_lag_20 > 0 THEN (l.holder_num_asof - l.holder_num_lag_20) / l.holder_num_lag_20 ELSE NULL END AS holder_num_chg_rate_20d,
        CASE WHEN l.holder_num_lag_60 > 0 THEN (l.holder_num_asof - l.holder_num_lag_60) / l.holder_num_lag_60 ELSE NULL END AS holder_num_chg_rate_60d,
        CASE WHEN l.holder_num_lag_120 > 0 THEN (l.holder_num_asof - l.holder_num_lag_120) / l.holder_num_lag_120 ELSE NULL END AS holder_num_chg_rate_120d,
        CASE WHEN l.holder_num_lag_250 > 0 THEN (l.holder_num_asof - l.holder_num_lag_250) / l.holder_num_lag_250 ELSE NULL END AS holder_num_chg_rate_250d,
        t.top1_holder_name_latest,
        t.top1_holder_type_latest,
        t.top10_institution_holder_ratio_latest,
        t.top10_individual_holder_ratio_latest,
        t.top10_holder_change_sum_latest,
        t.top10_holder_positive_change_count,
        t.top10_holder_negative_change_count,
        CASE
            WHEN t.previous_holder_name_set IS NULL OR t.holder_name_set IS NULL THEN NULL
            WHEN t.previous_holder_name_set = t.holder_name_set THEN 0 ELSE 1
        END AS top10_holder_name_churn_1report,
        tf.top1_float_holder_name_latest,
        tf.top1_float_holder_type_latest,
        tf.top10_float_institution_ratio_latest,
        tf.top10_float_individual_ratio_latest,
        tf.top10_float_holder_change_sum_latest,
        tf.top10_float_holder_positive_change_count,
        tf.top10_float_holder_negative_change_count,
        CASE
            WHEN tf.previous_holder_name_set IS NULL OR tf.holder_name_set IS NULL THEN NULL
            WHEN tf.previous_holder_name_set = tf.holder_name_set THEN 0 ELSE 1
        END AS top10_float_holder_name_churn_1report,
        pd.pledge_detail_active_count_asof,
        pd.pledge_detail_active_amount_asof,
        pr.pledge_release_count_365d,
        l.updated_at
    FROM lagged l
    ASOF LEFT JOIN top10_agg_lagged t
      ON l.ts_code = t.ts_code AND l.trade_date >= t.ann_date
    ASOF LEFT JOIN top10_float_agg_lagged tf
      ON l.ts_code = tf.ts_code AND l.trade_date >= tf.ann_date
    LEFT JOIN LATERAL (
        SELECT
            count(*)::INTEGER AS pledge_detail_active_count_asof,
            sum(pledge_amount) AS pledge_detail_active_amount_asof
        FROM financial_pledge_detail p
        WHERE p.ts_code = l.ts_code
          AND coalesce(p.start_date, p.ann_date) <= l.trade_date
          AND (p.end_date IS NULL OR p.end_date >= l.trade_date)
          AND coalesce(lower(CAST(p.is_release AS VARCHAR)) IN ('true', '1', 'yes', 'y', 't'), false) = false
    ) pd ON true
    LEFT JOIN LATERAL (
        SELECT count(*)::INTEGER AS pledge_release_count_365d
        FROM financial_pledge_detail p
        WHERE p.ts_code = l.ts_code
          AND coalesce(lower(CAST(p.is_release AS VARCHAR)) IN ('true', '1', 'yes', 'y', 't'), false) = true
          AND coalesce(p.ann_date, p.end_date) BETWEEN l.trade_date - INTERVAL 365 DAY AND l.trade_date
    ) pr ON true
    """


def main() -> None:
    with duckdb.connect(DB_PATH) as con:
        con.execute(build_concentration_view_sql())
        con.execute(build_timeline_view_sql())
        con.execute(build_full_view_sql())
        counts = {
            "ownership_holder_concentration_v": con.execute(
                "SELECT count(*) FROM pragma_table_info('ownership_holder_concentration_v')"
            ).fetchone()[0],
            "ownership_governance_event_timeline_v": con.execute(
                "SELECT count(*) FROM pragma_table_info('ownership_governance_event_timeline_v')"
            ).fetchone()[0],
            "derived_ownership_governance_full_v": con.execute(
                "SELECT count(*) FROM pragma_table_info('derived_ownership_governance_full_v')"
            ).fetchone()[0],
        }
        print(counts)


if __name__ == "__main__":
    main()
