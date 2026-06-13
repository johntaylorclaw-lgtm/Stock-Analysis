from __future__ import annotations

import ast
from pathlib import Path

import pytest

from stock_maintainance import views


def test_views_module_parses_with_python_311_grammar():
    source = (Path(__file__).resolve().parents[1] / "src" / "stock_maintainance" / "views.py").read_text(encoding="utf-8")

    ast.parse(source, filename="views.py", feature_version=(3, 11))


def test_create_views_collects_errors_and_continues(monkeypatch):
    calls: list[str] = []

    class _Conn:
        def execute(self, sql):
            calls.append(sql)
            if "bad_view" in sql:
                raise RuntimeError("bad sql")

    monkeypatch.setattr(views, "VIEW_SQL", ["CREATE VIEW good_view AS SELECT 1", "CREATE VIEW bad_view AS SELECT"])
    monkeypatch.setattr(views, "_create_stock_features_core", lambda con: calls.append("core"))
    monkeypatch.setattr(views, "_create_stock_features_plus", lambda con: calls.append("plus"))
    monkeypatch.setattr(views, "_create_stock_features_full", lambda con: calls.append("full"))

    with pytest.raises(RuntimeError, match="completed with 1 error"):
        views.create_views(_Conn())

    assert calls == ["CREATE VIEW good_view AS SELECT 1", "CREATE VIEW bad_view AS SELECT", "core", "plus", "full"]


def test_feature_view_score_filter_keeps_zscore_columns(monkeypatch):
    class _Conn:
        def execute(self, sql):
            assert "PRAGMA table_info" in sql

            class _Rows:
                def fetchall(self):
                    return [
                        (0, "ts_code"),
                        (1, "trade_date"),
                        (2, "alpha_score"),
                        (3, "north_money_zscore_20"),
                        (4, "plain_value"),
                    ]

            return _Rows()

    monkeypatch.setitem(views.FEATURE_MODULES, "m", ("module_table", "m"))

    selected = {"ts_code", "trade_date"}
    exprs = views._module_select_exprs(_Conn(), module_alias="m", selected=selected)

    assert all("alpha_score" not in expr for expr in exprs)
    assert any("north_money_zscore_20" in expr for expr in exprs)
    assert any("plain_value" in expr for expr in exprs)
