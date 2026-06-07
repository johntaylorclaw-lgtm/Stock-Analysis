from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from stock_maintainance.features.build import build_features


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "phase3_trading_technical_core_run.jsonl"


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    modules = ["price_technical", "volume_liquidity", "volatility_risk", "trading_constraint"]
    with REPORT_PATH.open("w", encoding="utf-8") as handle:
        for year in range(2006, 2027):
            start_date = f"{year}-01-01"
            end_date = "2026-05-26" if year == 2026 else f"{year}-12-31"
            started_at = datetime.now().isoformat(timespec="seconds")
            result = build_features(
                modules=modules,
                start_date=start_date,
                end_date=end_date,
                mode="history",
                allow_confirmed_history=True,
            )
            payload = {
                "year": year,
                "start_date": start_date,
                "end_date": end_date,
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "results": result["results"],
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
