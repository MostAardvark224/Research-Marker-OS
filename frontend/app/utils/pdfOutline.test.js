import assert from "node:assert/strict";
import test from "node:test";

import {
  findActivePdfOutlineItem,
  findPdfOutlinePath,
  normalizePdfOutline,
  resolvePdfOutlinePage,
} from "./pdfOutline.js";

test("resolves named, referenced, and numeric PDF destinations", async () => {
  const pageReference = { num: 42, gen: 0 };
  const pdfDocument = {
    getDestination: async (name) =>
      name === "chapter-one" ? [pageReference, { name: "XYZ" }] : null,
    getPageIndex: async (reference) => {
      assert.equal(reference, pageReference);
      return 6;
    },
  };

  assert.equal(
    await resolvePdfOutlinePage(pdfDocument, "chapter-one"),
    7,
  );
  assert.equal(await resolvePdfOutlinePage(pdfDocument, [3]), 4);
  assert.equal(await resolvePdfOutlinePage(pdfDocument, null), null);
});

test("normalizes nested outline items using stable tree paths", async () => {
  const pdfDocument = {
    getPageIndex: async ({ num }) => num,
  };
  const outline = await normalizePdfOutline(pdfDocument, [
    {
      title: " Chapter 1 ",
      dest: [{ num: 4 }],
      items: [{ title: "Section 1.1", dest: [7], items: [] }],
    },
  ]);

  assert.deepEqual(outline, [
    {
      id: "0",
      title: "Chapter 1",
      page: 5,
      children: [
        {
          id: "0.0",
          title: "Section 1.1",
          page: 8,
          children: [],
        },
      ],
    },
  ]);
});

test("finds the current section and its ancestors by PDF page", () => {
  const outline = [
    {
      id: "0",
      title: "Chapter 1",
      page: 3,
      children: [
        { id: "0.0", title: "Section 1.1", page: 3, children: [] },
        { id: "0.1", title: "Section 1.2", page: 8, children: [] },
      ],
    },
    { id: "1", title: "Chapter 2", page: 15, children: [] },
  ];

  assert.equal(findActivePdfOutlineItem(outline, 7)?.id, "0.0");
  assert.equal(findActivePdfOutlineItem(outline, 10)?.id, "0.1");
  assert.deepEqual(findPdfOutlinePath(outline, "0.1"), ["0", "0.1"]);
});
