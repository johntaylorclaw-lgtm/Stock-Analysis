from __future__ import annotations

from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"


def build_timeline_sql() -> str:
    return """
    CREATE OR REPLACE VIEW corporate_action_event_timeline_v AS
    SELECT
        ts_code,
        'dividend' AS event_type,
        coalesce(ex_date, record_date, ann_date) AS event_date,
        coalesce(ann_date, record_date, ex_date) AS effective_date,
        end_date,
        record_key,
        cash_div AS event_value_1,
        coalesce(stk_bo_rate, 0) + coalesce(stk_co_rate, 0) AS event_value_2,
        div_proc AS event_text,
        'financial_dividend' AS source_table
    FROM financial_dividend
    UNION ALL
    SELECT
        ts_code,
        'forecast' AS event_type,
        ann_date AS event_date,
        ann_date AS effective_date,
        end_date,
        record_key,
        CASE WHEN net_profit_min IS NOT NULL AND net_profit_max IS NOT NULL THEN (net_profit_min + net_profit_max) / 2 ELSE NULL END,
        CASE WHEN p_change_min IS NOT NULL AND p_change_max IS NOT NULL THEN (p_change_min + p_change_max) / 2 ELSE NULL END,
        forecast_type,
        'financial_forecast'
    FROM financial_forecast
    UNION ALL
    SELECT
        ts_code,
        'express' AS event_type,
        ann_date AS event_date,
        ann_date AS effective_date,
        end_date,
        record_key,
        net_profit,
        yoy_net_profit,
        performance_summary,
        'financial_express'
    FROM financial_express
    UNION ALL
    SELECT
        ts_code,
        'audit' AS event_type,
        ann_date AS event_date,
        ann_date AS effective_date,
        end_date,
        record_key,
        audit_fees,
        NULL::DOUBLE,
        audit_result,
        'financial_audit_opinion'
    FROM financial_audit_opinion
    UNION ALL
    SELECT
        ts_code,
        'main_business' AS event_type,
        COALESCE(
            TRY_CAST(ann_date AS DATE),
            TRY_STRPTIME(CAST(ann_date AS VARCHAR), '%Y%m%d')::DATE
        ) AS event_date,
        COALESCE(
            TRY_CAST(ann_date AS DATE),
            TRY_STRPTIME(CAST(ann_date AS VARCHAR), '%Y%m%d')::DATE
        ) AS effective_date,
        end_date,
        record_key,
        TRY_CAST(json_extract_string(payload_json, '$.bz_sales') AS DOUBLE),
        TRY_CAST(json_extract_string(payload_json, '$.bz_profit') AS DOUBLE),
        json_extract_string(payload_json, '$.bz_item'),
        'financial_event_raw:fina_mainbz'
    FROM financial_event_raw
    WHERE api_name = 'fina_mainbz'
    UNION ALL
    SELECT
        ts_code,
        'repurchase' AS event_type,
        ann_date AS event_date,
        ann_date AS effective_date,
        end_date,
        record_key,
        amount,
        volume,
        proc,
        'financial_repurchase'
    FROM financial_repurchase
    UNION ALL
    SELECT
        ts_code,
        'share_float' AS event_type,
        float_date AS event_date,
        ann_date AS effective_date,
        NULL::DATE AS end_date,
        record_key,
        float_share,
        float_ratio,
        share_type,
        'financial_share_float'
    FROM financial_share_float
    """


def build_full_view_sql() -> str:
    return """
    CREATE OR REPLACE VIEW derived_corporate_action_full_v AS
    WITH mainbz_detail AS (
        SELECT
            ts_code,
            coalesce(
                COALESCE(
                    TRY_CAST(ann_date AS DATE),
                    TRY_STRPTIME(CAST(ann_date AS VARCHAR), '%Y%m%d')::DATE
                ),
                end_date + INTERVAL 120 DAY
            ) AS ann_date,
            end_date,
            json_extract_string(payload_json, '$.bz_item') AS bz_item,
            json_extract_string(payload_json, '$.bz_code') AS bz_code,
            TRY_CAST(json_extract_string(payload_json, '$.bz_sales') AS DOUBLE) AS bz_sales,
            TRY_CAST(json_extract_string(payload_json, '$.bz_profit') AS DOUBLE) AS bz_profit
        FROM financial_event_raw
        WHERE api_name = 'fina_mainbz'
    ),
    mainbz_latest AS (
        SELECT
            c.ts_code,
            c.trade_date,
            arg_max(m.bz_item, m.bz_sales) AS mainbz_top1_item_latest,
            arg_max(m.bz_code, m.bz_sales) AS mainbz_top1_code_latest,
            sum(power(m.bz_sales / NULLIF(c.mainbz_revenue_total_latest, 0), 2)) AS mainbz_hhi_revenue_latest,
            sum(power(m.bz_profit / NULLIF(c.mainbz_profit_total_latest, 0), 2)) AS mainbz_hhi_profit_latest
        FROM derived_corporate_action c
        LEFT JOIN mainbz_detail m
          ON c.ts_code = m.ts_code
         AND c.latest_mainbz_end_date = m.end_date
         AND m.ann_date <= c.trade_date
        GROUP BY c.ts_code, c.trade_date
    ),
    lagged AS (
        SELECT
            c.*,
            lag(total_share_asof, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) AS total_share_lag_60,
            lag(total_share_asof, 120) OVER (PARTITION BY ts_code ORDER BY trade_date) AS total_share_lag_120,
            lag(total_share_asof, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS total_share_lag_250,
            lag(float_share_asof, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) AS float_share_lag_60,
            lag(float_share_asof, 120) OVER (PARTITION BY ts_code ORDER BY trade_date) AS float_share_lag_120,
            lag(float_share_asof, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS float_share_lag_250,
            lag(free_share_asof, 60) OVER (PARTITION BY ts_code ORDER BY trade_date) AS free_share_lag_60,
            lag(free_share_asof, 120) OVER (PARTITION BY ts_code ORDER BY trade_date) AS free_share_lag_120,
            lag(free_share_asof, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS free_share_lag_250,
            lag(mainbz_segment_count_latest, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS mainbz_segment_count_lag_1y,
            lag(mainbz_top1_revenue_ratio_latest, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS mainbz_top1_revenue_ratio_lag_1y,
            lag(audit_fees_latest, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS audit_fees_lag_1y,
            lag(audit_agency_latest, 250) OVER (PARTITION BY ts_code ORDER BY trade_date) AS audit_agency_lag_1y,
            lag(latest_dividend_ex_date, 1) OVER (PARTITION BY ts_code ORDER BY trade_date) AS previous_dividend_ex_date_daily
        FROM derived_corporate_action c
    )
    SELECT
        l.* EXCLUDE (
            total_share_lag_60,
            total_share_lag_120,
            total_share_lag_250,
            float_share_lag_60,
            float_share_lag_120,
            float_share_lag_250,
            free_share_lag_60,
            free_share_lag_120,
            free_share_lag_250,
            mainbz_segment_count_lag_1y,
            mainbz_top1_revenue_ratio_lag_1y,
            audit_fees_lag_1y,
            audit_agency_lag_1y,
            previous_dividend_ex_date_daily
        ),
        div3.cash_dividend_3y_sum,
        div5.cash_dividend_5y_sum,
        div3.dividend_year_count_3y,
        div5.dividend_year_count_5y,
        CASE
            WHEN l.latest_dividend_ex_date IS NOT NULL AND l.previous_dividend_ex_date_daily IS NOT NULL
            THEN (l.latest_dividend_ex_date - l.previous_dividend_ex_date_daily)::INTEGER
            ELSE NULL
        END AS dividend_interval_days_latest,
        CASE WHEN sdb.close > 0 THEN l.cash_dividend_ttm / sdb.close ELSE NULL END AS cash_dividend_ttm_to_close,
        CASE WHEN sdb.total_mv > 0 THEN l.cash_dividend_ttm * sdb.total_share / sdb.total_mv ELSE NULL END AS cash_dividend_ttm_to_total_mv,
        fc.forecast_count_365d,
        fcr.forecast_revision_count_same_end_date,
        fcl.summary AS forecast_latest_summary,
        fcl.change_reason AS forecast_latest_change_reason,
        exr.express_count_365d,
        exl.performance_summary AS express_latest_performance_summary,
        l.audit_fees_latest - l.audit_fees_lag_1y AS audit_fees_change_1y,
        CASE WHEN l.audit_fees_lag_1y > 0 THEN (l.audit_fees_latest - l.audit_fees_lag_1y) / l.audit_fees_lag_1y ELSE NULL END AS audit_fees_change_rate_1y,
        CASE WHEN l.audit_agency_lag_1y IS NULL OR l.audit_agency_latest IS NULL THEN NULL ELSE l.audit_agency_latest != l.audit_agency_lag_1y END AS audit_agency_changed_flag,
        aud5.non_standard_audit_count_5y,
        mb.mainbz_top1_item_latest,
        mb.mainbz_top1_code_latest,
        mb.mainbz_hhi_revenue_latest,
        mb.mainbz_hhi_profit_latest,
        l.mainbz_segment_count_latest - l.mainbz_segment_count_lag_1y AS mainbz_segment_count_change_1y,
        l.mainbz_top1_revenue_ratio_latest - l.mainbz_top1_revenue_ratio_lag_1y AS mainbz_top1_revenue_ratio_change_1y,
        CASE WHEN sdb.total_mv > 0 THEN l.repurchase_amount_365d / sdb.total_mv ELSE NULL END AS repurchase_amount_to_total_mv_365d,
        CASE WHEN sdb.total_share > 0 THEN l.repurchase_volume_365d / sdb.total_share ELSE NULL END AS repurchase_volume_to_total_share_365d,
        rp3.repurchase_amount_3y,
        rp3.repurchase_count_3y,
        sf_future.next_share_float_share_180d,
        sf_future.next_share_float_ratio_180d,
        sf3.share_float_share_3y,
        sf3.share_float_ratio_3y,
        l.total_share_asof - l.total_share_lag_60 AS total_share_chg_60d,
        l.total_share_asof - l.total_share_lag_120 AS total_share_chg_120d,
        l.total_share_asof - l.total_share_lag_250 AS total_share_chg_250d,
        l.float_share_asof - l.float_share_lag_60 AS float_share_chg_60d,
        l.float_share_asof - l.float_share_lag_120 AS float_share_chg_120d,
        l.float_share_asof - l.float_share_lag_250 AS float_share_chg_250d,
        l.free_share_asof - l.free_share_lag_60 AS free_share_chg_60d,
        l.free_share_asof - l.free_share_lag_120 AS free_share_chg_120d,
        l.free_share_asof - l.free_share_lag_250 AS free_share_chg_250d
    FROM lagged l
    LEFT JOIN stock_daily_basic sdb
      ON l.ts_code = sdb.ts_code AND l.trade_date = sdb.trade_date
    LEFT JOIN mainbz_latest mb
      ON l.ts_code = mb.ts_code AND l.trade_date = mb.trade_date
    LEFT JOIN LATERAL (
        SELECT sum(cash_div) AS cash_dividend_3y_sum, count(DISTINCT year(coalesce(ex_date, record_date, ann_date)))::INTEGER AS dividend_year_count_3y
        FROM financial_dividend d
        WHERE d.ts_code = l.ts_code AND coalesce(d.ex_date, d.record_date, d.ann_date) BETWEEN l.trade_date - INTERVAL 3 YEAR AND l.trade_date
    ) div3 ON true
    LEFT JOIN LATERAL (
        SELECT sum(cash_div) AS cash_dividend_5y_sum, count(DISTINCT year(coalesce(ex_date, record_date, ann_date)))::INTEGER AS dividend_year_count_5y
        FROM financial_dividend d
        WHERE d.ts_code = l.ts_code AND coalesce(d.ex_date, d.record_date, d.ann_date) BETWEEN l.trade_date - INTERVAL 5 YEAR AND l.trade_date
    ) div5 ON true
    LEFT JOIN LATERAL (
        SELECT count(*)::INTEGER AS forecast_count_365d
        FROM financial_forecast f
        WHERE f.ts_code = l.ts_code AND f.ann_date BETWEEN l.trade_date - INTERVAL 365 DAY AND l.trade_date
    ) fc ON true
    LEFT JOIN LATERAL (
        SELECT count(DISTINCT ann_date)::INTEGER AS forecast_revision_count_same_end_date
        FROM financial_forecast f
        WHERE f.ts_code = l.ts_code AND f.end_date = l.latest_forecast_end_date AND f.ann_date <= l.trade_date
    ) fcr ON true
    LEFT JOIN LATERAL (
        SELECT summary, change_reason
        FROM financial_forecast f
        WHERE f.ts_code = l.ts_code
          AND f.ann_date = l.latest_forecast_ann_date
          AND f.end_date = l.latest_forecast_end_date
        ORDER BY record_key DESC NULLS LAST
        LIMIT 1
    ) fcl ON true
    LEFT JOIN LATERAL (
        SELECT count(*)::INTEGER AS express_count_365d
        FROM financial_express e
        WHERE e.ts_code = l.ts_code AND e.ann_date BETWEEN l.trade_date - INTERVAL 365 DAY AND l.trade_date
    ) exr ON true
    LEFT JOIN LATERAL (
        SELECT performance_summary
        FROM financial_express e
        WHERE e.ts_code = l.ts_code
          AND e.ann_date = l.latest_express_ann_date
          AND e.end_date = l.latest_express_end_date
        ORDER BY record_key DESC NULLS LAST
        LIMIT 1
    ) exl ON true
    LEFT JOIN LATERAL (
        SELECT count(*)::INTEGER AS non_standard_audit_count_5y
        FROM financial_audit_opinion a
        WHERE a.ts_code = l.ts_code
          AND a.ann_date BETWEEN l.trade_date - INTERVAL 5 YEAR AND l.trade_date
          AND (
              a.audit_result NOT LIKE '%标准无保留%'
              OR a.audit_result LIKE '%强调事项%'
          )
    ) aud5 ON true
    LEFT JOIN LATERAL (
        SELECT sum(amount) AS repurchase_amount_3y, count(*)::INTEGER AS repurchase_count_3y
        FROM financial_repurchase r
        WHERE r.ts_code = l.ts_code AND r.ann_date BETWEEN l.trade_date - INTERVAL 3 YEAR AND l.trade_date
    ) rp3 ON true
    LEFT JOIN LATERAL (
        SELECT sum(float_share) AS next_share_float_share_180d, sum(float_ratio) AS next_share_float_ratio_180d
        FROM financial_share_float sf
        WHERE sf.ts_code = l.ts_code
          AND sf.ann_date <= l.trade_date
          AND sf.float_date > l.trade_date
          AND sf.float_date <= l.trade_date + INTERVAL 180 DAY
    ) sf_future ON true
    LEFT JOIN LATERAL (
        SELECT sum(float_share) AS share_float_share_3y, sum(float_ratio) AS share_float_ratio_3y
        FROM financial_share_float sf
        WHERE sf.ts_code = l.ts_code AND sf.float_date BETWEEN l.trade_date - INTERVAL 3 YEAR AND l.trade_date
    ) sf3 ON true
    """


def main() -> None:
    with duckdb.connect(DB_PATH) as con:
        con.execute(build_timeline_sql())
        con.execute(build_full_view_sql())
        timeline_cols = con.execute("SELECT count(*) FROM pragma_table_info('corporate_action_event_timeline_v')").fetchone()[0]
        full_cols = con.execute("SELECT count(*) FROM pragma_table_info('derived_corporate_action_full_v')").fetchone()[0]
        print({"corporate_action_event_timeline_v": timeline_cols, "derived_corporate_action_full_v": full_cols})


if __name__ == "__main__":
    main()
