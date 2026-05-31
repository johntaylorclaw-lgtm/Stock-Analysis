import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = path.join(root, "outputs", "phase2");
const outputPath = path.join(outputDir, "base_variable_dictionary_v2.xlsx");

const schema = JSON.parse(await fs.readFile(path.join(root, "config", "schema_registry.json"), "utf8"));
const baseRegistry = JSON.parse(await fs.readFile(path.join(root, "config", "variables", "base_variables.json"), "utf8"));
const draftPath = path.join(root, "outputs", "phase2", "base_variables_draft.json");
const draftRegistry = await fileExists(draftPath)
  ? JSON.parse(await fs.readFile(draftPath, "utf8"))
  : { variables: [] };

const registered = baseRegistry.variables.map((item) => ({
  name: item.name ?? "",
  label_zh: item.label_zh ?? "",
  table: item.table ?? "",
  module: item.module ?? "",
  category: item.category ?? "",
  tier: item.tier ?? "",
  dtype: item.dtype ?? "",
  unit: item.unit ?? "",
  frequency: item.frequency ?? "",
  grain: (item.grain ?? []).join(", "),
  source_type: item.source_type ?? "",
  source_api: item.source_api ?? "",
  source_field: item.source_field ?? "",
  price_basis: item.price_basis ?? "",
  point_in_time: String(item.point_in_time ?? ""),
  missing_policy: item.missing_policy ?? "",
  validation: JSON.stringify(item.validation ?? {}, null, 0),
}));

const registeredKeys = new Set(registered.map((row) => `${row.table}.${row.source_field || row.name}`));
const draft = draftRegistry.variables.map((item) => ({
  name: item.name ?? "",
  label_zh: item.label_zh ?? "",
  table: item.table ?? "",
  module: item.module ?? "",
  category: item.category ?? "",
  tier: item.tier ?? "",
  dtype: item.dtype ?? "",
  unit: item.unit ?? "",
  frequency: item.frequency ?? "",
  grain: (item.grain ?? []).join(", "),
  source_type: item.source_type ?? "",
  source_api: item.source_api ?? "",
  source_field: item.source_field ?? "",
  price_basis: item.price_basis ?? "",
  point_in_time: String(item.point_in_time ?? ""),
  missing_policy: item.missing_policy ?? "",
  validation: JSON.stringify(item.validation ?? {}, null, 0),
}));

const skipFields = new Set(["updated_at", "payload_json", "record_key", "error_message"]);
const candidates = [];
for (const table of schema.tables) {
  for (const field of table.fields ?? []) {
    if (skipFields.has(field.name)) continue;
    const sourceApi = field.source_api ?? table.source_api ?? "";
    const key = `${table.name}.${field.name}`;
    candidates.push({
      variable_name: field.name,
      label_zh: "",
      table: table.name,
      phase: table.phase ?? "",
      module_suggestion: suggestModule(table.name, sourceApi),
      category_suggestion: suggestCategory(table.name, field.name, sourceApi),
      tier_suggestion: table.phase === "P0" ? "p0" : "core",
      dtype: field.dtype ?? "",
      unit_suggestion: suggestUnit(field.name, field.dtype),
      frequency_suggestion: suggestFrequency(table.name),
      grain: (table.primary_key ?? []).join(", "),
      source_type: sourceApi === "local_derived" ? "derived" : "tushare",
      source_api: sourceApi,
      source_field: field.source_field ?? field.name,
      price_basis: suggestPriceBasis(table.name, field.name),
      point_in_time: "TRUE",
      missing_policy_suggestion: field.nullable === false ? "required" : "source_optional",
      registered: registeredKeys.has(key) ? "YES" : "NO",
      description: field.description ?? "",
    });
  }
}

const gaps = candidates.filter((row) => row.registered === "NO" && !row.table.startsWith("metadata_"));
const byModule = countBy(candidates, "module_suggestion");
const byTable = countBy(candidates, "table");
const registeredByTable = countBy(registered, "table");

const wb = Workbook.create();
const summary = wb.worksheets.add("Summary");
const registeredSheet = wb.worksheets.add("Registered_Base");
const candidatesSheet = wb.worksheets.add("Schema_Candidates");
const gapsSheet = wb.worksheets.add("Coverage_Gaps");
const draftSheet = wb.worksheets.add("Draft_Registry");
const modulesSheet = wb.worksheets.add("Module_Summary");

summary.getRange("A1:F1").merge();
summary.getRange("A1").values = [["Base Variable Dictionary"]];
summary.getRange("A3:B11").values = [
  ["Generated At", new Date()],
  ["Registered base variables", registered.length],
  ["Draft base variables", draft.length],
  ["Schema-derived candidate variables", candidates.length],
  ["Unregistered candidates excluding metadata", gaps.length],
  ["Schema tables", schema.tables.length],
  ["Review status", gaps.length === 0 ? "Current schema-derived base variables are registered." : "Use Coverage_Gaps as expansion backlog."],
  ["Workbook purpose", "Review registered base variables and schema-derived candidates."],
  ["Next action", gaps.length === 0 ? "Proceed with Phase 2 confirmation review." : "Expand config/variables/base_variables.json from remaining gaps."],
];
summary.getRange("A1:F1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A3:A11").format = { font: { bold: true }, fill: "#D9EAF7" };
summary.getRange("B3:B11").format = { wrapText: true };
summary.getRange("B3").setNumberFormat("yyyy-mm-dd hh:mm");
summary.getRange("A12:D12").values = [["Table", "Schema candidates", "Registered variables", "Gap"]];
const tableRows = Object.entries(byTable)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([table, count]) => [table, count, registeredByTable[table] ?? 0, count - (registeredByTable[table] ?? 0)]);
summary.getRangeByIndexes(12, 0, tableRows.length, 4).values = tableRows;
summary.tables.add(`A12:D${12 + tableRows.length}`, true, "SummaryTable");

writeSheet(registeredSheet, registered, "RegisteredBaseTable");
writeSheet(candidatesSheet, candidates, "SchemaCandidatesTable");
writeSheet(gapsSheet, gaps, "CoverageGapsTable");
writeSheet(draftSheet, draft, "DraftRegistryTable");
writeSheet(
  modulesSheet,
  Object.entries(byModule).map(([module, count]) => ({ module, candidate_count: count })),
  "ModuleSummaryTable",
);

for (const sheet of [summary, registeredSheet, candidatesSheet, gapsSheet, draftSheet, modulesSheet]) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  const used = sheet.getUsedRange();
  used.format.wrapText = true;
  used.format.font = { name: "Aptos", size: 10 };
  used.format.autofitColumns();
  used.format.autofitRows();
}

const headerSheets = [registeredSheet, candidatesSheet, gapsSheet, draftSheet, modulesSheet];
for (const sheet of headerSheets) {
  const used = sheet.getUsedRange();
  const firstRow = used.getRow(0);
  firstRow.format = { fill: "#305496", font: { bold: true, color: "#FFFFFF" } };
}

const preview = await wb.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(path.join(outputDir, "base_variable_dictionary_summary.png"), new Uint8Array(await preview.arrayBuffer()));

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(outputPath);
console.log(outputPath);

function writeSheet(sheet, rows, tableName) {
  if (rows.length === 0) {
    sheet.getRange("A1").values = [["No rows"]];
    return;
  }
  const headers = Object.keys(rows[0]);
  sheet.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
  const matrix = rows.map((row) => headers.map((header) => row[header] ?? ""));
  sheet.getRangeByIndexes(1, 0, matrix.length, headers.length).values = matrix;
  sheet.tables.add(`A1:${columnName(headers.length)}${matrix.length + 1}`, true, tableName);
}

async function fileExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

function countBy(rows, key) {
  const result = {};
  for (const row of rows) {
    const value = row[key] || "";
    result[value] = (result[value] ?? 0) + 1;
  }
  return result;
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

function suggestModule(table, sourceApi) {
  if (table.includes("financial")) return "base_financial";
  if (table.includes("daily_basic")) return "base_valuation";
  if (table.includes("daily") || table.includes("adj_factor") || table.includes("limit")) return "base_price";
  if (table.includes("index")) return "base_index";
  if (table.includes("concept") || table.includes("industry")) return "base_sector";
  if (table.includes("calendar")) return "base_calendar";
  if (sourceApi === "stock_basic") return "base_security";
  return "base_misc";
}

function suggestCategory(table, field, sourceApi) {
  if (table.includes("financial_income")) return "income_statement";
  if (table.includes("financial_balance")) return "balance_sheet";
  if (table.includes("financial_cashflow")) return "cashflow_statement";
  if (table.includes("financial_indicator")) return "financial_indicator";
  if (table.includes("financial_event")) return "financial_event";
  if (table.includes("daily_basic")) return "valuation";
  if (["open", "high", "low", "close", "pre_close", "change", "pct_chg", "volume", "amount"].includes(field)) return "ohlcv";
  if (table.includes("limit")) return "limit_price";
  if (table.includes("adj_factor")) return "adjustment";
  if (table.includes("index_weight")) return "constituent";
  if (table.includes("index_daily")) return "index_ohlcv";
  if (table.includes("concept")) return "concept";
  if (table.includes("industry")) return "industry";
  if (sourceApi === "stock_basic") return "security_master";
  return "base";
}

function suggestFrequency(table) {
  if (table.includes("daily") || table.includes("limit") || table.includes("adj_factor")) return "daily";
  if (table.includes("financial_income") || table.includes("financial_balance") || table.includes("financial_cashflow") || table.includes("financial_indicator")) return "quarterly";
  if (table.includes("weight") || table.includes("event") || table.includes("member")) return "event";
  if (table.includes("basic") || table.includes("classify")) return "snapshot";
  return "snapshot";
}

function suggestUnit(field, dtype) {
  if (field.includes("date") || field.includes("code") || dtype === "VARCHAR") return "none";
  if (field.includes("pct") || field.includes("rate") || field.includes("ratio") || field.includes("weight") || field.includes("margin") || field.includes("roe") || field.includes("roa")) return "percent_or_ratio";
  if (field.includes("price") || ["open", "high", "low", "close", "pre_close", "up_limit", "down_limit"].includes(field)) return "yuan";
  if (field.includes("volume") || field === "vol") return "lot";
  if (field.includes("amount") || field.includes("profit") || field.includes("asset") || field.includes("liab") || field.includes("cash") || field.includes("revenue")) return "yuan";
  return "none";
}

function suggestPriceBasis(table, field) {
  if (["open", "high", "low", "close", "pre_close"].includes(field)) return "raw";
  if (table.includes("adj_factor")) return "adjustment_factor";
  return "not_price";
}
