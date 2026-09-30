// Fails when the main entry chunk (gzip) exceeds the budget, or when map/PDF
// libraries leak into it. Budget is recorded at scaffold and raised deliberately.
import { readFileSync, readdirSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";

// Shell + form only: react-dom (~63 kB gzip), react-hook-form, zod/mini, query, base-ui combobox and
// number field. Results (summary, stops, logs), the map and the tooltip load in their own chunks.
// The bundler may split shared code into a chunk the entry imports statically (modulepreload), so the
// budget covers the entry plus its static imports. Raised 165 to 190 deliberately: measured 182 kB
// (157 kB at scaffold, before the log-sheet empty state and the shared Base UI code moved in).
const BUDGET_GZIP_KB = 190;
const FORBIDDEN = ["leaflet", "jspdf", "svg2pdf"];

const dir = join(import.meta.dirname, "..", "dist");
const manifest = JSON.parse(readFileSync(join(dir, ".vite", "manifest.json"), "utf8"));
const entry = Object.values(manifest).find((chunk) => chunk.isEntry);
if (!entry) {
  throw new Error("No entry chunk in dist/.vite/manifest.json. Run npm run build first.");
}

// Entry chunk plus everything it imports statically (they all load before the first paint).
const critical = [entry.file, ...(entry.imports ?? []).map((key) => manifest[key]?.file)].filter(
  (file) => typeof file === "string",
);
const code = Buffer.concat(critical.map((file) => readFileSync(join(dir, file))));
const gzipKb =
  critical.reduce((sum, file) => sum + gzipSync(readFileSync(join(dir, file))).length, 0) / 1024;
const text = code.toString("utf8").toLowerCase();
const leaked = FORBIDDEN.filter((name) => text.includes(name));

console.log(
  `main chunk ${entry.file} + ${String(critical.length - 1)} static imports: ${(code.length / 1024).toFixed(1)} kB raw, ${gzipKb.toFixed(1)} kB gzip (budget ${BUDGET_GZIP_KB})`,
);
console.log(`dist files: ${readdirSync(join(dir, "assets")).length}`);

if (gzipKb > BUDGET_GZIP_KB) {
  console.error("Bundle budget exceeded.");
  process.exit(1);
}
if (leaked.length > 0) {
  console.error(`Forbidden libraries in main chunk: ${leaked.join(", ")}`);
  process.exit(1);
}
