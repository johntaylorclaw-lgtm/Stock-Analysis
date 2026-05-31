from stock_maintainance.schema import field_sql
from stock_maintainance.validate import validate_variable_schema_alignment


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
