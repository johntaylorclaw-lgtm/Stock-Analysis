from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
WINDOW = 1250


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    df = con.execute(
        """
        SELECT
            ts_code,
            trade_date,
            pe_ttm,
            pb,
            ps_ttm,
            total_mv
        FROM derived_valuation_size
        ORDER BY ts_code, trade_date
        """
    ).fetchdf()
    print({"stage": "loaded", "rows": len(df)})
    metrics = {
        "pe_ttm": "pe_ttm_pct_5y",
        "pb": "pb_pct_5y",
        "ps_ttm": "ps_ttm_pct_5y",
        "total_mv": "total_mv_pct_5y",
    }
    for source, target in metrics.items():
        df[target] = (
            df.groupby("ts_code", sort=False)[source]
            .transform(lambda s: s.rolling(WINDOW, min_periods=1).rank(pct=True))
        )
        print({"stage": "computed", "field": target})
    update_df = df[["ts_code", "trade_date", *metrics.values()]]
    con.register("valuation_pct_update_df", update_df)
    con.execute(
        """
        UPDATE derived_valuation_size AS v
        SET
            pe_ttm_pct_5y = u.pe_ttm_pct_5y,
            pb_pct_5y = u.pb_pct_5y,
            ps_ttm_pct_5y = u.ps_ttm_pct_5y,
            total_mv_pct_5y = u.total_mv_pct_5y
        FROM valuation_pct_update_df AS u
        WHERE v.ts_code = u.ts_code
          AND v.trade_date = u.trade_date
        """
    )
    summary = con.execute(
        """
        SELECT
            count(*) AS rows,
            count(pe_ttm_pct_5y) AS pe_ttm_pct_5y_non_null,
            count(pb_pct_5y) AS pb_pct_5y_non_null,
            count(ps_ttm_pct_5y) AS ps_ttm_pct_5y_non_null,
            count(total_mv_pct_5y) AS total_mv_pct_5y_non_null
        FROM derived_valuation_size
        """
    ).fetchone()
    print(
        {
            "stage": "updated",
            "rows": summary[0],
            "pe_ttm_pct_5y_non_null": summary[1],
            "pb_pct_5y_non_null": summary[2],
            "ps_ttm_pct_5y_non_null": summary[3],
            "total_mv_pct_5y_non_null": summary[4],
        }
    )


if __name__ == "__main__":
    main()
