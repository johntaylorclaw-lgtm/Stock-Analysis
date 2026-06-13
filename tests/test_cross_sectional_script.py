from __future__ import annotations

import json
from pathlib import Path


def test_cross_sectional_standalone_year_batches_are_transactional() -> None:
    source = (Path("scripts") / "build_phase3_cross_sectional_core.py").read_text(encoding="utf-8")

    assert 'con.execute("BEGIN TRANSACTION")' in source
    assert 'con.execute("COMMIT")' in source
    assert 'con.execute("ROLLBACK")' in source


def test_cross_sectional_full_view_dictionary_documents_actual_transform() -> None:
    registry = json.loads((Path("config") / "schema_registry.json").read_text(encoding="utf-8"))
    table = next(item for item in registry["tables"] if item["name"] == "derived_cross_sectional_full_v")
    fields = {field["name"]: field["description"] for field in table["fields"]}

    assert "完整视图扩展截面字段" not in "\n".join(fields.values())
    assert "基于核心表 ret_20_hfq_z_all" in fields["ret_20_hfq_z_market"]
    assert "winsor(source,1%,99%)" in fields["ret_5_hfq_z_all"]
    assert "样本数 < 5 时返回NULL" in fields["ret_5_hfq_rank_all_desc"]
    assert "样本数 < 20 或标准差为0时返回NULL" in fields["ret_5_hfq_z_all"]
