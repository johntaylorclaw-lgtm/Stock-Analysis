from __future__ import annotations

from calendar import monthrange
from datetime import datetime
from hashlib import sha1
from typing import Any

import pandas as pd

from .database import (
    connect,
    fetch_task_state,
    init_database,
    record_task_failure,
    record_task_state,
    upsert_dataframe,
)
from .config import load_pipeline
from .transform import add_payload_json, add_updated_at, normalize_dates, rename_columns
from .tushare_source import TushareClient


STOCK_BASIC_FIELDS = (
    "ts_code,symbol,name,area,industry,market,exchange,list_status,list_date,delist_date"
)

INDEX_MARKETS = ["SSE", "SZSE", "CSI", "CNI", "SW"]

DATE_COLUMNS = [
    "trade_date",
    "cal_date",
    "pretrade_date",
    "ann_date",
    "f_ann_date",
    "first_ann_date",
    "end_date",
    "list_date",
    "delist_date",
    "base_date",
    "event_date",
]

FINANCIAL_EVENT_APIS = [
    "forecast",
    "express",
    "dividend",
    "fina_audit",
    "fina_mainbz",
    "disclosure_date",
    "stk_holdernumber",
    "top10_holders",
    "top10_floatholders",
    "pledge_stat",
    "pledge_detail",
    "repurchase",
    "share_float",
]


def sync_stock_basic(client: TushareClient | None = None) -> dict[str, int]:
    client = client or TushareClient()
    frames = []
    for status in ["L", "D", "P"]:
        df = client.call("stock_basic", exchange="", list_status=status, fields=STOCK_BASIC_FIELDS)
        if not df.empty:
            frames.append(df)
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raw = normalize_dates(raw, ["list_date", "delist_date"])
    raw["is_active"] = raw["list_status"].eq("L") if "list_status" in raw.columns else False
    raw = add_updated_at(raw)

    with connect() as con:
        init_database(con)
        rows = upsert_dataframe(con, "stock_basic_info", raw, ["ts_code"])
        record_task_state(con, "sync_stock_basic", "all_status", "success", row_count=rows)
    return {"stock_basic_info": rows}


def sync_trade_calendar(start_date: str = "20060101", end_date: str | None = None) -> dict[str, int]:
    client = TushareClient()
    params: dict[str, Any] = {"exchange": "SSE", "start_date": start_date}
    if end_date:
        params["end_date"] = end_date
    df = client.call("trade_cal", **params)
    df = normalize_dates(df, ["cal_date", "pretrade_date"])
    if "is_open" in df.columns:
        df["is_open"] = df["is_open"].astype(bool)
    df = add_updated_at(df)
    with connect() as con:
        init_database(con)
        rows = upsert_dataframe(con, "trade_calendar", df, ["cal_date", "exchange"])
        record_task_state(con, "sync_trade_calendar", "SSE", "success", checkpoint_value=end_date, row_count=rows)
    return {"trade_calendar": rows}


def sync_index_basic() -> dict[str, int]:
    client = TushareClient()
    frames = []
    for market in INDEX_MARKETS:
        df = client.call("index_basic", market=market)
        if not df.empty:
            df["market"] = market
            frames.append(df)
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raw = rename_columns(raw, {"ts_code": "index_code", "name": "index_name"})
    raw = normalize_dates(raw, ["base_date", "list_date"])
    raw = add_updated_at(raw)
    with connect() as con:
        init_database(con)
        rows = upsert_dataframe(con, "index_basic_info", raw, ["index_code"])
        record_task_state(con, "sync_index_basic", "all_markets", "success", row_count=rows)
    return {"index_basic_info": rows}


def sync_stock_company() -> dict[str, int]:
    client = TushareClient()
    frames = []
    for exchange in ["SSE", "SZSE", "BSE"]:
        df = client.call("stock_company", exchange=exchange)
        if not df.empty:
            frames.append(df)
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raw = rename_columns(
        raw,
        {
            "com_name": "company_name",
            "com_id": "company_id",
            "reg_capital": "registered_capital",
        },
    )
    raw = normalize_dates(raw, ["setup_date"])
    raw = add_updated_at(raw)
    with connect() as con:
        init_database(con)
        rows = upsert_dataframe(con, "stock_company_info", raw, ["ts_code"])
        record_task_state(con, "sync_stock_company", "all_exchanges", "success", row_count=rows)
    return {"stock_company_info": rows}


def sync_stock_status_history() -> dict[str, int]:
    with connect() as con:
        init_database(con)
        rows_df = con.execute(
            """
            SELECT
                ts_code,
                list_date AS effective_date,
                'L' AS list_status,
                name,
                true AS is_active,
                'listed' AS change_reason
            FROM stock_basic_info
            WHERE list_date IS NOT NULL
            UNION ALL
            SELECT
                ts_code,
                delist_date AS effective_date,
                'D' AS list_status,
                name,
                false AS is_active,
                'delisted' AS change_reason
            FROM stock_basic_info
            WHERE delist_date IS NOT NULL
            """
        ).fetchdf()
        rows_df = add_updated_at(rows_df)
        rows = upsert_dataframe(con, "stock_status_history", rows_df, ["ts_code", "effective_date", "list_status"])
        record_task_state(con, "sync_stock_status_history", "derived_from_stock_basic", "success", row_count=rows)
    return {"stock_status_history": rows}


def sync_daily_for_date(trade_date: str) -> dict[str, int]:
    client = TushareClient()
    outputs: dict[str, int] = {}
    calls = [
        ("daily", "stock_daily", ["ts_code", "trade_date"]),
        ("daily_basic", "stock_daily_basic", ["ts_code", "trade_date"]),
        ("stk_limit", "stock_limit_price", ["ts_code", "trade_date"]),
    ]
    with connect() as con:
        init_database(con)
        for api_name, table_name, pk in calls:
            raw = client.call(api_name, trade_date=trade_date)
            raw = rename_columns(raw, {"vol": "volume", "turnover_rate_f": "turnover_rate_free"})
            raw = normalize_dates(raw, ["trade_date"])
            if table_name == "stock_daily" and {"high", "low", "pre_close"}.issubset(raw.columns):
                raw["amplitude"] = (raw["high"] - raw["low"]) / raw["pre_close"] * 100
            raw = add_updated_at(raw)
            rows = upsert_dataframe(con, table_name, raw, pk)
            outputs[table_name] = rows
            record_task_state(con, f"sync_{api_name}", trade_date, "success", row_count=rows)
    return outputs


def sync_market_behavior_for_date(trade_date: str) -> dict[str, int]:
    client = TushareClient()
    outputs: dict[str, int] = {}
    calls = [
        ("moneyflow", "stock_moneyflow_daily", ["ts_code", "trade_date"]),
        ("margin_detail", "margin_detail", ["ts_code", "trade_date"]),
        ("moneyflow_hsgt", "northbound_daily", ["trade_date"]),
        ("hk_hold", "northbound_holding", ["ts_code", "trade_date", "exchange_type"]),
        ("top_list", "top_list_daily", ["ts_code", "trade_date", "reason"]),
        ("top_inst", "top_inst_detail", ["ts_code", "trade_date", "exalter", "side", "reason"]),
    ]
    with connect() as con:
        init_database(con)
        for api_name, table_name, pk in calls:
            raw = client.call(api_name, trade_date=trade_date)
            raw = rename_columns(
                raw,
                {
                    "rzye": "margin_balance",
                    "rqye": "short_balance",
                    "rzmre": "margin_buy",
                    "rqyl": "short_volume",
                    "rzche": "margin_repay",
                    "rqchl": "short_repay_volume",
                    "rqmcl": "short_sell_volume",
                    "rzrqye": "total_balance",
                    "code": "hk_code",
                    "vol": "hold_shares",
                    "ratio": "hold_ratio",
                    "exchange": "exchange_type",
                },
            )
            raw = normalize_dates(raw, ["trade_date"])
            raw = add_updated_at(raw)
            rows = upsert_dataframe(con, table_name, raw, pk)
            outputs[table_name] = rows
            record_task_state(con, f"sync_{api_name}", trade_date, "success", row_count=rows)
    return outputs


def sync_market_behavior_range(start_date: str, end_date: str, limit: int | None = None) -> dict[str, int]:
    dates = open_trade_dates(start_date, end_date)
    if limit is not None:
        dates = dates[:limit]
    totals = {
        "stock_moneyflow_daily": 0,
        "margin_detail": 0,
        "northbound_daily": 0,
        "northbound_holding": 0,
        "top_list_daily": 0,
        "top_inst_detail": 0,
        "trade_dates": len(dates),
    }
    for trade_date in dates:
        with connect() as con:
            state = fetch_task_state(con, "sync_market_behavior_date", trade_date)
        if state and state.get("status") == "success":
            continue
        result = sync_market_behavior_for_date(trade_date)
        for key, value in result.items():
            totals[key] = totals.get(key, 0) + value
        with connect() as con:
            init_database(con)
            record_task_state(con, "sync_market_behavior_date", trade_date, "success", row_count=sum(result.values()))
    return totals


def sync_dividend_batch(
    start_date: str = "20060101",
    end_date: str | None = None,
    limit: int | None = None,
    resume: bool = True,
) -> dict[str, int]:
    client = TushareClient()
    codes = stock_codes(["L", "D", "P"])
    if limit is not None:
        codes = codes[:limit]
    totals = {"financial_dividend_raw": 0, "stocks_seen": 0, "stocks_done": 0, "stocks_failed": 0, "stocks_skipped": 0}
    checkpoint = end_date or "latest"
    with connect() as con:
        init_database(con)
    for code in codes:
        totals["stocks_seen"] += 1
        if resume:
            with connect() as con:
                state = fetch_task_state(con, "sync_dividend", code)
            if state and state.get("status") == "success" and state.get("checkpoint_value") == checkpoint:
                totals["stocks_skipped"] += 1
                continue
        try:
            params: dict[str, Any] = {"ts_code": code}
            raw = client.call("dividend", **params)
            if not raw.empty:
                raw = raw[
                    (raw.get("ann_date").fillna("") >= start_date)
                    & (raw.get("ann_date").fillna("") <= checkpoint.replace("-", ""))
                ] if end_date and "ann_date" in raw.columns else raw
            payload_df = add_payload_json(raw.copy())
            raw = normalize_dates(raw, DATE_COLUMNS + ["record_date", "ex_date", "pay_date", "div_listdate"])
            if not raw.empty:
                raw["record_key"] = [
                    sha1(f"dividend|{code}|{payload}".encode("utf-8")).hexdigest()
                    for payload in payload_df["payload_json"].tolist()
                ]
                raw["payload_json"] = payload_df["payload_json"]
            raw = add_updated_at(raw)
            with connect() as con:
                init_database(con)
                rows = upsert_dataframe(con, "financial_dividend_raw", raw, ["ts_code", "end_date", "ann_date", "record_key"])
                record_task_state(con, "sync_dividend", code, "success", checkpoint_value=checkpoint, row_count=rows)
            totals["financial_dividend_raw"] += rows
            totals["stocks_done"] += 1
        except Exception as exc:  # noqa: BLE001
            totals["stocks_failed"] += 1
            with connect() as con:
                init_database(con)
                record_task_failure(con, "sync_dividend", code, str(exc))
                record_task_state(con, "sync_dividend", code, "failed", checkpoint_value=checkpoint, error_message=str(exc))
    return totals


def sync_disclosure_schedule(start_date: str = "20060101", end_date: str | None = None) -> dict[str, int]:
    client = TushareClient()
    params: dict[str, Any] = {"start_date": start_date}
    if end_date:
        params["end_date"] = end_date
    raw = client.call("disclosure_date", **params)
    raw = normalize_dates(raw, ["ann_date", "end_date", "pre_date", "actual_date", "modify_date"])
    raw = add_updated_at(raw)
    with connect() as con:
        init_database(con)
        rows = upsert_dataframe(con, "financial_disclosure_schedule", raw, ["ts_code", "end_date", "ann_date"])
        record_task_state(con, "sync_disclosure_schedule", f"{start_date}:{end_date or 'latest'}", "success", row_count=rows)
    return {"financial_disclosure_schedule": rows}


def sync_disclosure_schedule_batch(
    start_date: str = "20060101",
    end_date: str | None = None,
    limit: int | None = None,
    resume: bool = True,
) -> dict[str, int]:
    client = TushareClient()
    codes = stock_codes(["L", "D", "P"])
    if limit is not None:
        codes = codes[:limit]
    totals = {"financial_disclosure_schedule": 0, "stocks_seen": 0, "stocks_done": 0, "stocks_failed": 0, "stocks_skipped": 0}
    checkpoint = end_date or "latest"
    for code in codes:
        totals["stocks_seen"] += 1
        if resume:
            with connect() as con:
                state = fetch_task_state(con, "sync_disclosure_schedule", code)
            if state and state.get("status") == "success" and state.get("checkpoint_value") == checkpoint:
                totals["stocks_skipped"] += 1
                continue
        try:
            raw = client.call("disclosure_date", ts_code=code)
            if not raw.empty:
                if "end_date" in raw.columns:
                    raw = raw[raw["end_date"].fillna("") >= start_date]
                    if end_date:
                        raw = raw[raw["end_date"].fillna("") <= end_date]
            payload_df = add_payload_json(raw.copy())
            raw = normalize_dates(raw, ["ann_date", "end_date", "pre_date", "actual_date", "modify_date"])
            if not raw.empty:
                raw["record_key"] = [
                    sha1(f"disclosure_date|{code}|{payload}".encode("utf-8")).hexdigest()
                    for payload in payload_df["payload_json"].tolist()
                ]
            raw = add_updated_at(raw)
            with connect() as con:
                init_database(con)
                rows = upsert_dataframe(con, "financial_disclosure_schedule", raw, ["ts_code", "end_date", "record_key"])
                record_task_state(con, "sync_disclosure_schedule", code, "success", checkpoint_value=checkpoint, row_count=rows)
            totals["financial_disclosure_schedule"] += rows
            totals["stocks_done"] += 1
        except Exception as exc:  # noqa: BLE001
            totals["stocks_failed"] += 1
            with connect() as con:
                init_database(con)
                record_task_failure(con, "sync_disclosure_schedule", code, str(exc))
                record_task_state(con, "sync_disclosure_schedule", code, "failed", checkpoint_value=checkpoint, error_message=str(exc))
    return totals


def sync_pledge_stat_batch(limit: int | None = None, resume: bool = True) -> dict[str, int]:
    client = TushareClient()
    codes = stock_codes(["L", "D", "P"])
    if limit is not None:
        codes = codes[:limit]
    totals = {"pledge_stat": 0, "stocks_seen": 0, "stocks_done": 0, "stocks_failed": 0, "stocks_skipped": 0}
    for code in codes:
        totals["stocks_seen"] += 1
        if resume:
            with connect() as con:
                state = fetch_task_state(con, "sync_pledge_stat", code)
            if state and state.get("status") == "success":
                totals["stocks_skipped"] += 1
                continue
        try:
            raw = client.call("pledge_stat", ts_code=code)
            raw = normalize_dates(raw, ["end_date"])
            raw = add_updated_at(raw)
            with connect() as con:
                init_database(con)
                rows = upsert_dataframe(con, "pledge_stat", raw, ["ts_code", "end_date"])
                record_task_state(con, "sync_pledge_stat", code, "success", row_count=rows)
            totals["pledge_stat"] += rows
            totals["stocks_done"] += 1
        except Exception as exc:  # noqa: BLE001
            totals["stocks_failed"] += 1
            with connect() as con:
                init_database(con)
                record_task_failure(con, "sync_pledge_stat", code, str(exc))
                record_task_state(con, "sync_pledge_stat", code, "failed", error_message=str(exc))
    return totals


def open_trade_dates(start_date: str, end_date: str) -> list[str]:
    with connect() as con:
        rows = con.execute(
            """
            SELECT strftime(cal_date, '%Y%m%d')
            FROM trade_calendar
            WHERE exchange = 'SSE'
              AND is_open = true
              AND cal_date BETWEEN strptime(?, '%Y%m%d') AND strptime(?, '%Y%m%d')
            ORDER BY cal_date
            """,
            [start_date, end_date],
        ).fetchall()
    return [row[0] for row in rows]


def sync_daily_range(start_date: str, end_date: str, limit: int | None = None) -> dict[str, int]:
    dates = open_trade_dates(start_date, end_date)
    if limit is not None:
        dates = dates[:limit]
    totals = {"stock_daily": 0, "stock_daily_basic": 0, "stock_limit_price": 0}
    for trade_date in dates:
        result = sync_daily_for_date(trade_date)
        for key, value in result.items():
            totals[key] = totals.get(key, 0) + value
    return totals | {"trade_dates": len(dates)}


def sync_adj_factor_for_stock(ts_code: str, start_date: str = "20060101", end_date: str | None = None) -> dict[str, int]:
    client = TushareClient()
    params: dict[str, Any] = {"ts_code": ts_code, "start_date": start_date}
    if end_date:
        params["end_date"] = end_date
    raw = client.call("adj_factor", **params)
    raw = normalize_dates(raw, ["trade_date"])
    raw = add_updated_at(raw)
    with connect() as con:
        init_database(con)
        rows = upsert_dataframe(con, "stock_adj_factor", raw, ["ts_code", "trade_date"])
        record_task_state(con, "sync_adj_factor", ts_code, "success", checkpoint_value=end_date, row_count=rows)
    return {"stock_adj_factor": rows}


def stock_codes(include_status: list[str] | None = None) -> list[str]:
    statuses = include_status or ["L", "D", "P"]
    placeholders = ", ".join(["?"] * len(statuses))
    with connect() as con:
        rows = con.execute(
            f"""
            SELECT ts_code
            FROM stock_basic_info
            WHERE list_status IN ({placeholders})
            ORDER BY ts_code
            """,
            statuses,
        ).fetchall()
    return [row[0] for row in rows]


def sync_adj_factor_batch(
    start_date: str = "20060101",
    end_date: str | None = None,
    limit: int | None = None,
    resume: bool = True,
) -> dict[str, int]:
    codes = stock_codes(["L", "D", "P"])
    if limit is not None:
        codes = codes[:limit]
    totals = {"stock_adj_factor": 0, "stocks_seen": 0, "stocks_done": 0, "stocks_failed": 0, "stocks_skipped": 0}
    for code in codes:
        totals["stocks_seen"] += 1
        if resume:
            with connect() as con:
                state = fetch_task_state(con, "sync_adj_factor", code)
            if state and state.get("status") == "success" and state.get("checkpoint_value") == end_date:
                totals["stocks_skipped"] += 1
                continue
        try:
            result = sync_adj_factor_for_stock(code, start_date=start_date, end_date=end_date)
            totals["stock_adj_factor"] += result["stock_adj_factor"]
            totals["stocks_done"] += 1
        except Exception as exc:  # noqa: BLE001 - batch must record source/API failures.
            totals["stocks_failed"] += 1
            with connect() as con:
                init_database(con)
                record_task_failure(con, "sync_adj_factor", code, str(exc))
                record_task_state(con, "sync_adj_factor", code, "failed", checkpoint_value=end_date, error_message=str(exc))
    return totals


def default_index_codes() -> list[str]:
    return [item["index_code"] for item in load_pipeline()["default_index_pool"]]


def sync_index_daily_range(
    start_date: str,
    end_date: str,
    index_codes: list[str] | None = None,
) -> dict[str, int]:
    client = TushareClient()
    codes = index_codes or default_index_codes()
    total = 0
    with connect() as con:
        init_database(con)
        for index_code in codes:
            raw = client.call("index_daily", ts_code=index_code, start_date=start_date, end_date=end_date)
            raw = rename_columns(raw, {"ts_code": "index_code", "vol": "volume"})
            raw = normalize_dates(raw, ["trade_date"])
            raw = add_updated_at(raw)
            rows = upsert_dataframe(con, "index_daily", raw, ["index_code", "trade_date"])
            total += rows
            record_task_state(con, "sync_index_daily", index_code, "success", checkpoint_value=end_date, row_count=rows)
    return {"index_daily": total, "index_count": len(codes)}


def sync_index_weight_month(
    month: str,
    index_codes: list[str] | None = None,
) -> dict[str, int]:
    client = TushareClient()
    codes = index_codes or default_index_codes()
    month_start = datetime.strptime(month, "%Y%m")
    month_end = month_start.replace(day=monthrange(month_start.year, month_start.month)[1])
    start_date = month_start.strftime("%Y%m%d")
    end_date = month_end.strftime("%Y%m%d")
    total = 0
    with connect() as con:
        init_database(con)
        for index_code in codes:
            raw = client.call("index_weight", index_code=index_code, start_date=start_date, end_date=end_date)
            raw = normalize_dates(raw, ["trade_date"])
            raw = add_updated_at(raw)
            rows = upsert_dataframe(con, "index_weight", raw, ["index_code", "con_code", "trade_date"])
            total += rows
            record_task_state(con, "sync_index_weight", f"{index_code}:{month}", "success", checkpoint_value=month, row_count=rows)
    return {"index_weight": total, "index_count": len(codes), "month": int(month)}


def iter_months(start_month: str, end_month: str) -> list[str]:
    current = datetime.strptime(start_month, "%Y%m")
    end = datetime.strptime(end_month, "%Y%m")
    months: list[str] = []
    while current <= end:
        months.append(current.strftime("%Y%m"))
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        current = current.replace(year=year, month=month)
    return months


def sync_index_weight_range(
    start_month: str,
    end_month: str,
    index_codes: list[str] | None = None,
    resume: bool = True,
) -> dict[str, int]:
    codes = index_codes or default_index_codes()
    totals = {"index_weight": 0, "months_seen": 0, "months_done": 0, "months_failed": 0, "months_skipped": 0}
    for month in iter_months(start_month, end_month):
        task_key = f"{','.join(codes)}:{month}"
        totals["months_seen"] += 1
        if resume:
            with connect() as con:
                state = fetch_task_state(con, "sync_index_weight_range", task_key)
            if state and state.get("status") == "success":
                totals["months_skipped"] += 1
                continue
        try:
            result = sync_index_weight_month(month, index_codes=codes)
            totals["index_weight"] += result["index_weight"]
            totals["months_done"] += 1
            with connect() as con:
                init_database(con)
                record_task_state(con, "sync_index_weight_range", task_key, "success", checkpoint_value=month, row_count=result["index_weight"])
        except Exception as exc:  # noqa: BLE001
            totals["months_failed"] += 1
            with connect() as con:
                init_database(con)
                record_task_failure(con, "sync_index_weight_range", task_key, str(exc))
                record_task_state(con, "sync_index_weight_range", task_key, "failed", checkpoint_value=month, error_message=str(exc))
    return totals


def sync_sw_industry(limit_members: int | None = None) -> dict[str, int]:
    client = TushareClient()
    classify = client.call("index_classify", src="SW2021")
    classify = rename_columns(classify, {"industry_code": "sw_code", "index_code": "industry_code"})
    classify["src"] = "SW2021"
    classify = add_updated_at(classify)

    member_frames = []
    industry_codes = classify["industry_code"].dropna().tolist() if "industry_code" in classify.columns else []
    if limit_members is not None:
        industry_codes = industry_codes[:limit_members]
    for industry_code in industry_codes:
        df = client.call("index_member_all", l1_code=industry_code)
        if not df.empty:
            member_frames.append(df)
    members = pd.concat(member_frames, ignore_index=True) if member_frames else pd.DataFrame()
    members = rename_columns(
        members,
        {
            "l1_code": "industry_code",
            "l1_name": "industry_name",
            "con_code": "ts_code",
            "con_name": "stock_name",
        },
    )
    members = normalize_dates(members, ["in_date", "out_date"])
    members = add_updated_at(members)

    with connect() as con:
        init_database(con)
        classify_rows = upsert_dataframe(con, "sw_industry_classify", classify, ["industry_code"])
        member_rows = upsert_dataframe(con, "sw_industry_member", members, ["industry_code", "ts_code", "in_date"])
        record_task_state(con, "sync_sw_industry", "SW2021", "success", row_count=classify_rows + member_rows)
    return {"sw_industry_classify": classify_rows, "sw_industry_member": member_rows}


def sync_concepts(limit_concepts: int | None = None) -> dict[str, int]:
    client = TushareClient()
    concepts = client.call("concept")
    concepts = rename_columns(concepts, {"code": "concept_id", "name": "concept_name", "src": "source"})
    concepts = add_updated_at(concepts)

    member_frames = []
    ids = concepts["concept_id"].dropna().tolist() if "concept_id" in concepts.columns else []
    if limit_concepts is not None:
        ids = ids[:limit_concepts]
    for concept_id in ids:
        df = client.call("concept_detail", id=concept_id)
        if not df.empty:
            if "id" not in df.columns:
                df["concept_id"] = concept_id
            member_frames.append(df)
    members = pd.concat(member_frames, ignore_index=True) if member_frames else pd.DataFrame()
    members = rename_columns(
        members,
        {
            "id": "concept_id",
            "concept_name": "concept_name",
            "name": "stock_name",
        },
    )
    members = normalize_dates(members, ["in_date", "out_date"])
    members = add_updated_at(members)

    with connect() as con:
        init_database(con)
        concept_rows = upsert_dataframe(con, "concept_basic", concepts, ["concept_id"])
        member_rows = upsert_dataframe(con, "concept_member", members, ["concept_id", "ts_code"])
        record_task_state(con, "sync_concepts", "all", "success", row_count=concept_rows + member_rows)
    return {"concept_basic": concept_rows, "concept_member": member_rows}


def sync_financial_sample(ts_code: str, start_date: str = "20240101", end_date: str | None = None) -> dict[str, int]:
    client = TushareClient()
    outputs: dict[str, int] = {}
    calls = [
        ("income", "financial_income_raw"),
        ("balancesheet", "financial_balance_raw"),
        ("cashflow", "financial_cashflow_raw"),
        ("fina_indicator", "financial_indicator_raw"),
    ]
    with connect() as con:
        init_database(con)
        for api_name, table_name in calls:
            params: dict[str, Any] = {"ts_code": ts_code, "start_date": start_date}
            if end_date:
                params["end_date"] = end_date
            raw = client.call(api_name, **params)
            payload_df = add_payload_json(raw.copy())
            raw = rename_columns(
                raw,
                {
                    "f_ann_date": "first_ann_date",
                    "oper_cost": "operating_cost",
                    "sell_exp": "selling_expense",
                    "admin_exp": "admin_expense",
                    "fin_exp": "finance_expense",
                    "operate_profit": "operating_profit",
                    "n_income": "net_profit",
                    "n_income_attr_p": "net_profit_attr_parent",
                    "money_cap": "cash_and_equivalents",
                    "accounts_receiv": "accounts_receivable",
                    "total_cur_assets": "current_assets",
                    "fix_assets": "fixed_assets",
                    "cip": "construction_in_process",
                    "intan_assets": "intangible_assets",
                    "st_borr": "short_term_borrowings",
                    "acct_payable": "accounts_payable",
                    "total_cur_liab": "current_liabilities",
                    "lt_borr": "long_term_borrowings",
                    "bond_payable": "bonds_payable",
                    "total_liab": "total_liabilities",
                    "total_hldr_eqy_inc_min_int": "total_equity",
                    "total_hldr_eqy_exc_min_int": "equity_attr_parent",
                    "minority_int": "minority_interest",
                    "c_fr_sale_sg": "cash_received_from_sales",
                    "c_inf_fr_operate_a": "total_operating_cash_inflow",
                    "c_paid_goods_s": "cash_paid_for_goods",
                    "c_paid_to_for_empl": "cash_paid_to_employees",
                    "c_paid_for_taxes": "taxes_paid",
                    "n_cashflow_act": "cf_from_operating",
                    "c_pay_acq_const_fiolta": "cash_paid_for_capex",
                    "c_paid_invest": "cash_paid_for_investment",
                    "n_cashflow_inv_act": "cf_from_investing",
                    "c_recp_borrow": "cash_received_from_borrowing",
                    "c_prepay_amt_borr": "cash_paid_for_debt",
                    "c_pay_dist_dpcp_int_exp": "cash_paid_for_dividend_interest",
                    "n_cash_flows_fnc_act": "cf_from_financing",
                    "n_incr_cash_cash_equ": "net_increase_in_cash",
                    "c_cash_equ_beg_period": "cash_at_beginning",
                    "c_cash_equ_end_period": "cash_at_end",
                },
            )
            raw = normalize_dates(raw, DATE_COLUMNS)
            if table_name == "financial_indicator_raw" and {"ann_date", "end_date"}.issubset(raw.columns):
                raw["ann_date"] = raw["ann_date"].fillna(raw["end_date"])
            if "payload_json" in payload_df.columns:
                raw["payload_json"] = payload_df["payload_json"]
            raw = add_updated_at(raw)
            pk = ["ts_code", "end_date", "ann_date"] if table_name == "financial_indicator_raw" else ["ts_code", "end_date", "comp_type", "report_type", "ann_date"]
            rows = upsert_dataframe(con, table_name, raw, pk)
            outputs[table_name] = rows
            record_task_state(con, f"sample_{api_name}", ts_code, "success", row_count=rows)
    return outputs


def sync_financial_batch(
    start_date: str = "20060101",
    end_date: str | None = None,
    limit: int | None = None,
    resume: bool = True,
) -> dict[str, int]:
    codes = stock_codes(["L", "D", "P"])
    if limit is not None:
        codes = codes[:limit]
    totals = {
        "financial_income_raw": 0,
        "financial_balance_raw": 0,
        "financial_cashflow_raw": 0,
        "financial_indicator_raw": 0,
        "stocks_seen": 0,
        "stocks_done": 0,
        "stocks_failed": 0,
        "stocks_skipped": 0,
    }
    checkpoint = end_date or "latest"
    for code in codes:
        totals["stocks_seen"] += 1
        if resume:
            with connect() as con:
                state = fetch_task_state(con, "sync_financial_batch", code)
            if state and state.get("status") == "success" and state.get("checkpoint_value") == checkpoint:
                totals["stocks_skipped"] += 1
                continue
        try:
            result = sync_financial_sample(code, start_date=start_date, end_date=end_date)
            for key in ["financial_income_raw", "financial_balance_raw", "financial_cashflow_raw", "financial_indicator_raw"]:
                totals[key] += result.get(key, 0)
            totals["stocks_done"] += 1
            with connect() as con:
                init_database(con)
                record_task_state(con, "sync_financial_batch", code, "success", checkpoint_value=checkpoint, row_count=sum(result.values()))
        except Exception as exc:  # noqa: BLE001 - batch must record source/API failures.
            totals["stocks_failed"] += 1
            with connect() as con:
                init_database(con)
                record_task_failure(con, "sync_financial_batch", code, str(exc))
                record_task_state(con, "sync_financial_batch", code, "failed", checkpoint_value=checkpoint, error_message=str(exc))
    return totals


def _event_date_from_row(row: dict[str, Any]) -> Any:
    for key in ["ann_date", "end_date", "trade_date", "date", "holder_date", "release_date", "in_date"]:
        value = row.get(key)
        if value not in (None, "") and not pd.isna(value):
            return value
    return None


def normalize_financial_event(api_name: str, raw: pd.DataFrame, ts_code: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["api_name", "ts_code", "record_key", "ann_date", "end_date", "event_date", "payload_json"])
    raw = normalize_dates(raw.copy(), DATE_COLUMNS + ["holder_date", "release_date", "date", "trade_date"])
    payload_df = add_payload_json(raw.copy())
    records = raw.where(pd.notna(raw), None).to_dict(orient="records")
    rows = []
    for idx, record in enumerate(records):
        code = record.get("ts_code") or ts_code
        key_payload = f"{api_name}|{code}|{payload_df['payload_json'].iloc[idx]}"
        rows.append(
            {
                "api_name": api_name,
                "ts_code": code,
                "record_key": sha1(key_payload.encode("utf-8")).hexdigest(),
                "ann_date": record.get("ann_date"),
                "end_date": record.get("end_date"),
                "event_date": _event_date_from_row(record),
                "payload_json": payload_df["payload_json"].iloc[idx],
            }
        )
    return add_updated_at(pd.DataFrame(rows))


def sync_financial_events_for_stock(
    ts_code: str,
    start_date: str = "20060101",
    end_date: str | None = None,
    apis: list[str] | None = None,
) -> dict[str, int]:
    client = TushareClient()
    selected_apis = apis or FINANCIAL_EVENT_APIS
    totals = {api: 0 for api in selected_apis}
    with connect() as con:
        init_database(con)
        for api_name in selected_apis:
            params: dict[str, Any] = {"ts_code": ts_code, "start_date": start_date}
            if end_date:
                params["end_date"] = end_date
            raw = client.call(api_name, **params)
            normalized = normalize_financial_event(api_name, raw, ts_code)
            rows = upsert_dataframe(con, "financial_event_raw", normalized, ["api_name", "ts_code", "record_key"])
            totals[api_name] = rows
            record_task_state(con, f"sync_financial_event_{api_name}", ts_code, "success", checkpoint_value=end_date or "latest", row_count=rows)
    return totals


def sync_financial_events_batch(
    start_date: str = "20060101",
    end_date: str | None = None,
    limit: int | None = None,
    apis: list[str] | None = None,
    resume: bool = True,
) -> dict[str, int]:
    codes = stock_codes(["L", "D", "P"])
    if limit is not None:
        codes = codes[:limit]
    selected_apis = apis or FINANCIAL_EVENT_APIS
    totals = {api: 0 for api in selected_apis}
    totals.update({"stocks_seen": 0, "stocks_done": 0, "stocks_failed": 0, "stocks_skipped": 0})
    checkpoint = end_date or "latest"
    api_key = ",".join(selected_apis)
    for code in codes:
        totals["stocks_seen"] += 1
        task_key = f"{code}:{api_key}"
        if resume:
            with connect() as con:
                state = fetch_task_state(con, "sync_financial_events_batch", task_key)
            if state and state.get("status") == "success" and state.get("checkpoint_value") == checkpoint:
                totals["stocks_skipped"] += 1
                continue
        try:
            result = sync_financial_events_for_stock(code, start_date=start_date, end_date=end_date, apis=selected_apis)
            for api_name, rows in result.items():
                totals[api_name] += rows
            totals["stocks_done"] += 1
            with connect() as con:
                init_database(con)
                record_task_state(con, "sync_financial_events_batch", task_key, "success", checkpoint_value=checkpoint, row_count=sum(result.values()))
        except Exception as exc:  # noqa: BLE001 - batch must record source/API failures.
            totals["stocks_failed"] += 1
            with connect() as con:
                init_database(con)
                record_task_failure(con, "sync_financial_events_batch", task_key, str(exc))
                record_task_state(con, "sync_financial_events_batch", task_key, "failed", checkpoint_value=checkpoint, error_message=str(exc))
    return totals


def smoke_tushare() -> dict[str, int]:
    client = TushareClient()
    results: dict[str, int] = {}
    results["stock_basic_L"] = len(client.call("stock_basic", exchange="", list_status="L", fields=STOCK_BASIC_FIELDS))
    results["stock_basic_D"] = len(client.call("stock_basic", exchange="", list_status="D", fields=STOCK_BASIC_FIELDS))
    results["index_basic_CSI"] = len(client.call("index_basic", market="CSI"))
    results["concept"] = len(client.call("concept"))
    return results
