export const MAX_NOTEPAD_MARKDOWN_BYTES = 10 * 1024 * 1024;

export const isMarkdownFilename = (filename) =>
  String(filename || "").toLowerCase().endsWith(".md");

export const decodeMarkdownBytes = (bytes) =>
  new TextDecoder("utf-8", { fatal: true }).decode(bytes);

export const mergeImportedMarkdown = (current, imported, mode) => {
  const currentText = String(current ?? "");
  const importedText = String(imported ?? "");

  if (mode === "replace") return importedText;
  if (mode !== "append") {
    throw new Error(`Unsupported Markdown import mode: ${mode}`);
  }
  if (!currentText) return importedText;
  if (!importedText) return currentText;

  const separator = currentText.endsWith("\n\n")
    ? ""
    : currentText.endsWith("\n")
      ? "\n"
      : "\n\n";
  return `${currentText}${separator}${importedText}`;
};
