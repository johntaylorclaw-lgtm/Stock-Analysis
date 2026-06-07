from __future__ import annotations

import argparse
import bisect
import json
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
REPORT_PATH = ROOT / "reports" / "phase3_corporate_action_core_run.jsonl"
TABLE_NAME = "derived_corporate_action"


class Fenwick:
    def __init__(self, n: int) -> None:
        self.n = n
        self.tree = [0.0] * (n + 1)

    def add(self, index: int, value: float) -> None:
        i = index + 1
        while i <= self.n:
            self.tree[i] += value
            i += i & -i

    def sum(self, index: int) -> float:
        if index < 0:
            return 0.0
        i = min(index + 1, self.n)
        total = 0.0
        while i > 0:
            total += self.tree[i]
            i -= i & -i
        return total

    def range_sum(self, left: int, right: int) -> float:
        if right < left:
            return 0.0
        return self.sum(right) - self.sum(left - 1)

    def find_first_prefix_gt(self, value: float) -> int | None:
        if self.sum(self.n - 1) <= value:
            return None
        idx = 0
        bit = 1 << (self.n.bit_length() - 1)
        running = 0.0
        while bit:
            nxt = idx + bit
            if nxt <= self.n and running + self.tree[nxt] <= value:
                idx = nxt
                running += self.tree[nxt]
            bit >>= 1
        return idx


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_fields() -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return [field["name"] for item in schema["tables"] if item["name"] == TABLE_NAME for field in item["fields"]]


def forecast_type_code(expr: str) -> str:
    return (
        "CASE "
        f"WHEN {expr} LIKE '%预增%' THEN 1 "
        f"WHEN {expr} LIKE '%略增%' THEN 2 "
        f"WHEN {expr} LIKE '%扭亏%' THEN 3 "
        f"WHEN {expr} LIKE '%续盈%' THEN 4 "
        f"WHEN {expr} LIKE '%预减%' THEN 5 "
        f"WHEN {expr} LIKE '%略减%' THEN 6 "
        f"WHEN {expr} LIKE '%首亏%' THEN 7 "
        f"WHEN {expr} LIKE '%续亏%' THEN 8 "
        f"WHEN {expr} LIKE '%不确定%' THEN 9 "
        f"WHEN {expr} IS NULL THEN NULL ELSE 99 END"
    )


def audit_code(expr: str) -> str:
    return (
        "CASE "
        f"WHEN {expr} LIKE '%标准无保留%' THEN 1 "
        f"WHEN {expr} LIKE '%强调事项%' THEN 2 "
        f"WHEN {expr} LIKE '%保留意见%' THEN 3 "
        f"WHEN {expr} LIKE '%否定意见%' THEN 4 "
        f"WHEN {expr} LIKE '%无法表示%' THEN 5 "
        f"WHEN {expr} IS NULL THEN NULL ELSE 99 END"
    )


def repurchase_code(expr: str) -> str:
    return (
        "CASE "
        f"WHEN {expr} LIKE '%预案%' THEN 1 "
        f"WHEN {expr} LIKE '%股东大会%' OR {expr} LIKE '%通过%' THEN 2 "
        f"WHEN {expr} LIKE '%实施%' AND {expr} NOT LIKE '%完成%' AND {expr} NOT LIKE '%停止%' THEN 3 "
        f"WHEN {expr} LIKE '%完成%' THEN 4 "
        f"WHEN {expr} LIKE '%停止%' OR {expr} LIKE '%终止%' THEN 5 "
        f"WHEN {expr} IS NULL THEN NULL ELSE 99 END"
    )


def safe_div(num: str, den: str) -> str:
    return f"CASE WHEN {den} > 0 THEN {num} / {den} ELSE NULL END"


def build_insert_sql(start: str, end: str, write_start: str | None = None) -> str:
    output_start = write_start or start
    fields = table_fields()
    column_list = ", ".join(q(name) for name in fields)
    select_list = ",\n        ".join(q(name) for name in fields)
    return f"""
    INSERT INTO {q(TABLE_NAME)} ({column_list})
    WITH days_context AS (
        SELECT
            ds.ts_code,
            ds.trade_date,
            sdb.close AS close_raw,
            sdb.total_share,
            sdb.float_share,
            sdb.free_share,
            sdb.total_mv
        FROM derived_daily_spine ds
        LEFT JOIN stock_daily_basic sdb
          ON ds.ts_code = sdb.ts_code AND ds.trade_date = sdb.trade_date
        WHERE ds.trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    ),
    days_enriched AS (
        SELECT
            *,
            total_share - lag(total_share, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) AS total_share_chg_20d,
            float_share - lag(float_share, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) AS float_share_chg_20d,
            free_share - lag(free_share, 20) OVER (PARTITION BY ts_code ORDER BY trade_date) AS free_share_chg_20d
        FROM days_context
    ),
    days AS (
        SELECT *
        FROM days_enriched
        WHERE trade_date BETWEEN DATE '{output_start}' AND DATE '{end}'
    ),
    dividend_events AS (
        SELECT
            ts_code,
            end_date,
            ann_date,
            record_key,
            div_proc,
            stk_div,
            stk_bo_rate,
            stk_co_rate,
            cash_div,
            cash_div_tax,
            record_date,
            ex_date,
            pay_date,
            coalesce(ann_date, record_date, ex_date) AS effective_date,
            coalesce(ex_date, record_date, ann_date) AS event_date
        FROM financial_dividend
        WHERE coalesce(ann_date, record_date, ex_date) IS NOT NULL
    ),
    dividend_latest AS (
        SELECT *
        FROM dividend_events
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, effective_date
            ORDER BY event_date DESC NULLS LAST, record_key DESC NULLS LAST
        ) = 1
    ),
    dividend_day AS (
        SELECT
            ts_code,
            event_date,
            sum(cash_div) AS cash_div_day,
            sum(cash_div_tax) AS cash_div_tax_day,
            sum(coalesce(stk_bo_rate, 0) + coalesce(stk_co_rate, 0)) AS stock_div_day,
            count(*) AS dividend_count_day
        FROM dividend_events
        WHERE event_date IS NOT NULL
        GROUP BY ts_code, event_date
    ),
    dividend_roll AS (
        SELECT
            d.ts_code,
            d.trade_date,
            sum(coalesce(dd.cash_div_day, 0)) OVER (
                PARTITION BY d.ts_code ORDER BY d.trade_date
                RANGE BETWEEN INTERVAL 365 DAY PRECEDING AND CURRENT ROW
            ) AS cash_dividend_ttm,
            sum(coalesce(dd.cash_div_tax_day, 0)) OVER (
                PARTITION BY d.ts_code ORDER BY d.trade_date
                RANGE BETWEEN INTERVAL 365 DAY PRECEDING AND CURRENT ROW
            ) AS cash_dividend_after_tax_ttm,
            sum(coalesce(dd.stock_div_day, 0)) OVER (
                PARTITION BY d.ts_code ORDER BY d.trade_date
                RANGE BETWEEN INTERVAL 365 DAY PRECEDING AND CURRENT ROW
            ) AS stock_dividend_ratio_ttm,
            sum(coalesce(dd.dividend_count_day, 0)) OVER (
                PARTITION BY d.ts_code ORDER BY d.trade_date
                RANGE BETWEEN INTERVAL 365 DAY PRECEDING AND CURRENT ROW
            )::INTEGER AS dividend_event_count_365d
        FROM days_context d
        LEFT JOIN dividend_day dd
          ON d.ts_code = dd.ts_code AND d.trade_date = dd.event_date
    ),
    dividend_next AS (
        SELECT
            d.ts_code,
            d.trade_date,
            min(e.ex_date) AS next_announced_ex_date,
            arg_min(e.cash_div, e.ex_date) AS next_announced_cash_dividend,
            count(*) > 0 AS has_dividend_announced_not_executed
        FROM days d
        LEFT JOIN dividend_events e
          ON d.ts_code = e.ts_code
         AND e.ann_date <= d.trade_date
         AND e.ex_date > d.trade_date
        GROUP BY d.ts_code, d.trade_date
    ),
    forecast_versions AS (
        SELECT *
        FROM financial_forecast
        WHERE ann_date IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, ann_date
            ORDER BY end_date DESC NULLS LAST, record_key DESC NULLS LAST
        ) = 1
    ),
    express_versions AS (
        SELECT *
        FROM financial_express
        WHERE ann_date IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, ann_date
            ORDER BY end_date DESC NULLS LAST, record_key DESC NULLS LAST
        ) = 1
    ),
    audit_versions AS (
        SELECT *
        FROM financial_audit_opinion
        WHERE ann_date IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, ann_date
            ORDER BY end_date DESC NULLS LAST, record_key DESC NULLS LAST
        ) = 1
    ),
    mainbz_raw AS (
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
            record_key,
            json_extract_string(payload_json, '$.bz_item') AS bz_item,
            json_extract_string(payload_json, '$.bz_code') AS bz_code,
            TRY_CAST(json_extract_string(payload_json, '$.bz_sales') AS DOUBLE) AS bz_sales,
            TRY_CAST(json_extract_string(payload_json, '$.bz_profit') AS DOUBLE) AS bz_profit,
            TRY_CAST(json_extract_string(payload_json, '$.bz_cost') AS DOUBLE) AS bz_cost
        FROM financial_event_raw
        WHERE api_name = 'fina_mainbz'
    ),
    mainbz_summary AS (
        SELECT
            ts_code,
            ann_date,
            end_date,
            count(*)::INTEGER AS mainbz_segment_count_latest,
            sum(bz_sales) AS mainbz_revenue_total_latest,
            sum(bz_profit) AS mainbz_profit_total_latest,
            sum(bz_cost) AS mainbz_cost_total_latest,
            {safe_div('max(bz_sales)', 'sum(bz_sales)')} AS mainbz_top1_revenue_ratio_latest,
            {safe_div('sum(CASE WHEN rn_sales <= 3 THEN bz_sales ELSE 0 END)', 'sum(bz_sales)')} AS mainbz_top3_revenue_ratio_latest,
            {safe_div('max(bz_profit)', 'sum(bz_profit)')} AS mainbz_top1_profit_ratio_latest,
            {safe_div('sum(bz_sales) - sum(bz_cost)', 'sum(bz_sales)')} AS mainbz_gross_margin_latest
        FROM (
            SELECT
                *,
                row_number() OVER (PARTITION BY ts_code, ann_date, end_date ORDER BY bz_sales DESC NULLS LAST) AS rn_sales
            FROM mainbz_raw
            WHERE ann_date IS NOT NULL
        )
        GROUP BY ts_code, ann_date, end_date
    ),
    repurchase_versions AS (
        SELECT *
        FROM financial_repurchase
        WHERE ann_date IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, ann_date
            ORDER BY end_date DESC NULLS LAST, record_key DESC NULLS LAST
        ) = 1
    ),
    repurchase_day AS (
        SELECT
            ts_code,
            ann_date,
            sum(amount) AS amount_day,
            sum(volume) AS volume_day,
            count(*) AS count_day
        FROM financial_repurchase
        WHERE ann_date IS NOT NULL
        GROUP BY ts_code, ann_date
    ),
    repurchase_roll AS (
        SELECT
            d.ts_code,
            d.trade_date,
            sum(coalesce(rd.amount_day, 0)) OVER (
                PARTITION BY d.ts_code ORDER BY d.trade_date
                RANGE BETWEEN INTERVAL 365 DAY PRECEDING AND CURRENT ROW
            ) AS repurchase_amount_365d,
            sum(coalesce(rd.volume_day, 0)) OVER (
                PARTITION BY d.ts_code ORDER BY d.trade_date
                RANGE BETWEEN INTERVAL 365 DAY PRECEDING AND CURRENT ROW
            ) AS repurchase_volume_365d,
            sum(coalesce(rd.count_day, 0)) OVER (
                PARTITION BY d.ts_code ORDER BY d.trade_date
                RANGE BETWEEN INTERVAL 365 DAY PRECEDING AND CURRENT ROW
            )::INTEGER AS repurchase_count_365d
        FROM days_context d
        LEFT JOIN repurchase_day rd
          ON d.ts_code = rd.ts_code AND d.trade_date = rd.ann_date
    ),
    share_float_roll AS (
        SELECT
            d.ts_code,
            d.trade_date,
            NULL::DATE AS latest_share_float_ann_date,
            NULL::DATE AS latest_share_float_date,
            NULL::DOUBLE AS share_float_share_365d,
            NULL::DOUBLE AS share_float_ratio_365d,
            NULL::INTEGER AS share_float_event_count_365d
        FROM days d
    ),
    share_float_latest_values AS (
        SELECT
            d.ts_code,
            d.trade_date,
            NULL::DOUBLE AS latest_share_float_share,
            NULL::DOUBLE AS latest_share_float_ratio
        FROM days d
    ),
    share_float_future AS (
        SELECT
            d.ts_code,
            d.trade_date,
            NULL::DATE AS next_share_float_date_30d,
            NULL::DOUBLE AS next_share_float_share_30d,
            NULL::DOUBLE AS next_share_float_ratio_30d,
            NULL::DOUBLE AS next_share_float_share_90d,
            NULL::DOUBLE AS next_share_float_ratio_90d
        FROM days d
    ),
    base AS (
        SELECT
            d.ts_code,
            d.trade_date,
            dl.ann_date AS latest_dividend_ann_date,
            dl.end_date AS latest_dividend_end_date,
            dl.ex_date AS latest_dividend_ex_date,
            dl.record_date AS latest_dividend_record_date,
            dl.pay_date AS latest_dividend_pay_date,
            dl.div_proc AS latest_dividend_proc,
            dl.cash_div AS cash_dividend_per_share_latest,
            dl.cash_div_tax AS cash_dividend_after_tax_latest,
            dl.stk_bo_rate AS bonus_share_ratio_latest,
            dl.stk_co_rate AS transfer_share_ratio_latest,
            coalesce(dl.stk_bo_rate, 0) + coalesce(dl.stk_co_rate, 0) AS stock_dividend_ratio_latest,
            dr.cash_dividend_ttm,
            dr.cash_dividend_after_tax_ttm,
            dr.stock_dividend_ratio_ttm,
            dr.dividend_event_count_365d,
            CASE WHEN dl.ann_date IS NOT NULL THEN (d.trade_date - dl.ann_date)::INTEGER ELSE NULL END AS days_since_dividend_ann,
            CASE WHEN dl.ex_date IS NOT NULL THEN (d.trade_date - dl.ex_date)::INTEGER ELSE NULL END AS days_since_ex_dividend,
            coalesce(dn.has_dividend_announced_not_executed, false) AS has_dividend_announced_not_executed,
            dn.next_announced_ex_date,
            dn.next_announced_cash_dividend,
            fc.ann_date AS latest_forecast_ann_date,
            fc.end_date AS latest_forecast_end_date,
            fc.forecast_type AS forecast_type_latest,
            {forecast_type_code('fc.forecast_type')} AS forecast_type_code_latest,
            fc.p_change_min AS forecast_p_change_min_latest,
            fc.p_change_max AS forecast_p_change_max_latest,
            CASE WHEN fc.p_change_min IS NOT NULL AND fc.p_change_max IS NOT NULL THEN (fc.p_change_min + fc.p_change_max) / 2 ELSE NULL END AS forecast_p_change_mid_latest,
            fc.net_profit_min AS forecast_net_profit_min_latest,
            fc.net_profit_max AS forecast_net_profit_max_latest,
            CASE WHEN fc.net_profit_min IS NOT NULL AND fc.net_profit_max IS NOT NULL THEN (fc.net_profit_min + fc.net_profit_max) / 2 ELSE NULL END AS forecast_net_profit_mid_latest,
            CASE WHEN fc.net_profit_min IS NOT NULL AND fc.net_profit_max IS NOT NULL THEN fc.net_profit_max - fc.net_profit_min ELSE NULL END AS forecast_range_width_latest,
            CASE WHEN fc.p_change_min IS NOT NULL AND fc.p_change_max IS NOT NULL THEN fc.p_change_max - fc.p_change_min ELSE NULL END AS forecast_change_range_width_latest,
            CASE WHEN fc.ann_date IS NOT NULL THEN (d.trade_date - fc.ann_date)::INTEGER ELSE NULL END AS days_since_forecast_ann,
            ex.ann_date AS latest_express_ann_date,
            ex.end_date AS latest_express_end_date,
            ex.revenue AS express_revenue_latest,
            ex.operating_profit AS express_operating_profit_latest,
            ex.total_profit AS express_total_profit_latest,
            ex.net_profit AS express_net_profit_latest,
            ex.total_assets AS express_total_assets_latest,
            ex.equity_attr_parent AS express_equity_attr_parent_latest,
            ex.diluted_eps AS express_diluted_eps_latest,
            ex.diluted_roe AS express_diluted_roe_latest,
            ex.yoy_net_profit AS express_yoy_net_profit_latest,
            CASE WHEN ex.ann_date IS NOT NULL THEN (d.trade_date - ex.ann_date)::INTEGER ELSE NULL END AS days_since_express_ann,
            au.ann_date AS latest_audit_ann_date,
            au.end_date AS latest_audit_end_date,
            au.audit_result AS audit_opinion_latest,
            {audit_code('au.audit_result')} AS audit_opinion_code_latest,
            ({audit_code('au.audit_result')}) IN (2,3,4,5,99) AS non_standard_audit_flag_latest,
            au.audit_fees AS audit_fees_latest,
            au.audit_agency AS audit_agency_latest,
            CASE WHEN au.ann_date IS NOT NULL THEN (d.trade_date - au.ann_date)::INTEGER ELSE NULL END AS days_since_audit_ann,
            mb.end_date AS latest_mainbz_end_date,
            mb.mainbz_segment_count_latest,
            mb.mainbz_revenue_total_latest,
            mb.mainbz_profit_total_latest,
            mb.mainbz_cost_total_latest,
            mb.mainbz_top1_revenue_ratio_latest,
            mb.mainbz_top3_revenue_ratio_latest,
            mb.mainbz_top1_profit_ratio_latest,
            mb.mainbz_gross_margin_latest,
            CASE WHEN mb.end_date IS NOT NULL THEN (d.trade_date - mb.end_date)::INTEGER ELSE NULL END AS days_since_mainbz_end_date,
            rp.ann_date AS latest_repurchase_ann_date,
            rp.proc AS latest_repurchase_proc,
            {repurchase_code('rp.proc')} AS latest_repurchase_proc_code,
            rp.volume AS latest_repurchase_volume,
            rp.amount AS latest_repurchase_amount,
            rp.high_limit AS latest_repurchase_high_limit,
            rp.low_limit AS latest_repurchase_low_limit,
            rr.repurchase_amount_365d,
            rr.repurchase_volume_365d,
            rr.repurchase_count_365d,
            CASE WHEN rp.ann_date IS NOT NULL THEN (d.trade_date - rp.ann_date)::INTEGER ELSE NULL END AS days_since_repurchase_ann,
            sfr.latest_share_float_ann_date,
            sfr.latest_share_float_date,
            sflv.latest_share_float_share,
            sflv.latest_share_float_ratio,
            sfr.share_float_event_count_365d,
            sfr.share_float_share_365d,
            sfr.share_float_ratio_365d,
            CASE WHEN sfr.latest_share_float_date IS NOT NULL THEN (d.trade_date - sfr.latest_share_float_date)::INTEGER ELSE NULL END AS days_since_share_float,
            sff.next_share_float_date_30d,
            sff.next_share_float_share_30d,
            sff.next_share_float_ratio_30d,
            sff.next_share_float_share_90d,
            sff.next_share_float_ratio_90d,
            d.total_share AS total_share_asof,
            d.float_share AS float_share_asof,
            d.free_share AS free_share_asof,
            {safe_div('d.float_share', 'd.total_share')} AS float_share_ratio_asof,
            {safe_div('d.free_share', 'd.total_share')} AS free_share_ratio_asof,
            d.total_share_chg_20d,
            d.float_share_chg_20d,
            d.free_share_chg_20d
        FROM days d
        ASOF LEFT JOIN (SELECT * FROM dividend_latest ORDER BY ts_code, effective_date) dl
          ON d.ts_code = dl.ts_code AND d.trade_date >= dl.effective_date
        LEFT JOIN dividend_roll dr
          ON d.ts_code = dr.ts_code AND d.trade_date = dr.trade_date
        LEFT JOIN dividend_next dn
          ON d.ts_code = dn.ts_code AND d.trade_date = dn.trade_date
        ASOF LEFT JOIN (SELECT * FROM forecast_versions ORDER BY ts_code, ann_date) fc
          ON d.ts_code = fc.ts_code AND d.trade_date >= fc.ann_date
        ASOF LEFT JOIN (SELECT * FROM express_versions ORDER BY ts_code, ann_date) ex
          ON d.ts_code = ex.ts_code AND d.trade_date >= ex.ann_date
        ASOF LEFT JOIN (SELECT * FROM audit_versions ORDER BY ts_code, ann_date) au
          ON d.ts_code = au.ts_code AND d.trade_date >= au.ann_date
        ASOF LEFT JOIN (SELECT * FROM mainbz_summary ORDER BY ts_code, ann_date) mb
          ON d.ts_code = mb.ts_code AND d.trade_date >= mb.ann_date
        ASOF LEFT JOIN (SELECT * FROM repurchase_versions ORDER BY ts_code, ann_date) rp
          ON d.ts_code = rp.ts_code AND d.trade_date >= rp.ann_date
        LEFT JOIN repurchase_roll rr
          ON d.ts_code = rr.ts_code AND d.trade_date = rr.trade_date
        LEFT JOIN share_float_roll sfr
          ON d.ts_code = sfr.ts_code AND d.trade_date = sfr.trade_date
        LEFT JOIN share_float_latest_values sflv
          ON d.ts_code = sflv.ts_code AND d.trade_date = sflv.trade_date
        LEFT JOIN share_float_future sff
          ON d.ts_code = sff.ts_code AND d.trade_date = sff.trade_date
    )
    SELECT
        {select_list}
    FROM (
        SELECT
            *,
            (latest_forecast_ann_date IS NOT NULL) AS has_forecast_asof,
            (latest_express_ann_date IS NOT NULL) AS has_express_asof,
            greatest(
                latest_dividend_ann_date,
                latest_dividend_ex_date,
                latest_forecast_ann_date,
                latest_express_ann_date,
                latest_audit_ann_date,
                latest_mainbz_end_date,
                latest_repurchase_ann_date,
                latest_share_float_date
            ) AS latest_corp_action_date,
            (
                coalesce(dividend_event_count_365d,0)
                + CASE WHEN latest_forecast_ann_date BETWEEN trade_date - INTERVAL 365 DAY AND trade_date THEN 1 ELSE 0 END
                + CASE WHEN latest_express_ann_date BETWEEN trade_date - INTERVAL 365 DAY AND trade_date THEN 1 ELSE 0 END
                + CASE WHEN latest_audit_ann_date BETWEEN trade_date - INTERVAL 365 DAY AND trade_date THEN 1 ELSE 0 END
                + CASE WHEN latest_repurchase_ann_date BETWEEN trade_date - INTERVAL 365 DAY AND trade_date THEN 1 ELSE 0 END
                + coalesce(share_float_event_count_365d,0)
            )::INTEGER AS corp_action_event_count_365d,
            (
                latest_dividend_ann_date IS NOT NULL
                OR latest_forecast_ann_date IS NOT NULL
                OR latest_express_ann_date IS NOT NULL
                OR latest_audit_ann_date IS NOT NULL
                OR latest_mainbz_end_date IS NOT NULL
                OR latest_repurchase_ann_date IS NOT NULL
                OR latest_share_float_date IS NOT NULL
            ) AS corp_action_available_flag,
            CASE
                WHEN greatest(
                    latest_dividend_ann_date,
                    latest_dividend_ex_date,
                    latest_forecast_ann_date,
                    latest_express_ann_date,
                    latest_audit_ann_date,
                    latest_mainbz_end_date,
                    latest_repurchase_ann_date,
                    latest_share_float_date
                ) IS NOT NULL
                THEN (trade_date - greatest(
                    latest_dividend_ann_date,
                    latest_dividend_ex_date,
                    latest_forecast_ann_date,
                    latest_express_ann_date,
                    latest_audit_ann_date,
                    latest_mainbz_end_date,
                    latest_repurchase_ann_date,
                    latest_share_float_date
                ))::INTEGER
                ELSE NULL
            END AS days_since_latest_corp_action,
            CURRENT_TIMESTAMP AS updated_at
        FROM base
    )
    WHERE trade_date BETWEEN DATE '{output_start}' AND DATE '{end}'
    """


def to_ord(value) -> int | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).date().toordinal()


def update_share_float_fields(
    con: duckdb.DuckDBPyConnection,
    start: str,
    end: str,
    write_start: str | None = None,
) -> None:
    output_start = write_start or start
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE sf_days AS
        SELECT ts_code, trade_date
        FROM {q(TABLE_NAME)}
        WHERE trade_date BETWEEN DATE '{output_start}' AND DATE '{end}';

        CREATE OR REPLACE TEMP TABLE sf_daily AS
        SELECT
            ts_code,
            float_date,
            max(ann_date) AS latest_ann_date,
            sum(coalesce(float_share, 0)) AS float_share_day,
            sum(coalesce(float_ratio, 0)) AS float_ratio_day,
            count(*)::INTEGER AS count_day
        FROM financial_share_float
        WHERE float_date IS NOT NULL
          AND float_date <= DATE '{end}' + INTERVAL 90 DAY
        GROUP BY ts_code, float_date;

        CREATE OR REPLACE TEMP TABLE sf_any AS
        SELECT DISTINCT ts_code
        FROM sf_daily;

        CREATE OR REPLACE TEMP TABLE sf_latest AS
        SELECT
            d.ts_code,
            d.trade_date,
            s.latest_ann_date AS latest_share_float_ann_date,
            s.float_date AS latest_share_float_date,
            s.float_share_day AS latest_share_float_share,
            s.float_ratio_day AS latest_share_float_ratio
        FROM sf_days d
        ASOF LEFT JOIN (
            SELECT *
            FROM sf_daily
            WHERE float_date <= DATE '{end}'
            ORDER BY ts_code, float_date
        ) s
          ON d.ts_code = s.ts_code
         AND d.trade_date >= s.float_date;

        CREATE OR REPLACE TEMP TABLE sf_roll AS
        SELECT
            d.ts_code,
            d.trade_date,
            CASE WHEN max(a.ts_code) IS NULL THEN NULL ELSE coalesce(sum(s.count_day), 0)::INTEGER END AS share_float_event_count_365d,
            CASE WHEN max(a.ts_code) IS NULL THEN NULL ELSE coalesce(sum(s.float_share_day), 0) END AS share_float_share_365d,
            CASE WHEN max(a.ts_code) IS NULL THEN NULL ELSE coalesce(sum(s.float_ratio_day), 0) END AS share_float_ratio_365d
        FROM sf_days d
        LEFT JOIN sf_any a
          ON d.ts_code = a.ts_code
        LEFT JOIN sf_daily s
          ON d.ts_code = s.ts_code
         AND s.float_date BETWEEN d.trade_date - INTERVAL 365 DAY AND d.trade_date
        GROUP BY d.ts_code, d.trade_date;

        CREATE OR REPLACE TEMP TABLE sf_future AS
        SELECT
            d.ts_code,
            d.trade_date,
            min(e.float_date) FILTER (
                WHERE e.float_date > d.trade_date
                  AND e.float_date <= d.trade_date + INTERVAL 30 DAY
            ) AS next_share_float_date_30d,
            sum(coalesce(e.float_share, 0)) FILTER (
                WHERE e.float_date > d.trade_date
                  AND e.float_date <= d.trade_date + INTERVAL 30 DAY
            ) AS next_share_float_share_30d,
            sum(coalesce(e.float_ratio, 0)) FILTER (
                WHERE e.float_date > d.trade_date
                  AND e.float_date <= d.trade_date + INTERVAL 30 DAY
            ) AS next_share_float_ratio_30d,
            sum(coalesce(e.float_share, 0)) FILTER (
                WHERE e.float_date > d.trade_date
                  AND e.float_date <= d.trade_date + INTERVAL 90 DAY
            ) AS next_share_float_share_90d,
            sum(coalesce(e.float_ratio, 0)) FILTER (
                WHERE e.float_date > d.trade_date
                  AND e.float_date <= d.trade_date + INTERVAL 90 DAY
            ) AS next_share_float_ratio_90d
        FROM sf_days d
        LEFT JOIN financial_share_float e
          ON d.ts_code = e.ts_code
         AND e.ann_date IS NOT NULL
         AND e.ann_date <= d.trade_date
         AND e.float_date > d.trade_date
         AND e.float_date <= d.trade_date + INTERVAL 90 DAY
        GROUP BY d.ts_code, d.trade_date;

        CREATE OR REPLACE TEMP TABLE sf_payload AS
        SELECT
            d.ts_code,
            d.trade_date,
            l.latest_share_float_ann_date,
            l.latest_share_float_date,
            l.latest_share_float_share,
            l.latest_share_float_ratio,
            r.share_float_event_count_365d,
            r.share_float_share_365d,
            r.share_float_ratio_365d,
            f.next_share_float_date_30d,
            f.next_share_float_share_30d,
            f.next_share_float_ratio_30d,
            f.next_share_float_share_90d,
            f.next_share_float_ratio_90d
        FROM sf_days d
        LEFT JOIN sf_latest l USING (ts_code, trade_date)
        LEFT JOIN sf_roll r USING (ts_code, trade_date)
        LEFT JOIN sf_future f USING (ts_code, trade_date);

        UPDATE {q(TABLE_NAME)} AS t
        SET
            latest_share_float_ann_date = p.latest_share_float_ann_date,
            latest_share_float_date = p.latest_share_float_date,
            latest_share_float_share = p.latest_share_float_share,
            latest_share_float_ratio = p.latest_share_float_ratio,
            share_float_event_count_365d = p.share_float_event_count_365d,
            share_float_share_365d = p.share_float_share_365d,
            share_float_ratio_365d = p.share_float_ratio_365d,
            days_since_share_float = CASE
                WHEN p.latest_share_float_date IS NOT NULL THEN (t.trade_date - p.latest_share_float_date)::INTEGER
                ELSE NULL
            END,
            next_share_float_date_30d = p.next_share_float_date_30d,
            next_share_float_share_30d = p.next_share_float_share_30d,
            next_share_float_ratio_30d = p.next_share_float_ratio_30d,
            next_share_float_share_90d = p.next_share_float_share_90d,
            next_share_float_ratio_90d = p.next_share_float_ratio_90d
        FROM sf_payload p
        WHERE t.ts_code = p.ts_code AND t.trade_date = p.trade_date
        """
    )


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
            update_share_float_fields(con, start, end)
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
