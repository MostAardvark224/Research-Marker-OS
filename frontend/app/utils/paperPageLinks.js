const PAPER_PAGE_PATTERN = /\[([^\]\n]+)\]\[(\d+)\]/g;
const PAPER_HREF_PATTERN = /^#research-marker-paper-(\d+)-page-(\d+)$/;

const normalizedTitle = (value) => String(value || "").trim().toLocaleLowerCase();
const escapeHtml = (value) =>
  String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export const findPaperByTitle = (papers, title) =>
  (papers || []).find((paper) => normalizedTitle(paper.title) === normalizedTitle(title)) || null;

export const validatePaperPageLink = (papers, title, page) => {
  const paper = findPaperByTitle(papers, title);
  const pageNumber = Number(page);
  if (!paper) return { valid: false, error: `No paper titled “${String(title).trim()}” exists in your library.` };
  if (!Number.isInteger(pageNumber) || pageNumber < 1) {
    return { valid: false, error: "Page must be a positive whole number." };
  }
  if (Number(paper.page_count) > 0 && pageNumber > Number(paper.page_count)) {
    return { valid: false, error: `“${paper.title}” only has ${paper.page_count} pages.` };
  }
  return { valid: true, paper, page: pageNumber };
};

export const renderPaperPageLinks = (markdown, papers) => {
  const errors = [];
  const rendered = String(markdown || "").replace(
    PAPER_PAGE_PATTERN,
    (source, title, page) => {
      const result = validatePaperPageLink(papers, title, page);
      if (!result.valid) {
        errors.push({ source, title: title.trim(), page: Number(page), message: result.error });
        return `<span class="paper-page-link-error">${escapeHtml(source)}</span>`;
      }
      const label = `${result.paper.title} · p. ${result.page}`.replace(/]/g, "\\]");
      return `[${label}](#research-marker-paper-${result.paper.id}-page-${result.page})`;
    },
  );
  return { markdown: rendered, errors };
};

export const parsePaperPageHref = (href) => {
  const match = String(href || "").match(PAPER_HREF_PATTERN);
  if (!match) return null;
  return { paperId: Number(match[1]), page: Number(match[2]) };
};

export const paperPageSource = (paper, page) => `[${paper.title}][${Number(page)}]`;

export const openPaperPageWindow = async (paperId, page) => {
  if (typeof window === "undefined") return;
  if (window.electronAPI?.openPaperWindow) {
    await window.electronAPI.openPaperWindow(String(paperId), Number(page));
    return;
  }
  const target = new URL(window.location.href);
  target.hash = `/annotate/${paperId}?page=${Number(page)}`;
  window.open(target.toString(), "_blank", "noopener,noreferrer");
};
