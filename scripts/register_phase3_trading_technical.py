from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema_registry.json"
DERIVED_VARIABLES_PATH = ROOT / "config" / "variables" / "derived_variables.json"

MODULES = {
    "derived_daily_spine": "daily_spine",
    "derived_price_technical": "price_technical",
    "derived_return_momentum": "return_momentum",
    "derived_volatility_risk": "volatility_risk",
    "derived_volume_liquidity": "volume_liquidity",
    "derived_trading_constraint": "trading_constraint",
}


def f(name: str, dtype: str, desc: str, nullable: bool = True) -> dict:
    payload = {
        "name": name,
        "dtype": dtype,
        "nullable": nullable,
        "description": desc,
        "source_api": "local_derived",
    }
    if name == "updated_at":
        payload["nullable"] = False
        payload["default"] = "CURRENT_TIMESTAMP"
    return payload


PK = [
    f("ts_code", "VARCHAR", "股票代码", False),
    f("trade_date", "DATE", "交易日期", False),
]
UPDATED = [f("updated_at", "TIMESTAMP", "本地更新时间", False)]


CORE_FIELDS = {
    "derived_daily_spine": PK
    + [
        f("is_trade", "BOOLEAN", "当日是否有个股行情"),
        f("is_listed_asof", "BOOLEAN", "交易日时点是否处于上市状态"),
        f("list_status_asof", "VARCHAR", "交易日时点上市状态"),
        f("days_since_list", "INTEGER", "距离上市日的自然日天数"),
        f("market", "VARCHAR", "市场板块"),
        f("exchange", "VARCHAR", "交易所"),
        f("open_raw", "DOUBLE", "不复权开盘价"),
        f("high_raw", "DOUBLE", "不复权最高价"),
        f("low_raw", "DOUBLE", "不复权最低价"),
        f("close_raw", "DOUBLE", "不复权收盘价"),
        f("pre_close_raw", "DOUBLE", "不复权昨收价"),
        f("change_raw", "DOUBLE", "不复权涨跌额"),
        f("pct_chg_raw", "DOUBLE", "不复权涨跌幅"),
        f("volume", "DOUBLE", "成交量"),
        f("amount", "DOUBLE", "成交额"),
        f("amplitude_raw", "DOUBLE", "不复权振幅"),
        f("adj_factor", "DOUBLE", "当日复权因子"),
        f("latest_adj_factor_asof", "DOUBLE", "最新复权因子"),
        f("open_hfq", "DOUBLE", "后复权开盘价"),
        f("high_hfq", "DOUBLE", "后复权最高价"),
        f("low_hfq", "DOUBLE", "后复权最低价"),
        f("close_hfq", "DOUBLE", "后复权收盘价"),
        f("pre_close_hfq", "DOUBLE", "后复权昨收价"),
        f("ret_1_raw", "DOUBLE", "不复权1日简单收益率"),
        f("ret_1_hfq", "DOUBLE", "后复权1日简单收益率"),
        f("log_ret_1_hfq", "DOUBLE", "后复权1日对数收益率"),
        f("overnight_ret_hfq", "DOUBLE", "后复权隔夜收益率"),
        f("intraday_ret_hfq", "DOUBLE", "后复权日内收益率"),
        f("high_low_range_hfq", "DOUBLE", "后复权日内高低区间"),
        f("gap_open_hfq", "DOUBLE", "后复权开盘跳空"),
        f("close_position_hfq", "DOUBLE", "后复权收盘价在日内区间的位置"),
        f("up_limit", "DOUBLE", "涨停价"),
        f("down_limit", "DOUBLE", "跌停价"),
        f("limit_up_flag", "BOOLEAN", "收盘涨停标记，按最小价格变动单位判断"),
        f("limit_down_flag", "BOOLEAN", "收盘跌停标记，按最小价格变动单位判断"),
        f("touch_limit_up_flag", "BOOLEAN", "盘中触及涨停标记，按最小价格变动单位判断"),
        f("touch_limit_down_flag", "BOOLEAN", "盘中触及跌停标记，按最小价格变动单位判断"),
        f("open_limit_up_flag", "BOOLEAN", "开盘涨停标记，按最小价格变动单位判断"),
        f("open_limit_down_flag", "BOOLEAN", "开盘跌停标记，按最小价格变动单位判断"),
        f("limit_up_gap", "DOUBLE", "收盘价距离涨停价的比例"),
        f("limit_down_gap", "DOUBLE", "收盘价距离跌停价的比例"),
        f("has_price", "BOOLEAN", "是否有完整OHLC价格"),
        f("has_adj_factor", "BOOLEAN", "是否有复权因子"),
        f("has_limit_price", "BOOLEAN", "是否有涨跌停价"),
        f("price_valid_flag", "BOOLEAN", "OHLC价格关系是否有效"),
        f("missing_reason", "VARCHAR", "行情或辅助数据缺失原因"),
    ]
    + UPDATED,
    "derived_price_technical": PK
    + [
        f("ma_5_hfq", "DOUBLE", "ma_5_hfq = avg(derived_daily_spine.close_hfq, 5)"),
        f("ma_10_hfq", "DOUBLE", "ma_10_hfq = avg(derived_daily_spine.close_hfq, 10)"),
        f("ma_20_hfq", "DOUBLE", "ma_20_hfq = avg(derived_daily_spine.close_hfq, 20)"),
        f("ma_60_hfq", "DOUBLE", "ma_60_hfq = avg(derived_daily_spine.close_hfq, 60)"),
        f("ma_120_hfq", "DOUBLE", "ma_120_hfq = avg(derived_daily_spine.close_hfq, 120)"),
        f("ma_250_hfq", "DOUBLE", "ma_250_hfq = avg(derived_daily_spine.close_hfq, 250)"),
        f("close_to_ma_20_hfq", "DOUBLE", "close_to_ma_20_hfq = close_hfq / ma_20_hfq - 1"),
        f("close_to_ma_60_hfq", "DOUBLE", "close_to_ma_60_hfq = close_hfq / ma_60_hfq - 1"),
        f("ma_20_slope_20_hfq", "DOUBLE", "ma_20_slope_20_hfq = ma_20_hfq / lag(ma_20_hfq,20) - 1"),
        f("ma_60_slope_60_hfq", "DOUBLE", "ma_60_slope_60_hfq = ma_60_hfq / lag(ma_60_hfq,60) - 1"),
        f("rsi_14", "DOUBLE", "rsi_14 = RSI(close_hfq, 14)"),
        f("price_position_20_hfq", "DOUBLE", "price_position_20_hfq = (close_hfq - min(low_hfq,20)) / (max(high_hfq,20)-min(low_hfq,20))"),
        f("price_position_60_hfq", "DOUBLE", "price_position_60_hfq = (close_hfq - min(low_hfq,60)) / (max(high_hfq,60)-min(low_hfq,60))"),
    ]
    + UPDATED,
    "derived_return_momentum": PK
    + [
        f("ret_2_hfq", "DOUBLE", "ret_2_hfq = close_hfq / lag(close_hfq,2) - 1"),
        f("ret_5_hfq", "DOUBLE", "ret_5_hfq = close_hfq / lag(close_hfq,5) - 1"),
        f("ret_10_hfq", "DOUBLE", "ret_10_hfq = close_hfq / lag(close_hfq,10) - 1"),
        f("ret_20_hfq", "DOUBLE", "ret_20_hfq = close_hfq / lag(close_hfq,20) - 1"),
        f("ret_60_hfq", "DOUBLE", "ret_60_hfq = close_hfq / lag(close_hfq,60) - 1"),
        f("ret_120_hfq", "DOUBLE", "ret_120_hfq = close_hfq / lag(close_hfq,120) - 1"),
        f("ret_250_hfq", "DOUBLE", "ret_250_hfq = close_hfq / lag(close_hfq,250) - 1"),
        f("log_ret_sum_20_hfq", "DOUBLE", "log_ret_sum_20_hfq = sum(log_ret_1_hfq,20)"),
        f("momentum_20_5_hfq", "DOUBLE", "momentum_20_5_hfq = lag(close_hfq,5) / lag(close_hfq,20) - 1"),
        f("momentum_60_20_hfq", "DOUBLE", "momentum_60_20_hfq = lag(close_hfq,20) / lag(close_hfq,60) - 1"),
        f("reversal_5_hfq", "DOUBLE", "reversal_5_hfq = -ret_5_hfq"),
        f("up_days_20", "INTEGER", "up_days_20 = rolling_sum(ret_1_hfq > 0,20)"),
        f("down_days_20", "INTEGER", "down_days_20 = rolling_sum(ret_1_hfq < 0,20)"),
    ]
    + UPDATED,
    "derived_volatility_risk": PK
    + [
        f("hv_20", "DOUBLE", "hv_20 = stddev_samp(log_ret_1_hfq,20) * sqrt(242)"),
        f("hv_60", "DOUBLE", "hv_60 = stddev_samp(log_ret_1_hfq,60) * sqrt(242)"),
        f("hv_120", "DOUBLE", "hv_120 = stddev_samp(log_ret_1_hfq,120) * sqrt(242)"),
        f("parkinson_vol_20", "DOUBLE", "parkinson_vol_20 = sqrt(avg((ln(high_hfq/low_hfq))^2,20)/(4*ln(2))*242)"),
        f("atr_14_hfq", "DOUBLE", "atr_14_hfq = avg(true_range_hfq,14)"),
        f("atr_14_pct_hfq", "DOUBLE", "atr_14_pct_hfq = atr_14_hfq / close_hfq"),
        f("max_drawdown_20_hfq", "DOUBLE", "max_drawdown_20_hfq = min(close_hfq / rolling_max(close_hfq,20)-1,20)"),
        f("max_drawdown_60_hfq", "DOUBLE", "max_drawdown_60_hfq = min(close_hfq / rolling_max(close_hfq,60)-1,60)"),
        f("downside_vol_60", "DOUBLE", "downside_vol_60 = stddev_samp(min(log_ret_1_hfq,0),60) * sqrt(242)"),
        f("var_5pct_60", "DOUBLE", "var_5pct_60 = quantile(ret_1_hfq,0.05,60)"),
    ]
    + UPDATED,
    "derived_volume_liquidity": PK
    + [
        f("volume_ma_5", "DOUBLE", "volume_ma_5 = avg(volume,5)"),
        f("volume_ma_20", "DOUBLE", "volume_ma_20 = avg(volume,20)"),
        f("volume_ma_60", "DOUBLE", "volume_ma_60 = avg(volume,60)"),
        f("amount_ma_20", "DOUBLE", "amount_ma_20 = avg(amount,20)"),
        f("amount_ma_60", "DOUBLE", "amount_ma_60 = avg(amount,60)"),
        f("turnover_rate_ma_20", "DOUBLE", "turnover_rate_ma_20 = avg(stock_daily_basic.turnover_rate,20)"),
        f("turnover_rate_free_ma_20", "DOUBLE", "turnover_rate_free_ma_20 = avg(stock_daily_basic.turnover_rate_free,20)"),
        f("volume_ratio_20", "DOUBLE", "volume_ratio_20 = volume / volume_ma_20"),
        f("amount_ratio_20", "DOUBLE", "amount_ratio_20 = amount / amount_ma_20"),
        f("amihud_20", "DOUBLE", "amihud_20 = avg(abs(ret_1_hfq) / amount,20)"),
        f("zero_volume_days_20", "INTEGER", "zero_volume_days_20 = rolling_sum(volume=0,20)"),
    ]
    + UPDATED,
    "derived_trading_constraint": PK
    + [
        f("limit_up_days_5", "INTEGER", "limit_up_days_5 = rolling_sum(limit_up_flag,5)"),
        f("limit_up_days_20", "INTEGER", "limit_up_days_20 = rolling_sum(limit_up_flag,20)"),
        f("limit_down_days_5", "INTEGER", "limit_down_days_5 = rolling_sum(limit_down_flag,5)"),
        f("limit_down_days_20", "INTEGER", "limit_down_days_20 = rolling_sum(limit_down_flag,20)"),
        f("touch_limit_up_days_20", "INTEGER", "touch_limit_up_days_20 = rolling_sum(touch_limit_up_flag,20)"),
        f("touch_limit_down_days_20", "INTEGER", "touch_limit_down_days_20 = rolling_sum(touch_limit_down_flag,20)"),
        f("consecutive_limit_up_days", "INTEGER", "按交易日连续 limit_up_flag 计数"),
        f("consecutive_limit_down_days", "INTEGER", "按交易日连续 limit_down_flag 计数"),
        f("one_price_limit_up_flag", "BOOLEAN", "open/high/low/close 均在 up_limit ± price_tick/2 范围内"),
        f("one_price_limit_down_flag", "BOOLEAN", "open/high/low/close 均在 down_limit ± price_tick/2 范围内"),
        f("tradable_state", "VARCHAR", "交易可达状态：normal/suspended/limit_locked/missing"),
    ]
    + UPDATED,
}

PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
PATH_PERIODS = [5, 10, 20, 30, 60, 120]
VOL_PERIODS = [5, 10, 20, 30, 60, 120, 250]
ATR_PERIODS = [5, 10, 14, 20, 30, 60]
LIMIT_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120]


def rolling(name: str, dtype: str, template: str, periods: list[int], exclude: set[int] | None = None) -> list[dict]:
    exclude = exclude or set()
    return [f(name.format(n=n), dtype, template.format(n=n)) for n in periods if n not in exclude]


VIEW_EXTRA_FIELDS = {
    "derived_daily_spine_full_v": [
        f("open_qfq", "DOUBLE", "open_qfq = open_raw * adj_factor / latest_adj_factor_asof"),
        f("high_qfq", "DOUBLE", "high_qfq = high_raw * adj_factor / latest_adj_factor_asof"),
        f("low_qfq", "DOUBLE", "low_qfq = low_raw * adj_factor / latest_adj_factor_asof"),
        f("close_qfq", "DOUBLE", "close_qfq = close_raw * adj_factor / latest_adj_factor_asof"),
        f("pre_close_qfq", "DOUBLE", "pre_close_qfq = pre_close_raw * adj_factor / latest_adj_factor_asof"),
        f("body_raw", "DOUBLE", "body_raw = close_raw - open_raw"),
        f("upper_shadow_raw", "DOUBLE", "upper_shadow_raw = high_raw - greatest(open_raw, close_raw)"),
        f("lower_shadow_raw", "DOUBLE", "lower_shadow_raw = least(open_raw, close_raw) - low_raw"),
        f("body_ratio_raw", "DOUBLE", "body_ratio_raw = abs(close_raw-open_raw)/nullif(high_raw-low_raw,0)"),
        f("true_range_hfq", "DOUBLE", "true_range_hfq = max(high_hfq-low_hfq, abs(high_hfq-lag(close_hfq)), abs(low_hfq-lag(close_hfq)))"),
        f("suspended_flag", "BOOLEAN", "suspended_flag = volume is null or volume = 0"),
        f("one_price_limit_flag", "BOOLEAN", "one_price_limit_flag = one_price_limit_up_flag or one_price_limit_down_flag"),
        f("ohlc_relation_error_flag", "BOOLEAN", "OHLC 价格关系异常标记"),
    ],
    "derived_price_technical_full_v": [
        *rolling("ma_{n}_hfq", "DOUBLE", "ma_{n}_hfq = avg(close_hfq,{n})", PERIODS, {5, 10, 20, 60, 120, 250}),
        *rolling("close_to_ma_{n}_hfq", "DOUBLE", "close_to_ma_{n}_hfq = close_hfq/ma_{n}_hfq-1", PERIODS, {20, 60}),
        *rolling("ma_{n}_slope_{n}_hfq", "DOUBLE", "ma_{n}_slope_{n}_hfq = ma_{n}_hfq/lag(ma_{n}_hfq,{n})-1", [2, 3, 5, 10, 20, 30, 60, 120], {20, 60}),
        f("ma_bullish_5_20_60_flag", "BOOLEAN", "ma_5_hfq > ma_20_hfq and ma_20_hfq > ma_60_hfq"),
        f("ma_bullish_10_30_120_flag", "BOOLEAN", "ma_10_hfq > ma_30_hfq and ma_30_hfq > ma_120_hfq"),
        f("ma_bearish_5_20_60_flag", "BOOLEAN", "ma_5_hfq < ma_20_hfq and ma_20_hfq < ma_60_hfq"),
        f("ma_bearish_10_30_120_flag", "BOOLEAN", "ma_10_hfq < ma_30_hfq and ma_30_hfq < ma_120_hfq"),
        f("rsi_6", "DOUBLE", "RSI(close_hfq,6)"),
        f("rsi_9", "DOUBLE", "RSI(close_hfq,9)"),
        f("rsi_24", "DOUBLE", "RSI(close_hfq,24)"),
        *rolling("bias_{n}_hfq", "DOUBLE", "bias_{n}_hfq = close_hfq/ma_{n}_hfq-1", [3, 5, 6, 10, 12, 20, 24, 30, 60]),
        *rolling("price_position_{n}_hfq", "DOUBLE", "price_position_{n}_hfq = (close_hfq - min(low_hfq,{n}))/(max(high_hfq,{n})-min(low_hfq,{n}))", [5, 10, 20, 30, 60, 120, 250], {20, 60}),
        *[item for n in [20, 30, 60] for item in [
            f(f"boll_mid_{n}_hfq", "DOUBLE", f"boll_mid_{n}_hfq = avg(close_hfq,{n})"),
            f(f"boll_upper_{n}_hfq", "DOUBLE", f"boll_upper_{n}_hfq = boll_mid_{n}_hfq + 2*stddev(close_hfq,{n})"),
            f(f"boll_lower_{n}_hfq", "DOUBLE", f"boll_lower_{n}_hfq = boll_mid_{n}_hfq - 2*stddev(close_hfq,{n})"),
            f(f"boll_width_{n}_hfq", "DOUBLE", f"boll_width_{n}_hfq = (boll_upper_{n}_hfq-boll_lower_{n}_hfq)/boll_mid_{n}_hfq"),
            f(f"boll_pct_b_{n}_hfq", "DOUBLE", f"boll_pct_b_{n}_hfq = (close_hfq-boll_lower_{n}_hfq)/(boll_upper_{n}_hfq-boll_lower_{n}_hfq)"),
        ]],
        f("macd_dif_12_26_hfq", "DOUBLE", "当前实现为 avg(close_hfq,12) - avg(close_hfq,26) 的窗口代理值"),
        f("macd_dea_9_hfq", "DOUBLE", "当前实现为 avg(macd_dif_12_26_hfq,9) 的窗口代理值"),
        f("macd_hist_12_26_9_hfq", "DOUBLE", "macd_dif_12_26_hfq - macd_dea_9_hfq"),
        f("kdj_k_9_3_3_hfq", "DOUBLE", "当前实现为 avg(RSV(9),3) 的窗口代理值"),
        f("kdj_d_9_3_3_hfq", "DOUBLE", "当前实现为 avg(kdj_k_9_3_3_hfq,3) 的窗口代理值"),
        f("kdj_j_9_3_3_hfq", "DOUBLE", "3*K - 2*D"),
    ],
    "derived_return_momentum_full_v": [
        f("ret_1_hfq", "DOUBLE", "derived_daily_spine.ret_1_hfq"),
        f("ret_3_hfq", "DOUBLE", "ret_3_hfq = close_hfq/lag(close_hfq,3)-1"),
        f("ret_30_hfq", "DOUBLE", "ret_30_hfq = close_hfq/lag(close_hfq,30)-1"),
        *rolling("log_ret_sum_{n}_hfq", "DOUBLE", "log_ret_sum_{n}_hfq = sum(log_ret_1_hfq,{n})", PERIODS, {20}),
        f("momentum_30_10_hfq", "DOUBLE", "momentum_30_10_hfq = lag(close_hfq,10)/lag(close_hfq,30)-1"),
        f("momentum_120_20_hfq", "DOUBLE", "momentum_120_20_hfq = lag(close_hfq,20)/lag(close_hfq,120)-1"),
        f("momentum_250_20_hfq", "DOUBLE", "momentum_250_20_hfq = lag(close_hfq,20)/lag(close_hfq,250)-1"),
        *rolling("reversal_{n}_hfq", "DOUBLE", "reversal_{n}_hfq = -ret_{n}_hfq", [2, 3, 10]),
        *rolling("up_days_{n}", "INTEGER", "up_days_{n} = rolling_sum(ret_1_hfq > 0,{n})", PATH_PERIODS, {20}),
        *rolling("down_days_{n}", "INTEGER", "down_days_{n} = rolling_sum(ret_1_hfq < 0,{n})", PATH_PERIODS, {20}),
        *rolling("up_ratio_{n}", "DOUBLE", "up_ratio_{n} = up_days_{n}/{n}", PATH_PERIODS),
        *rolling("new_high_{n}_flag", "BOOLEAN", "new_high_{n}_flag = close_hfq >= rolling_max(close_hfq,{n})", [5, 10, 20, 30, 60, 120, 250]),
        *rolling("new_low_{n}_flag", "BOOLEAN", "new_low_{n}_flag = close_hfq <= rolling_min(close_hfq,{n})", [5, 10, 20, 30, 60, 120, 250]),
        *rolling("drawdown_from_high_{n}_hfq", "DOUBLE", "drawdown_from_high_{n}_hfq = close_hfq/rolling_max(close_hfq,{n})-1", [5, 10, 20, 30, 60, 120, 250]),
        *rolling("bounce_from_low_{n}_hfq", "DOUBLE", "bounce_from_low_{n}_hfq = close_hfq/rolling_min(close_hfq,{n})-1", [5, 10, 20, 30, 60, 120, 250]),
    ],
    "derived_volatility_risk_full_v": [
        *rolling("hv_{n}", "DOUBLE", "hv_{n} = stddev(log_ret_1_hfq,{n})*sqrt(242)", VOL_PERIODS, {20, 60, 120}),
        *rolling("parkinson_vol_{n}", "DOUBLE", "parkinson_vol_{n} = Parkinson volatility window {n}", [5, 10, 20, 30, 60, 120], {20}),
        *rolling("atr_{n}_hfq", "DOUBLE", "atr_{n}_hfq = avg(true_range_hfq,{n})", ATR_PERIODS, {14}),
        *rolling("atr_{n}_pct_hfq", "DOUBLE", "atr_{n}_pct_hfq = atr_{n}_hfq / close_hfq", ATR_PERIODS, {14}),
        *rolling("max_drawdown_{n}_hfq", "DOUBLE", "max_drawdown_{n}_hfq = close_hfq/rolling_max(close_hfq,{n})-1", [5, 10, 20, 30, 60, 120, 250], {20, 60}),
        *rolling("downside_vol_{n}", "DOUBLE", "downside_vol_{n} = stddev(min(log_ret_1_hfq,0),{n})*sqrt(242)", [20, 30, 60, 120, 250], {60}),
        *rolling("var_5pct_{n}", "DOUBLE", "var_5pct_{n} = quantile(ret_1_hfq,0.05,{n})", [20, 30, 60, 120, 250], {60}),
        *rolling("cvar_5pct_{n}", "DOUBLE", "cvar_5pct_{n} = avg(ret_1_hfq where ret_1_hfq <= var_5pct_{n},{n})", [20, 30, 60, 120, 250]),
    ],
    "derived_volume_liquidity_full_v": [
        *rolling("volume_ma_{n}", "DOUBLE", "volume_ma_{n} = avg(volume,{n})", [2, 3, 5, 10, 20, 30, 60, 120], {5, 20, 60}),
        *rolling("amount_ma_{n}", "DOUBLE", "amount_ma_{n} = avg(amount,{n})", [2, 3, 5, 10, 20, 30, 60, 120], {20, 60}),
        *rolling("turnover_rate_ma_{n}", "DOUBLE", "turnover_rate_ma_{n} = avg(turnover_rate,{n})", [2, 3, 5, 10, 20, 30, 60, 120], {20}),
        *rolling("turnover_rate_free_ma_{n}", "DOUBLE", "turnover_rate_free_ma_{n} = avg(turnover_rate_free,{n})", [2, 3, 5, 10, 20, 30, 60, 120], {20}),
        *rolling("volume_ratio_{n}", "DOUBLE", "volume_ratio_{n} = volume/volume_ma_{n}", [2, 3, 5, 10, 20, 30, 60, 120], {20}),
        *rolling("amount_ratio_{n}", "DOUBLE", "amount_ratio_{n} = amount/amount_ma_{n}", [2, 3, 5, 10, 20, 30, 60, 120], {20}),
        *rolling("amihud_{n}", "DOUBLE", "amihud_{n} = avg(abs(ret_1_hfq)/amount,{n})", [5, 10, 20, 30, 60, 120], {20}),
        *rolling("zero_volume_days_{n}", "INTEGER", "zero_volume_days_{n} = rolling_sum(volume=0,{n})", [5, 10, 20, 30, 60, 120], {20}),
        *rolling("amount_cv_{n}", "DOUBLE", "amount_cv_{n} = stddev(amount,{n})/avg(amount,{n})", [5, 10, 20, 30, 60, 120]),
    ],
    "derived_trading_constraint_full_v": [
        *rolling("limit_up_days_{n}", "INTEGER", "limit_up_days_{n} = rolling_sum(limit_up_flag,{n})", LIMIT_PERIODS, {5, 20}),
        *rolling("limit_down_days_{n}", "INTEGER", "limit_down_days_{n} = rolling_sum(limit_down_flag,{n})", LIMIT_PERIODS, {5, 20}),
        *rolling("touch_limit_up_days_{n}", "INTEGER", "touch_limit_up_days_{n} = rolling_sum(touch_limit_up_flag,{n})", LIMIT_PERIODS, {20}),
        *rolling("touch_limit_down_days_{n}", "INTEGER", "touch_limit_down_days_{n} = rolling_sum(touch_limit_down_flag,{n})", LIMIT_PERIODS, {20}),
        *rolling("open_limit_up_days_{n}", "INTEGER", "open_limit_up_days_{n} = rolling_sum(open_limit_up_flag,{n})", LIMIT_PERIODS),
        *rolling("open_limit_down_days_{n}", "INTEGER", "open_limit_down_days_{n} = rolling_sum(open_limit_down_flag,{n})", LIMIT_PERIODS),
        f("limit_locked_flag", "BOOLEAN", "one_price_limit_up_flag or one_price_limit_down_flag"),
        *rolling("missing_price_days_{n}", "INTEGER", "missing_price_days_{n} = rolling_sum(not has_price,{n})", [5, 10, 20, 30, 60, 120]),
        *rolling("suspended_days_{n}", "INTEGER", "suspended_days_{n} = rolling_sum(volume is null or volume=0,{n})", [5, 10, 20, 30, 60, 120]),
    ],
}

VIEW_BASE = {
    "derived_daily_spine_full_v": "derived_daily_spine",
    "derived_price_technical_full_v": "derived_price_technical",
    "derived_return_momentum_full_v": "derived_return_momentum",
    "derived_volatility_risk_full_v": "derived_volatility_risk",
    "derived_volume_liquidity_full_v": "derived_volume_liquidity",
    "derived_trading_constraint_full_v": "derived_trading_constraint",
}


def variable(table: str, field: dict) -> dict:
    name = field["name"]
    return {
        "name": name,
        "label_zh": field["description"].split("=")[0].strip(),
        "table": table,
        "module": MODULES[table],
        "category": "trading_technical",
        "tier": "core",
        "dtype": field["dtype"],
        "unit": "none" if field["dtype"] in {"BOOLEAN", "VARCHAR", "DATE"} else "ratio_or_source_unit",
        "frequency": "daily",
        "grain": ["ts_code", "trade_date"],
        "source_type": "derived",
        "dependencies": ["derived_daily_spine"],
        "formula_ref": field["description"],
        "formula_zh": field["description"],
        "price_basis": infer_price_basis(name),
        "point_in_time": True,
        "min_history": infer_min_history(name),
        "read_window": infer_read_window(name),
        "write_window": 10,
        "missing_policy": "initial_window_null",
        "validation": {"constant_allowed": field["dtype"] in {"BOOLEAN", "VARCHAR", "INTEGER"}},
    }


def infer_price_basis(name: str) -> str:
    if name.endswith("_hfq") or "_hfq_" in name:
        return "hfq"
    if name.endswith("_raw") or "limit" in name:
        return "raw"
    if "volume" in name or "amount" in name or "turnover" in name:
        return "not_price"
    return "not_price"


def infer_min_history(name: str) -> int:
    for token in ("250", "180", "120", "90", "60", "30", "24", "20", "14", "12", "10", "6", "5", "3", "2"):
        if token in name:
            return int(token)
    return 1


def infer_read_window(name: str) -> int:
    return max(20, infer_min_history(name) * 3)


def upsert_table(schema: dict, table: dict) -> None:
    for index, existing in enumerate(schema["tables"]):
        if existing["name"] == table["name"]:
            schema["tables"][index] = table
            return
    schema["tables"].append(table)


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for name, fields in CORE_FIELDS.items():
        old = next((item for item in schema["tables"] if item["name"] == name), {})
        upsert_table(
            schema,
            {
                "name": name,
                "phase": old.get("phase", "P3"),
                "description": f"Phase 3 trading technical core physical table: {MODULES[name]}",
                "primary_key": ["ts_code", "trade_date"],
                "fields": fields,
            },
        )
    for view_name, base_name in VIEW_BASE.items():
        upsert_table(
            schema,
            {
                "name": view_name,
                "phase": "P3",
                "description": f"Phase 3 trading technical full view for {base_name}",
                "table_type": "view",
                "primary_key": ["ts_code", "trade_date"],
                "fields": CORE_FIELDS[base_name][:-1] + VIEW_EXTRA_FIELDS[view_name] + UPDATED,
            },
        )
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    module_set = set(MODULES.values())
    for variables_path in (ROOT / "config" / "variables").glob("*.json"):
        payload = json.loads(variables_path.read_text(encoding="utf-8"))
        original_count = len(payload.get("variables", []))
        payload["variables"] = [
            item for item in payload.get("variables", []) if item.get("module") not in module_set
        ]
        if len(payload["variables"]) != original_count:
            variables_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = json.loads(DERIVED_VARIABLES_PATH.read_text(encoding="utf-8"))
    existing_names = {
        item.get("name")
        for variables_path in (ROOT / "config" / "variables").glob("*.json")
        for item in json.loads(variables_path.read_text(encoding="utf-8")).get("variables", [])
    }
    for table, fields in CORE_FIELDS.items():
        for field in fields:
            if field["name"] in {"ts_code", "trade_date", "updated_at"}:
                continue
            if field["name"] in existing_names:
                continue
            registry["variables"].append(variable(table, field))
            existing_names.add(field["name"])
    DERIVED_VARIABLES_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({name: len(fields) for name, fields in CORE_FIELDS.items()})
    print({name: len(CORE_FIELDS[base][:-1] + VIEW_EXTRA_FIELDS[name] + UPDATED) for name, base in VIEW_BASE.items()})


if __name__ == "__main__":
    main()
