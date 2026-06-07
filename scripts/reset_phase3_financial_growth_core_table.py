from __future__ import annotations

from stock_maintainance.database import connect, init_database
from stock_maintainance.schema import quote_ident


def main() -> None:
    with connect() as con:
        con.execute(f"DROP VIEW IF EXISTS {quote_ident('derived_financial_growth_full_v')}")
        con.execute(f"DROP TABLE IF EXISTS {quote_ident('derived_financial_growth')}")
        init_database(con)
        columns = con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'derived_financial_growth'
            """
        ).fetchall()
        print({"derived_financial_growth_columns": len(columns)})


if __name__ == "__main__":
    main()
