from __future__ import annotations

from typing import Any


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def field_sql(field: dict[str, Any]) -> str:
    parts = [quote_ident(field["name"]), field["dtype"]]
    if not field.get("nullable", True):
        parts.append("NOT NULL")
    if field.get("default"):
        parts.append(f"DEFAULT {field['default']}")
    return " ".join(parts)


def create_table_sql(table: dict[str, Any]) -> str:
    lines = [field_sql(field) for field in table["fields"]]
    pk = table.get("primary_key") or []
    if pk:
        cols = ", ".join(quote_ident(col) for col in pk)
        lines.append(f"PRIMARY KEY ({cols})")
    body = ",\n    ".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {quote_ident(table['name'])} (\n    {body}\n);"


def all_create_table_sql(registry: dict[str, Any]) -> str:
    return "\n\n".join(
        create_table_sql(table)
        for table in registry.get("tables", [])
        if table.get("table_type") != "view"
    )


def schema_summary(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for table in registry.get("tables", []):
        rows.append(
            {
                "table": table["name"],
                "phase": table.get("phase", ""),
                "fields": len(table.get("fields", [])),
                "primary_key": ", ".join(table.get("primary_key", [])),
                "description": table.get("description", ""),
            }
        )
    return rows
