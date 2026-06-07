import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = path.join(root, "outputs", "variable_dictionary");
const outputPath = path.join(outputDir, "global_variable_dictionary.xlsx");

const schema = JSON.parse(await fs.readFile(path.join(root, "config", "schema_registry.json"), "utf8"));
const variableFiles = (await fs.readdir(path.join(root, "config", "variables")))
  .filter((name) => name.endsWith(".json"))
  .sort();

const variables = [];
for (const fileName of variableFiles) {
  const payload = JSON.parse(await fs.readFile(path.join(root, "config", "variables", fileName), "utf8"));
  for (const item of payload.variables ?? []) {
    variables.push({ ...item, registry_file: fileName });
  }
}

const variablesByExact = new Map();
const variablesBySource = new Map();
for (const variable of variables) {
  if (variable.table && variable.name) pushMap(variablesByExact, `${variable.table}.${variable.name}`, variable);
  if (variable.table && variable.source_field) pushMap(variablesBySource, `${variable.table}.${variable.source_field}`, variable);
}

const TABLE_ZH = {
  trade_calendar: "交易日历",
  stock_basic_info: "股票基础信息",
  stock_daily: "股票日行情",
  stock_daily_basic: "每日基础指标",
  stock_adj_factor: "复权因子",
  stock_limit_price: "每日涨跌停价格",
  stock_company_info: "上市公司基础信息",
  stock_status_history: "股票上市状态历史",
  stock_moneyflow_daily: "个股资金流向",
  margin_detail: "融资融券交易明细",
  northbound_daily: "沪深港通资金汇总",
  northbound_holding: "沪深港通持股明细",
  top_list_daily: "龙虎榜每日明细",
  top_inst_detail: "龙虎榜机构席位明细",
  financial_dividend_raw: "分红送股原始数据",
  financial_disclosure_schedule: "财报披露计划",
  pledge_stat: "股权质押统计",
  index_basic_info: "指数基础信息",
  index_daily: "指数日行情",
  index_weight: "指数成分权重",
  sw_industry_classify: "申万行业分类",
  sw_industry_member: "申万行业成分历史",
  concept_basic: "概念板块基础信息",
  concept_member: "概念板块成分",
  financial_income_raw: "利润表原始明细",
  financial_balance_raw: "资产负债表原始明细",
  financial_cashflow_raw: "现金流量表原始明细",
  financial_indicator_raw: "财务指标原始数据",
  financial_event_raw: "财务增强事件原始数据",
  derived_daily_spine: "日频衍生变量主干表",
  derived_price_technical: "价格技术分析衍生表",
  derived_volume_liquidity: "成交与流动性衍生表",
  derived_return_momentum: "收益与动量衍生表",
  derived_volatility_risk: "波动与风险衍生表",
  derived_trading_constraint: "交易约束衍生表",
  derived_valuation_size: "估值与规模衍生表",
  derived_financial_asof: "财务可得时点衍生表",
  derived_financial_quality: "财务质量衍生表",
  derived_financial_growth: "财务成长衍生表",
  derived_corporate_action: "公司行为衍生表",
  derived_ownership_governance: "股权与治理衍生表",
  derived_ownership_governance_full_v: "股权与治理完整视图",
  ownership_governance_event_timeline_v: "股权与治理事件时间线视图",
  ownership_holder_concentration_v: "持有人集中度低频视图",
  derived_capital_flow: "资金流衍生表",
  derived_sector_concept_context: "行业与概念上下文衍生表",
  derived_index_market_context: "指数与市场环境衍生表",
  derived_cross_sectional: "截面转换衍生表",
  derived_composite_state: "综合事实状态衍生表",
  derived_composite_state_full_v: "综合事实状态完整视图",
  composite_state_condition_detail_v: "综合事实状态条件明细视图",
  composite_state_module_coverage_v: "综合事实状态模块覆盖视图",
  stock_features_core: "统一核心特征出口视图",
  stock_features_plus: "统一增强特征出口视图",
  stock_features_full: "统一完整特征出口视图",
};

const FIELD_ZH = {
  ts_code: "证券代码",
  con_code: "成分证券代码",
  index_code: "指数代码",
  concept_code: "概念代码",
  industry_code: "行业代码",
  symbol: "股票简称代码",
  name: "名称",
  short_name: "简称",
  fullname: "公司全称",
  enname: "英文名称",
  cnspell: "拼音缩写",
  trade_date: "交易日期",
  cal_date: "日历日期",
  ann_date: "公告日期",
  first_ann_date: "首次公告日期",
  end_date: "报告期",
  start_date: "开始日期",
  list_date: "上市日期",
  delist_date: "退市日期",
  entry_date: "纳入日期",
  out_date: "剔除日期",
  exp_date: "到期日期",
  effective_date: "生效日期",
  update_flag: "更新标识",
  exchange: "交易所",
  market: "市场板块",
  area: "地域",
  industry: "所属行业",
  list_status: "上市状态",
  is_open: "是否交易日",
  pretrade_date: "上一交易日",
  is_active: "是否当前有效",
  open: "开盘价",
  high: "最高价",
  low: "最低价",
  close: "收盘价",
  pre_close: "昨收价",
  change: "涨跌额",
  pct_chg: "涨跌幅",
  vol: "成交量",
  volume: "成交量",
  amount: "成交额",
  amplitude: "振幅",
  adj_factor: "复权因子",
  up_limit: "涨停价",
  down_limit: "跌停价",
  turnover_rate: "换手率",
  turnover_rate_free: "自由流通换手率",
  volume_ratio: "量比",
  pe: "市盈率",
  pe_ttm: "滚动市盈率",
  pb: "市净率",
  ps: "市销率",
  ps_ttm: "滚动市销率",
  dv_ratio: "股息率",
  dv_ttm: "滚动股息率",
  total_share: "总股本",
  float_share: "流通股本",
  free_share: "自由流通股本",
  total_mv: "总市值",
  circ_mv: "流通市值",
  report_type: "报告类型",
  comp_type: "公司类型",
  basic_eps: "基本每股收益",
  diluted_eps: "稀释每股收益",
  total_revenue: "营业总收入",
  revenue: "营业收入",
  total_cogs: "营业总成本",
  operating_cost: "营业成本",
  sell_exp: "销售费用",
  selling_expense: "销售费用",
  admin_exp: "管理费用",
  admin_expense: "管理费用",
  fin_exp: "财务费用",
  finance_expense: "财务费用",
  rd_exp: "研发费用",
  rd_expense: "研发费用",
  oper_profit: "营业利润",
  operating_profit: "营业利润",
  total_profit: "利润总额",
  income_tax: "所得税费用",
  n_income: "净利润",
  net_profit: "净利润",
  n_income_attr_p: "归母净利润",
  net_profit_attr_parent: "归母净利润",
  ebit: "息税前利润",
  ebitda: "息税折旧摊销前利润",
  money_cap: "货币资金",
  cash_and_equivalents: "货币资金",
  accounts_receivable: "应收账款",
  inventories: "存货",
  total_cur_assets: "流动资产合计",
  current_assets: "流动资产",
  fix_assets: "固定资产",
  fixed_assets: "固定资产",
  cip: "在建工程",
  construction_in_process: "在建工程",
  intan_assets: "无形资产",
  intangible_assets: "无形资产",
  goodwill: "商誉",
  total_assets: "资产总计",
  st_borr: "短期借款",
  short_term_borrowings: "短期借款",
  accounts_payable: "应付账款",
  total_cur_liab: "流动负债合计",
  current_liabilities: "流动负债",
  lt_borr: "长期借款",
  long_term_borrowings: "长期借款",
  bond_payable: "应付债券",
  bonds_payable: "应付债券",
  total_liab: "负债合计",
  total_liabilities: "负债合计",
  total_hldr_eqy_exc_min_int: "归母所有者权益",
  equity_attr_parent: "归母所有者权益",
  total_hldr_eqy_inc_min_int: "所有者权益合计",
  total_equity: "所有者权益合计",
  minority_int: "少数股东权益",
  minority_interest: "少数股东权益",
  n_cashflow_act: "经营活动现金流量净额",
  cf_from_operating: "经营活动现金流量净额",
  n_cashflow_inv_act: "投资活动现金流量净额",
  cf_from_investing: "投资活动现金流量净额",
  n_cash_flows_fnc_act: "筹资活动现金流量净额",
  cf_from_financing: "筹资活动现金流量净额",
  free_cashflow: "自由现金流",
  n_incr_cash_cash_equ: "现金及现金等价物净增加额",
  net_increase_in_cash: "现金及现金等价物净增加额",
  eps: "每股收益",
  dt_eps: "扣非每股收益",
  bps: "每股净资产",
  ocfps: "每股经营现金流",
  cfps: "每股现金流",
  gross_margin: "毛利率",
  grossprofit_margin: "销售毛利率",
  netprofit_margin: "净利率",
  roe: "净资产收益率",
  roe_waa: "加权平均净资产收益率",
  roe_dt: "扣非净资产收益率",
  roa: "总资产收益率",
  roic: "投入资本回报率",
  debt_to_assets: "资产负债率",
  current_ratio: "流动比率",
  quick_ratio: "速动比率",
  cash_ratio: "现金比率",
  assets_turn: "总资产周转率",
  netprofit_yoy: "净利润同比",
  dt_netprofit_yoy: "扣非净利润同比",
  tr_yoy: "营业总收入同比",
  or_yoy: "营业收入同比",
  buy_sm_vol: "小单买入量",
  buy_sm_amount: "小单买入金额",
  sell_sm_vol: "小单卖出量",
  sell_sm_amount: "小单卖出金额",
  buy_md_vol: "中单买入量",
  buy_md_amount: "中单买入金额",
  sell_md_vol: "中单卖出量",
  sell_md_amount: "中单卖出金额",
  buy_lg_vol: "大单买入量",
  buy_lg_amount: "大单买入金额",
  sell_lg_vol: "大单卖出量",
  sell_lg_amount: "大单卖出金额",
  buy_elg_vol: "特大单买入量",
  buy_elg_amount: "特大单买入金额",
  sell_elg_vol: "特大单卖出量",
  sell_elg_amount: "特大单卖出金额",
  net_mf_vol: "资金净流入量",
  net_mf_amount: "资金净流入金额",
  basic_eps: "基本每股收益",
  diluted_eps: "稀释每股收益",
  business_tax_surcharge: "税金及附加",
  operating_expense: "营业费用",
  asset_impairment_loss: "资产减值损失",
  investment_income: "投资收益",
  associate_investment_income: "联营及合营企业投资收益",
  fair_value_change_income: "公允价值变动收益",
  foreign_exchange_gain: "汇兑收益",
  non_operating_income: "营业外收入",
  non_operating_expense: "营业外支出",
  minority_profit: "少数股东损益",
  continued_net_profit: "持续经营净利润",
  total_comprehensive_income: "综合收益总额",
  comprehensive_income_parent: "归母综合收益",
  comprehensive_income_minority: "少数股东综合收益",
  interest_income: "利息收入",
  interest_expense: "利息支出",
  commission_income: "手续费及佣金收入",
  commission_expense: "手续费及佣金支出",
  premium_income: "保险业务收入",
  premium_earned: "已赚保费",
  insurance_expense: "保险业务支出",
  compensation_payout: "赔付支出",
  undistributed_profit: "未分配利润",
  trading_financial_assets: "交易性金融资产",
  derivative_financial_assets: "衍生金融资产",
  notes_receivable: "应收票据",
  accounts_receivable_bill: "应收票据及应收账款",
  prepayment: "预付款项",
  other_receivable: "其他应收款",
  total_other_receivable: "其他应收款合计",
  contract_assets: "合同资产",
  other_current_assets: "其他流动资产",
  total_noncurrent_assets: "非流动资产合计",
  long_term_equity_investment: "长期股权投资",
  investment_property: "投资性房地产",
  fixed_assets_total: "固定资产合计",
  construction_in_process_total: "在建工程合计",
  right_of_use_assets: "使用权资产",
  development_expenditure: "开发支出",
  long_term_deferred_expense: "长期待摊费用",
  deferred_tax_assets: "递延所得税资产",
  other_noncurrent_assets: "其他非流动资产",
  notes_payable: "应付票据",
  advance_receipts: "预收款项",
  contract_liabilities: "合同负债",
  payroll_payable: "应付职工薪酬",
  taxes_payable: "应交税费",
  interest_payable: "应付利息",
  dividend_payable: "应付股利",
  other_payable: "其他应付款",
  total_other_payable: "其他应付款合计",
  noncurrent_liability_due_1y: "一年内到期的非流动负债",
  other_current_liabilities: "其他流动负债",
  total_noncurrent_liabilities: "非流动负债合计",
  long_term_payable: "长期应付款",
  estimated_liabilities: "预计负债",
  deferred_income: "递延收益",
  deferred_tax_liabilities: "递延所得税负债",
  other_noncurrent_liabilities: "其他非流动负债",
  total_liabilities_and_equity: "负债和所有者权益总计",
  capital_reserve: "资本公积",
  surplus_reserve: "盈余公积",
  treasury_share: "库存股",
  other_comprehensive_income: "其他综合收益",
  special_reserve: "专项储备",
  tax_refund_received: "收到的税费返还",
  other_operating_cash_received: "收到其他与经营活动有关的现金",
  total_operating_cash_outflow: "经营活动现金流出小计",
  other_operating_cash_paid: "支付其他与经营活动有关的现金",
  cash_received_from_investment_withdrawal: "收回投资收到的现金",
  cash_received_from_asset_disposal: "处置固定资产、无形资产和其他长期资产收回的现金",
  cash_received_from_subsidiary_disposal: "处置子公司及其他营业单位收到的现金",
  total_investing_cash_inflow: "投资活动现金流入小计",
  cash_paid_for_subsidiary_acquisition: "取得子公司及其他营业单位支付的现金",
  other_investing_cash_paid: "支付其他与投资活动有关的现金",
  total_investing_cash_outflow: "投资活动现金流出小计",
  cash_received_from_investors: "吸收投资收到的现金",
  cash_received_from_bond_issue: "发行债券收到的现金",
  other_financing_cash_received: "收到其他与筹资活动有关的现金",
  total_financing_cash_inflow: "筹资活动现金流入小计",
  total_financing_cash_outflow: "筹资活动现金流出小计",
  other_financing_cash_paid: "支付其他与筹资活动有关的现金",
  fx_effect_on_cash: "汇率变动对现金及现金等价物的影响",
  begin_cash_balance: "期初现金余额",
  end_cash_balance: "期末现金余额",
  net_profit_indirect: "间接法净利润",
  asset_depreciation: "固定资产等折旧",
  intangible_asset_amortization: "无形资产摊销",
  deferred_expense_amortization: "长期待摊费用摊销",
  financial_expense_indirect: "间接法财务费用",
  investment_loss_indirect: "间接法投资损失",
  credit_impairment_loss_indirect: "间接法信用减值损失",
  inventory_decrease: "存货减少",
  operating_receivable_decrease: "经营性应收项目减少",
  operating_payable_increase: "经营性应付项目增加",
  updated_at: "更新时间",
};

const DERIVED_FORMULA_OVERRIDES = {
  "derived_daily_spine.adj_factor": "adj_factor = stock_adj_factor.adj_factor",
  "derived_daily_spine.up_limit": "up_limit = stock_limit_price.up_limit",
  "derived_daily_spine.down_limit": "down_limit = stock_limit_price.down_limit",
  "derived_daily_spine.open_raw": "open_raw = stock_daily.open",
  "derived_daily_spine.high_raw": "high_raw = stock_daily.high",
  "derived_daily_spine.low_raw": "low_raw = stock_daily.low",
  "derived_daily_spine.close_raw": "close_raw = stock_daily.close",
  "derived_daily_spine.pre_close_raw": "pre_close_raw = stock_daily.pre_close",
  "derived_daily_spine.volume": "volume = stock_daily.vol",
  "derived_daily_spine.amount": "amount = stock_daily.amount",
  "derived_daily_spine.close_hfq": "close_hfq = stock_daily.close * stock_adj_factor.adj_factor",
  "derived_daily_spine.open_hfq": "open_hfq = stock_daily.open * stock_adj_factor.adj_factor",
  "derived_daily_spine.high_hfq": "high_hfq = stock_daily.high * stock_adj_factor.adj_factor",
  "derived_daily_spine.low_hfq": "low_hfq = stock_daily.low * stock_adj_factor.adj_factor",
  "derived_daily_spine.pre_close_hfq": "pre_close_hfq = stock_daily.pre_close * stock_adj_factor.adj_factor",
  "derived_daily_spine.close_qfq": "close_qfq = stock_daily.close * stock_adj_factor.adj_factor / latest_adj_factor_asof",
  "derived_daily_spine.open_qfq": "open_qfq = stock_daily.open * stock_adj_factor.adj_factor / latest_adj_factor_asof",
  "derived_daily_spine.high_qfq": "high_qfq = stock_daily.high * stock_adj_factor.adj_factor / latest_adj_factor_asof",
  "derived_daily_spine.low_qfq": "low_qfq = stock_daily.low * stock_adj_factor.adj_factor / latest_adj_factor_asof",
  "derived_daily_spine.pre_close_qfq": "pre_close_qfq = stock_daily.pre_close * stock_adj_factor.adj_factor / latest_adj_factor_asof",
  "derived_daily_spine.ret_1_raw": "ret_1_raw = stock_daily.close / lag(stock_daily.close, 1) - 1",
  "derived_daily_spine.ret_1_hfq": "ret_1_hfq = close_hfq / lag(close_hfq, 1) - 1",
  "derived_daily_spine.ret_1_qfq": "ret_1_qfq = close_qfq / lag(close_qfq, 1) - 1",
  "derived_daily_spine.log_ret_1_hfq": "log_ret_1_hfq = ln(close_hfq / lag(close_hfq, 1))",
  "derived_daily_spine.log_ret_1": "log_ret_1 = log_ret_1_hfq",
  "derived_daily_spine.intraday_ret_raw": "intraday_ret_raw = stock_daily.close / stock_daily.open - 1",
  "derived_daily_spine.gap_ret_raw": "gap_ret_raw = stock_daily.open / stock_daily.pre_close - 1",
  "derived_daily_spine.limit_up_gap": "limit_up_gap = stock_limit_price.up_limit / stock_daily.close - 1",
  "derived_daily_spine.limit_down_gap": "limit_down_gap = stock_daily.close / stock_limit_price.down_limit - 1",
  "derived_daily_spine.limit_up_flag": "limit_up_flag = close_raw >= up_limit - 0.005",
  "derived_daily_spine.limit_down_flag": "limit_down_flag = close_raw <= down_limit + 0.005",
  "derived_daily_spine.touch_limit_up_flag": "touch_limit_up_flag = high_raw >= up_limit - 0.005",
  "derived_daily_spine.touch_limit_down_flag": "touch_limit_down_flag = low_raw <= down_limit + 0.005",
  "derived_daily_spine.open_limit_up_flag": "open_limit_up_flag = open_raw >= up_limit - 0.005",
  "derived_daily_spine.open_limit_down_flag": "open_limit_down_flag = open_raw <= down_limit + 0.005",
  "derived_daily_spine.price_valid_flag": "price_valid_flag = open/high/low/close 非空且 high >= max(open, close) 且 low <= min(open, close)",
  "derived_daily_spine.missing_reason": "missing_reason = case when stock_daily 缺失 then 'missing_daily' when adj_factor 缺失 then 'missing_adj_factor' when limit_price 缺失 then 'missing_limit_price' else null end",
};

const tables = schema.tables
  .filter((table) => !table.name.startsWith("metadata_"))
  .map((table) => ({
    ...table,
    table_type: resolveTableType(table),
  }));

const wb = Workbook.create();
const summary = wb.worksheets.add("Summary");
const indexSheet = wb.worksheets.add("Table_Index");

const sheetNames = new Map();
const indexRows = [];
let totalFields = 0;
let totalRegistered = 0;

for (const table of tables) {
  const sheetName = uniqueSheetName(table.name, sheetNames);
  sheetNames.set(sheetName, true);

  const sheet = wb.worksheets.add(sheetName);
  const rows = rowsForTable(table);
  writeSheet(sheet, rows, tableNameForExcel(sheetName));

  totalFields += rows.length;
  const registeredCount = rows.filter((row) => row["是否注册"] === "是").length;
  totalRegistered += registeredCount;
  indexRows.push({
    "Sheet名": sheetName,
    "物理表名": tableChineseName(table),
    "英文表名": table.name,
    "表类型": tableTypeLabel(table.table_type),
    "阶段": table.phase ?? "",
    "主键": (table.primary_key ?? []).join(", "),
    "字段数": rows.length,
    "已注册变量数": registeredCount,
    "表说明": table.description ?? "",
  });
}

summary.getRange("A1:G1").merge();
summary.getRange("A1").values = [["全局变量数据字典"]];
summary.getRange("A3:B13").values = [
  ["生成时间", new Date()],
  ["工作簿用途", "基础变量表、衍生变量表和统一出口视图的全局数据字典，每个对象一个 sheet。"],
  ["基础变量表数量", tables.filter((table) => table.table_type === "base").length],
  ["衍生变量表数量", tables.filter((table) => table.table_type === "derived").length],
  ["视图数量", tables.filter((table) => table.table_type === "view").length],
  ["对象总数", tables.length],
  ["Schema字段总数", totalFields],
  ["注册变量总数", variables.length],
  ["已匹配注册字段数", totalRegistered],
  ["维护规则", "新增或修改变量时刷新本文件，作为全局设计总账。"],
  ["变量注册文件", variableFiles.join(", ")],
];

summary.getRange("A14:D14").values = [["表类型", "表数量", "字段数", "已注册字段数"]];
const baseRows = indexRows.filter((row) => row["表类型"] === "基础变量表");
const derivedRows = indexRows.filter((row) => row["表类型"] === "衍生变量表");
const viewRows = indexRows.filter((row) => row["表类型"] === "视图");
summary.getRange("A15:D17").values = [
  ["基础变量表", baseRows.length, sum(baseRows, "字段数"), sum(baseRows, "已注册变量数")],
  ["衍生变量表", derivedRows.length, sum(derivedRows, "字段数"), sum(derivedRows, "已注册变量数")],
  ["视图", viewRows.length, sum(viewRows, "字段数"), sum(viewRows, "已注册变量数")],
];
summary.tables.add("A14:D17", true, "SummaryTable");

summary.getRange("A20:I20").values = [[
  "Sheet名",
  "物理表名",
  "英文表名",
  "表类型",
  "阶段",
  "主键",
  "字段数",
  "已注册变量数",
  "表说明",
]];
const summaryRows = indexRows.map((row) => [
  "",
  row["物理表名"],
  row["英文表名"],
  row["表类型"],
  row["阶段"],
  row["主键"],
  row["字段数"],
  row["已注册变量数"],
  row["表说明"],
]);
summary.getRangeByIndexes(20, 0, summaryRows.length, 9).values = summaryRows;
summary.getRangeByIndexes(20, 0, summaryRows.length, 1).formulas = indexRows.map((row) => [
  hyperlinkFormula(row["Sheet名"], row["Sheet名"]),
]);
summary.tables.add(`A20:I${20 + summaryRows.length}`, true, "SummaryTableLinks");

writeSheet(indexSheet, indexRows, "TableIndexTable");
indexSheet.getRangeByIndexes(1, 0, indexRows.length, 1).formulas = indexRows.map((row) => [
  hyperlinkFormula(row["Sheet名"], row["Sheet名"]),
]);

for (const sheet of wb.worksheets.items) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  const used = sheet.getUsedRange();
  used.format.font = { name: "Aptos", size: 10 };
  used.format.wrapText = true;
  used.format.autofitColumns();
  used.format.autofitRows();
  const header = used.getRow(0);
  header.format = { fill: "#305496", font: { bold: true, color: "#FFFFFF" } };
}

summary.getRange("A1:G1").format = { fill: "#244062", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A3:A13").format = { font: { bold: true }, fill: "#D9EAF7" };
summary.getRange("B3:B13").format = { wrapText: true };
summary.getRange("B3").setNumberFormat("yyyy-mm-dd hh:mm");

await fs.mkdir(outputDir, { recursive: true });
const preview = await wb.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
await fs.writeFile(path.join(outputDir, "global_variable_dictionary_summary.png"), new Uint8Array(await preview.arrayBuffer()));

const errors = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await saveWorkbook(xlsx, outputPath);

function rowsForTable(table) {
  const primaryKey = new Set(table.primary_key ?? []);
  return (table.fields ?? []).map((field) => {
    const matched = [
      ...(variablesByExact.get(`${table.name}.${field.name}`) ?? []),
      ...(variablesBySource.get(`${table.name}.${field.name}`) ?? []),
    ];
    const unique = uniqueVariables(matched);
    const variable = unique[0] ?? {};
    return {
      "字段名": field.name,
      "中文名": bestChineseLabel(unique, table, field),
      "字段含义": bestChineseDescription(unique, table, field),
      "衍生逻辑": formulaFor(table, field, variable),
      "复权口径": normalizePriceBasis(variable.price_basis ?? inferPriceBasis(table, field.name)),
      "用途": variable.use_case_zh ?? "",
      "物理表名": tableChineseName(table),
      "英文表名": table.name,
      "表类型": tableTypeLabel(table.table_type),
      "阶段": table.phase ?? "",
      "数据类型": field.dtype ?? "",
      "是否可空": String(field.nullable ?? true),
      "是否主键": primaryKey.has(field.name) ? "是" : "",
      "Schema说明": field.description ?? "",
      "是否注册": unique.length ? "是" : "否",
      "变量英文名": joinValues(unique.map((item) => item.name)),
      "模块": variable.module ?? "",
      "分类": variable.category ?? "",
      "层级": variable.tier ?? "",
      "单位": variable.unit ?? "",
      "频率": variable.frequency ?? "",
      "粒度": joinArray(variable.grain),
      "来源类型": variable.source_type ?? "",
      "来源API": variable.source_api ?? field.source_api ?? table.source_api ?? "",
      "来源字段": variable.source_field ?? field.source_field ?? "",
      "来源字段组": joinArray(variable.source_fields),
      "依赖字段": joinArray(variable.dependencies),
      "算法引用": variable.formula_ref ?? "",
      "点时安全": variable.point_in_time === undefined ? "" : String(variable.point_in_time),
      "最小历史": variable.min_history ?? "",
      "读取窗口": variable.read_window ?? "",
      "写入窗口": variable.write_window ?? "",
      "缺失策略": variable.missing_policy ?? "",
      "校验规则": JSON.stringify(variable.validation ?? {}, null, 0),
      "注册文件": joinValues(unique.map((item) => item.registry_file)),
    };
  });
}

function writeSheet(sheet, rows, tableName) {
  if (!rows.length) {
    sheet.getRange("A1").values = [["No rows"]];
    return;
  }
  const headers = Object.keys(rows[0]);
  sheet.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
  const matrix = rows.map((row) => headers.map((header) => row[header] ?? ""));
  sheet.getRangeByIndexes(1, 0, matrix.length, headers.length).values = matrix;
  sheet.tables.add(`A1:${columnName(headers.length)}${matrix.length + 1}`, true, tableName);
}

function bestChineseLabel(unique, table, field) {
  const registered = unique.map((item) => item.label_zh).find(containsChinese);
  if (registered) return registered;
  if (FIELD_ZH[field.name]) return FIELD_ZH[field.name];

  const sourceField = unique.find((item) => item.source_field)?.source_field ?? field.source_field;
  if (sourceField && FIELD_ZH[sourceField]) return FIELD_ZH[sourceField];

  return humanizeFieldName(field.name);
}

function bestChineseDescription(unique, table, field) {
  const registered = unique.map((item) => item.description_zh).find(containsChinese);
  if (registered) return registered;

  const label = bestChineseLabel(unique, table, field);
  const sourceApi = unique[0]?.source_api ?? field.source_api ?? table.source_api ?? "";
  const sourceField = unique[0]?.source_field ?? field.source_field ?? field.name;
  if (table.table_type === "derived") {
    const formula = formulaFor(table, field, unique[0] ?? {});
    return formula ? `${label}，由${formula}计算。` : `${label}，由衍生变量构建流程生成。`;
  }
  return sourceApi ? `${label}，来自 ${sourceApi}.${sourceField}。` : `${label}。`;
}

function formulaFor(table, field, variable) {
  const override = DERIVED_FORMULA_OVERRIDES[`${table.name}.${field.name}`];
  if (override) return override;
  if (!["derived", "view"].includes(table.table_type)) return "";
  if ((table.primary_key ?? []).includes(field.name) || field.name === "updated_at") return "";

  const formulaRef = variable.formula_ref ?? "";
  if (formulaRef) return `${field.name} = ${formulaRef}`;

  const deps = joinArray(variable.dependencies) || joinArray(variable.source_fields);
  if (deps) return `${field.name} = f(${deps})`;

  const sourceField = variable.source_field ?? field.source_field ?? "";
  const sourceApi = variable.source_api ?? field.source_api ?? "";
  if (sourceField || sourceApi) {
    return `${field.name} = ${[sourceApi, sourceField].filter(Boolean).join(".")}`;
  }
  if (field.description) return field.description.includes("=") ? field.description : `${field.name} = ${field.description}`;
  return "";
}

function inferPriceBasis(table, fieldName) {
  if (!["derived", "view"].includes(table.table_type)) return "";
  if (fieldName.includes("_hfq") || fieldName === "close_hfq" || fieldName === "log_ret_1") return "后复权";
  if (fieldName.includes("_qfq")) return "前复权";
  if (fieldName.includes("_raw") || ["up_limit", "down_limit"].includes(fieldName)) return "不复权";
  return "";
}

function normalizePriceBasis(value) {
  const text = String(value ?? "");
  const map = {
    raw: "不复权",
    hfq: "后复权",
    qfq: "前复权",
    none: "不复权",
    mixed: "混合口径",
  };
  return map[text] ?? text;
}

function tableChineseName(table) {
  return TABLE_ZH[table.name] ?? table.description ?? table.name;
}

function resolveTableType(table) {
  if (table.table_type === "view") return "view";
  if (table.name.startsWith("derived_")) return "derived";
  return "base";
}

function tableTypeLabel(tableType) {
  if (tableType === "derived") return "衍生变量表";
  if (tableType === "view") return "视图";
  return "基础变量表";
}

function containsChinese(value) {
  return /[\u3400-\u9FFF]/.test(String(value ?? ""));
}

function humanizeFieldName(fieldName) {
  return fieldName
    .split("_")
    .filter(Boolean)
    .map((part) => FIELD_ZH[part] ?? part)
    .join("/");
}

function pushMap(map, key, value) {
  if (!map.has(key)) map.set(key, []);
  map.get(key).push(value);
}

function uniqueVariables(items) {
  const seen = new Set();
  const result = [];
  for (const item of items) {
    const key = `${item.registry_file}.${item.table}.${item.name}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}

function joinArray(value) {
  if (!value) return "";
  return Array.isArray(value) ? value.join(", ") : String(value);
}

function joinValues(values) {
  return [...new Set(values.filter((value) => value !== undefined && value !== null && value !== ""))].join(" | ");
}

function uniqueSheetName(tableName, used) {
  const aliases = [
    [/^derived_/, "d_"],
    [/^financial_/, "fin_"],
    [/^stock_/, "stk_"],
    [/^metadata_/, "meta_"],
    [/_daily$/, "_d"],
  ];
  let base = tableName;
  for (const [pattern, replacement] of aliases) base = base.replace(pattern, replacement);
  base = base.replace(/[:\\/?*[\]]/g, "_");
  if (base.length > 31) base = base.slice(0, 31);
  let candidate = base;
  let i = 2;
  while (used.has(candidate)) {
    const suffix = `_${i}`;
    candidate = `${base.slice(0, 31 - suffix.length)}${suffix}`;
    i += 1;
  }
  return candidate;
}

function tableNameForExcel(sheetName) {
  return `${sheetName.replace(/[^A-Za-z0-9_]/g, "_").slice(0, 240)}Table`;
}

function columnName(count) {
  let n = count;
  let name = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    name = String.fromCharCode(65 + rem) + name;
    n = Math.floor((n - 1) / 26);
  }
  return name;
}

function sum(rows, key) {
  return rows.reduce((acc, row) => acc + Number(row[key] ?? 0), 0);
}

function hyperlinkFormula(sheetName, label) {
  const escapedSheet = sheetName.replace(/'/g, "''");
  const escapedLabel = String(label).replace(/"/g, '""');
  return `=HYPERLINK("#'${escapedSheet}'!A1","${escapedLabel}")`;
}

async function saveWorkbook(xlsx, targetPath) {
  try {
    await xlsx.save(targetPath);
    console.log(targetPath);
  } catch (error) {
    if (error?.code !== "EBUSY") throw error;
    const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
    const fallback = path.join(outputDir, `global_variable_dictionary_${stamp}.xlsx`);
    await xlsx.save(fallback);
    console.log(`主文件被占用，已生成副本: ${fallback}`);
  }
}
