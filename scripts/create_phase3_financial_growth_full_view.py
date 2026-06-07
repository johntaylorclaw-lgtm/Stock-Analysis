from __future__ import annotations

from pathlib import Path

import duckdb

from register_phase3_financial_growth import (
    AMOUNT_METRICS,
    AMOUNT_SUFFIXES,
    QUALITY_DIFF_SUFFIXES,
    SINGLE_QUARTER_SUFFIXES,
    STATUS_FIELDS,
    TUSHARE_GROWTH_FIELDS,
    build_growth_definitions,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"


RAW_VALUE_EXPRESSIONS = {
    "revenue": "inc.revenue",
    "total_revenue": "inc.total_revenue",
    "operating_cost": "inc.operating_cost",
    "total_cogs": "inc.total_cogs",
    "operating_profit": "inc.operating_profit",
    "total_profit": "inc.total_profit",
    "net_profit": "inc.net_profit",
    "parent_net_profit": "inc.net_profit_attr_parent",
    "deducted_profit": "i.profit_dedt",
    "ebit": "inc.ebit",
    "ebitda": "inc.ebitda",
    "ocf": "cf.cf_from_operating",
    "icf": "cf.cf_from_investing",
    "fcf": "cf.cf_from_financing",
    "free_cashflow": "cf.free_cashflow",
    "cash_received_from_sales": "cf.cash_received_from_sales",
    "cash_paid_for_goods": "cf.cash_paid_for_goods",
    "cash_paid_for_capex": "cf.cash_paid_for_capex",
    "total_assets": "bal.total_assets",
    "current_assets": "bal.current_assets",
    "noncurrent_assets": "bal.total_noncurrent_assets",
    "total_liabilities": "bal.total_liabilities",
    "current_liabilities": "bal.current_liabilities",
    "total_equity": "bal.total_equity",
    "equity_attr_parent": "bal.equity_attr_parent",
    "interestdebt": "i.interestdebt",
    "netdebt": "i.netdebt",
    "rd_expense": "inc.rd_expense",
    "selling_expense": "inc.selling_expense",
    "admin_expense": "inc.admin_expense",
    "finance_expense": "inc.finance_expense",
}

TUSHARE_EXPRESSIONS = {
    "revenue_yoy_asof": "cur.or_yoy",
    "total_revenue_yoy_asof": "cur.tr_yoy",
    "netprofit_yoy_asof": "cur.netprofit_yoy",
    "deducted_netprofit_yoy_asof": "cur.dt_netprofit_yoy",
    "ocf_yoy_asof": "cur.ocf_yoy",
    "eps_yoy_asof": "cur.basic_eps_yoy",
    "dt_eps_yoy_asof": "cur.dt_eps_yoy",
    "cfps_yoy_asof": "cur.cfps_yoy",
    "roe_yoy_asof": "cur.roe_yoy",
    "bps_yoy_asof": "cur.bps_yoy",
    "assets_yoy_asof": "cur.assets_yoy",
    "equity_yoy_asof": "cur.eqt_yoy",
    "q_revenue_yoy_asof": "cur.q_sales_yoy",
    "q_revenue_qoq_asof": "cur.q_sales_qoq",
    "q_operating_profit_yoy_asof": "cur.q_op_yoy",
    "q_operating_profit_qoq_asof": "cur.q_op_qoq",
    "q_netprofit_yoy_asof": "cur.q_netprofit_yoy",
    "q_netprofit_qoq_asof": "cur.q_netprofit_qoq",
}

STATUS_SQL = {
    "revenue_positive_growth_flag": "revenue_yoy_1y_calc_asof > 0",
    "profit_positive_growth_flag": "parent_net_profit_yoy_1y_calc_asof > 0",
    "deducted_profit_positive_growth_flag": "deducted_profit_yoy_1y_calc_asof > 0",
    "ocf_positive_growth_flag": "ocf_yoy_1y_calc_asof > 0",
    "revenue_profit_same_direction_flag": (
        "(revenue_yoy_1y_calc_asof > 0 AND parent_net_profit_yoy_1y_calc_asof > 0) "
        "OR (revenue_yoy_1y_calc_asof < 0 AND parent_net_profit_yoy_1y_calc_asof < 0)"
    ),
    "profit_ocf_same_direction_flag": (
        "(parent_net_profit_yoy_1y_calc_asof > 0 AND ocf_yoy_1y_calc_asof > 0) "
        "OR (parent_net_profit_yoy_1y_calc_asof < 0 AND ocf_yoy_1y_calc_asof < 0)"
    ),
    "roe_yoy_improving_flag": "roe_yoy_diff_asof > 0",
    "gross_margin_yoy_improving_flag": "gross_margin_yoy_diff_asof > 0",
    "debt_to_assets_yoy_increasing_flag": "debt_to_assets_yoy_diff_asof > 0",
    "ocf_to_profit_yoy_improving_flag": "ocf_to_profit_yoy_diff_asof > 0",
}


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def special_code(num: str, den: str) -> str:
    return (
        "CAST(('-9' || "
        f"CASE WHEN {num} = 0 THEN '1' ELSE '0' END || "
        f"CASE WHEN {num} IS NULL THEN '1' ELSE '0' END || "
        f"CASE WHEN {num} < 0 THEN '1' ELSE '0' END || "
        f"CASE WHEN {den} = 0 THEN '1' ELSE '0' END || "
        f"CASE WHEN {den} IS NULL THEN '1' ELSE '0' END || "
        f"CASE WHEN {den} < 0 THEN '1' ELSE '0' END) AS DOUBLE)"
    )


def safe_growth(num: str, den: str) -> str:
    return f"CASE WHEN {num} > 0 AND {den} > 0 THEN {num} / {den} - 1 ELSE {special_code(num, den)} END"


def safe_cagr(num: str, den: str, years: int) -> str:
    return (
        f"CASE WHEN {num} > 0 AND {den} > 0 "
        f"THEN power({num} / {den}, 1.0 / {years}) - 1 ELSE {special_code(num, den)} END"
    )


def amount_expression(metric: str, suffix: str) -> str:
    current = f"cur.{metric}"
    comparisons = {
        "qoq_report_asof": (current, f"prev.{metric}", "growth"),
        "change_2report_asof": (current, f"lag2.{metric}", "growth"),
        "change_4report_asof": (current, f"lag4.{metric}", "growth"),
        "change_8report_asof": (current, f"lag8.{metric}", "growth"),
        "yoy_1y_calc_asof": (current, f"same1.{metric}", "growth"),
        "yoy_2y_calc_asof": (current, f"same2.{metric}", "growth"),
        "yoy_3y_calc_asof": (current, f"same3.{metric}", "growth"),
        "cagr_2y_asof": (current, f"same2.{metric}", "cagr2"),
        "cagr_3y_asof": (current, f"same3.{metric}", "cagr3"),
    }
    num, den, kind = comparisons[suffix]
    if kind == "cagr2":
        return safe_cagr(num, den, 2)
    if kind == "cagr3":
        return safe_cagr(num, den, 3)
    return safe_growth(num, den)


def single_quarter_expression(metric: str, suffix: str) -> str:
    current = f"cur.{metric}_single_quarter_value"
    if suffix == "single_quarter_value_asof":
        return current
    if suffix == "single_quarter_yoy_asof":
        return safe_growth(current, f"same1.{metric}_single_quarter_value")
    if suffix == "single_quarter_qoq_asof":
        return safe_growth(current, f"prev.{metric}_single_quarter_value")
    raise ValueError(suffix)


def quality_expression(field: str, suffix: str) -> str:
    expressions = {
        "diff_1report_asof": f"qcur.{field} - qprev.{field}",
        "diff_4report_asof": f"qcur.{field} - qlag4.{field}",
        "diff_8report_asof": f"qcur.{field} - qlag8.{field}",
        "yoy_diff_asof": f"qcur.{field} - qsame1.{field}",
        "growth_1report_asof": safe_growth(f"qcur.{field}", f"qprev.{field}"),
        "growth_4report_asof": safe_growth(f"qcur.{field}", f"qlag4.{field}"),
        "growth_8report_asof": safe_growth(f"qcur.{field}", f"qlag8.{field}"),
        "yoy_growth_asof": safe_growth(f"qcur.{field}", f"qsame1.{field}"),
    }
    return expressions[suffix]


def build_view_sql() -> str:
    amount_select = [
        "a.ts_code",
        "a.trade_date",
        "a.latest_report_end_date AS current_report_end_date",
        "seq.prev_report_end_date",
        "seq.lag_2report_end_date",
        "seq.lag_4report_end_date",
        "seq.lag_8report_end_date",
        "seq.same_period_1y_end_date",
        "seq.same_period_2y_end_date",
        "seq.same_period_3y_end_date",
    ]
    for name, _label, _formula in TUSHARE_GROWTH_FIELDS:
        amount_select.append(f"{TUSHARE_EXPRESSIONS[name]} AS {quote_ident(name)}")
    for metric, _label, _source, is_flow in AMOUNT_METRICS:
        for suffix, _suffix_label, _formula in AMOUNT_SUFFIXES:
            name = f"{metric}_{suffix}"
            amount_select.append(f"{amount_expression(metric, suffix)} AS {quote_ident(name)}")
        if is_flow:
            for suffix, _suffix_label, _formula in SINGLE_QUARTER_SUFFIXES:
                name = f"{metric}_{suffix}"
                amount_select.append(f"{single_quarter_expression(metric, suffix)} AS {quote_ident(name)}")

    quality_select = ["agb.*"]
    definitions = build_growth_definitions()
    for name, _label, _dtype, _formula, category in definitions:
        if category != "quality_change":
            continue
        for suffix, _suffix_label, _suffix_formula in QUALITY_DIFF_SUFFIXES:
            if name.endswith(f"_{suffix}"):
                field = f"{name[: -len('_' + suffix)]}_asof"
                quality_select.append(f"{quality_expression(field, suffix)} AS {quote_ident(name)}")
                break
    quality_select.extend(
        [
            "coalesce(qcur.negative_net_profit_flag, false) AND coalesce(qprev.negative_net_profit_flag, false) AS negative_profit_continued_flag",
            "coalesce(qcur.negative_ocf_flag, false) AND coalesce(qprev.negative_ocf_flag, false) AS negative_ocf_continued_flag",
            "coalesce(qcur.high_goodwill_flag, false) AND coalesce(qprev.high_goodwill_flag, false) AS high_goodwill_continued_flag",
            "coalesce(qcur.high_leverage_flag, false) AND coalesce(qprev.high_leverage_flag, false) AS high_leverage_continued_flag",
        ]
    )

    final_expressions = []
    for name, _label, _dtype, _formula, category in definitions:
        if name in {"ts_code", "trade_date"}:
            final_expressions.append(name)
        elif category == "growth_state":
            if name in {
                "negative_profit_continued_flag",
                "negative_ocf_continued_flag",
                "high_goodwill_continued_flag",
                "high_leverage_continued_flag",
            }:
                final_expressions.append(name)
            else:
                formula = STATUS_SQL.get(name, next(item[2] for item in STATUS_FIELDS if item[0] == name))
                final_expressions.append(f"({formula}) AS {quote_ident(name)}")
        else:
            final_expressions.append(quote_ident(name))
    final_expressions.append("CURRENT_TIMESTAMP AS updated_at")

    raw_select = [
        "rs.ts_code",
        "rs.current_report_end_date",
        "EXTRACT(year FROM rs.current_report_end_date) AS report_year",
        "EXTRACT(quarter FROM rs.current_report_end_date) AS report_quarter",
        "i.or_yoy",
        "i.tr_yoy",
        "i.netprofit_yoy",
        "i.dt_netprofit_yoy",
        "i.ocf_yoy",
        "i.basic_eps_yoy",
        "i.dt_eps_yoy",
        "i.cfps_yoy",
        "i.roe_yoy",
        "i.bps_yoy",
        "i.assets_yoy",
        "i.eqt_yoy",
        "i.q_sales_yoy",
        "i.q_sales_qoq",
        "i.q_op_yoy",
        "i.q_op_qoq",
        "i.q_netprofit_yoy",
        "i.q_netprofit_qoq",
    ]
    raw_select.extend(f"{expr} AS {quote_ident(metric)}" for metric, expr in RAW_VALUE_EXPRESSIONS.items())
    single_quarter_select = []
    for metric, _label, _source, is_flow in AMOUNT_METRICS:
        if not is_flow:
            continue
        single_quarter_select.append(
            f"""
            CASE
                WHEN report_quarter = 1 THEN {quote_ident(metric)}
                ELSE {quote_ident(metric)} - lag({quote_ident(metric)}) OVER (
                    PARTITION BY ts_code, report_year ORDER BY current_report_end_date
                )
            END AS {quote_ident(metric + "_single_quarter_value")}
            """.strip()
        )

    return f"""
    CREATE OR REPLACE VIEW derived_financial_growth_full_v AS
    WITH report_base AS (
        SELECT DISTINCT ts_code, latest_report_end_date AS current_report_end_date
        FROM derived_financial_asof
        WHERE latest_report_end_date IS NOT NULL
    ),
    report_seq AS (
        SELECT
            rb.*,
            lag(rb.current_report_end_date, 1) OVER (PARTITION BY rb.ts_code ORDER BY rb.current_report_end_date) AS prev_report_end_date,
            lag(rb.current_report_end_date, 2) OVER (PARTITION BY rb.ts_code ORDER BY rb.current_report_end_date) AS lag_2report_end_date,
            lag(rb.current_report_end_date, 4) OVER (PARTITION BY rb.ts_code ORDER BY rb.current_report_end_date) AS lag_4report_end_date,
            lag(rb.current_report_end_date, 8) OVER (PARTITION BY rb.ts_code ORDER BY rb.current_report_end_date) AS lag_8report_end_date,
            y1.current_report_end_date AS same_period_1y_end_date,
            y2.current_report_end_date AS same_period_2y_end_date,
            y3.current_report_end_date AS same_period_3y_end_date
        FROM report_base rb
        LEFT JOIN report_base y1 ON rb.ts_code = y1.ts_code AND y1.current_report_end_date = rb.current_report_end_date - INTERVAL 1 YEAR
        LEFT JOIN report_base y2 ON rb.ts_code = y2.ts_code AND y2.current_report_end_date = rb.current_report_end_date - INTERVAL 2 YEAR
        LEFT JOIN report_base y3 ON rb.ts_code = y3.ts_code AND y3.current_report_end_date = rb.current_report_end_date - INTERVAL 3 YEAR
    ),
    indicator_latest AS (
        SELECT *
        FROM financial_indicator_raw
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, end_date
            ORDER BY coalesce(effective_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
        ) = 1
    ),
    income_latest AS (
        SELECT *
        FROM financial_income_raw
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, end_date
            ORDER BY coalesce(effective_date, first_ann_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
        ) = 1
    ),
    balance_latest AS (
        SELECT *
        FROM financial_balance_raw
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, end_date
            ORDER BY coalesce(effective_date, first_ann_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
        ) = 1
    ),
    cashflow_latest AS (
        SELECT *
        FROM financial_cashflow_raw
        QUALIFY row_number() OVER (
            PARTITION BY ts_code, end_date
            ORDER BY coalesce(effective_date, first_ann_date, ann_date) DESC NULLS LAST, ann_date DESC NULLS LAST
        ) = 1
    ),
    report_values AS (
        SELECT
            {",\n            ".join(raw_select)}
        FROM report_seq rs
        LEFT JOIN indicator_latest i ON rs.ts_code = i.ts_code AND rs.current_report_end_date = i.end_date
        LEFT JOIN income_latest inc ON rs.ts_code = inc.ts_code AND rs.current_report_end_date = inc.end_date
        LEFT JOIN balance_latest bal ON rs.ts_code = bal.ts_code AND rs.current_report_end_date = bal.end_date
        LEFT JOIN cashflow_latest cf ON rs.ts_code = cf.ts_code AND rs.current_report_end_date = cf.end_date
    ),
    report_values_enriched AS (
        SELECT
            *,
            {",\n            ".join(single_quarter_select)}
        FROM report_values
    ),
    report_quality AS (
        SELECT
            a.ts_code,
            a.latest_report_end_date AS report_end_date,
            q.*
        FROM derived_financial_asof a
        JOIN derived_financial_quality q ON a.ts_code = q.ts_code AND a.trade_date = q.trade_date
        WHERE a.latest_report_end_date IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY a.ts_code, a.latest_report_end_date
            ORDER BY a.trade_date DESC
        ) = 1
    ),
    amount_growth_base AS (
        SELECT
            {",\n            ".join(amount_select)}
        FROM derived_financial_asof a
        LEFT JOIN report_seq seq ON a.ts_code = seq.ts_code AND a.latest_report_end_date = seq.current_report_end_date
        LEFT JOIN report_values_enriched cur ON a.ts_code = cur.ts_code AND a.latest_report_end_date = cur.current_report_end_date
        LEFT JOIN report_values_enriched prev ON a.ts_code = prev.ts_code AND seq.prev_report_end_date = prev.current_report_end_date
        LEFT JOIN report_values_enriched lag2 ON a.ts_code = lag2.ts_code AND seq.lag_2report_end_date = lag2.current_report_end_date
        LEFT JOIN report_values_enriched lag4 ON a.ts_code = lag4.ts_code AND seq.lag_4report_end_date = lag4.current_report_end_date
        LEFT JOIN report_values_enriched lag8 ON a.ts_code = lag8.ts_code AND seq.lag_8report_end_date = lag8.current_report_end_date
        LEFT JOIN report_values_enriched same1 ON a.ts_code = same1.ts_code AND seq.same_period_1y_end_date = same1.current_report_end_date
        LEFT JOIN report_values_enriched same2 ON a.ts_code = same2.ts_code AND seq.same_period_2y_end_date = same2.current_report_end_date
        LEFT JOIN report_values_enriched same3 ON a.ts_code = same3.ts_code AND seq.same_period_3y_end_date = same3.current_report_end_date
    ),
    quality_growth_base AS (
        SELECT
            {",\n            ".join(quality_select)}
        FROM amount_growth_base agb
        LEFT JOIN report_quality qcur ON agb.ts_code = qcur.ts_code AND agb.current_report_end_date = qcur.report_end_date
        LEFT JOIN report_quality qprev ON agb.ts_code = qprev.ts_code AND agb.prev_report_end_date = qprev.report_end_date
        LEFT JOIN report_quality qlag4 ON agb.ts_code = qlag4.ts_code AND agb.lag_4report_end_date = qlag4.report_end_date
        LEFT JOIN report_quality qlag8 ON agb.ts_code = qlag8.ts_code AND agb.lag_8report_end_date = qlag8.report_end_date
        LEFT JOIN report_quality qsame1 ON agb.ts_code = qsame1.ts_code AND agb.same_period_1y_end_date = qsame1.report_end_date
    )
    SELECT
        {",\n        ".join(final_expressions)}
    FROM quality_growth_base
    """


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    con.execute(build_view_sql())
    row = con.execute(
        """
        SELECT count(*)
        FROM derived_financial_growth_full_v
        WHERE trade_date BETWEEN DATE '2026-05-20' AND DATE '2026-05-26'
        """
    ).fetchone()
    field_count = len(con.execute("PRAGMA table_info('derived_financial_growth_full_v')").fetchall())
    print(f"created derived_financial_growth_full_v fields={field_count} sample_rows={row[0]}")


if __name__ == "__main__":
    main()
