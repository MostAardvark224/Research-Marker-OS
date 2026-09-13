import test from "node:test";
import assert from "node:assert/strict";
import {
  parsePaperPageHref,
  renderPaperPageLinks,
  validatePaperPageLink,
} from "./paperPageLinks.js";

const papers = [{ id: 7, title: "Attention Is All You Need", page_count: 15 }];

test("valid paper-page source renders as an internal Research Marker link", () => {
  const result = renderPaperPageLinks("See [Attention Is All You Need][12].", papers);
  assert.equal(result.errors.length, 0);
  assert.match(result.markdown, /#research-marker-paper-7-page-12/);
  assert.deepEqual(parsePaperPageHref("#research-marker-paper-7-page-12"), { paperId: 7, page: 12 });
});

test("unknown papers and out-of-range pages produce validation errors", () => {
  assert.equal(validatePaperPageLink(papers, "Missing", 1).valid, false);
  assert.match(validatePaperPageLink(papers, papers[0].title, 16).error, /only has 15 pages/);
});
