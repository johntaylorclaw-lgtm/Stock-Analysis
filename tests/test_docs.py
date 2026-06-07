from stock_maintainance.docs import GENERATED_DOCS_DIR, check_docs


def test_docs_check_uses_current_main_docs_and_excel_dictionary() -> None:
    assert check_docs() == []


def test_generated_markdown_dictionary_is_not_required_in_docs_root() -> None:
    assert not (GENERATED_DOCS_DIR.parent / "generated_schema_dictionary.md").exists()
