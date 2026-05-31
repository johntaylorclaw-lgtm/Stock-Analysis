from __future__ import annotations

import argparse
import json
from pathlib import Path

from stock_maintainance.database import connect


ROOT = Path(__file__).resolve().parents[1]


def clean_value(value):
    try:
        if value != value:
            return None
    except TypeError:
        pass
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ts-code", default="000001.SZ")
    args = parser.parse_args()

    out = ROOT / "outputs" / "phase3"
    out.mkdir(parents=True, exist_ok=True)

    con = connect()
    try:
        stock = con.execute(
            "SELECT ts_code, name, market, exchange, list_status FROM stock_basic_info WHERE ts_code = ?",
            [args.ts_code],
        ).fetchdf()
        if stock.empty:
            raise ValueError(f"no stock found: {args.ts_code}")
        df = con.execute(
            "SELECT * FROM stock_features_full WHERE ts_code = ? ORDER BY trade_date",
            [args.ts_code],
        ).fetchdf()
        if df.empty:
            raise ValueError(f"no feature rows found: {args.ts_code}")
    finally:
        con.close()

    coverage = []
    for column in df.columns:
        non_null = int(df[column].notna().sum())
        coverage.append(
            {
                "column": column,
                "non_null": non_null,
                "rows": int(len(df)),
                "non_null_rate": non_null / len(df),
            }
        )

    for column in df.columns:
        if str(df[column].dtype).startswith("datetime"):
            df[column] = df[column].dt.strftime("%Y-%m-%d")

    rows = []
    for record in df.to_dict(orient="records"):
        rows.append({key: clean_value(value) for key, value in record.items()})

    payload = {
        "stock": stock.iloc[0].where(stock.iloc[0].notna(), None).to_dict(),
        "summary": {
            "min_trade_date": str(df["trade_date"].min()),
            "max_trade_date": str(df["trade_date"].max()),
        },
        "columns": list(df.columns),
        "coverage": coverage,
        "rows": rows,
    }
    output_path = out / f"sample_derived_variables_{args.ts_code.replace('.', '_')}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(output_path)
    print(f"rows={len(df)} columns={len(df.columns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
