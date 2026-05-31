from stock_maintainance.transform import parse_tushare_date


def test_parse_tushare_date_accepts_full_year_month_and_year_only() -> None:
    assert parse_tushare_date("20160229") == "2016-02-29"
    assert parse_tushare_date("201602") == "2016-02-29"
    assert parse_tushare_date("2014") == "2014-12-31"


def test_parse_tushare_date_preserves_unknown_format() -> None:
    assert parse_tushare_date("2016-02-29") == "2016-02-29"
    assert parse_tushare_date("") is None

