import assert from "node:assert/strict";
import test from "node:test";

import { renderAnnotationContent } from "./renderAnnotationContent.js";

test("renders single-dollar LaTeX inline", () => {
  const html = renderAnnotationContent("The function $f(x)$ is continuous.");

  assert.match(html, /The function <span class="katex">/);
  assert.match(html, /is continuous\./);
  assert.doesNotMatch(html, /\$f\(x\)\$/);
  assert.doesNotMatch(html, /katex-display/);
});

test("keeps ordinary annotation text safe", () => {
  const html = renderAnnotationContent('<img src=x onerror="alert(1)">');

  assert.equal(
    html,
    "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;",
  );
});

test("does not treat currency as a delimited expression", () => {
  assert.equal(renderAnnotationContent("Costs $5 and $10"), "Costs $5 and $10");
});

test("renders annotation line breaks", () => {
  assert.equal(renderAnnotationContent("first\nsecond"), "first<br />second");
});

test("highlights search matches without exposing raw HTML", () => {
  const html = renderAnnotationContent("Find <this> term", {
    highlight: "<this>",
  });

  assert.match(html, /<span class="text-green-400[^>]+>&lt;this&gt;<\/span>/);
  assert.doesNotMatch(html, /Find <this>/);
});
