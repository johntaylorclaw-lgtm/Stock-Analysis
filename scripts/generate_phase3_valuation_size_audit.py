from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
REPORT_PATH = ROOT / "reports" / "phase3_valuation_size_audit.md"

OBJECTS = [
    "derived_valuation_size",
    "derived_valuation_percentile_cache",
    "derived_valuation_size_full_v",
]

KEY_FIELDS = {
    "derived_valuation_size": [
        "pe_ttm",
        "pb",
        "ps_ttm",
        "total_mv",
        "free_float_mv",
        "pe_ttm_pct_5y",
        "pb_pct_5y",
        "ps_ttm_pct_5y",
        "total_mv_pct_5y",
    ],
    "derived_valuation_percentile_cache": [
        "pe_ttm_pct_10y",
        "pb_pct_10y",
        "ps_ttm_pct_10y",
        "total_mv_pct_10y",
        "free_float_mv_pct_10y",
    ],
}


def columns(con: duckdb.DuckDBPyConnection, name: str) -> list[str]:
    return [
        row[1]
        for row in con.execute(f"PRAGMA table_info('{name}')").fetchall()
    ]


def schema_count(schema: dict, name: str) -> int | None:
    for table in schema.get("tables", []):
        if table.get("name") == name:
            return len(table.get("fields", []))
    return None


def table_summary(con: duckdb.DuckDBPyConnection, table: str) -> tuple:
    return con.execute(
        f"""
        SELECT count(*), count(DISTINCT ts_code), min(trade_date), max(trade_date)
        FROM {table}
        """
    ).fetchone()


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    con = duckdb.connect(str(DB_PATH))
    lines = [
        "# Phase 3 估值与规模模块审计报告",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 数据库：`{DB_PATH}`",
        "- 说明：历史分位字段采用物理缓存表 `derived_valuation_percentile_cache`，完整视图通过 join 读取，避免视图查询时重复构造 10 年滚动窗口。",
        "",
        "## 1. 字段注册与实际对象核对",
        "",
        "| 对象 | 注册字段数 | 实际字段数 | 状态 |",
        "|---|---:|---:|---|",
    ]
    for name in OBJECTS:
        registered = schema_count(schema, name)
        actual = len(columns(con, name))
        lines.append(f"| `{name}` | {registered} | {actual} | {'OK' if registered == actual else 'MISMATCH'} |")
    lines.extend(["", "## 2. 覆盖率", "", "| 表 | 行数 | 股票数 | 最早日期 | 最新日期 |", "|---|---:|---:|---|---|"])
    for name in ["derived_valuation_size", "derived_valuation_percentile_cache"]:
        row = table_summary(con, name)
        lines.append(f"| `{name}` | {row[0]:,} | {row[1]:,} | {row[2]} | {row[3]} |")

    lines.extend(["", "## 3. 关键字段非空率", "", "| 表 | 字段 | 非空行数 | 总行数 | 非空率 |", "|---|---|---:|---:|---:|"])
    for table, fields in KEY_FIELDS.items():
        total = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for field in fields:
            non_null = con.execute(f"SELECT count({field}) FROM {table}").fetchone()[0]
            lines.append(f"| `{table}` | `{field}` | {non_null:,} | {total:,} | {non_null / total:.4%} |")

    recent = con.execute(
        """
        SELECT
            count(*),
            count(DISTINCT ts_code),
            min(trade_date),
            max(trade_date),
            count(pe_ttm_pct_10y),
            count(amount_to_total_mv),
            count(peg_ttm)
        FROM derived_valuation_size_full_v
        WHERE trade_date BETWEEN DATE '2026-05-20' AND DATE '2026-05-26'
        """
    ).fetchone()
    lines.extend(
        [
            "",
            "## 4. 完整视图近端可查询核对",
            "",
            "| 项目 | 数值 |",
            "|---|---:|",
            f"| 行数 | {recent[0]:,} |",
            f"| 股票数 | {recent[1]:,} |",
            f"| 日期范围 | {recent[2]} ~ {recent[3]} |",
            f"| `pe_ttm_pct_10y` 非空 | {recent[4]:,} |",
            f"| `amount_to_total_mv` 非空 | {recent[5]:,} |",
            f"| `peg_ttm` 非空 | {recent[6]:,} |",
            "",
            "## 5. 单位校准结论",
            "",
            "- `free_float_mv = close_raw * free_share`，与 Tushare `total_mv/circ_mv` 的万元口径一致。",
            "- `stock_daily.amount` 为千元口径，`total_mv/circ_mv` 为万元口径，因此 `amount_to_total_mv = amount / 10 / total_mv`。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
