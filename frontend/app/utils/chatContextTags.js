// Parsing for the "@" context tags used by the knowledge-base AI chat.
//
// Three tag shapes are supported:
//   @recent            — limit context to items touched in the past week
//   @paper:"Title"     — pull in a paper's annotations by title
//   @note:"Title"      — pull in a standalone note's content by title
//
// Titles are quoted because they routinely contain spaces and punctuation.

const CONTEXT_TAG_PATTERN = '@recent|@paper:"[^"]*"|@note:"[^"]*"';

// A populated title is required here: an empty `@paper:""` shouldn't suppress
// RAG, since it can't resolve to anything.
export const hasContextTag = (text) =>
  new RegExp(`(@recent|@paper:"[^"]+"|@note:"[^"]+")`).test(String(text || ""));

// Splits input into plain-text and tag runs so the composer can render tags as
// highlighted chips behind a transparent textarea.
export const parseChatInputParts = (text) => {
  if (!text) return [{ type: "text", text: "" }];

  const parts = [];
  const regex = new RegExp(`(${CONTEXT_TAG_PATTERN})`, "g");
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", text: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: "tag", text: match[0] });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push({ type: "text", text: text.slice(lastIndex) });
  }

  return parts.length ? parts : [{ type: "text", text }];
};

// Resolves tags against the search index (which holds papers and standalone
// notes side by side, discriminated by `item_type`) and strips them from the
// prompt so the model never sees the raw tag text.
//
// Titles are matched within their own kind: a paper and a note can share a
// title, and `@paper:"X"` must not resolve to the note called "X".
export const parseContextFromInput = (text, items = []) => {
  const paperIds = [];
  const noteIds = [];
  let atRecent = false;
  let cleanPrompt = String(text || "");

  if (cleanPrompt.includes("@recent")) {
    atRecent = true;
    cleanPrompt = cleanPrompt.replace("@recent", "");
  }

  const resolve = (pattern, isNote, collect) => {
    for (const match of String(text || "").matchAll(pattern)) {
      const found = (items || []).find(
        (item) => (item.item_type === "note") === isNote && item.title === match[1],
      );
      if (found) collect(found);
      // Unresolvable tags are still stripped, so a typo degrades to a plain
      // question rather than leaking "@note:"Typo"" into the prompt.
      cleanPrompt = cleanPrompt.replace(match[0], "");
    }
  };

  resolve(/@paper:"([^"]+)"/g, false, (paper) => paperIds.push(paper.doc_id));
  resolve(/@note:"([^"]+)"/g, true, (note) => noteIds.push(note.note_id));

  return {
    prompt: cleanPrompt.trim(),
    paper_ids: paperIds,
    note_ids: noteIds,
    at_recent: atRecent,
  };
};
