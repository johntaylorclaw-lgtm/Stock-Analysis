from __future__ import annotations

import json
from datetime import datetime

from stock_maintainance.database import connect


def main() -> None:
    with connect() as con:
        def one(sql: str):
            return con.execute(sql).fetchone()[0]

        stock_daily_min, stock_daily_max = con.execute(
            "SELECT min(trade_date), max(trade_date) FROM stock_daily"
        ).fetchone()
        spine_min, spine_max = con.execute(
            "SELECT min(trade_date), max(trade_date) FROM derived_daily_spine"
        ).fetchone()
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "stock_basic_info_rows": one("SELECT count(*) FROM stock_basic_info"),
            "stock_basic_distinct": one("SELECT count(distinct ts_code) FROM stock_basic_info"),
            "stock_active": one("SELECT count(*) FROM stock_basic_info WHERE list_status = 'L'"),
            "stock_delisted": one("SELECT count(*) FROM stock_basic_info WHERE list_status = 'D'"),
            "stock_daily_rows": one("SELECT count(*) FROM stock_daily"),
            "stock_daily_distinct": one("SELECT count(distinct ts_code) FROM stock_daily"),
            "stock_daily_min_date": str(stock_daily_min),
            "stock_daily_max_date": str(stock_daily_max),
            "derived_spine_rows": one("SELECT count(*) FROM derived_daily_spine"),
            "derived_spine_distinct": one("SELECT count(distinct ts_code) FROM derived_daily_spine"),
            "derived_spine_min_date": str(spine_min),
            "derived_spine_max_date": str(spine_max),
            "trade_days_to_data_max": one(
                """
                SELECT count(*)
                FROM trade_calendar
                WHERE is_open = 1
                  AND cal_date BETWEEN (SELECT min(trade_date) FROM stock_daily)
                                  AND (SELECT max(trade_date) FROM stock_daily)
                """
            ),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
