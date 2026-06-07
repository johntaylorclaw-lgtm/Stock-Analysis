import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const samplePath = process.argv[2];
const tsCode = process.argv[3] ?? "AUTO";
const outputPrefix = process.argv[4] ?? "phase5_sample_stock";
if (!samplePath) {
  throw new Error("usage: node scripts/build_phase5_sample_stock_excel.mjs <sample-json> [ts_code] [output_prefix]");
}

const payload = JSON.parse(await fs.readFile(samplePath, "utf8"));
const outputDir = path.join(root, "outputs", "phase5");
const safeCode = tsCode.replace(".", "_");
const outputPath = path.join(outputDir, `${outputPrefix}_${safeCode}.xlsx`);

const wb = Workbook.create();
const summary = wb.worksheets.add("Summary");
const quality = wb.worksheets.add("Quality_Report");
const baseIndex = wb.worksheets.add("Base_Index");
const derivedIndex = wb.worksheets.add("Derived_Index");

summary.getRange("A1:H1").merge();
summary.getRange("A1").values = [["Phase 5 Stock Sample Workbook"]];
summary.getRange("A3:B12").values = [
  ["证券代码", payload.stock.ts_code ?? tsCode],
  ["证券名称", payload.stock.name ?? ""],
  ["市场", payload.stock.market ?? ""],
  ["交易所", payload.stock.exchange ?? ""],
  ["样本起始日期", payload.filters.start_date ?? ""],
  ["样本结束日期", payload.filters.end_date ?? ""],
  ["每表最大行数", payload.filters.row_limit ?? ""],
  ["基础表数量", payload.base_tables.length],
  ["衍生表数量", payload.derived_tables.length],
  ["生成时间", payload.generated_at],
];
summary.getRange("D3:H7").values = [
  ["工作簿结构", "", "", "", ""],
  ["Summary", "样本参数与股票信息", "", "", ""],
  ["Base_Index", "基础变量样本表索引", "", "", ""],
  ["Derived_Index", "衍生变量样本表索引", "", "", ""],
  ["Quality_Report", "每张表的样本覆盖与重复键摘要", "", "", ""],
];

writeSheet(quality, payload.quality_report, "QualityReportTable");
writeIndex(baseIndex, payload.base_tables, "BaseIndexTable");
writeIndex(derivedIndex, payload.derived_tables, "DerivedIndexTable");

const usedNames = new Set(["Summary", "Quality_Report", "Base_Index", "Derived_Index"]);
for (const item of payload.base_tables) {
  const sheetName = uniqueSheetName(`B_${item.table}`, usedNames);
  const sheet = wb.worksheets.add(sheetName);
  writeSheet(sheet, item.rows, cleanTableName(`${sheetName}_Table`));
}
for (const item of payload.derived_tables) {
  const sheetName = uniqueSheetName(`D_${item.table}`, usedNames);
  const sheet = wb.worksheets.add(sheetName);
  writeSheet(sheet, item.rows, cleanTableName(`${sheetName}_Table`));
}

for (const sheet of wb.worksheets) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const used = sheet.getUsedRange();
  used.format.font = { name: "Aptos", size: 10 };
  used.format.wrapText = true;
  used.format.autofitColumns();
  used.format.autofitRows();
  const header = used.getRow(0);
  header.format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
}
summary.getRange("A1:H1").format = { fill: "#244062", font: { bold: true, color: "#FFFFFF", size: 14 } };
summary.getRange("A3:A12").format = { font: { bold: true }, fill: "#D9EAF7" };
summary.getRange("D3:H3").format = { font: { bold: true }, fill: "#E2F0D9" };

const errors = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

const preview = await wb.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(path.join(outputDir, `${outputPrefix}_${safeCode}_summary.png`), new Uint8Array(await preview.arrayBuffer()));

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(outputPath);
console.log(outputPath);

function writeIndex(sheet, tableItems, tableName) {
  const rows = tableItems.map((item) => ({
    table: item.table,
    exists: item.exists,
    date_column: item.date_column ?? "",
    sample_rows: item.rows.length,
    first_sample_date: firstDate(item.rows, item.date_column),
    last_sample_date: lastDate(item.rows, item.date_column),
  }));
  writeSheet(sheet, rows, tableName);
}

function writeSheet(sheet, rows, tableName) {
  if (!rows.length) {
    sheet.getRange("A1:B1").values = [["status", "message"]];
    sheet.getRange("A2:B2").values = [["empty", "No rows matched the sample filter."]];
    sheet.tables.add("A1:B2", true, tableName);
    return;
  }
  const headers = Array.from(rows.reduce((set, row) => {
    Object.keys(row).forEach((key) => set.add(key));
    return set;
  }, new Set()));
  sheet.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
  const matrix = rows.map((row) => headers.map((header) => valueForCell(row[header])));
  sheet.getRangeByIndexes(1, 0, matrix.length, headers.length).values = matrix;
  sheet.tables.add(`A1:${columnName(headers.length)}${matrix.length + 1}`, true, tableName);
}

function valueForCell(value) {
  if (value === null || value === undefined) return "";
  return value;
}

function firstDate(rows, dateColumn) {
  if (!dateColumn || !rows.length) return "";
  return rows.at(-1)?.[dateColumn] ?? "";
}

function lastDate(rows, dateColumn) {
  if (!dateColumn || !rows.length) return "";
  return rows[0]?.[dateColumn] ?? "";
}

function uniqueSheetName(rawName, usedNames) {
  const base = rawName.replace(/[\[\]\*\/\\\?\:]/g, "_").slice(0, 28);
  let name = base;
  let index = 1;
  while (usedNames.has(name)) {
    const suffix = `_${index}`;
    name = `${base.slice(0, 31 - suffix.length)}${suffix}`;
    index += 1;
  }
  usedNames.add(name);
  return name;
}

function cleanTableName(name) {
  return name.replace(/[^A-Za-z0-9_]/g, "_").slice(0, 200);
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
