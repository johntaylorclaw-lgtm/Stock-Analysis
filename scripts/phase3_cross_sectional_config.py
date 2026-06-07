from __future__ import annotations

from dataclasses import dataclass


FULL_PERIODS = [2, 3, 5, 10, 20, 30, 60, 120, 250]
WINSOR_LOWER = 0.01
WINSOR_UPPER = 0.99
MIN_GROUP_ZSCORE_N = 20
MIN_GROUP_RANK_N = 5


@dataclass(frozen=True)
class XsVariable:
    name: str
    source_table: str
    source_field: str
    label_zh: str
    valid_rule: str = "default"
    physical: bool = True


def v(
    name: str,
    source_table: str,
    source_field: str,
    label_zh: str,
    valid_rule: str = "default",
    physical: bool = True,
) -> XsVariable:
    return XsVariable(name, source_table, source_field, label_zh, valid_rule, physical)


PHYSICAL_VARIABLES: list[XsVariable] = [
    v("ret_20_hfq", "derived_return_momentum", "ret_20_hfq", "20日收益"),
    v("ret_60_hfq", "derived_return_momentum", "ret_60_hfq", "60日收益"),
    v("ret_120_hfq", "derived_return_momentum", "ret_120_hfq", "120日收益"),
    v("ret_250_hfq", "derived_return_momentum", "ret_250_hfq", "250日收益"),
    v("momentum_60_20_hfq", "derived_return_momentum", "momentum_60_20_hfq", "60-20日动量"),
    v("reversal_5_hfq", "derived_return_momentum", "reversal_5_hfq", "5日反转"),
    v("amount_ma_20", "derived_volume_liquidity", "amount_ma_20", "20日成交额均值", "non_negative"),
    v("turnover_rate_ma_20", "derived_volume_liquidity", "turnover_rate_ma_20", "20日换手率均值", "non_negative"),
    v("amihud_20", "derived_volume_liquidity", "amihud_20", "20日Amihud流动性冲击", "non_negative"),
    v("hv_20", "derived_volatility_risk", "hv_20", "20日历史波动率", "non_negative"),
    v("hv_60", "derived_volatility_risk", "hv_60", "60日历史波动率", "non_negative"),
    v("atr_14_pct_hfq", "derived_volatility_risk", "atr_14_pct_hfq", "14日ATR占价格比例", "non_negative"),
    v("max_drawdown_60_hfq", "derived_volatility_risk", "max_drawdown_60_hfq", "60日最大回撤"),
    v("log_total_mv", "derived_valuation_size", "log_total_mv", "总市值对数"),
    v("log_free_float_mv", "derived_valuation_size", "log_free_float_mv", "自由流通市值对数"),
    v("pe_ttm", "derived_valuation_size", "pe_ttm", "市盈率TTM", "positive"),
    v("pb", "derived_valuation_size", "pb", "市净率", "positive"),
    v("earnings_yield_ttm", "derived_valuation_size", "earnings_yield_ttm", "盈利收益率TTM"),
    v("book_to_price", "derived_valuation_size", "book_to_price", "账面市值比"),
    v("dividend_yield_ttm", "derived_valuation_size", "dividend_yield_ttm", "股息率TTM"),
    v("roe_asof", "derived_financial_quality", "roe_asof", "ROE"),
    v("roa_asof", "derived_financial_quality", "roa_asof", "ROA"),
    v("roic_asof", "derived_financial_quality", "roic_asof", "ROIC"),
    v("gross_margin_asof", "derived_financial_quality", "gross_margin_asof", "毛利率"),
    v("netprofit_margin_asof", "derived_financial_quality", "netprofit_margin_asof", "净利率"),
    v("ocf_to_profit_asof", "derived_financial_quality", "ocf_to_profit_asof", "经营现金流占利润"),
    v("accrual_ratio_asof", "derived_financial_quality", "accrual_ratio_asof", "应计比率"),
    v("debt_to_assets_asof", "derived_financial_quality", "debt_to_assets_asof", "资产负债率"),
    v("current_ratio_asof", "derived_financial_quality", "current_ratio_asof", "流动比率", "non_negative"),
    v("assets_turn_asof", "derived_financial_quality", "assets_turn_asof", "总资产周转率"),
    v("revenue_yoy_asof", "derived_financial_growth", "revenue_yoy_asof", "营业收入同比"),
    v("netprofit_yoy_asof", "derived_financial_growth", "netprofit_yoy_asof", "净利润同比"),
    v("ocf_yoy_asof", "derived_financial_growth", "ocf_yoy_asof", "经营现金流同比"),
    v("revenue_cagr_3y_asof", "derived_financial_growth", "revenue_cagr_3y_asof", "营业收入3年复合增长"),
    v("net_profit_cagr_3y_asof", "derived_financial_growth", "net_profit_cagr_3y_asof", "净利润3年复合增长"),
    v("main_flow_sum_20", "derived_capital_flow", "main_flow_sum_20", "20日主力净流入累计"),
    v("main_flow_to_total_mv_20", "derived_capital_flow", "main_flow_to_total_mv_20", "20日主力净流入占总市值"),
    v("main_flow_persist_ratio_20", "derived_capital_flow", "main_flow_persist_ratio_20", "20日主力净流入持续比例"),
    v("margin_balance_chg_20", "derived_capital_flow", "margin_balance_chg_20", "融资融券余额20日变化"),
    v("north_hold_ratio_chg_20", "derived_capital_flow", "north_hold_ratio_chg_20", "北向持股比例20日变化"),
    v("stock_excess_sw_l2_20", "derived_sector_concept_context", "stock_excess_sw_l2_20", "20日相对申万二级超额收益"),
    v("concept_count", "derived_sector_concept_context", "concept_count", "概念数量", "non_negative"),
    v("concept_avg_ret_20", "derived_sector_concept_context", "concept_avg_ret_20", "所属概念20日平均收益"),
    v("concept_hot_count_20", "derived_sector_concept_context", "concept_hot_count_20", "20日高热概念数量", "non_negative"),
    v("stock_excess_hs300_20", "derived_index_market_context", "stock_excess_hs300_20", "20日相对沪深300超额收益"),
]


VIEW_EXTRA_VARIABLES: list[XsVariable] = [
    v("ret_5_hfq", "derived_return_momentum", "ret_5_hfq", "5日收益", physical=False),
    v("up_days_20", "derived_return_momentum", "up_days_20", "20日上涨天数", "non_negative", False),
    v("down_days_20", "derived_return_momentum", "down_days_20", "20日下跌天数", "non_negative", False),
    v("amount_ma_60", "derived_volume_liquidity", "amount_ma_60", "60日成交额均值", "non_negative", False),
    v("volume_ratio_20", "derived_volume_liquidity", "volume_ratio_20", "20日成交量相对均值", "non_negative", False),
    v("amount_ratio_20", "derived_volume_liquidity", "amount_ratio_20", "20日成交额相对均值", "non_negative", False),
    v("parkinson_vol_20", "derived_volatility_risk", "parkinson_vol_20", "20日Parkinson波动率", "non_negative", False),
    v("max_drawdown_20_hfq", "derived_volatility_risk", "max_drawdown_20_hfq", "20日最大回撤", physical=False),
    v("pe_ttm_pct_5y", "derived_valuation_size", "pe_ttm_pct_5y", "PE_TTM五年历史分位", "non_negative", False),
    v("pb_pct_5y", "derived_valuation_size", "pb_pct_5y", "PB五年历史分位", "non_negative", False),
    v("ps_ttm_pct_5y", "derived_valuation_size", "ps_ttm_pct_5y", "PS_TTM五年历史分位", "non_negative", False),
    v("total_mv_pct_5y", "derived_valuation_size", "total_mv_pct_5y", "总市值五年历史分位", "non_negative", False),
    v("operating_profit_margin_asof", "derived_financial_quality", "operating_profit_margin_asof", "营业利润率", physical=False),
    v("cash_to_assets_asof", "derived_financial_quality", "cash_to_assets_asof", "货币资金占资产", physical=False),
    v("goodwill_to_assets_asof", "derived_financial_quality", "goodwill_to_assets_asof", "商誉占资产", physical=False),
    v("liabilities_to_equity_asof", "derived_financial_quality", "liabilities_to_equity_asof", "负债权益比", physical=False),
    v("revenue_change_4report_asof", "derived_financial_growth", "revenue_change_4report_asof", "营业收入4报告期变化", physical=False),
    v("net_profit_change_4report_asof", "derived_financial_growth", "net_profit_change_4report_asof", "净利润4报告期变化", physical=False),
    v("ocf_change_4report_asof", "derived_financial_growth", "ocf_change_4report_asof", "经营现金流4报告期变化", physical=False),
    v("main_flow_sum_60", "derived_capital_flow", "main_flow_sum_60", "60日主力净流入累计", physical=False),
    v("small_net_amount_rate", "derived_capital_flow", "small_net_amount_rate", "小单净流入比例", physical=False),
    v("stock_excess_sw_l2_60", "derived_sector_concept_context", "stock_excess_sw_l2_60", "60日相对申万二级超额收益", physical=False),
    v("stock_excess_zz1000_20", "derived_index_market_context", "stock_excess_zz1000_20", "20日相对中证1000超额收益", physical=False),
]


RESIDUAL_VARIABLES = [
    "ret_20_hfq",
    "ret_60_hfq",
    "momentum_60_20_hfq",
    "hv_60",
    "amihud_20",
    "earnings_yield_ttm",
    "book_to_price",
    "roe_asof",
    "revenue_yoy_asof",
    "main_flow_to_total_mv_20",
]


EXPOSURES: dict[str, tuple[str, list[tuple[str, int]]]] = {
    "size_exposure_z": ("规模暴露z值", [("log_total_mv", 1), ("log_free_float_mv", 1)]),
    "value_exposure_z": (
        "价值暴露z值",
        [("earnings_yield_ttm", 1), ("book_to_price", 1), ("dividend_yield_ttm", 1)],
    ),
    "momentum_exposure_z": (
        "动量暴露z值",
        [("ret_20_hfq", 1), ("ret_60_hfq", 1), ("momentum_60_20_hfq", 1)],
    ),
    "reversal_exposure_z": ("短期反转暴露z值", [("reversal_5_hfq", 1)]),
    "volatility_exposure_z": (
        "波动暴露z值",
        [("hv_20", 1), ("hv_60", 1), ("atr_14_pct_hfq", 1)],
    ),
    "liquidity_exposure_z": (
        "流动性活跃暴露z值",
        [("amount_ma_20", 1), ("turnover_rate_ma_20", 1), ("amihud_20", -1)],
    ),
    "quality_exposure_z": (
        "财务质量暴露z值",
        [("roe_asof", 1), ("roa_asof", 1), ("roic_asof", 1), ("ocf_to_profit_asof", 1), ("accrual_ratio_asof", -1)],
    ),
    "growth_exposure_z": (
        "财务成长暴露z值",
        [("revenue_yoy_asof", 1), ("netprofit_yoy_asof", 1), ("revenue_cagr_3y_asof", 1), ("net_profit_cagr_3y_asof", 1)],
    ),
    "flow_exposure_z": (
        "资金流暴露z值",
        [("main_flow_to_total_mv_20", 1), ("main_flow_persist_ratio_20", 1), ("north_hold_ratio_chg_20", 1)],
    ),
}


def physical_field_names(var_name: str) -> list[str]:
    return [
        f"{var_name}_rank_all_desc",
        f"{var_name}_pct_all_desc",
        f"{var_name}_z_all",
        f"{var_name}_rank_market_desc",
        f"{var_name}_pct_market_desc",
        f"{var_name}_rank_sw_l2_desc",
        f"{var_name}_pct_sw_l2_desc",
    ]


def view_extra_field_names(var_name: str) -> list[str]:
    return [
        f"{var_name}_z_market",
        f"{var_name}_rank_sw_l1_desc",
        f"{var_name}_pct_sw_l1_desc",
        f"{var_name}_z_sw_l1",
        f"{var_name}_z_sw_l2",
        f"{var_name}_rank_exchange_desc",
        f"{var_name}_pct_exchange_desc",
        f"{var_name}_z_exchange",
    ]
