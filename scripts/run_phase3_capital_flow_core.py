from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from stock_maintainance.database import connect, init_database
from stock_maintainance.features.context import FeatureBuildContext
from stock_maintainance.features.modules import build_capital_flow


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "phase3_capital_flow_core_run.jsonl"


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = connect()
    init_database(con)
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    start = date(2006, 1, 1)
    end = date(2026, 5, 26)
    read_start = start - timedelta(days=420)
    ctx = FeatureBuildContext(
        con=con,
        module="capital_flow",
        read_start_date=read_start.isoformat(),
        write_start_date=start.isoformat(),
        write_end_date=end.isoformat(),
        dry_run=False,
    )
    started_at = datetime.now().isoformat(timespec="seconds")
    result = build_capital_flow(ctx)
    payload = {
        "mode": "full_once",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "read_start_date": read_start.isoformat(),
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "result": result.__dict__,
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
