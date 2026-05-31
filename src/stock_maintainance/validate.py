from __future__ import annotations

from collections import Counter


REQUIRED_VARIABLE_KEYS = {
    "name",
    "label_zh",
    "table",
    "module",
    "category",
    "tier",
    "dtype",
    "unit",
    "frequency",
    "grain",
    "source_type",
    "price_basis",
    "point_in_time",
    "missing_policy",
    "validation",
}


def validate_schema_registry(registry: dict) -> list[str]:
    errors: list[str] = []
    names = [table.get("name") for table in registry.get("tables", [])]
    for name, count in Counter(names).items():
        if count > 1:
            errors.append(f"duplicate table: {name}")
    for table in registry.get("tables", []):
        if not table.get("name"):
            errors.append("table missing name")
        fields = table.get("fields", [])
        field_names = [field.get("name") for field in fields]
        for name, count in Counter(field_names).items():
            if count > 1:
                errors.append(f"{table.get('name')}: duplicate field {name}")
        for pk in table.get("primary_key", []):
            if pk not in field_names:
                errors.append(f"{table.get('name')}: primary key {pk} is not a field")
        for field in fields:
            for key in ["name", "dtype", "description"]:
                if key not in field:
                    errors.append(f"{table.get('name')}: field missing {key}")
    return errors


def validate_variable_registry(registry: dict) -> list[str]:
    errors: list[str] = []
    variables = registry.get("variables", [])
    names = [item.get("name") for item in variables]
    for name, count in Counter(names).items():
        if count > 1:
            errors.append(f"duplicate variable: {name}")
    for item in variables:
        missing = sorted(REQUIRED_VARIABLE_KEYS - set(item))
        if missing:
            errors.append(f"{item.get('name', '<unnamed>')}: missing keys {', '.join(missing)}")
        if not isinstance(item.get("grain", []), list):
            errors.append(f"{item.get('name')}: grain must be a list")
    return errors


def validate_variable_schema_alignment(variable_registry: dict, schema_registry: dict) -> list[str]:
    errors: list[str] = []
    table_fields = {
        table.get("name"): {field.get("name") for field in table.get("fields", [])}
        for table in schema_registry.get("tables", [])
    }
    for item in variable_registry.get("variables", []):
        table = item.get("table")
        name = item.get("name")
        if not table or not name:
            continue
        if not str(table).startswith("derived_"):
            continue
        if table not in table_fields:
            errors.append(f"{name}: target table {table} is not registered in schema")
            continue
        if name not in table_fields[table]:
            errors.append(f"{name}: missing field in schema table {table}")
    return errors
