from __future__ import annotations

import json
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
TABLE_NAME = "derived_ownership_governance"


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    table = next(item for item in schema["tables"] if item["name"] == TABLE_NAME)
    columns = []
    for field in table["fields"]:
        col = f"{q(field['name'])} {field['dtype']}"
        if not field.get("nullable", True):
            col += " NOT NULL"
        columns.append(col)
    pk = ", ".join(q(name) for name in table["primary_key"])
    ddl = f"CREATE TABLE {q(TABLE_NAME)} ({', '.join(columns)}, PRIMARY KEY ({pk}))"
    with duckdb.connect(DB_PATH) as con:
        con.execute(f"DROP TABLE IF EXISTS {q(TABLE_NAME)}")
        con.execute(ddl)
        cols = con.execute(f"SELECT count(*) FROM pragma_table_info('{TABLE_NAME}')").fetchone()[0]
        print({TABLE_NAME: cols})


if __name__ == "__main__":
    main()
