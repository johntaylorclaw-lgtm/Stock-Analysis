from stock_maintainance.schema import field_sql
from stock_maintainance.validate import validate_variable_registry, validate_variable_schema_alignment


def test_field_sql_renders_nullable_migration_column() -> None:
    field = {"name": "sw_code", "dtype": "VARCHAR", "nullable": True}

    assert field_sql(field) == '"sw_code" VARCHAR'


def test_field_sql_renders_default_for_not_null_column() -> None:
    field = {"name": "updated_at", "dtype": "TIMESTAMP", "nullable": False, "default": "CURRENT_TIMESTAMP"}

    assert field_sql(field) == '"updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'


def test_variable_schema_alignment_reports_missing_field() -> None:
    variables = {
        "variables": [
            {
                "name": "missing_feature",
                "table": "derived_daily_spine",
            }
        ]
    }
    schema = {
        "tables": [
            {
                "name": "derived_daily_spine",
                "fields": [{"name": "ts_code"}],
            }
        ]
    }

    assert validate_variable_schema_alignment(variables, schema) == [
        "missing_feature: missing field in schema table derived_daily_spine"
    ]


def test_variable_registry_allows_same_name_across_tables() -> None:
    base = {
        "label_zh": "测试字段",
        "module": "test",
        "category": "test",
        "tier": "core",
        "dtype": "DOUBLE",
        "unit": "",
        "frequency": "daily",
        "grain": ["ts_code", "trade_date"],
        "source_type": "derived",
        "price_basis": "none",
        "point_in_time": True,
        "missing_policy": "nullable",
        "validation": {},
    }
    registry = {
        "variables": [
            {"name": "event_date", "table": "derived_corporate_action", **base},
            {"name": "event_date", "table": "derived_ownership_governance", **base},
        ]
    }

    assert validate_variable_registry(registry) == []


def test_variable_registry_rejects_duplicate_name_within_table() -> None:
    base = {
        "label_zh": "测试字段",
        "table": "derived_corporate_action",
        "module": "test",
        "category": "test",
        "tier": "core",
        "dtype": "DOUBLE",
        "unit": "",
        "frequency": "daily",
        "grain": ["ts_code", "trade_date"],
        "source_type": "derived",
        "price_basis": "none",
        "point_in_time": True,
        "missing_policy": "nullable",
        "validation": {},
    }
    registry = {"variables": [{"name": "event_date", **base}, {"name": "event_date", **base}]}

    assert validate_variable_registry(registry) == ["duplicate variable in derived_corporate_action: event_date"]
