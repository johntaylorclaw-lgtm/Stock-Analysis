from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import duckdb

from build_phase3_sector_index_caches import DB_PATH, index_membership_cache_sql, q


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "phase3_index_membership_cache_run.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 3 index membership cache.")
    parser.add_argument("--start-date", help="Write-window start date, YYYY-MM-DD. Omit for full rebuild.")
    parser.add_argument("--end-date", help="Write-window end date, YYYY-MM-DD. Omit for full rebuild.")
    args = parser.parse_args()
    if bool(args.start_date) != bool(args.end_date):
        raise SystemExit("--start-date and --end-date must be provided together")

    started_at = datetime.now().isoformat(timespec="seconds")
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    table = "derived_index_membership_cache"
    con.execute("BEGIN TRANSACTION")
    try:
        if args.start_date and args.end_date:
            con.execute(f"DELETE FROM {q(table)} WHERE trade_date BETWEEN ? AND ?", [args.start_date, args.end_date])
            con.execute(index_membership_cache_sql(args.start_date, args.end_date, args.start_date))
        else:
            con.execute(f"DELETE FROM {q(table)}")
            con.execute(index_membership_cache_sql())
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    if args.start_date and args.end_date:
        rows = con.execute(
            f"SELECT count(*) FROM {q(table)} WHERE trade_date BETWEEN ? AND ?",
            [args.start_date, args.end_date],
        ).fetchone()[0]
        has_weight = con.execute(
            f"SELECT count(*) FROM {q(table)} WHERE has_index_weight AND trade_date BETWEEN ? AND ?",
            [args.start_date, args.end_date],
        ).fetchone()[0]
    else:
        rows = con.execute(f"SELECT count(*) FROM {q(table)}").fetchone()[0]
        has_weight = con.execute(f"SELECT count(*) FROM {q(table)} WHERE has_index_weight").fetchone()[0]
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "window" if args.start_date and args.end_date else "full",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "rows": int(rows),
        "has_index_weight_rows": int(has_weight),
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
