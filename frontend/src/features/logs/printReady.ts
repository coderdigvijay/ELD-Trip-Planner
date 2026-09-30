/** Resolves once web fonts are loaded (when the browser exposes them) and two frames have painted. */
export async function whenSheetsPainted(): Promise<void> {
  const fonts = (document as Partial<Document>).fonts;
  await fonts?.ready;
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        resolve();
      });
    });
  });
}
