from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from .database import DB_PATH, connect
from .paths import REPORTS_DIR
from .schema import quote_ident


DEFAULT_COMPARE_TABLES = [
    "derived_daily_spine",
    "derived_price_technical",
    "derived_volume_liquidity",
    "derived_return_momentum",
    "derived_volatility_risk",
    "derived_trading_constraint",
    "derived_valuation_size",
    "derived_valuation_percentile_cache",
    "derived_financial_asof",
    "derived_financial_quality",
    "derived_financial_growth",
    "derived_capital_flow",
    "derived_northbound_flow_cache",
    "derived_capital_flow_event_cache",
    "derived_sector_daily_cache",
    "derived_concept_daily_cache",
    "derived_sector_concept_context",
    "derived_concept_stock_context_cache",
    "derived_index_daily_cache",
    "derived_index_membership_cache",
    "derived_index_market_context",
    "derived_cross_sectional",
    "derived_corporate_action",
    "derived_composite_state",
]

NUMERIC_TYPE_MARKERS = ("INT", "DOUBLE", "FLOAT", "DECIMAL", "REAL", "NUMERIC", "HUGEINT")


@dataclass(frozen=True)
class CompareResult:
    report: dict[str, Any]
    json_path: Path
    markdown_path: Path

    @property
    def passed(self) -> bool:
        return bool(self.report["summary"]["passed"])


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return bool(
        con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()[0]
    )


def _table_info(con: duckdb.DuckDBPyConnection, table_name: str) -> list[tuple[Any, ...]]:
    return con.execute(f"PRAGMA table_info({quote_ident(table_name)})").fetchall()


def _key_columns(columns: list[tuple[Any, ...]]) -> list[str]:
    names = [str(col[1]) for col in columns]
    if "industry_level" in names and "industry_code" in names:
        return ["industry_level", "industry_code", "trade_date"]
    if "concept_id" in names:
        return ["concept_id", "trade_date"]
    if "index_code" in names:
        return ["index_code", "trade_date"]
    return ["ts_code", "trade_date"]


def _is_numeric_type(type_name: str) -> bool:
    upper = type_name.upper()
    return any(marker in upper for marker in NUMERIC_TYPE_MARKERS)


def _numeric_diff_expr(name: str, *, abs_tol: float, rel_tol: float) -> str:
    col = quote_ident(name)
    av = f"CAST(a.{col} AS DOUBLE)"
    bv = f"CAST(b.{col} AS DOUBLE)"
    a_missing = f"(a.{col} IS NULL OR isnan({av}))"
    b_missing = f"(b.{col} IS NULL OR isnan({bv}))"
    return f"""
        CASE
            WHEN {a_missing} AND {b_missing} THEN FALSE
            WHEN {a_missing} OR {b_missing} THEN TRUE
            WHEN isinf({av}) AND isinf({bv}) AND {av} = {bv} THEN FALSE
            WHEN isinf({av}) OR isinf({bv}) THEN TRUE
            WHEN abs({av} - {bv}) > greatest({abs_tol}, {rel_tol} * greatest(abs({av}), abs({bv}), 1.0)) THEN TRUE
            ELSE FALSE
        END
    """


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# 增量窗口一致性对照报告",
        "",
        f"生成时间：{report['generated_at']}",
        f"窗口：`{report['start_date']}` 至 `{report['end_date']}`",
        f"快照前缀：`{report['snapshot_prefix']}`",
        f"结果：{'pass' if summary['passed'] else 'fail'}",
        "",
        "## 汇总",
        "",
        f"- 表数量：{summary['table_count']}",
        f"- 通过表：{summary['pass_table_count']}",
        f"- 失败表：{summary['fail_table_count']}",
        f"- 键缺失/额外行：{summary['missing_or_extra_key_rows']}",
        f"- 差异字段数：{summary['mismatch_column_count']}",
        f"- 差异单元格数：{summary['mismatch_cell_count']}",
        "",
        "## 表级结果",
        "",
        "| 表 | 当前行数 | 快照行数 | 比较字段数 | 键差异 | 差异字段数 | 差异单元格 | 结果 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["tables"]:
        mismatch_cells = sum(item.get("mismatch_columns", {}).values())
        lines.append(
            f"| `{item['table']}` | {item.get('current_rows', '')} | {item.get('snapshot_rows', '')} | "
            f"{item.get('columns_compared', '')} | {item.get('missing_or_extra_key_rows', '')} | "
            f"{len(item.get('mismatch_columns', {}))} | {mismatch_cells} | {item['status']} |"
        )
    failed = [item for item in report["tables"] if item["status"] != "pass"]
    if failed:
        lines.extend(["", "## 差异明细", ""])
        for item in failed:
            lines.append(f"### {item['table']}")
            if item.get("error"):
                lines.append(f"- 错误：{item['error']}")
            if item.get("missing_or_extra_key_rows"):
                lines.append(f"- 键缺失/额外：{item['missing_or_extra_key_rows']}")
            for name, count in item.get("mismatch_columns", {}).items():
                lines.append(f"- `{name}`：{count}")
    lines.append("")
    return "\n".join(lines)


def compare_incremental_window(
    *,
    start_date: str,
    end_date: str,
    tables: list[str] | None = None,
    snapshot_prefix: str = "audit_tmp_phase4_full_",
    output_prefix: str = "incremental_window_compare",
    abs_tol: float = 1e-6,
    rel_tol: float = 1e-12,
    db_path: Path = DB_PATH,
) -> CompareResult:
    table_names = tables or DEFAULT_COMPARE_TABLES
    output_json = REPORTS_DIR / f"{output_prefix}.json"
    output_md = REPORTS_DIR / f"{output_prefix}.md"
    table_reports: list[dict[str, Any]] = []
    with connect(db_path) as con:
        for table in table_names:
            snapshot = f"{snapshot_prefix}{table}"
            if not _table_exists(con, table):
                table_reports.append({"table": table, "snapshot_table": snapshot, "status": "fail", "error": "missing_current_table"})
                continue
            if not _table_exists(con, snapshot):
                table_reports.append({"table": table, "snapshot_table": snapshot, "status": "fail", "error": "missing_snapshot_table"})
                continue
            columns = _table_info(con, table)
            key_columns = _key_columns(columns)
            missing_keys = [col for col in key_columns if col not in [str(item[1]) for item in columns]]
            if missing_keys:
                table_reports.append(
                    {
                        "table": table,
                        "snapshot_table": snapshot,
                        "status": "fail",
                        "error": f"missing key columns: {', '.join(missing_keys)}",
                    }
                )
                continue
            current_cte = (
                f"(SELECT * FROM {quote_ident(table)} "
                f"WHERE trade_date BETWEEN DATE '{start_date}' AND DATE '{end_date}')"
            )
            join_sql = " AND ".join(f"a.{quote_ident(col)} = b.{quote_ident(col)}" for col in key_columns)
            null_side_sql = " OR ".join(
                [f"a.{quote_ident(col)} IS NULL" for col in key_columns]
                + [f"b.{quote_ident(col)} IS NULL" for col in key_columns]
            )
            current_rows = int(con.execute(f"SELECT count(*) FROM {current_cte}").fetchone()[0])
            snapshot_rows = int(con.execute(f"SELECT count(*) FROM {quote_ident(snapshot)}").fetchone()[0])
            missing_or_extra = int(
                con.execute(
                    f"""
                    SELECT count(*)
                    FROM {current_cte} a
                    FULL OUTER JOIN {quote_ident(snapshot)} b ON {join_sql}
                    WHERE {null_side_sql}
                    """
                ).fetchone()[0]
            )
            mismatch_columns: dict[str, int] = {}
            skipped_columns = set(key_columns) | {"updated_at"}
            for _, name, type_name, *_ in columns:
                name = str(name)
                if name in skipped_columns:
                    continue
                if _is_numeric_type(str(type_name)):
                    diff_expr = _numeric_diff_expr(name, abs_tol=abs_tol, rel_tol=rel_tol)
                else:
                    diff_expr = f"a.{quote_ident(name)} IS DISTINCT FROM b.{quote_ident(name)}"
                count = int(
                    con.execute(
                        f"""
                        SELECT count(*)
                        FROM {current_cte} a
                        JOIN {quote_ident(snapshot)} b ON {join_sql}
                        WHERE {diff_expr}
                        """
                    ).fetchone()[0]
                )
                if count:
                    mismatch_columns[name] = count
            table_reports.append(
                {
                    "table": table,
                    "snapshot_table": snapshot,
                    "current_rows": current_rows,
                    "snapshot_rows": snapshot_rows,
                    "missing_or_extra_key_rows": missing_or_extra,
                    "columns_compared": len([col for col in columns if str(col[1]) not in skipped_columns]),
                    "mismatch_columns": mismatch_columns,
                    "status": "pass" if missing_or_extra == 0 and not mismatch_columns else "fail",
                }
            )

    fail_tables = [item for item in table_reports if item["status"] != "pass"]
    summary = {
        "passed": not fail_tables,
        "table_count": len(table_reports),
        "pass_table_count": len(table_reports) - len(fail_tables),
        "fail_table_count": len(fail_tables),
        "missing_or_extra_key_rows": sum(int(item.get("missing_or_extra_key_rows") or 0) for item in table_reports),
        "mismatch_column_count": sum(len(item.get("mismatch_columns", {})) for item in table_reports),
        "mismatch_cell_count": sum(sum(item.get("mismatch_columns", {}).values()) for item in table_reports),
        "fail_tables": [item["table"] for item in fail_tables],
    }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date,
        "end_date": end_date,
        "snapshot_prefix": snapshot_prefix,
        "abs_tol": abs_tol,
        "rel_tol": rel_tol,
        "summary": summary,
        "tables": table_reports,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(_render_markdown(report), encoding="utf-8")
    return CompareResult(report=report, json_path=output_json, markdown_path=output_md)
