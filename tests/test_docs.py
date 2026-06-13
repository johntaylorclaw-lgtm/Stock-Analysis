from stock_maintainance.docs import GENERATED_DOCS_DIR, check_docs
from stock_maintainance.config import CONFIG_DIR, load_json, load_variable_registry


def test_docs_check_uses_current_main_docs_and_excel_dictionary() -> None:
    assert check_docs() == []


def test_generated_markdown_dictionary_is_not_required_in_docs_root() -> None:
    assert not (GENERATED_DOCS_DIR.parent / "generated_schema_dictionary.md").exists()


def test_financial_variable_labels_do_not_contain_question_mark_garbled_text() -> None:
    registry = load_variable_registry()
    offenders = [
        item["name"]
        for item in registry["variables"]
        if item.get("table") in {"derived_financial_asof", "derived_financial_quality"}
        and set(str(item.get("label_zh", ""))) <= {"?"}
        and "?" in str(item.get("label_zh", ""))
    ]

    assert offenders == []


def test_latest_adj_factor_anchor_is_not_marked_point_in_time_safe() -> None:
    registry = load_variable_registry()
    variable = next(
        item
        for item in registry["variables"]
        if item.get("table") == "derived_daily_spine" and item.get("name") == "latest_adj_factor_asof"
    )

    assert variable["point_in_time"] is False
    assert variable["price_basis"] == "qfq_current_anchor"


def test_base_variable_registry_has_chinese_labels_and_is_not_draft() -> None:
    registry = load_json(CONFIG_DIR / "variables" / "base_variables.json")
    assert "Draft generated" not in registry.get("note", "")

    offenders = [
        item["name"]
        for item in registry["variables"]
        if not any("\u4e00" <= ch <= "\u9fff" for ch in str(item.get("label_zh", "")))
    ]
    fallback_labels = [
        item["name"]
        for item in registry["variables"]
        if "字段：" in str(item.get("label_zh", ""))
    ]

    assert offenders == []
    assert fallback_labels == []
