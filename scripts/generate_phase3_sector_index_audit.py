from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("STOCK_DB_PATH", ROOT / "data" / "duckdb" / "stock_data.duckdb"))
REPORT_PATH = ROOT / "reports" / "phase3_sector_index_context_audit.md"

OBJECTS = [
    "derived_sw_industry_member_enhanced",
    "derived_sector_daily_cache",
    "derived_concept_daily_cache",
    "derived_concept_stock_context_cache",
    "derived_sector_concept_context",
    "derived_sector_concept_context_full_v",
    "derived_index_daily_cache",
    "derived_index_membership_cache",
    "derived_index_market_context",
    "derived_index_market_context_full_v",
]


def summary(con: duckdb.DuckDBPyConnection, name: str) -> dict:
    cols = len(con.execute(f"PRAGMA table_info('{name}')").fetchall())
    if name == "derived_sw_industry_member_enhanced":
        row = con.execute(
            f"SELECT count(*), count(distinct ts_code), min(in_date), max(coalesce(out_date,in_date)) FROM {name}"
        ).fetchone()
    elif "sector_daily" in name:
        row = con.execute(
            f"SELECT count(*), count(distinct industry_code), min(trade_date), max(trade_date) FROM {name}"
        ).fetchone()
    elif "concept_daily" in name:
        row = con.execute(
            f"SELECT count(*), count(distinct concept_id), min(trade_date), max(trade_date) FROM {name}"
        ).fetchone()
    elif "index_daily" in name:
        row = con.execute(
            f"SELECT count(*), count(distinct index_code), min(trade_date), max(trade_date) FROM {name}"
        ).fetchone()
    else:
        row = con.execute(
            f"SELECT count(*), count(distinct ts_code), min(trade_date), max(trade_date) FROM {name}"
        ).fetchone()
    return {"rows": int(row[0]), "entities": int(row[1]) if row[1] is not None else None, "min": row[2], "max": row[3], "cols": cols}


def nn(con: duckdb.DuckDBPyConnection, table: str, field: str) -> tuple[int, float]:
    total = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    count = con.execute(f"SELECT count({field}) FROM {table}").fetchone()[0]
    return int(count), int(count) / int(total) if total else 0


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    summaries = {name: summary(con, name) for name in OBJECTS}
    checks = {
        "derived_concept_stock_context_cache": [
            "concept_count", "concept_ids_all", "concept_ids_top_2", "concept_ids_top_20", "concept_active_ids_120",
        ],
        "derived_sector_concept_context": [
            "sw_l1_code", "sw_l2_code", "concept_count", "concept_ids_top_20", "sw_l2_ret_20", "stock_ret_rank_industry_20",
        ],
        "derived_sector_concept_context_full_v": [
            "concept_ids_top_2", "concept_lagging_ids_30", "concept_active_ids_60", "concept_narrow_leading_ids_250",
        ],
        "derived_index_market_context": [
            "market_up_ratio", "hs300_ret_20", "stock_excess_hs300_20", "index_member_count", "primary_index_code",
        ],
    }
    lines = [
        "# Phase 3 行业概念与指数市场上下文审计报告",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 1. 表与视图覆盖",
        "",
        "| 对象 | 行数 | 实体数 | 起始日期 | 截止日期 | 字段数 |",
        "|---|---:|---:|---|---|---:|",
    ]
    for name in OBJECTS:
        s = summaries[name]
        lines.append(f"| `{name}` | {s['rows']:,} | {s['entities'] if s['entities'] is not None else ''} | {s['min']} | {s['max']} | {s['cols']} |")
    lines.extend(["", "## 2. 关键字段非空率", ""])
    for table, fields in checks.items():
        lines.append(f"### {table}")
        lines.append("")
        lines.append("| 字段 | 非空行数 | 非空率 |")
        lines.append("|---|---:|---:|")
        for field in fields:
            count, rate = nn(con, table, field)
            lines.append(f"| `{field}` | {count:,} | {rate:.2%} |")
        lines.append("")
    latest = con.execute(
        """
        SELECT
            (SELECT count(*) FROM derived_sector_concept_context_full_v WHERE trade_date=(SELECT max(trade_date) FROM derived_sector_concept_context)) AS sector_latest_rows,
            (SELECT count(*) FROM derived_index_market_context_full_v WHERE trade_date=(SELECT max(trade_date) FROM derived_index_market_context)) AS index_latest_rows
        """
    ).fetchone()
    lines.extend(
        [
            "## 3. 口径说明",
            "",
            "- 申万行业一、二级成员已通过 `index_member_all(l2_code=...)` 实证并同步，增强成员表包含 L1/L2/L3 字段；三级字段暂不进入核心上下文。",
            "- 概念成员缺少可靠进出日期，第一阶段按静态暴露处理。",
            "- 概念多周期列表已通过 `derived_concept_stock_context_cache` 物理缓存实现，完整视图扩展 2/3/5/10/20/30/60/120/250 日领涨、领跌、活跃、窄口径领涨和统计字段。",
            "- 指数权重按最近月度 asof 展开，最长回看 90 天。",
            "",
            "## 4. 最近交易日视图抽检",
            "",
            f"- `derived_sector_concept_context_full_v` 最新交易日行数：{latest[0]:,}",
            f"- `derived_index_market_context_full_v` 最新交易日行数：{latest[1]:,}",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
