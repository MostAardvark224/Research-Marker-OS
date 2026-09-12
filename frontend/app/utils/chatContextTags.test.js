import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  hasContextTag,
  parseChatInputParts,
  parseContextFromInput,
} from "./chatContextTags.js";

// Mirrors the shape returned by /search-notes/, which interleaves papers and
// standalone notes in one list.
const items = [
  { item_type: "paper", title: "Attention Is All You Need", doc_id: 7 },
  { item_type: "paper", title: "Shared Title", doc_id: 8 },
  { item_type: "note", title: "Reading log", note_id: 3 },
  { item_type: "note", title: "Shared Title", note_id: 4 },
];

describe("hasContextTag", () => {
  it("detects each tag kind", () => {
    assert.equal(hasContextTag("summarise @recent"), true);
    assert.equal(hasContextTag('compare @paper:"Attention Is All You Need"'), true);
    assert.equal(hasContextTag('expand @note:"Reading log"'), true);
  });

  it("ignores untagged input and bare or empty tags", () => {
    assert.equal(hasContextTag("what is attention?"), false);
    assert.equal(hasContextTag("email me @ noon"), false);
    assert.equal(hasContextTag('@note:""'), false);
    assert.equal(hasContextTag(""), false);
    assert.equal(hasContextTag(undefined), false);
  });
});

describe("parseChatInputParts", () => {
  it("splits notes tags out of surrounding text", () => {
    assert.deepEqual(parseChatInputParts('tidy @note:"Reading log" please'), [
      { type: "text", text: "tidy " },
      { type: "tag", text: '@note:"Reading log"' },
      { type: "text", text: " please" },
    ]);
  });

  it("handles mixed paper and note tags", () => {
    const parts = parseChatInputParts('@paper:"Shared Title"@note:"Reading log"');
    assert.deepEqual(parts, [
      { type: "tag", text: '@paper:"Shared Title"' },
      { type: "tag", text: '@note:"Reading log"' },
    ]);
  });

  it("returns a single text part when there are no tags", () => {
    assert.deepEqual(parseChatInputParts("plain question"), [
      { type: "text", text: "plain question" },
    ]);
    assert.deepEqual(parseChatInputParts(""), [{ type: "text", text: "" }]);
  });
});

describe("parseContextFromInput", () => {
  it("resolves a note tag to its id and strips it from the prompt", () => {
    const result = parseContextFromInput('summarise @note:"Reading log"', items);
    assert.deepEqual(result, {
      prompt: "summarise",
      paper_ids: [],
      note_ids: [3],
      at_recent: false,
    });
  });

  it("resolves multiple note tags", () => {
    const result = parseContextFromInput(
      '@note:"Reading log" and @note:"Shared Title"',
      items,
    );
    assert.deepEqual(result.note_ids, [3, 4]);
    assert.equal(result.prompt, "and");
  });

  it("keeps paper and note titles in separate namespaces", () => {
    // "Shared Title" exists as both a paper (8) and a note (4); each tag must
    // resolve within its own kind.
    assert.deepEqual(
      parseContextFromInput('@paper:"Shared Title"', items).paper_ids,
      [8],
    );
    assert.deepEqual(
      parseContextFromInput('@paper:"Shared Title"', items).note_ids,
      [],
    );
    assert.deepEqual(
      parseContextFromInput('@note:"Shared Title"', items).note_ids,
      [4],
    );
    assert.deepEqual(
      parseContextFromInput('@note:"Shared Title"', items).paper_ids,
      [],
    );
  });

  it("never resolves a note title against a paper tag", () => {
    const result = parseContextFromInput('@paper:"Reading log" why?', items);
    assert.deepEqual(result.paper_ids, []);
    assert.deepEqual(result.note_ids, []);
    assert.equal(result.prompt, "why?");
  });

  it("strips unresolvable tags instead of leaking them into the prompt", () => {
    const result = parseContextFromInput('@note:"No Such Note" explain', items);
    assert.deepEqual(result.note_ids, []);
    assert.equal(result.prompt, "explain");
  });

  it("combines @recent with a note tag", () => {
    const result = parseContextFromInput('@recent @note:"Reading log" recap', items);
    assert.equal(result.at_recent, true);
    assert.deepEqual(result.note_ids, [3]);
    assert.equal(result.prompt, "recap");
  });

  it("returns empty context for an untagged prompt", () => {
    assert.deepEqual(parseContextFromInput("hello", items), {
      prompt: "hello",
      paper_ids: [],
      note_ids: [],
      at_recent: false,
    });
  });

  it("tolerates a missing item list", () => {
    const result = parseContextFromInput('@note:"Reading log" hi');
    assert.deepEqual(result.note_ids, []);
    assert.equal(result.prompt, "hi");
  });
});
