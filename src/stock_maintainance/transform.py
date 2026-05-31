from __future__ import annotations

import json
from calendar import monthrange
from datetime import UTC, datetime
from typing import Any

import pandas as pd


def parse_tushare_date(value: Any) -> Any:
    if value is None or pd.isna(value) or value == "":
        return None
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) == 6 and text.isdigit():
        year = int(text[:4])
        month = int(text[4:6])
        day = monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-{day:02d}"
    if len(text) == 4 and text.isdigit():
        return f"{text}-12-31"
    return value


def normalize_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = df[column].map(parse_tushare_date)
    return df


def add_payload_json(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        df["payload_json"] = []
        return df
    records = df.where(pd.notna(df), None).to_dict(orient="records")
    df["payload_json"] = [
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records
    ]
    return df


def add_updated_at(df: pd.DataFrame) -> pd.DataFrame:
    df["updated_at"] = datetime.now(UTC).replace(tzinfo=None)
    return df


def rename_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    existing = {src: dst for src, dst in mapping.items() if src in df.columns}
    return df.rename(columns=existing)
