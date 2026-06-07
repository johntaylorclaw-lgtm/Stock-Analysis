from __future__ import annotations

from stock_maintainance.database import connect, init_database
from stock_maintainance.schema import quote_ident


FIELD_MAP: dict[str, dict[str, str]] = {
    "financial_income_raw": {
        "basic_eps": "basic_eps",
        "diluted_eps": "diluted_eps",
        "business_tax_surcharge": "biz_tax_surchg",
        "operating_expense": "oper_exp",
        "asset_impairment_loss": "assets_impair_loss",
        "investment_income": "invest_income",
        "associate_investment_income": "ass_invest_income",
        "fair_value_change_income": "fv_value_chg_gain",
        "foreign_exchange_gain": "forex_gain",
        "non_operating_income": "non_oper_income",
        "non_operating_expense": "non_oper_exp",
        "minority_profit": "minority_gain",
        "continued_net_profit": "continued_net_profit",
        "total_comprehensive_income": "t_compr_income",
        "comprehensive_income_parent": "compr_inc_attr_p",
        "comprehensive_income_minority": "compr_inc_attr_m_s",
        "interest_income": "int_income",
        "interest_expense": "int_exp",
        "commission_income": "comm_income",
        "commission_expense": "comm_exp",
        "premium_income": "prem_income",
        "premium_earned": "prem_earned",
        "insurance_expense": "insurance_exp",
        "compensation_payout": "compens_payout",
        "undistributed_profit": "undist_profit",
    },
    "financial_balance_raw": {
        "trading_financial_assets": "trad_asset",
        "derivative_financial_assets": "deriv_assets",
        "notes_receivable": "notes_receiv",
        "accounts_receivable_bill": "accounts_receiv_bill",
        "prepayment": "prepayment",
        "other_receivable": "oth_receiv",
        "total_other_receivable": "oth_rcv_total",
        "contract_assets": "contract_assets",
        "other_current_assets": "oth_cur_assets",
        "total_noncurrent_assets": "total_nca",
        "long_term_equity_investment": "lt_eqt_invest",
        "investment_property": "invest_real_estate",
        "fixed_assets_total": "fix_assets_total",
        "construction_in_process_total": "cip_total",
        "right_of_use_assets": "use_right_assets",
        "development_expenditure": "r_and_d",
        "long_term_deferred_expense": "lt_amor_exp",
        "deferred_tax_assets": "defer_tax_assets",
        "other_noncurrent_assets": "oth_nca",
        "notes_payable": "notes_payable",
        "advance_receipts": "adv_receipts",
        "contract_liabilities": "contract_liab",
        "payroll_payable": "payroll_payable",
        "taxes_payable": "taxes_payable",
        "interest_payable": "int_payable",
        "dividend_payable": "div_payable",
        "other_payable": "oth_payable",
        "total_other_payable": "oth_pay_total",
        "noncurrent_liability_due_1y": "non_cur_liab_due_1y",
        "other_current_liabilities": "oth_cur_liab",
        "total_noncurrent_liabilities": "total_ncl",
        "long_term_payable": "lt_payable",
        "estimated_liabilities": "estimated_liab",
        "deferred_income": "defer_inc_non_cur_liab",
        "deferred_tax_liabilities": "defer_tax_liab",
        "other_noncurrent_liabilities": "oth_ncl",
        "total_liabilities_and_equity": "total_liab_hldr_eqy",
        "capital_reserve": "cap_rese",
        "surplus_reserve": "surplus_rese",
        "undistributed_profit": "undistr_porfit",
        "treasury_share": "treasury_share",
        "other_comprehensive_income": "oth_comp_income",
        "special_reserve": "special_rese",
    },
    "financial_cashflow_raw": {
        "tax_refund_received": "recp_tax_rends",
        "other_operating_cash_received": "c_fr_oth_operate_a",
        "total_operating_cash_outflow": "st_cash_out_act",
        "other_operating_cash_paid": "oth_cash_pay_oper_act",
        "cash_received_from_investment_withdrawal": "c_recp_return_invest",
        "cash_received_from_asset_disposal": "n_recp_disp_fiolta",
        "cash_received_from_subsidiary_disposal": "n_recp_disp_sobu",
        "total_investing_cash_inflow": "stot_inflows_inv_act",
        "cash_paid_for_subsidiary_acquisition": "n_disp_subs_oth_biz",
        "other_investing_cash_paid": "oth_pay_ral_inv_act",
        "total_investing_cash_outflow": "stot_out_inv_act",
        "cash_received_from_investors": "c_recp_cap_contrib",
        "cash_received_from_bond_issue": "proc_issue_bonds",
        "other_financing_cash_received": "oth_cash_recp_ral_fnc_act",
        "total_financing_cash_inflow": "stot_cash_in_fnc_act",
        "total_financing_cash_outflow": "stot_cashout_fnc_act",
        "other_financing_cash_paid": "oth_cashpay_ral_fnc_act",
        "fx_effect_on_cash": "eff_fx_flu_cash",
        "begin_cash_balance": "beg_bal_cash",
        "end_cash_balance": "end_bal_cash",
        "net_profit_indirect": "net_profit",
        "asset_depreciation": "depr_fa_coga_dpba",
        "intangible_asset_amortization": "amort_intang_assets",
        "deferred_expense_amortization": "lt_amort_deferred_exp",
        "financial_expense_indirect": "finan_exp",
        "investment_loss_indirect": "invest_loss",
        "credit_impairment_loss_indirect": "credit_impa_loss",
        "inventory_decrease": "decr_inventories",
        "operating_receivable_decrease": "decr_oper_payable",
        "operating_payable_increase": "incr_oper_payable",
    },
}


def main() -> None:
    with connect() as con:
        init_database(con)
        for table, fields in FIELD_MAP.items():
            assignments = []
            for column, source_field in fields.items():
                assignments.append(
                    f"{quote_ident(column)} = COALESCE({quote_ident(column)}, "
                    f"TRY_CAST(json_extract_string(payload_json, '$.{source_field}') AS DOUBLE))"
                )
            con.execute(f"UPDATE {quote_ident(table)} SET {', '.join(assignments)} WHERE payload_json IS NOT NULL")
            print(f"backfilled {table}: {len(fields)} fields")


if __name__ == "__main__":
    main()
