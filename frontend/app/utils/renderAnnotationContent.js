import katex from "katex";

const INLINE_LATEX_PATTERN =
  /(?<!\\)(\$\$([\s\S]+?)(?<!\\)\$\$|\$(?![$\s])([^$\n]*?\S)(?<!\\)\$(?!\d))/g;

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const renderEscapedText = (value, breaks) => {
  const escaped = escapeHtml(value).replaceAll("\\$", "$");
  return breaks ? escaped.replaceAll("\n", "<br />") : escaped;
};

const renderPlainText = (value, { breaks, highlight }) => {
  if (!highlight) return renderEscapedText(value, breaks);

  const pattern = new RegExp(`(${escapeRegExp(highlight)})`, "gi");
  return value
    .split(pattern)
    .map((part, index) =>
      index % 2 === 1
        ? `<span class="text-green-400 font-bold bg-green-400/10 rounded px-1">${renderEscapedText(part, breaks)}</span>`
        : renderEscapedText(part, breaks),
    )
    .join("");
};

/**
 * Renders dollar-delimited LaTeX while leaving annotation text as plain text.
 * Single-dollar expressions stay inline; double-dollar expressions use KaTeX's
 * display mode. All non-math content is escaped for safe use with v-html.
 */
export const renderAnnotationContent = (
  value,
  { breaks = true, highlight = "" } = {},
) => {
  const text = String(value ?? "");
  if (!text) return "";
  const renderOptions = { breaks, highlight: String(highlight || "") };

  let html = "";
  let lastIndex = 0;

  for (const match of text.matchAll(INLINE_LATEX_PATTERN)) {
    const [source, , displayLatex, inlineLatex] = match;
    html += renderPlainText(text.slice(lastIndex, match.index), renderOptions);

    try {
      html += katex.renderToString(displayLatex ?? inlineLatex, {
        displayMode: displayLatex !== undefined,
        throwOnError: false,
        trust: false,
      });
    } catch {
      html += renderPlainText(source, renderOptions);
    }

    lastIndex = match.index + source.length;
  }

  return html + renderPlainText(text.slice(lastIndex), renderOptions);
};
