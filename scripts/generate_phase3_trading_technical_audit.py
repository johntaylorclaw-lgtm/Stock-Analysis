from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
REPORT_PATH = ROOT / "reports" / "phase3_trading_technical_audit.md"

CORE_TABLES = [
    "derived_daily_spine",
    "derived_price_technical",
    "derived_return_momentum",
    "derived_volatility_risk",
    "derived_volume_liquidity",
    "derived_trading_constraint",
]

FULL_VIEWS = [
    "derived_daily_spine_full_v",
    "derived_price_technical_full_v",
    "derived_return_momentum_full_v",
    "derived_volatility_risk_full_v",
    "derived_volume_liquidity_full_v",
    "derived_trading_constraint_full_v",
]

KEY_FIELDS = {
    "derived_daily_spine": [
        "close_hfq",
        "log_ret_1_hfq",
        "limit_up_flag",
        "price_valid_flag",
    ],
    "derived_price_technical": [
        "ma_20_hfq",
        "ma_250_hfq",
        "rsi_14",
        "price_position_60_hfq",
    ],
    "derived_return_momentum": ["ret_20_hfq", "ret_250_hfq", "up_days_20"],
    "derived_volatility_risk": ["hv_60", "atr_14_hfq", "var_5pct_60"],
    "derived_volume_liquidity": ["volume_ma_20", "amount_ma_20", "amihud_20"],
    "derived_trading_constraint": [
        "limit_up_days_20",
        "consecutive_limit_up_days",
        "tradable_state",
    ],
}


def q(con: duckdb.DuckDBPyConnection, sql: str, params: tuple = ()) -> tuple:
    return con.execute(sql, params).fetchone()


def columns(con: duckdb.DuckDBPyConnection, name: str) -> list[str]:
    rows = con.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = ?
        ORDER BY ordinal_position
        """,
        [name],
    ).fetchall()
    return [row[0] for row in rows]


def schema_field_count(schema: dict, name: str) -> int | None:
    for table in schema.get("tables", []):
        if table.get("name") == name:
            return len(table.get("fields", []))
    return None


def table_summary(con: duckdb.DuckDBPyConnection, table: str) -> dict:
    row = q(
        con,
        f"""
        SELECT
            count(*) AS row_count,
            count(DISTINCT ts_code) AS stock_count,
            min(trade_date) AS min_trade_date,
            max(trade_date) AS max_trade_date
        FROM {table}
        """,
    )
    return {
        "row_count": row[0],
        "stock_count": row[1],
        "min_trade_date": row[2],
        "max_trade_date": row[3],
    }


def non_null_rates(con: duckdb.DuckDBPyConnection, table: str, fields: list[str]) -> list[tuple]:
    total = q(con, f"SELECT count(*) FROM {table}")[0]
    result = []
    for field in fields:
        non_null = q(con, f"SELECT count({field}) FROM {table}")[0]
        result.append((field, non_null, total, non_null / total if total else None))
    return result


def price_tick_audit(con: duckdb.DuckDBPyConnection) -> dict:
    row = q(
        con,
        """
        WITH base AS (
            SELECT
                close_raw,
                up_limit,
                down_limit,
                CASE WHEN up_limit IS NOT NULL THEN close_raw >= up_limit - 0.005 END AS tick_up,
                CASE WHEN up_limit IS NOT NULL THEN close_raw >= up_limit * 0.9999 END AS ratio_up,
                CASE WHEN down_limit IS NOT NULL THEN close_raw <= down_limit + 0.005 END AS tick_down,
                CASE WHEN down_limit IS NOT NULL THEN close_raw <= down_limit * 1.0001 END AS ratio_down
            FROM derived_daily_spine
            WHERE close_raw IS NOT NULL
        )
        SELECT
            count(*) AS rows_checked,
            sum(CASE WHEN tick_up THEN 1 ELSE 0 END) AS tick_up_count,
            sum(CASE WHEN ratio_up THEN 1 ELSE 0 END) AS ratio_up_count,
            sum(CASE WHEN tick_up IS DISTINCT FROM ratio_up THEN 1 ELSE 0 END) AS up_diff_count,
            sum(CASE WHEN tick_down THEN 1 ELSE 0 END) AS tick_down_count,
            sum(CASE WHEN ratio_down THEN 1 ELSE 0 END) AS ratio_down_count,
            sum(CASE WHEN tick_down IS DISTINCT FROM ratio_down THEN 1 ELSE 0 END) AS down_diff_count
        FROM base
        """,
    )
    return {
        "rows_checked": row[0],
        "tick_up_count": row[1],
        "ratio_up_count": row[2],
        "up_diff_count": row[3],
        "tick_down_count": row[4],
        "ratio_down_count": row[5],
        "down_diff_count": row[6],
    }


def recent_view_summary(con: duckdb.DuckDBPyConnection, view: str) -> dict:
    row = q(
        con,
        f"""
        SELECT count(*), count(DISTINCT ts_code), min(trade_date), max(trade_date)
        FROM {view}
        WHERE trade_date BETWEEN DATE '2026-05-20' AND DATE '2026-05-26'
        """,
    )
    return {
        "row_count": row[0],
        "stock_count": row[1],
        "min_trade_date": row[2],
        "max_trade_date": row[3],
    }


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    con = duckdb.connect(str(DB_PATH))
    lines: list[str] = []
    lines.append("# Phase 3 交易行情与技术分析核心模块审计报告")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- 数据库：`{DB_PATH}`")
    lines.append(f"- 价格最小变动单位口径：`price_tick = 0.01`，涨跌停判断容忍区间为 `price_tick / 2 = 0.005`")
    lines.append("")

    lines.append("## 1. 字段注册与实际落库核对")
    lines.append("")
    lines.append("| 对象 | 类型 | 注册字段数 | 实际字段数 | 状态 |")
    lines.append("|---|---:|---:|---:|---|")
    for name in CORE_TABLES + FULL_VIEWS:
        actual = len(columns(con, name))
        registered = schema_field_count(schema, name)
        status = "OK" if registered == actual else "MISMATCH"
        obj_type = "物理表" if name in CORE_TABLES else "视图"
        lines.append(f"| `{name}` | {obj_type} | {registered} | {actual} | {status} |")
    lines.append("")

    lines.append("## 2. 核心物理表覆盖率")
    lines.append("")
    lines.append("| 表 | 行数 | 股票数 | 最早交易日 | 最新交易日 |")
    lines.append("|---|---:|---:|---|---|")
    for table in CORE_TABLES:
        s = table_summary(con, table)
        lines.append(
            f"| `{table}` | {s['row_count']:,} | {s['stock_count']:,} | {s['min_trade_date']} | {s['max_trade_date']} |"
        )
    lines.append("")

    lines.append("## 3. 完整视图近端可查询核对")
    lines.append("")
    lines.append("| 视图 | 2026-05-20 至 2026-05-26 行数 | 股票数 | 日期范围 |")
    lines.append("|---|---:|---:|---|")
    for view in FULL_VIEWS:
        s = recent_view_summary(con, view)
        lines.append(
            f"| `{view}` | {s['row_count']:,} | {s['stock_count']:,} | {s['min_trade_date']} ~ {s['max_trade_date']} |"
        )
    lines.append("")

    lines.append("## 4. 关键字段非空率")
    lines.append("")
    lines.append("| 表 | 字段 | 非空行数 | 总行数 | 非空率 |")
    lines.append("|---|---|---:|---:|---:|")
    for table, fields in KEY_FIELDS.items():
        for field, non_null, total, rate in non_null_rates(con, table, fields):
            rate_text = "" if rate is None else f"{rate:.4%}"
            lines.append(f"| `{table}` | `{field}` | {non_null:,} | {total:,} | {rate_text} |")
    lines.append("")

    tick = price_tick_audit(con)
    lines.append("## 5. 涨跌停口径实证")
    lines.append("")
    lines.append("| 口径项 | 数值 |")
    lines.append("|---|---:|")
    for key, value in tick.items():
        lines.append(f"| `{key}` | {value:,} |")
    lines.append("")
    lines.append(
        "结论：本模块采用最小价格变动单位半档作为涨跌停判断容忍区间，更贴近A股报价规则；与旧比例口径存在差异的样本已在上表列出，后续如需进一步精细化，可按股票价格档位和历史规则版本拆分审计。"
    )
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
