from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "duckdb" / "stock_data.duckdb"
REPORT_PATH = ROOT / "reports" / "phase3_capital_flow_audit.md"

TABLES = [
    "derived_capital_flow",
    "derived_northbound_flow_cache",
    "derived_capital_flow_event_cache",
]

NON_NULL_FIELDS = {
    "derived_capital_flow": [
        "main_net_amount", "main_net_amount_rate", "main_flow_ma_20",
        "margin_balance", "margin_buy_to_amount", "north_hold_shares", "has_moneyflow",
    ],
    "derived_northbound_flow_cache": [
        "north_money", "north_money_ma_20", "north_money_sum_60", "north_hold_shares_chg_250",
    ],
    "derived_capital_flow_event_cache": [
        "top_list_flag", "top_inst_flag", "top_list_days_20", "top_inst_net_buy_sum_20",
    ],
}


def table_info(con: duckdb.DuckDBPyConnection, table: str) -> dict:
    row = con.execute(
        f"""
        SELECT count(*) AS rows,
               count(distinct ts_code) AS stocks,
               min(trade_date) AS min_date,
               max(trade_date) AS max_date
        FROM {table}
        """
    ).fetchone()
    cols = con.execute(f"PRAGMA table_info('{table}')").fetchall()
    return {
        "rows": int(row[0]),
        "stocks": int(row[1]),
        "min_date": row[2],
        "max_date": row[3],
        "columns": len(cols),
    }


def non_null(con: duckdb.DuckDBPyConnection, table: str, field: str, total: int) -> tuple[str, int, float]:
    n = con.execute(f"SELECT count({field}) FROM {table}").fetchone()[0]
    return field, int(n), (int(n) / total if total else 0)


def moneyflow_unit(con: duckdb.DuckDBPyConnection) -> tuple:
    return con.execute(
        """
        WITH x AS (
            SELECT
                (coalesce(buy_sm_amount,0)+coalesce(sell_sm_amount,0)+coalesce(buy_md_amount,0)+coalesce(sell_md_amount,0)
                 +coalesce(buy_lg_amount,0)+coalesce(sell_lg_amount,0)+coalesce(buy_elg_amount,0)+coalesce(sell_elg_amount,0)) AS mf_gross,
                ds.amount
            FROM stock_moneyflow_daily mf
            JOIN derived_daily_spine ds USING (ts_code, trade_date)
            WHERE mf.trade_date BETWEEN DATE '2024-01-01' AND DATE '2026-05-26'
              AND ds.amount > 0
        )
        SELECT count(*), median(mf_gross / amount), avg(mf_gross / amount)
        FROM x
        WHERE mf_gross > 0
        """
    ).fetchone()


def margin_unit(con: duckdb.DuckDBPyConnection) -> tuple:
    return con.execute(
        """
        WITH x AS (
            SELECT m.margin_buy, ds.amount
            FROM margin_detail m
            JOIN derived_daily_spine ds USING (ts_code, trade_date)
            WHERE m.trade_date BETWEEN DATE '2024-01-01' AND DATE '2026-05-26'
              AND ds.amount > 0
              AND m.margin_buy > 0
        )
        SELECT count(*), median(margin_buy / amount), median(margin_buy / (amount * 1000.0))
        FROM x
        """
    ).fetchone()


def recent_view(con: duckdb.DuckDBPyConnection) -> dict:
    row = con.execute(
        """
        WITH recent_dates AS (
            SELECT trade_date
            FROM derived_daily_spine
            GROUP BY trade_date
            ORDER BY trade_date DESC
            LIMIT 10
        )
        SELECT count(*) AS rows,
               count(main_flow_ma_20) AS main_flow_ma_20_nn,
               count(north_money) AS north_money_nn,
               count(top_list_flag) AS top_list_flag_nn,
               count(margin_buy_to_amount_ma_20) AS margin_buy_to_amount_ma_20_nn
        FROM derived_capital_flow_full_v
        WHERE trade_date IN (SELECT trade_date FROM recent_dates)
        """
    ).fetchone()
    return {
        "rows": int(row[0]),
        "main_flow_ma_20_nn": int(row[1]),
        "north_money_nn": int(row[2]),
        "top_list_flag_nn": int(row[3]),
        "margin_buy_to_amount_ma_20_nn": int(row[4]),
    }


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    table_summaries = {table: table_info(con, table) for table in TABLES}
    unit_mf = moneyflow_unit(con)
    unit_margin = margin_unit(con)
    view_summary = recent_view(con)

    lines = [
        "# Phase 3 资金流与交易行为模块审计报告",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 1. 表覆盖",
        "",
        "| 表 | 行数 | 股票数 | 起始日期 | 截止日期 | 字段数 |",
        "|---|---:|---:|---|---|---:|",
    ]
    for table, info in table_summaries.items():
        lines.append(
            f"| `{table}` | {info['rows']:,} | {info['stocks']:,} | {info['min_date']} | {info['max_date']} | {info['columns']} |"
        )
    lines.extend(["", "## 2. 关键字段非空率", ""])
    for table, fields in NON_NULL_FIELDS.items():
        total = table_summaries[table]["rows"]
        lines.append(f"### {table}")
        lines.append("")
        lines.append("| 字段 | 非空行数 | 非空率 |")
        lines.append("|---|---:|---:|")
        for field, n, rate in [non_null(con, table, field, total) for field in fields]:
            lines.append(f"| `{field}` | {n:,} | {rate:.2%} |")
        lines.append("")
    lines.extend(
        [
            "## 3. 单位实证结论",
            "",
            f"- 个股资金流金额实证样本数：{int(unit_mf[0]):,}；`sum(buy/sell amount) / stock_daily.amount` 中位数：{unit_mf[1]:.6f}，均值：{unit_mf[2]:.6f}。",
            "- 解释：Tushare 个股资金流金额为万元，`stock_daily.amount` 为千元；总买卖额约等于两倍成交额，因此未换算比值约为 0.2。资金流占成交额统一采用 `moneyflow_amount * 10 / amount`。",
            f"- 两融金额实证样本数：{int(unit_margin[0]):,}；`margin_buy / amount` 中位数：{unit_margin[1]:.6f}，`margin_buy / (amount * 1000)` 中位数：{unit_margin[2]:.6f}。",
            "- 解释：两融金额按元计，成交额按千元计；融资买入占成交额统一采用 `margin_buy / (amount * 1000)`。",
            "",
            "## 4. 完整视图最近10个交易日抽检",
            "",
            "| 指标 | 数值 |",
            "|---|---:|",
            f"| 行数 | {view_summary['rows']:,} |",
            f"| `main_flow_ma_20` 非空 | {view_summary['main_flow_ma_20_nn']:,} |",
            f"| `north_money` 非空 | {view_summary['north_money_nn']:,} |",
            f"| `top_list_flag` 非空 | {view_summary['top_list_flag_nn']:,} |",
            f"| `margin_buy_to_amount_ma_20` 非空 | {view_summary['margin_buy_to_amount_ma_20_nn']:,} |",
            "",
            "## 5. 结论",
            "",
            "资金流与交易行为模块已完成核心物理表、北向缓存、事件缓存和完整视图构建。市场级北向资金流已按交易日广播到个股完整视图，并在字段说明中标记为市场级背景变量。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
