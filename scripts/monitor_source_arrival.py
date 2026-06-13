#!/usr/bin/env python3
"""Monitor Tushare source data arrival times for daily-light pipeline.

Usage:
    .venv-wsl/bin/python scripts/monitor_source_arrival.py <time_slot>
    time_slot: 16|17|18|19

Checks 9 T+0 Tushare APIs at the given hour, comparing today's row count
against the previous trading day's count. Data is considered "arrived" when
today's row count is >= 80% of the previous day's baseline.

Output: JSON log per timeslot → logs/source_arrival/<date>_<hour>.json
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path("/mnt/d/Opencode Workspace/Stock_Maintainance")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stock_maintainance.database import connect
from stock_maintainance.tushare_source import TushareClient

# ── 9 T+0 APIs ──────────────────────────────────────────────────────
T0_APIS: list[tuple[str, str]] = [
    ("daily",           "stock_daily"),
    ("daily_basic",     "stock_daily_basic"),
    ("stk_limit",       "stock_limit_price"),
    ("adj_factor",      "stock_adj_factor"),
    ("moneyflow",       "stock_moneyflow_daily"),
    ("moneyflow_hsgt",  "northbound_daily"),
    ("top_list",        "top_list_daily"),
    ("top_inst",        "top_inst_detail"),
    ("index_daily",     "index_daily"),
]

# index_daily requires ts_code; use 上证综指 as representative
INDEX_PROXY = "000001.SH"

LOG_DIR = PROJECT_ROOT / "logs" / "source_arrival"
ARRIVAL_THRESHOLD = 0.80   # today >= 80% of prev → available
MIN_ABSOLUTE_ROWS  = 100   # minimum row count when no baseline exists

# ── helpers ─────────────────────────────────────────────────────────

def _compact(d: str) -> str:
    """2026-06-09 → 20260609"""
    return d.replace("-", "")


def get_trade_dates(today_iso: str) -> tuple[str | None, str | None]:
    """Return (today_trade_date, prev_trade_date) in ISO format, or (None, None)."""
    with connect() as con:
        r = con.execute(
            """SELECT cal_date FROM trade_calendar
               WHERE exchange = 'SSE' AND is_open = true AND cal_date <= ?::DATE
               ORDER BY cal_date DESC LIMIT 1""",
            [today_iso],
        ).fetchone()
        if not r:
            return None, None
        latest = r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0])

        r = con.execute(
            """SELECT cal_date FROM trade_calendar
               WHERE exchange = 'SSE' AND is_open = true AND cal_date < ?::DATE
               ORDER BY cal_date DESC LIMIT 1""",
            [latest],
        ).fetchone()
        prev = r[0].isoformat() if r and hasattr(r[0], "isoformat") else None
        if prev is None and r:
            prev = str(r[0])
        return latest, prev


def probe_api(
    client: TushareClient,
    api_name: str,
    trade_date_compact: str,
    prev_date_compact: str | None,
) -> dict:
    """Call one API for today and previous day; return availability verdict."""
    result: dict = {
        "api": api_name,
        "today_count": 0,
        "prev_count": None,
        "ratio": None,
        "available": False,
        "error": None,
    }

    # ── today ──
    try:
        if api_name == "index_daily":
            df = client.call(api_name, ts_code=INDEX_PROXY,
                             start_date=trade_date_compact, end_date=trade_date_compact)
        else:
            df = client.call(api_name, trade_date=trade_date_compact)
        result["today_count"] = int(len(df))
    except Exception as exc:
        result["error"] = str(exc)[:300]
        return result

    # ── previous baseline ──
    prev_count: int | None = None
    if prev_date_compact:
        try:
            if api_name == "index_daily":
                df_prev = client.call(api_name, ts_code=INDEX_PROXY,
                                      start_date=prev_date_compact, end_date=prev_date_compact)
            else:
                df_prev = client.call(api_name, trade_date=prev_date_compact)
            prev_count = int(len(df_prev))
            result["prev_count"] = prev_count
        except Exception:
            pass

    # ── verdict ──
    today_cnt = result["today_count"]
    if today_cnt == 0:
        return result

    if prev_count and prev_count > 0:
        ratio = today_cnt / prev_count
        result["ratio"] = round(ratio, 4)
        result["available"] = ratio >= ARRIVAL_THRESHOLD
    else:
        # no baseline — fall back to absolute minimum
        result["ratio"] = None
        result["available"] = today_cnt >= MIN_ABSOLUTE_ROWS

    return result


# ── main ────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: monitor_source_arrival.py <time_slot>", file=sys.stderr)
        sys.exit(1)

    time_slot = sys.argv[1]
    today_iso = date.today().isoformat()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    trade_date, prev_trade_date = get_trade_dates(today_iso)

    if trade_date is None:
        print(f"[SKIP] No trade date found for {today_iso}")
        return

    if trade_date != today_iso:
        print(f"[SKIP] {today_iso} is not a trading day (latest: {trade_date})")
        return

    print(f"[MONITOR] {trade_date} @ {time_slot}:00 — probing 9 T+0 APIs …")

    client = TushareClient()
    today_compact = _compact(trade_date)
    prev_compact = _compact(prev_trade_date) if prev_trade_date else None

    results = []
    for api_name, table_name in T0_APIS:
        r = probe_api(client, api_name, today_compact, prev_compact)
        r["table"] = table_name
        results.append(r)

        icon = "✓" if r["available"] else "✗"
        ratio_str = f"{r['ratio']}" if r["ratio"] is not None else "—"
        prev_str = str(r["prev_count"]) if r["prev_count"] is not None else "—"
        err = f" ERR:{r['error'][:60]}" if r["error"] else ""
        print(f"  {icon} {api_name:16s} today={r['today_count']:6d}  prev={prev_str:>6s}  "
              f"ratio={ratio_str:>8s}{err}")

    available_count = sum(1 for r in results if r["available"])
    all_ok = all(r["available"] for r in results)

    log = {
        "date": today_iso,
        "trade_date": trade_date,
        "prev_trade_date": prev_trade_date,
        "time_slot": time_slot,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "threshold": ARRIVAL_THRESHOLD,
        "results": results,
        "summary": {
            "total": len(results),
            "available": available_count,
            "all_available": all_ok,
        },
    }

    log_path = LOG_DIR / f"{today_iso}_{time_slot}.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] {available_count}/9 available | all_ok={all_ok} | log → {log_path}")


if __name__ == "__main__":
    main()
