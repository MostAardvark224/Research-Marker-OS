import assert from "node:assert/strict";
import test from "node:test";

import { createNotepadHistory } from "./notepadHistory.js";

const caret = (position) => ({
  start: position,
  end: position,
  direction: "forward",
});

const recordTyping = (history, before, after, timestamp) =>
  history.record({
    before,
    after,
    beforeSelection: caret(before.length),
    afterSelection: caret(after.length),
    inputType: "insertText",
    timestamp,
  });

test("continuous typing is undone and redone as one transaction", () => {
  const history = createNotepadHistory();
  let value = "";
  for (const [index, character] of [..."A whole sentence."].entries()) {
    const before = value;
    value += character;
    recordTyping(history, before, value, index * 100);
  }

  assert.equal(history.undoCount, 1);
  const undone = history.undo(value);
  assert.equal(undone.value, "");
  assert.deepEqual(undone.selection, caret(0));
  const redone = history.redo(undone.value);
  assert.equal(redone.value, "A whole sentence.");
  assert.deepEqual(redone.selection, caret(17));
});

test("a typing pause starts a new undo transaction", () => {
  const history = createNotepadHistory({ mergeDelay: 1000 });
  recordTyping(history, "", "hello", 0);
  recordTyping(history, "hello", "hello world", 1500);

  assert.equal(history.undoCount, 2);
  assert.equal(history.undo("hello world").value, "hello");
  assert.equal(history.undo("hello").value, "");
});

test("moving or refocusing the caret explicitly ends the typing group", () => {
  const history = createNotepadHistory();
  recordTyping(history, "", "one", 0);
  history.breakGroup();
  recordTyping(history, "one", "onetwo", 10);

  assert.equal(history.undoCount, 2);
  assert.equal(history.undo("onetwo").value, "one");
});

test("continuous typing in the middle of a note restores the full original", () => {
  const history = createNotepadHistory();
  history.record({
    before: "ac",
    after: "abc",
    beforeSelection: caret(1),
    afterSelection: caret(2),
    inputType: "insertText",
    timestamp: 0,
  });
  history.record({
    before: "abc",
    after: "abdc",
    beforeSelection: caret(2),
    afterSelection: caret(3),
    inputType: "insertText",
    timestamp: 50,
  });

  assert.equal(history.undo("abdc").value, "ac");
});

test("continuous backspaces coalesce while preserving the original caret", () => {
  const history = createNotepadHistory();
  history.record({
    before: "word",
    after: "wor",
    beforeSelection: caret(4),
    afterSelection: caret(3),
    inputType: "deleteContentBackward",
    timestamp: 0,
  });
  history.record({
    before: "wor",
    after: "wo",
    beforeSelection: caret(3),
    afterSelection: caret(2),
    inputType: "deleteContentBackward",
    timestamp: 50,
  });

  assert.equal(history.undoCount, 1);
  const undone = history.undo("wo");
  assert.equal(undone.value, "word");
  assert.deepEqual(undone.selection, caret(4));
});

test("paste, formatting, and selection replacement stay discrete", () => {
  const history = createNotepadHistory();
  recordTyping(history, "", "a", 0);
  history.record({
    before: "a",
    after: "a pasted block",
    beforeSelection: caret(1),
    afterSelection: caret(14),
    inputType: "insertFromPaste",
    timestamp: 10,
  });
  history.record({
    before: "a pasted block",
    after: "**a** pasted block",
    beforeSelection: { start: 0, end: 1, direction: "forward" },
    afterSelection: caret(5),
    inputType: "formatBold",
    timestamp: 20,
    forceNewGroup: true,
  });

  assert.equal(history.undoCount, 3);
  assert.equal(history.undo("**a** pasted block").value, "a pasted block");
  assert.equal(history.undo("a pasted block").value, "a");
});

test("a new edit invalidates redo history", () => {
  const history = createNotepadHistory();
  recordTyping(history, "", "one", 0);
  assert.equal(history.undo("one").value, "");
  assert.equal(history.canRedo, true);
  recordTyping(history, "", "two", 2000);
  assert.equal(history.canRedo, false);
});

test("popup history can be exported and restored with the exact selection", () => {
  const popupHistory = createNotepadHistory();
  popupHistory.record({
    before: "first line\nsecond",
    after: "first line\nSECOND",
    beforeSelection: { start: 11, end: 17, direction: "forward" },
    afterSelection: caret(17),
    inputType: "insertReplacementText",
    timestamp: 100,
    forceNewGroup: true,
  });

  const viewerHistory = createNotepadHistory();
  const state = popupHistory.exportState("first line\nSECOND");
  assert.equal(state.undo[0].before, undefined);
  assert.equal(state.undo[0].after, undefined);
  assert.equal(state.undo[0].operations.length, 1);
  assert.equal(viewerHistory.importState(state, state.present), true);
  const undone = viewerHistory.undo(state.present);
  assert.equal(undone.value, "first line\nsecond");
  assert.deepEqual(undone.selection, {
    start: 11,
    end: 17,
    direction: "forward",
  });
});

test("undo refuses to touch text from a mismatched popup revision", () => {
  const history = createNotepadHistory();
  recordTyping(history, "", "safe", 0);
  assert.equal(history.undo("different current text"), null);
  assert.equal(history.canUndo, true);
});
