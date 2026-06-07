from __future__ import annotations

import json
from pathlib import Path

from stock_maintainance.database import connect


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
FEATURE_VIEWS = [
    "stock_features_core",
    "stock_features_plus",
    "stock_features_full",
]


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    tables = {table["name"]: table for table in schema["tables"]}
    with connect() as con:
        for view in FEATURE_VIEWS:
            if view not in tables:
                raise ValueError(f"{view} is not registered in schema_registry.json")
            registered = tables[view]
            old_fields = {field["name"]: field for field in registered.get("fields", [])}
            new_fields = []
            for _, name, dtype, nullable, *_ in con.execute(f"PRAGMA table_info({view})").fetchall():
                if name in old_fields:
                    field = {**old_fields[name], "dtype": str(dtype), "nullable": bool(nullable)}
                else:
                    field = {
                        "name": name,
                        "dtype": str(dtype),
                        "nullable": bool(nullable),
                        "description": f"{view}.{name} 统一出口字段",
                    }
                new_fields.append(field)
            registered["fields"] = new_fields
            registered["primary_key"] = ["ts_code", "trade_date"]
            registered["table_type"] = "view"
            registered["description"] = f"{view} unified feature export view"
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for view in FEATURE_VIEWS:
        print(view, len(tables[view]["fields"]))


if __name__ == "__main__":
    main()
