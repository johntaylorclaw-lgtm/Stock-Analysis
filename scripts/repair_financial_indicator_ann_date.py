from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "financial_indicator_ann_date_repair_20260611.json"


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(DB_PATH) as con:
        before = con.execute(
            """
            SELECT count(*)
            FROM financial_indicator_raw
            WHERE ann_date = end_date
            """
        ).fetchone()[0]
        candidates = con.execute(
            """
            WITH bad AS (
                SELECT ts_code, end_date
                FROM financial_indicator_raw
                WHERE ann_date = end_date
            ),
            peer_ann AS (
                SELECT ts_code, end_date, ann_date, first_ann_date FROM financial_income_raw
                UNION ALL
                SELECT ts_code, end_date, ann_date, first_ann_date FROM financial_balance_raw
                UNION ALL
                SELECT ts_code, end_date, ann_date, first_ann_date FROM financial_cashflow_raw
            ),
            recovered AS (
                SELECT
                    b.ts_code,
                    b.end_date,
                    min(coalesce(p.ann_date, p.first_ann_date)) AS recovered_ann_date
                FROM bad b
                LEFT JOIN peer_ann p
                  ON b.ts_code = p.ts_code
                 AND b.end_date = p.end_date
                GROUP BY b.ts_code, b.end_date
            )
            SELECT ts_code, end_date, recovered_ann_date
            FROM recovered
            ORDER BY ts_code, end_date
            """
        ).fetchall()
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(
                """
                WITH bad AS (
                    SELECT ts_code, end_date
                    FROM financial_indicator_raw
                    WHERE ann_date = end_date
                ),
                peer_ann AS (
                    SELECT ts_code, end_date, ann_date, first_ann_date FROM financial_income_raw
                    UNION ALL
                    SELECT ts_code, end_date, ann_date, first_ann_date FROM financial_balance_raw
                    UNION ALL
                    SELECT ts_code, end_date, ann_date, first_ann_date FROM financial_cashflow_raw
                ),
                recovered AS (
                    SELECT
                        b.ts_code,
                        b.end_date,
                        min(coalesce(p.ann_date, p.first_ann_date)) AS recovered_ann_date
                    FROM bad b
                    LEFT JOIN peer_ann p
                      ON b.ts_code = p.ts_code
                     AND b.end_date = p.end_date
                    GROUP BY b.ts_code, b.end_date
                )
                DELETE FROM financial_indicator_raw t
                USING recovered r
                WHERE t.ts_code = r.ts_code
                  AND t.end_date = r.end_date
                  AND t.ann_date = t.end_date
                  AND r.recovered_ann_date IS NOT NULL
                  AND EXISTS (
                      SELECT 1
                      FROM financial_indicator_raw existing
                      WHERE existing.ts_code = t.ts_code
                        AND existing.end_date = t.end_date
                        AND existing.ann_date = r.recovered_ann_date
                  )
                """
            )
            con.execute(
                """
                WITH bad AS (
                    SELECT ts_code, end_date
                    FROM financial_indicator_raw
                    WHERE ann_date = end_date
                ),
                peer_ann AS (
                    SELECT ts_code, end_date, ann_date, first_ann_date FROM financial_income_raw
                    UNION ALL
                    SELECT ts_code, end_date, ann_date, first_ann_date FROM financial_balance_raw
                    UNION ALL
                    SELECT ts_code, end_date, ann_date, first_ann_date FROM financial_cashflow_raw
                ),
                recovered AS (
                    SELECT
                        b.ts_code,
                        b.end_date,
                        min(coalesce(p.ann_date, p.first_ann_date)) AS recovered_ann_date
                    FROM bad b
                    LEFT JOIN peer_ann p
                      ON b.ts_code = p.ts_code
                     AND b.end_date = p.end_date
                    GROUP BY b.ts_code, b.end_date
                )
                UPDATE financial_indicator_raw t
                SET ann_date = coalesce(r.recovered_ann_date, t.end_date + INTERVAL 120 DAY),
                    effective_date = coalesce(r.recovered_ann_date, t.end_date + INTERVAL 120 DAY),
                    updated_at = current_timestamp
                FROM recovered r
                WHERE t.ts_code = r.ts_code
                  AND t.end_date = r.end_date
                  AND t.ann_date = t.end_date
                """
            )
        except Exception:
            con.execute("ROLLBACK")
            raise
        else:
            con.execute("COMMIT")
        after = con.execute(
            """
            SELECT count(*)
            FROM financial_indicator_raw
            WHERE ann_date = end_date
            """
        ).fetchone()[0]
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "before_ann_date_eq_end_date": before,
        "after_ann_date_eq_end_date": after,
        "candidate_count": len(candidates),
        "candidates": [
            {
                "ts_code": row[0],
                "end_date": row[1].isoformat() if row[1] else None,
                "recovered_ann_date": row[2].isoformat() if row[2] else None,
                "fallback_used": row[2] is None,
            }
            for row in candidates
        ],
        "fallback_policy": "end_date + 120 days only when peer statement announcement date is unavailable",
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
