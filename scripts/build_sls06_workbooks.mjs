import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = process.argv[2];
if (!outputDir) throw new Error("output directory is required");

const headerFill = "#1F4E78";
const border = { preset: "all", style: "thin", color: "#D9D9D9" };

async function build(csvName, outputName, sheetName, widths) {
  const csvText = await fs.readFile(path.join(outputDir, csvName), "utf8");
  const workbook = await Workbook.fromCSV(csvText, { sheetName });
  const sheet = workbook.worksheets.getItem(sheetName);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const used = sheet.getUsedRange();
  used.format.font = { name: "Arial", size: 10, color: "#202124" };
  used.format.verticalAlignment = "center";
  used.format.wrapText = true;
  used.format.borders = border;
  const header = used.getRow(0);
  header.format.fill = headerFill;
  header.format.font = { name: "Arial", size: 10, bold: true, color: "#FFFFFF" };
  header.format.horizontalAlignment = "center";
  header.format.rowHeight = 34;
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, used.rowCount, 1).format.columnWidth = width;
  });
  used.format.autofitRows();
  workbook.recalculate();
  const keyRange = await workbook.inspect({
    kind: "table",
    range: `${sheetName}!A1:F6`,
    include: "values,formulas",
    tableMaxRows: 6,
    tableMaxCols: 6,
  });
  if (!keyRange.ndjson.includes("CaseID")) throw new Error(keyRange.ndjson);
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 100 },
    summary: `${outputName} formula errors`,
  });
  if (errors.ndjson.includes('"matchCount":') && !errors.ndjson.includes('"matchCount":0')) {
    throw new Error(errors.ndjson);
  }
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(path.join(outputDir, outputName));
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1.5, format: "png" });
  const qaDir = path.join(path.dirname(outputDir), "qa-previews");
  await fs.mkdir(qaDir, { recursive: true });
  await fs.writeFile(path.join(qaDir, `${outputName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

await build(
  "source_to_runtime.csv",
  "Source_to_Runtime.xlsx",
  "Source to Runtime",
  [14, 11, 28, 11, 13, 14, 10, 34, 30, 10, 22, 22, 17, 34, 22],
);
await build(
  "review_protocol.csv",
  "Review_Protocol.xlsx",
  "Review Protocol",
  [14, 11, 28, 11, 34, 34, 34, 30, 12, 28, 18, 14, 24, 16],
);
