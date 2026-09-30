import { whenSheetsPainted } from "./printReady";

// Optional "Download PDF" (LOG_SHEET_RENDER_SPEC 5.4). jsPDF and svg2pdf.js load on click only.

const FONT_DIR = "/fonts/pdf/";
const FONT_FILES = {
  sansRegular: "PublicSans-Regular.ttf",
  sansSemiBold: "PublicSans-SemiBold.ttf",
  monoMedium: "IBMPlexMono-Medium.ttf",
  monoRegular: "IBMPlexMono-Regular.ttf",
} as const;

const PAGE_MARGIN = 29;
const SHEET_W = 554;
const SHEET_H = 565;

async function fetchBase64(file: string): Promise<string> {
  const response = await fetch(`${FONT_DIR}${file}`);
  if (!response.ok) throw new Error(`Font ${file} could not be loaded (${response.status})`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

/**
 * Names svg2pdf can resolve. It looks fonts up by family plus normal or bold, so the heavier weight of each
 * family (Public Sans 600, IBM Plex Mono 500) becomes bold and is registered to the matching file below;
 * anything else is normal. Works on a clone.
 */
export function prepareForPdf(svg: SVGSVGElement): void {
  svg.removeAttribute("style");
  svg.setAttribute("width", String(SHEET_W));
  svg.setAttribute("height", String(SHEET_H));
  svg.querySelectorAll<SVGElement>("[font-family]").forEach((el) => {
    el.setAttribute(
      "font-family",
      el.getAttribute("font-family")?.includes("Mono") ? "IBM Plex Mono" : "Public Sans",
    );
  });
  svg.querySelectorAll<SVGElement>('[font-weight="600"], [font-weight="500"]').forEach((el) => {
    el.setAttribute("font-weight", "bold");
  });
  svg.querySelectorAll("title, desc").forEach((el) => {
    el.remove();
  });
}

export interface PdfExportOptions {
  filename: string;
}

/** Renders the given mounted sheets to a letter-size PDF, one page each, and triggers the download. */
export async function exportLogsPdf(
  sheets: readonly SVGSVGElement[],
  { filename }: PdfExportOptions,
): Promise<void> {
  const [{ jsPDF }, { svg2pdf }, sansRegular, sansSemiBold, monoMedium, monoRegular] =
    await Promise.all([
      import("jspdf"),
      import("svg2pdf.js"),
      fetchBase64(FONT_FILES.sansRegular),
      fetchBase64(FONT_FILES.sansSemiBold),
      fetchBase64(FONT_FILES.monoMedium),
      fetchBase64(FONT_FILES.monoRegular),
    ]);
  await whenSheetsPainted();

  const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
  const register = (file: string, data: string, name: string, style: "normal" | "bold") => {
    doc.addFileToVFS(file, data);
    doc.addFont(file, name, style);
  };
  register(FONT_FILES.sansRegular, sansRegular, "Public Sans", "normal");
  register(FONT_FILES.sansSemiBold, sansSemiBold, "Public Sans", "bold");
  register(FONT_FILES.monoMedium, monoMedium, "IBM Plex Mono", "bold");
  register(FONT_FILES.monoRegular, monoRegular, "IBM Plex Mono", "normal");

  // svg2pdf resolves styles from the document, so the clones live off-screen while they render.
  const stage = document.createElement("div");
  stage.setAttribute("aria-hidden", "true");
  stage.style.cssText = `position:fixed;left:-10000px;top:0;width:${SHEET_W}px;`;
  document.body.appendChild(stage);
  try {
    for (const [index, sheet] of sheets.entries()) {
      const clone = sheet.cloneNode(true) as SVGSVGElement;
      prepareForPdf(clone);
      stage.replaceChildren(clone);
      if (index > 0) doc.addPage();
      await svg2pdf(clone, doc, {
        x: PAGE_MARGIN,
        y: PAGE_MARGIN,
        width: SHEET_W,
        height: SHEET_H,
      });
    }
  } finally {
    stage.remove();
  }
  doc.save(filename);
}
