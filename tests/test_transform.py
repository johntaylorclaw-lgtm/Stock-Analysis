from datetime import datetime

import pandas as pd

from stock_maintainance import transform
from stock_maintainance.transform import parse_tushare_date


def test_parse_tushare_date_accepts_full_year_month_and_year_only() -> None:
    assert parse_tushare_date("20160229") == "2016-02-29"
    assert parse_tushare_date("201602") == "2016-02-29"
    assert parse_tushare_date("2014") == "2014-12-31"


def test_parse_tushare_date_preserves_unknown_format() -> None:
    assert parse_tushare_date("2016-02-29") == "2016-02-29"
    assert parse_tushare_date("") is None


def test_add_updated_at_uses_local_naive_timestamp(monkeypatch) -> None:
    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 12, 20, 30, tzinfo=tz)

    monkeypatch.setattr(transform, "datetime", FrozenDateTime)

    df = transform.add_updated_at(pd.DataFrame([{"ts_code": "000001.SZ"}]))

    value = df.loc[0, "updated_at"]
    assert value == datetime(2026, 6, 12, 20, 30)
    assert value.tzinfo is None
