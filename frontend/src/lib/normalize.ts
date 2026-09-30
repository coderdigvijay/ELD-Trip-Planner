/** Split `text` around the first case-insensitive occurrence of `needle` for emphasis. */
export function splitMatch(
  text: string,
  needle: string,
): { before: string; match: string; after: string } {
  const term = needle.trim();
  const at = term ? text.toLowerCase().indexOf(term.toLowerCase()) : -1;
  if (at < 0) return { before: text, match: "", after: "" };
  return {
    before: text.slice(0, at),
    match: text.slice(at, at + term.length),
    after: text.slice(at + term.length),
  };
}
