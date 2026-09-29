import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

const SRC = join(import.meta.dirname, "..");
const EXTENSIONS = /\.(ts|tsx|css)$/;
const SELF = /guards\.test\.ts$/;
const HEX_ALLOWED = /(index\.css|features[\\/]logs[\\/]tokens\.ts)$/;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = join(dir, entry.name);
    return entry.isDirectory() ? sourceFiles(full) : [full];
  });
}

const files = sourceFiles(SRC).filter((f) => EXTENSIONS.test(f) && !SELF.test(f));

function offenders(pattern: RegExp, skip?: RegExp): string[] {
  return files
    .filter((f) => !skip?.test(f))
    .filter((f) => pattern.test(readFileSync(f, "utf8")))
    .map((f) => relative(SRC, f));
}

describe("design system guards (DESIGN_SYSTEM 2.1)", () => {
  it("has no hex colors outside the token files", () => {
    expect(offenders(/#[0-9a-fA-F]{3,8}\b/, HEX_ALLOWED)).toEqual([]);
  });

  it("has no dark: variants, backdrop blur or font-bold", () => {
    expect(offenders(/\bdark:|backdrop-blur|font-bold/)).toEqual([]);
  });

  it("has no em or en dashes", () => {
    expect(offenders(/[–—]/)).toEqual([]);
  });

  it("has no CRLF line endings", () => {
    expect(offenders(/\r\n/)).toEqual([]);
  });
});
