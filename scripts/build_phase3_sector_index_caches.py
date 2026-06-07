from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_sector_index_cache_run.json"

FULL_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
VOL_PERIODS = [5, 20, 60, 120, 250]
INDEX_MAP = {
    "hs300": ("000300.SH", "沪深300"),
    "zz500": ("000905.SH", "中证500"),
    "zz1000": ("000852.SH", "中证1000"),
    "sse50": ("000016.SH", "上证50"),
    "star50": ("000688.SH", "科创50"),
    "chinext": ("399006.SZ", "创业板指"),
}


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def date_literal(value: str) -> str:
    return "DATE '" + value.replace("'", "''") + "'"


def resolve_read_start(con: duckdb.DuckDBPyConnection, start: str, context_days: int) -> str:
    row = con.execute(
        """
        SELECT min(cal_date)
        FROM (
            SELECT cal_date
            FROM trade_calendar
            WHERE is_open AND cal_date <= CAST(? AS DATE)
            ORDER BY cal_date DESC
            LIMIT ?
        )
        """,
        [start, context_days + 1],
    ).fetchone()
    return str(row[0] or start)


def delete_table_window(con: duckdb.DuckDBPyConnection, table: str, start: str | None, end: str | None) -> None:
    if start and end:
        con.execute(f"DELETE FROM {q(table)} WHERE trade_date BETWEEN ? AND ?", [start, end])
    else:
        con.execute(f"DELETE FROM {q(table)}")


def table_count(con: duckdb.DuckDBPyConnection, table: str, start: str | None, end: str | None) -> int:
    if start and end:
        return int(
            con.execute(
                f"SELECT count(*) FROM {q(table)} WHERE trade_date BETWEEN ? AND ?",
                [start, end],
            ).fetchone()[0]
        )
    return int(con.execute(f"SELECT count(*) FROM {q(table)}").fetchone()[0])


def sector_cache_sql(start: str | None = None, end: str | None = None, read_start: str | None = None) -> str:
    rolling = []
    for n in FULL_PERIODS:
        rolling.extend(
            [
                f"avg(amount_total) OVER w{n} AS industry_amount_ma_{n}",
                f"avg(turnover_rate_avg) OVER w{n} AS industry_turnover_ma_{n}",
                f"avg(up_ratio) OVER w{n} AS industry_up_ratio_{n}",
                f"sum(limit_up_count) OVER w{n} AS industry_limit_up_count_{n}",
                f"sum(main_net_amount_sum) OVER w{n} AS industry_main_flow_sum_{n}",
            ]
        )
    select_items = [
        "industry_level",
        "industry_code",
        "trade_date",
        "industry_name",
        "industry_stock_count",
        "industry_total_mv",
    ]
    for n in FULL_PERIODS:
        select_items.extend(
            [
                f"industry_ret_{n}",
                f"rank() OVER (PARTITION BY industry_level, trade_date ORDER BY industry_ret_{n} DESC NULLS LAST)::INTEGER AS industry_ret_rank_all_{n}",
                f"percent_rank() OVER (PARTITION BY industry_level, trade_date ORDER BY industry_ret_{n}) AS industry_ret_pct_all_{n}",
                f"industry_amount_ma_{n}",
                f"percent_rank() OVER (PARTITION BY industry_level, trade_date ORDER BY industry_amount_ma_{n}) AS industry_amount_pct_all_{n}",
                f"industry_turnover_ma_{n}",
                f"industry_up_ratio_{n}",
                f"industry_limit_up_count_{n}::INTEGER AS industry_limit_up_count_{n}",
                f"industry_main_flow_sum_{n}",
                f"CASE WHEN industry_total_mv > 0 THEN industry_main_flow_sum_{n} / industry_total_mv ELSE NULL END AS industry_main_flow_to_mv_{n}",
            ]
        )
    windows = ", ".join(
        f"w{n} AS (PARTITION BY industry_level, industry_code ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)"
        for n in FULL_PERIODS
    )
    ret_base_where = ""
    stock_context_where = ""
    final_where = ""
    if start and end and read_start:
        ret_base_where = f"WHERE ds.trade_date BETWEEN {date_literal(read_start)} AND {date_literal(end)}"
        stock_context_where = f"WHERE ds.trade_date BETWEEN {date_literal(read_start)} AND {date_literal(end)}"
        final_where = f"WHERE trade_date BETWEEN {date_literal(start)} AND {date_literal(end)}"
    return f"""
    INSERT INTO derived_sector_daily_cache
    WITH member AS (
        SELECT 'L1' AS industry_level, sw_l1_code AS industry_code, sw_l1_name AS industry_name, ts_code, in_date, out_date
        FROM derived_sw_industry_member_enhanced
        UNION ALL
        SELECT 'L2' AS industry_level, sw_l2_code AS industry_code, sw_l2_name AS industry_name, ts_code, in_date, out_date
        FROM derived_sw_industry_member_enhanced
    ),
    ret_base AS (
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
        {ret_base_where}
    ),
    stock_context AS (
        SELECT
            m.industry_level,
            m.industry_code,
            any_value(m.industry_name) AS industry_name,
            ds.trade_date,
            count(DISTINCT ds.ts_code)::INTEGER AS industry_stock_count,
            avg(r.ret_2_hfq) AS industry_ret_2,
            avg(r.ret_3_hfq) AS industry_ret_3,
            avg(r.ret_5_hfq) AS industry_ret_5,
            avg(r.ret_10_hfq) AS industry_ret_10,
            avg(r.ret_20_hfq) AS industry_ret_20,
            avg(r.ret_30_hfq) AS industry_ret_30,
            avg(r.ret_60_hfq) AS industry_ret_60,
            avg(r.ret_120_hfq) AS industry_ret_120,
            avg(r.ret_250_hfq) AS industry_ret_250,
            sum(ds.amount) AS amount_total,
            avg(b.turnover_rate) AS turnover_rate_avg,
            avg(CASE WHEN ds.ret_1_hfq > 0 THEN 1.0 ELSE 0.0 END) AS up_ratio,
            sum(CASE WHEN ds.limit_up_flag THEN 1 ELSE 0 END) AS limit_up_count,
            sum(cf.main_net_amount) AS main_net_amount_sum,
            sum(v.total_mv) AS industry_total_mv
        FROM member m
        JOIN derived_daily_spine ds
          ON m.ts_code = ds.ts_code
         AND ds.trade_date >= m.in_date
         AND (m.out_date IS NULL OR ds.trade_date <= m.out_date)
        LEFT JOIN ret_base r ON ds.ts_code = r.ts_code AND ds.trade_date = r.trade_date
        LEFT JOIN stock_daily_basic b ON ds.ts_code = b.ts_code AND ds.trade_date = b.trade_date
        LEFT JOIN derived_capital_flow cf ON ds.ts_code = cf.ts_code AND ds.trade_date = cf.trade_date
        LEFT JOIN derived_valuation_size v ON ds.ts_code = v.ts_code AND ds.trade_date = v.trade_date
        {stock_context_where}
        GROUP BY m.industry_level, m.industry_code, ds.trade_date
    ),
    rolling AS (
        SELECT
            *,
            {", ".join(rolling)}
        FROM stock_context
        WINDOW {windows}
    )
    SELECT
        {", ".join(select_items)},
        CURRENT_TIMESTAMP AS updated_at
    FROM rolling
    {final_where}
    """


def concept_cache_sql(start: str | None = None, end: str | None = None, read_start: str | None = None) -> str:
    rolling = []
    for n in FULL_PERIODS:
        rolling.extend(
            [
                f"CASE WHEN count(ret_ratio) OVER w{n} >= {n} THEN exp(sum(ln(1 + ret_ratio)) OVER w{n}) - 1 ELSE NULL END AS concept_ret_{n}",
                f"avg(amount_total) OVER w{n} AS concept_amount_ma_{n}",
                f"avg(up_ratio) OVER w{n} AS concept_up_ratio_{n}",
                f"sum(limit_up_count) OVER w{n} AS concept_limit_up_count_{n}",
            ]
        )
    select_items = [
        "concept_id", "trade_date", "concept_name", "concept_stock_count",
        "concept_member_share", "concept_member_share > 0.10 AS concept_broad_flag",
        "concept_stock_count >= 5 AND concept_member_share <= 0.10 AS concept_narrow_flag",
    ]
    for n in FULL_PERIODS:
        select_items.extend(
            [
                f"concept_ret_{n}",
                f"rank() OVER (PARTITION BY trade_date ORDER BY concept_ret_{n} DESC NULLS LAST)::INTEGER AS concept_ret_rank_all_{n}",
                f"percent_rank() OVER (PARTITION BY trade_date ORDER BY concept_ret_{n}) AS concept_ret_pct_all_{n}",
                f"concept_amount_ma_{n}",
                f"percent_rank() OVER (PARTITION BY trade_date ORDER BY concept_amount_ma_{n}) AS concept_amount_pct_all_{n}",
                f"concept_up_ratio_{n}",
                f"concept_limit_up_count_{n}::INTEGER AS concept_limit_up_count_{n}",
                f"NULL::DOUBLE AS concept_main_flow_sum_{n}",
                f"(percent_rank() OVER (PARTITION BY trade_date ORDER BY concept_ret_{n}) >= 0.8 OR percent_rank() OVER (PARTITION BY trade_date ORDER BY concept_amount_ma_{n}) >= 0.8) AS concept_hot_flag_{n}",
            ]
        )
    windows = ", ".join(
        f"w{n} AS (PARTITION BY concept_id ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)"
        for n in FULL_PERIODS
    )
    stock_context_where = ""
    final_where = ""
    if start and end and read_start:
        stock_context_where = f"WHERE cd.trade_date BETWEEN {date_literal(read_start)} AND {date_literal(end)}"
        final_where = f"WHERE trade_date BETWEEN {date_literal(start)} AND {date_literal(end)}"
    return f"""
    INSERT INTO derived_concept_daily_cache
    WITH stock_context AS (
        SELECT
            cd.concept_id,
            cd.concept_name,
            cd.trade_date,
            cd.member_count::INTEGER AS concept_stock_count,
            cd.member_count::DOUBLE / nullif(mb.stock_count, 0) AS concept_member_share,
            CASE WHEN cd.ret_equal_weight > -100 THEN cd.ret_equal_weight / 100.0 ELSE NULL END AS ret_ratio,
            cd.amount_total,
            CASE WHEN cd.member_count > 0 THEN cd.limit_up_count::DOUBLE / cd.member_count ELSE NULL END AS up_ratio,
            cd.limit_up_count
        FROM concept_daily cd
        LEFT JOIN market_breadth_daily mb ON cd.trade_date = mb.trade_date
        {stock_context_where}
    ),
    rolling AS (
        SELECT
            *,
            {", ".join(rolling)}
        FROM stock_context
        WINDOW {windows}
    )
    SELECT
        {", ".join(select_items)},
        CURRENT_TIMESTAMP AS updated_at
    FROM rolling
    {final_where}
    """


def index_daily_cache_sql(start: str | None = None, end: str | None = None, read_start: str | None = None) -> str:
    rolling = []
    for n in FULL_PERIODS:
        rolling.append(
            f"CASE WHEN close > 0 AND lag(close, {n}) OVER idx > 0 THEN close / lag(close, {n}) OVER idx - 1 ELSE NULL END AS index_ret_{n}"
        )
    for n in VOL_PERIODS:
        rolling.extend(
            [
                f"stddev_samp(log_ret_1) OVER w{n} * sqrt(242) AS index_vol_{n}",
                f"avg(amount) OVER w{n} AS index_amount_ma_{n}",
            ]
        )
    change_items = []
    final_select = ["index_code", "trade_date", "index_name", "index_close"]
    final_select.extend(f"index_ret_{n}" for n in FULL_PERIODS)
    for n in VOL_PERIODS:
        change_items.append(
            f"CASE WHEN lag(index_amount_ma_{n}, {n}) OVER (PARTITION BY index_code ORDER BY trade_date) > 0 THEN index_amount_ma_{n} / lag(index_amount_ma_{n}, {n}) OVER (PARTITION BY index_code ORDER BY trade_date) - 1 ELSE NULL END AS index_amount_chg_{n}"
        )
        final_select.extend(
            [
                f"index_vol_{n}",
                f"index_amount_ma_{n}",
                f"index_amount_chg_{n}",
            ]
        )
    windows = ", ".join([f"w{n} AS (PARTITION BY index_code ORDER BY trade_date ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)" for n in VOL_PERIODS] + ["idx AS (PARTITION BY index_code ORDER BY trade_date)"])
    base_where = ""
    final_where = ""
    if start and end and read_start:
        base_where = f"WHERE d.trade_date BETWEEN {date_literal(read_start)} AND {date_literal(end)}"
        final_where = f"WHERE trade_date BETWEEN {date_literal(start)} AND {date_literal(end)}"
    return f"""
    INSERT INTO derived_index_daily_cache
    WITH base AS (
        SELECT
            d.index_code,
            d.trade_date,
            coalesce(i.index_name, d.index_code) AS index_name,
            d.close,
            d.amount,
            CASE WHEN d.close > 0 AND lag(d.close) OVER (PARTITION BY d.index_code ORDER BY d.trade_date) > 0
                 THEN ln(d.close / lag(d.close) OVER (PARTITION BY d.index_code ORDER BY d.trade_date))
                ELSE NULL END AS log_ret_1
        FROM index_daily d
        LEFT JOIN index_basic_info i USING (index_code)
        {base_where}
    ),
    rolling AS (
        SELECT
            index_code,
            trade_date,
            index_name,
            close AS index_close,
            {", ".join(rolling)}
        FROM base
        WINDOW {windows}
    ),
    changed AS (
        SELECT
            *,
            {", ".join(change_items)}
        FROM rolling
    )
    SELECT
        {", ".join(final_select)},
        CURRENT_TIMESTAMP AS updated_at
    FROM changed
    {final_where}
    """


def index_membership_cache_sql(start: str | None = None, end: str | None = None, read_start: str | None = None) -> str:
    values = []
    for prefix, (code, name) in INDEX_MAP.items():
        values.append(f"('{prefix}', '{code}', '{name}')")
    member_flags = [f"p.{p}_weight IS NOT NULL AS is_{p}_member" for p in INDEX_MAP]
    weights = [f"p.{p}_weight" for p in INDEX_MAP]
    count_expr = " + ".join(f"CASE WHEN p.{p}_weight IS NOT NULL THEN 1 ELSE 0 END" for p in INDEX_MAP)
    primary_case = """
        CASE
            WHEN p.sse50_weight IS NOT NULL THEN '000016.SH'
            WHEN p.star50_weight IS NOT NULL THEN '000688.SH'
            WHEN p.chinext_weight IS NOT NULL THEN '399006.SZ'
            WHEN p.hs300_weight IS NOT NULL THEN '000300.SH'
            WHEN p.zz500_weight IS NOT NULL THEN '000905.SH'
            WHEN p.zz1000_weight IS NOT NULL THEN '000852.SH'
            ELSE NULL
        END
    """
    primary_name = """
        CASE
            WHEN p.sse50_weight IS NOT NULL THEN '上证50'
            WHEN p.star50_weight IS NOT NULL THEN '科创50'
            WHEN p.chinext_weight IS NOT NULL THEN '创业板指'
            WHEN p.hs300_weight IS NOT NULL THEN '沪深300'
            WHEN p.zz500_weight IS NOT NULL THEN '中证500'
            WHEN p.zz1000_weight IS NOT NULL THEN '中证1000'
            ELSE NULL
        END
    """
    open_dates_where = ""
    spine_where = ""
    if start and end:
        open_dates_where = f"AND cal_date BETWEEN {date_literal(start)} AND {date_literal(end)}"
        spine_where = f"WHERE ds.trade_date BETWEEN {date_literal(start)} AND {date_literal(end)}"
    return f"""
    INSERT INTO derived_index_membership_cache
    WITH index_map(prefix, index_code, index_name) AS (
        VALUES {", ".join(values)}
    ),
    weight_interval AS (
        SELECT
            im.prefix,
            iw.con_code AS ts_code,
            iw.trade_date AS start_date,
            least(
                lead(iw.trade_date, 1, DATE '2999-12-31') OVER (
                    PARTITION BY iw.index_code, iw.con_code ORDER BY iw.trade_date
                ),
                iw.trade_date + INTERVAL 91 DAY
            ) AS end_date,
            iw.weight
        FROM index_weight iw
        JOIN index_map im ON iw.index_code = im.index_code
    ),
    open_dates AS (
        SELECT DISTINCT cal_date AS trade_date
        FROM trade_calendar
        WHERE is_open
        {open_dates_where}
    ),
    expanded AS (
        SELECT
            w.prefix,
            w.ts_code,
            d.trade_date,
            w.weight
        FROM weight_interval w
        JOIN open_dates d
          ON d.trade_date >= w.start_date
         AND d.trade_date < w.end_date
    ),
    pivoted AS (
        SELECT
            ts_code,
            trade_date,
            max(CASE WHEN prefix = 'hs300' THEN weight END) AS hs300_weight,
            max(CASE WHEN prefix = 'zz500' THEN weight END) AS zz500_weight,
            max(CASE WHEN prefix = 'zz1000' THEN weight END) AS zz1000_weight,
            max(CASE WHEN prefix = 'sse50' THEN weight END) AS sse50_weight,
            max(CASE WHEN prefix = 'star50' THEN weight END) AS star50_weight,
            max(CASE WHEN prefix = 'chinext' THEN weight END) AS chinext_weight
        FROM expanded
        GROUP BY ts_code, trade_date
    )
    SELECT
        ds.ts_code,
        ds.trade_date,
        {", ".join(member_flags)},
        {", ".join(weights)},
        ({count_expr})::INTEGER AS index_member_count,
        {primary_case} AS primary_index_code,
        {primary_name} AS primary_index_name,
        ({count_expr}) > 0 AS has_index_weight,
        CURRENT_TIMESTAMP AS updated_at
    FROM derived_daily_spine ds
    LEFT JOIN pivoted p USING (ts_code, trade_date)
    {spine_where}
    """


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 3 sector/index cache tables.")
    parser.add_argument("--start-date", help="Write-window start date, YYYY-MM-DD. Omit for full rebuild.")
    parser.add_argument("--end-date", help="Write-window end date, YYYY-MM-DD. Omit for full rebuild.")
    parser.add_argument("--context-days", type=int, default=260, help="Trading-day read context for rolling cache refresh.")
    args = parser.parse_args()
    if bool(args.start_date) != bool(args.end_date):
        raise SystemExit("--start-date and --end-date must be provided together")

    started_at = datetime.now().isoformat(timespec="seconds")
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    start = args.start_date
    end = args.end_date
    read_start = resolve_read_start(con, start, args.context_days) if start and end else None
    jobs = [
        ("derived_sector_daily_cache", sector_cache_sql(start, end, read_start)),
        ("derived_concept_daily_cache", concept_cache_sql(start, end, read_start)),
        ("derived_index_daily_cache", index_daily_cache_sql(start, end, read_start)),
        ("derived_index_membership_cache", index_membership_cache_sql(start, end, read_start)),
    ]
    summary = {}
    for table, sql in jobs:
        con.execute("BEGIN TRANSACTION")
        try:
            delete_table_window(con, table, start, end)
            con.execute(sql)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        summary[table] = table_count(con, table, start, end)
        print(json.dumps({"table": table, "rows": summary[table]}, ensure_ascii=False))
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "window" if start and end else "full",
        "start_date": start,
        "end_date": end,
        "read_start_date": read_start,
        "context_days": args.context_days,
        "summary": summary,
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
