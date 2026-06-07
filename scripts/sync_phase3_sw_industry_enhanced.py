from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from stock_maintainance.database import connect, init_database, upsert_dataframe
from stock_maintainance.ingest import add_updated_at, normalize_dates, rename_columns
from stock_maintainance.tushare_source import TushareClient


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "phase3_sw_industry_enhanced_sync.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Full sync SW enhanced industry members from Tushare.")
    parser.add_argument("--confirm-full-refresh", action="store_true", help="Required to delete and refresh the full enhanced industry member table.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect L2 industry code count without calling Tushare or writing data.")
    args = parser.parse_args()

    started_at = datetime.now().isoformat(timespec="seconds")
    con = connect()
    init_database(con)
    l2_codes = [
        row[0]
        for row in con.execute(
            "SELECT industry_code FROM sw_industry_classify WHERE level = 'L2' ORDER BY industry_code"
        ).fetchall()
    ]
    if args.dry_run:
        payload = {
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "dry_run",
            "l2_codes": len(l2_codes),
            "rows": 0,
            "stocks": 0,
            "failed": [],
        }
        REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return
    if not args.confirm_full_refresh:
        raise SystemExit("Refusing full refresh without --confirm-full-refresh; use --dry-run to inspect scope.")

    client = TushareClient()
    frames: list[pd.DataFrame] = []
    failed: list[dict] = []
    for code in l2_codes:
        try:
            df = client.call("index_member_all", l2_code=code)
            if not df.empty:
                frames.append(df)
        except Exception as exc:  # noqa: BLE001
            failed.append({"l2_code": code, "error": str(exc)[:500]})
    members = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not members.empty:
        members = rename_columns(
            members,
            {
                "ts_code": "ts_code",
                "name": "stock_name",
                "l1_code": "sw_l1_code",
                "l1_name": "sw_l1_name",
                "l2_code": "sw_l2_code",
                "l2_name": "sw_l2_name",
                "l3_code": "sw_l3_code",
                "l3_name": "sw_l3_name",
            },
        )
        members = normalize_dates(members, ["in_date", "out_date"])
        members = add_updated_at(members)
        keep = [
            "ts_code", "stock_name", "sw_l1_code", "sw_l1_name", "sw_l2_code", "sw_l2_name",
            "sw_l3_code", "sw_l3_name", "in_date", "out_date", "is_new", "updated_at",
        ]
        members = members[[col for col in keep if col in members.columns]]
        con.execute("DELETE FROM derived_sw_industry_member_enhanced")
        rows = upsert_dataframe(con, "derived_sw_industry_member_enhanced", members, ["sw_l2_code", "ts_code", "in_date"])
    else:
        rows = 0
    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "l2_codes": len(l2_codes),
        "rows": rows,
        "stocks": int(members["ts_code"].nunique()) if not members.empty else 0,
        "failed": failed,
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
