from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .database import connect
from .paths import DATA_DIR
from .schema import quote_ident


PARQUET_DIR = DATA_DIR / "parquet"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class ParquetExportResult:
    dataset: str
    source: str
    start_date: str
    end_date: str
    output_dir: str
    columns: list[str]
    partitions: list[dict[str, Any]]
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "source": self.source,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "output_dir": self.output_dir,
            "columns": self.columns,
            "partitions": self.partitions,
            "dry_run": self.dry_run,
        }


def _source_columns(con, source: str) -> list[str]:
    rows = con.execute(f"DESCRIBE SELECT * FROM {quote_ident(source)}").fetchall()
    return [str(row[0]) for row in rows]


def _trade_dates(con, source: str, start_date: str, end_date: str) -> list[str]:
    rows = con.execute(
        f"""
        SELECT DISTINCT trade_date::VARCHAR
        FROM {quote_ident(source)}
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date
        """,
        [start_date, end_date],
    ).fetchall()
    return [str(row[0]) for row in rows]


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _validate_date(value: str, name: str) -> None:
    if not DATE_RE.fullmatch(value):
        raise ValueError(f"{name} must use YYYY-MM-DD format: {value}")


def export_parquet(
    *,
    source: str = "stock_features_core",
    dataset: str | None = None,
    start_date: str,
    end_date: str,
    columns: list[str] | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> ParquetExportResult:
    _validate_date(start_date, "start_date")
    _validate_date(end_date, "end_date")
    dataset_name = dataset or source
    root = output_dir or (PARQUET_DIR / dataset_name)
    with connect() as con:
        available_columns = _source_columns(con, source)
        selected_columns = columns or available_columns
        missing = sorted(set(selected_columns) - set(available_columns))
        if missing:
            raise ValueError(f"unknown columns for {source}: {', '.join(missing)}")
        if "trade_date" not in selected_columns:
            selected_columns = ["trade_date", *selected_columns]
        if "ts_code" in available_columns and "ts_code" not in selected_columns:
            selected_columns = ["ts_code", *selected_columns]
        trade_dates = _trade_dates(con, source, start_date, end_date)
        partitions: list[dict[str, Any]] = []
        select_columns = ", ".join(quote_ident(col) for col in selected_columns)
        order_columns = ["trade_date"]
        if "ts_code" in available_columns:
            order_columns.append("ts_code")
        order_sql = ", ".join(quote_ident(col) for col in order_columns)
        for trade_date in trade_dates:
            partition_dir = root / f"trade_date={trade_date}"
            output_file = partition_dir / "part.parquet"
            temp_file = partition_dir / "part.parquet.tmp"
            row_count = int(
                con.execute(
                    f"SELECT count(*) FROM {quote_ident(source)} WHERE trade_date = ?",
                    [trade_date],
                ).fetchone()[0]
            )
            partitions.append(
                {
                    "trade_date": trade_date,
                    "rows": row_count,
                    "path": str(output_file),
                }
            )
            if dry_run:
                continue
            partition_dir.mkdir(parents=True, exist_ok=True)
            if temp_file.exists():
                temp_file.unlink()
            con.execute(
                f"""
                COPY (
                    SELECT {select_columns}
                    FROM {quote_ident(source)}
                    WHERE trade_date = ?
                    ORDER BY {order_sql}
                )
                TO {_sql_string(str(temp_file))}
                (FORMAT PARQUET, COMPRESSION ZSTD)
                """,
                [trade_date],
            )
            temp_file.replace(output_file)
    return ParquetExportResult(
        dataset=dataset_name,
        source=source,
        start_date=start_date,
        end_date=end_date,
        output_dir=str(root),
        columns=selected_columns,
        partitions=partitions,
        dry_run=dry_run,
    )
