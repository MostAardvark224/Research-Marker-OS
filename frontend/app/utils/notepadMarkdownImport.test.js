import assert from "node:assert/strict";
import test from "node:test";

import {
  decodeMarkdownBytes,
  isMarkdownFilename,
  markdownDownloadFilename,
  mergeImportedMarkdown,
} from "./notepadMarkdownImport.js";

test("recognizes Markdown filenames case-insensitively", () => {
  assert.equal(isMarkdownFilename("paper-notes.md"), true);
  assert.equal(isMarkdownFilename("PAPER-NOTES.MD"), true);
  assert.equal(isMarkdownFilename("paper-notes.txt"), false);
});

test("replace uses the uploaded Markdown as the complete notepad", () => {
  assert.equal(
    mergeImportedMarkdown("old", "# Imported", "replace"),
    "# Imported",
  );
});

test("append joins existing and uploaded Markdown with one blank line", () => {
  assert.equal(
    mergeImportedMarkdown("# Existing", "# Imported", "append"),
    "# Existing\n\n# Imported",
  );
  assert.equal(
    mergeImportedMarkdown("# Existing\n", "# Imported", "append"),
    "# Existing\n\n# Imported",
  );
  assert.equal(
    mergeImportedMarkdown("# Existing\n\n", "# Imported", "append"),
    "# Existing\n\n# Imported",
  );
});

test("append handles either empty document without adding separators", () => {
  assert.equal(mergeImportedMarkdown("", "Imported", "append"), "Imported");
  assert.equal(mergeImportedMarkdown("Existing", "", "append"), "Existing");
});

test("decodes UTF-8 Markdown and strips its byte-order mark", () => {
  const bytes = Uint8Array.from([
    0xef, 0xbb, 0xbf, 0x23, 0x20, 0x4e, 0x6f, 0x74, 0x65,
  ]);
  assert.equal(decodeMarkdownBytes(bytes), "# Note");
  assert.throws(
    () => decodeMarkdownBytes(Uint8Array.from([0xff, 0xfe])),
    /encoded data/i,
  );
});

test("builds a safe Markdown download filename from the note title", () => {
  assert.equal(markdownDownloadFilename("Research notes"), "Research notes.md");
  assert.equal(markdownDownloadFilename("Research.md"), "Research.md");
  assert.equal(markdownDownloadFilename("Paper: notes / draft"), "Paper- notes - draft.md");
  assert.equal(markdownDownloadFilename("  "), "notes.md");
});
