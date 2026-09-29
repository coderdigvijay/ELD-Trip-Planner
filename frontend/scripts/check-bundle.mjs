// Fails when the main entry chunk (gzip) exceeds the budget, or when map/PDF
// libraries leak into it. Budget is recorded at scaffold and raised deliberately.
import { readFileSync, readdirSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";

const BUDGET_GZIP_KB = 150; // scaffold baseline is about 91 kB; headroom for form, zod, log sheets
const FORBIDDEN = ["leaflet", "jspdf", "svg2pdf"];

const dir = join(import.meta.dirname, "..", "dist");
const manifest = JSON.parse(readFileSync(join(dir, ".vite", "manifest.json"), "utf8"));
const entry = Object.values(manifest).find((chunk) => chunk.isEntry);
if (!entry) {
  throw new Error("No entry chunk in dist/.vite/manifest.json. Run npm run build first.");
}

const code = readFileSync(join(dir, entry.file));
const gzipKb = gzipSync(code).length / 1024;
const text = code.toString("utf8").toLowerCase();
const leaked = FORBIDDEN.filter((name) => text.includes(name));

console.log(
  `main chunk ${entry.file}: ${(code.length / 1024).toFixed(1)} kB raw, ${gzipKb.toFixed(1)} kB gzip (budget ${BUDGET_GZIP_KB})`,
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
