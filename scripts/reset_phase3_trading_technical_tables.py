from __future__ import annotations

from stock_maintainance.database import connect, init_database
from stock_maintainance.schema import quote_ident
import duckdb


OBJECTS = [
    "derived_daily_spine_full_v",
    "derived_price_technical_full_v",
    "derived_return_momentum_full_v",
    "derived_volatility_risk_full_v",
    "derived_volume_liquidity_full_v",
    "derived_trading_constraint_full_v",
    "derived_trading_constraint",
    "derived_volume_liquidity",
    "derived_volatility_risk",
    "derived_return_momentum",
    "derived_price_technical",
    "derived_daily_spine",
]


def main() -> None:
    with connect() as con:
        for name in OBJECTS:
            try:
                con.execute(f"DROP VIEW IF EXISTS {quote_ident(name)}")
            except duckdb.CatalogException:
                pass
        for name in OBJECTS:
            try:
                con.execute(f"DROP TABLE IF EXISTS {quote_ident(name)}")
            except duckdb.CatalogException:
                pass
        init_database(con)
        for name in OBJECTS:
            if name.endswith("_full_v"):
                continue
            columns = con.execute(
                """
                SELECT count(1)
                FROM information_schema.columns
                WHERE table_name = ?
                """,
                [name],
            ).fetchone()[0]
            print({"table": name, "columns": columns})


if __name__ == "__main__":
    main()
