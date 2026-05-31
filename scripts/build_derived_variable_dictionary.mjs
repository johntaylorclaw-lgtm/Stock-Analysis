import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = path.join(root, "outputs", "phase3");
const outputPath = path.join(outputDir, "derived_variable_dictionary_v1.xlsx");

const schema = JSON.parse(await fs.readFile(path.join(root, "config", "schema_registry.json"), "utf8"));
const registry = JSON.parse(await fs.readFile(path.join(root, "config", "variables", "derived_variables.json"), "utf8"));
const audit = JSON.parse(await fs.readFile(path.join(outputDir, "derived_variable_audit.json"), "utf8"));

const derivedTables = schema.tables.filter((table) => table.name.startsWith("derived_"));
const registryByTableField = new Map(registry.variables.map((item) => [`${item.table}.${item.name}`, item]));
const auditByTable = new Map(audit.rows.map((item) => [item.table, item]));

const landedFields = [];
for (const table of derivedTables) {
  for (const field of table.fields ?? []) {
    if (field.name === "updated_at") continue;
    const variable = registryByTableField.get(`${table.name}.${field.name}`);
    const tableAudit = auditByTable.get(table.name) ?? {};
    landedFields.push({
      table: table.name,
      field: field.name,
      registered: variable ? "YES" : "NO",
      module: variable?.module ?? inferModule(table.name),
      label_zh: variable?.label_zh ?? field.description ?? "",
      dtype: field.dtype ?? variable?.dtype ?? "",
      tier: variable?.tier ?? "",
      category: variable?.category ?? "",
      frequency: variable?.frequency ?? "daily",
      grain: (variable?.grain ?? table.primary_key ?? []).join(", "),
      source_type: variable?.source_type ?? "derived",
      dependencies: (variable?.dependencies ?? []).join(", "),
      formula_ref: variable?.formula_ref ?? "",
      point_in_time: String(variable?.point_in_time ?? true),
      min_history: variable?.min_history ?? "",
      read_window: variable?.read_window ?? "",
      write_window: variable?.write_window ?? "",
      missing_policy: variable?.missing_policy ?? "",
      validation: JSON.stringify(variable?.validation ?? {}, null, 0),
      rows_landed: tableAudit.rows ?? "",
      min_trade_date: tableAudit.min_date ?? "",
      max_trade_date: tableAudit.max_date ?? "",
      stock_count: tableAudit.stocks ?? "",
      non_null_rate: tableAudit.primary_variable === field.name ? tableAudit.non_null_rate ?? "" : "",
      min_value: tableAudit.primary_variable === field.name ? tableAudit.min_value ?? "" : "",
      max_value: tableAudit.primary_variable === field.name ? tableAudit.max_value ?? "" : "",
      table_description: table.description ?? "",
    });
  }
}

const registered = registry.variables.map((item) => ({
  name: item.name ?? "",
  table: item.table ?? "",
  module: item.module ?? "",
  label_zh: item.label_zh ?? "",
  tier: item.tier ?? "",
  category: item.category ?? "",
  dtype: item.dtype ?? "",
  unit: item.unit ?? "",
  frequency: item.frequency ?? "",
  grain: (item.grain ?? []).join(", "),
  dependencies: (item.dependencies ?? []).join(", "),
  formula_ref: item.formula_ref ?? "",
  params: JSON.stringify(item.params ?? {}, null, 0),
  price_basis: item.price_basis ?? "",
  point_in_time: String(item.point_in_time ?? ""),
  min_history: item.min_history ?? "",
  read_window: item.read_window ?? "",
  write_window: item.write_window ?? "",
  missing_policy: item.missing_policy ?? "",
  validation: JSON.stringify(item.validation ?? {}, null, 0),
}));

const moduleSummary = Object.entries(countBy(landedFields, "module"))
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([module, field_count]) => ({ module, field_count }));

const gaps = landedFields.filter((row) => row.registered === "NO");
const qualityRows = audit.rows.map((row) => ({
  module: row.module,
  table: row.table,
  primary_variable: row.primary_variable,
  rows: row.rows,
  min_date: row.min_date,
  max_date: row.max_date,
  stock_count: row.stocks,
  non_null_rate: row.non_null_rate,
  min_value: row.min_value,
  max_value: row.max_value,
}));

const wb = Workbook.create();
const summary = wb.worksheets.add("Summary");
const landedSheet = wb.worksheets.add("Landed_Derived_Fields");
const registeredSheet = wb.worksheets.add("Registered_Derived");
const qualitySheet = wb.worksheets.add("Quality_Audit");
const gapsSheet = wb.worksheets.add("Registration_Gaps");
const moduleSheet = wb.worksheets.add("Module_Summary");

summary.getRange("A1:F1").merge();
summary.getRange("A1").values = [["Phase 3 Derived Variable Dictionary"]];
summary.getRange("A3:B12").values = [
  ["Generated At", new Date()],
  ["Audit Window", `${audit.window_start} to ${audit.window_end}`],
  ["Base stock_daily max trade date", audit.base_stock_daily_max_trade_date],
  ["Derived tables", derivedTables.length],
  ["Actual landed fields", landedFields.length],
  ["Registered derived variables", registered.length],
  ["Unregistered landed fields", gaps.length],
  ["Quality rows", qualityRows.length],
  ["Build mode", "Phase 3 daily recent-window build"],
  ["Review focus", "Check actual landed fields, registry alignment, coverage, and non-null rates."],
];
summary.getRange("A1:F1").format = { fill: "#244062", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A3:A12").format = { font: { bold: true }, fill: "#D9EAF7" };
summary.getRange("B3:B12").format = { wrapText: true };
summary.getRange("B3").setNumberFormat("yyyy-mm-dd hh:mm");
summary.getRange("A14:D14").values = [["Module", "Landed fields", "Primary table rows max", "Notes"]];
const summaryRows = moduleSummary.map((row) => {
  const moduleAuditRows = audit.rows.filter((item) => item.module === row.module);
  const maxRows = moduleAuditRows.reduce((acc, item) => Math.max(acc, item.rows ?? 0), 0);
  return [row.module, row.field_count, maxRows, ""];
});
summary.getRangeByIndexes(14, 0, summaryRows.length, 4).values = summaryRows;
summary.tables.add(`A14:D${14 + summaryRows.length}`, true, "SummaryModuleTable");

writeSheet(landedSheet, landedFields, "LandedDerivedFieldsTable");
writeSheet(registeredSheet, registered, "RegisteredDerivedTable");
writeSheet(qualitySheet, qualityRows, "QualityAuditTable");
writeSheet(gapsSheet, gaps, "RegistrationGapsTable");
writeSheet(moduleSheet, moduleSummary, "ModuleSummaryTable");

for (const sheet of [summary, landedSheet, registeredSheet, qualitySheet, gapsSheet, moduleSheet]) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  const used = sheet.getUsedRange();
  used.format.wrapText = true;
  used.format.font = { name: "Aptos", size: 10 };
  used.format.autofitColumns();
  used.format.autofitRows();
}

for (const sheet of [landedSheet, registeredSheet, qualitySheet, gapsSheet, moduleSheet]) {
  sheet.getUsedRange().getRow(0).format = { fill: "#305496", font: { bold: true, color: "#FFFFFF" } };
}
qualitySheet.getRange("H2:H200").format.numberFormat = "0.00%";
landedSheet.getRange("V2:V200").format.numberFormat = "0.00%";

await fs.mkdir(outputDir, { recursive: true });
const preview = await wb.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
await fs.writeFile(path.join(outputDir, "derived_variable_dictionary_summary.png"), new Uint8Array(await preview.arrayBuffer()));

const errors = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

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

function inferModule(tableName) {
  return tableName.replace(/^derived_/, "");
}
