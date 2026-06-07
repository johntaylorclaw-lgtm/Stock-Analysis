from __future__ import annotations

import json
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def field_sql(field: dict) -> str:
    parts = [q(field["name"]), field["dtype"]]
    if not field.get("nullable", True):
        parts.append("NOT NULL")
    if field.get("default"):
        parts.append(f"DEFAULT {field['default']}")
    return " ".join(parts)


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    table = next(item for item in schema["tables"] if item["name"] == "derived_cross_sectional")
    fields = ",\n    ".join(field_sql(field) for field in table["fields"])
    pk = ", ".join(q(col) for col in table["primary_key"])
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    con.execute("DROP TABLE IF EXISTS derived_cross_sectional")
    con.execute(f"CREATE TABLE derived_cross_sectional (\n    {fields},\n    PRIMARY KEY ({pk})\n)")
    print({"derived_cross_sectional": len(table["fields"])})


if __name__ == "__main__":
    main()
