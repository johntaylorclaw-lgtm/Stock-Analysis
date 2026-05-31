import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const samplePath = process.argv[2];
const tsCode = process.argv[3] ?? "000001.SZ";
if (!samplePath) {
  throw new Error("usage: node scripts/build_sample_derived_variable_excel.mjs <sample-json> [ts_code]");
}

const payload = JSON.parse(await fs.readFile(samplePath, "utf8"));
const outputDir = path.join(root, "outputs", "phase3");
const outputPath = path.join(outputDir, `sample_derived_variables_${tsCode.replace(".", "_")}.xlsx`);

const wb = Workbook.create();
const summary = wb.worksheets.add("Summary");
const dataSheet = wb.worksheets.add("Features_Full");
const coverageSheet = wb.worksheets.add("Coverage");

summary.getRange("A1:F1").merge();
summary.getRange("A1").values = [["Sample Derived Variables"]];
summary.getRange("A3:B10").values = [
  ["Stock", payload.stock.ts_code],
  ["Name", payload.stock.name ?? ""],
  ["Market", payload.stock.market ?? ""],
  ["Rows", payload.rows.length],
  ["Min trade_date", payload.summary.min_trade_date],
  ["Max trade_date", payload.summary.max_trade_date],
  ["Columns", payload.columns.length],
  ["Generated At", new Date()],
];

summary.getRange("A1:F1").format = { fill: "#244062", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A3:A10").format = { font: { bold: true }, fill: "#D9EAF7" };
summary.getRange("B10").setNumberFormat("yyyy-mm-dd hh:mm");

writeSheet(dataSheet, payload.rows, "SampleFeaturesFullTable");
writeSheet(coverageSheet, payload.coverage, "SampleCoverageTable");

for (const sheet of [summary, dataSheet, coverageSheet]) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  const used = sheet.getUsedRange();
  used.format.font = { name: "Aptos", size: 10 };
  used.format.wrapText = true;
  used.format.autofitColumns();
  used.format.autofitRows();
}

for (const sheet of [dataSheet, coverageSheet]) {
  sheet.getUsedRange().getRow(0).format = { fill: "#305496", font: { bold: true, color: "#FFFFFF" } };
}

const preview = await wb.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(
  path.join(outputDir, `sample_derived_variables_${tsCode.replace(".", "_")}_summary.png`),
  new Uint8Array(await preview.arrayBuffer()),
);

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
  if (!rows.length) {
    sheet.getRange("A1").values = [["No rows"]];
    return;
  }
  const headers = Object.keys(rows[0]);
  sheet.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
  const matrix = rows.map((row) => headers.map((header) => valueForCell(row[header])));
  sheet.getRangeByIndexes(1, 0, matrix.length, headers.length).values = matrix;
  sheet.tables.add(`A1:${columnName(headers.length)}${matrix.length + 1}`, true, tableName);
}

function valueForCell(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  return value;
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
