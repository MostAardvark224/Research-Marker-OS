export const NOTEPAD_HISTORY_MERGE_DELAY_MS = 1200;
export const NOTEPAD_HISTORY_LIMIT = 500;

const INSERT_INPUT_TYPES = new Set([
  "insertText",
  "insertCompositionText",
  "insertFromComposition",
  "insertReplacementText",
]);

const DELETE_INPUT_TYPES = new Set([
  "deleteContentBackward",
  "deleteContentForward",
  "deleteWordBackward",
  "deleteWordForward",
  "deleteSoftLineBackward",
  "deleteSoftLineForward",
  "deleteHardLineBackward",
  "deleteHardLineForward",
  "deleteCompositionText",
]);

const clamp = (value, minimum, maximum) =>
  Math.min(maximum, Math.max(minimum, value));

// A fast deterministic checksum lets undo refuse stale cross-window state
// without storing a complete copy of the document for every transaction.
const hashText = (text) => {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
};

export const normalizeNotepadSelection = (selection, textLength) => {
  const start = clamp(Number(selection?.start) || 0, 0, textLength);
  const end = clamp(Number(selection?.end) || start, start, textLength);
  return {
    start,
    end,
    direction: selection?.direction === "backward" ? "backward" : "forward",
  };
};

const selectionsMatch = (left, right) =>
  left.start === right.start &&
  left.end === right.end &&
  left.direction === right.direction;

const editCategory = (inputType) => {
  if (INSERT_INPUT_TYPES.has(inputType)) return "insert";
  if (DELETE_INPUT_TYPES.has(inputType)) return "delete";
  return null;
};

export const isMergeableNotepadInputType = (inputType) =>
  editCategory(inputType) !== null;

const createOperation = (before, after) => {
  let start = 0;
  const sharedLength = Math.min(before.length, after.length);
  while (start < sharedLength && before[start] === after[start]) start += 1;

  let suffixLength = 0;
  while (
    suffixLength < sharedLength - start &&
    before[before.length - 1 - suffixLength] ===
      after[after.length - 1 - suffixLength]
  ) {
    suffixLength += 1;
  }

  return {
    start,
    removed: before.slice(start, before.length - suffixLength),
    inserted: after.slice(start, after.length - suffixLength),
  };
};

const sanitizeNewAction = (action) => {
  if (
    !action ||
    typeof action.before !== "string" ||
    typeof action.after !== "string" ||
    action.before === action.after
  ) {
    return null;
  }

  return {
    operations: [createOperation(action.before, action.after)],
    beforeSelection: normalizeNotepadSelection(
      action.beforeSelection,
      action.before.length,
    ),
    afterSelection: normalizeNotepadSelection(
      action.afterSelection,
      action.after.length,
    ),
    inputType:
      typeof action.inputType === "string" ? action.inputType : "unknown",
    timestamp: Number.isFinite(action.timestamp) ? action.timestamp : Date.now(),
    forceNewGroup: Boolean(action.forceNewGroup),
    beforeLength: action.before.length,
    afterLength: action.after.length,
    beforeHash: hashText(action.before),
    afterHash: hashText(action.after),
  };
};

const sanitizeOperation = (operation) => {
  if (
    !operation ||
    !Number.isSafeInteger(operation.start) ||
    operation.start < 0 ||
    typeof operation.removed !== "string" ||
    typeof operation.inserted !== "string"
  ) {
    return null;
  }
  return {
    start: operation.start,
    removed: operation.removed,
    inserted: operation.inserted,
  };
};

const sanitizeSerializedAction = (action) => {
  if (!action || !Array.isArray(action.operations) || !action.operations.length) {
    return null;
  }
  const operations = action.operations.map(sanitizeOperation);
  if (operations.some((operation) => !operation)) return null;
  if (
    !Number.isSafeInteger(action.beforeLength) ||
    !Number.isSafeInteger(action.afterLength) ||
    !Number.isSafeInteger(action.beforeHash) ||
    !Number.isSafeInteger(action.afterHash)
  ) {
    return null;
  }

  return {
    operations,
    beforeSelection: normalizeNotepadSelection(
      action.beforeSelection,
      action.beforeLength,
    ),
    afterSelection: normalizeNotepadSelection(
      action.afterSelection,
      action.afterLength,
    ),
    inputType:
      typeof action.inputType === "string" ? action.inputType : "unknown",
    timestamp: Number.isFinite(action.timestamp) ? action.timestamp : Date.now(),
    forceNewGroup: Boolean(action.forceNewGroup),
    beforeLength: action.beforeLength,
    afterLength: action.afterLength,
    beforeHash: action.beforeHash,
    afterHash: action.afterHash,
  };
};

const cloneAction = (action) => ({
  operations: action.operations.map((operation) => ({ ...operation })),
  beforeSelection: { ...action.beforeSelection },
  afterSelection: { ...action.afterSelection },
  inputType: action.inputType,
  timestamp: action.timestamp,
  forceNewGroup: Boolean(action.forceNewGroup),
  beforeLength: action.beforeLength,
  afterLength: action.afterLength,
  beforeHash: action.beforeHash,
  afterHash: action.afterHash,
});

export const canMergeNotepadEdits = (
  previous,
  next,
  mergeDelay = NOTEPAD_HISTORY_MERGE_DELAY_MS,
) => {
  const previousCategory = editCategory(previous?.inputType);
  const nextCategory = editCategory(next?.inputType);
  if (!previousCategory || previousCategory !== nextCategory) return false;
  if (next.forceNewGroup) return false;
  if (next.timestamp - previous.timestamp > mergeDelay) return false;
  if (next.timestamp < previous.timestamp) return false;
  if (
    previous.afterLength !== next.beforeLength ||
    previous.afterHash !== next.beforeHash
  ) {
    return false;
  }
  if (!selectionsMatch(previous.afterSelection, next.beforeSelection)) {
    return false;
  }

  // Selection replacement, paste, drop, cut, formatting, and structural edits
  // are intentionally their own undo steps. Only uninterrupted collapsed-caret
  // typing and deletion coalesce like a native document editor.
  return (
    previous.beforeSelection.start === previous.beforeSelection.end &&
    previous.afterSelection.start === previous.afterSelection.end &&
    next.beforeSelection.start === next.beforeSelection.end &&
    next.afterSelection.start === next.afterSelection.end
  );
};

const matchesDocument = (value, length, hash) =>
  value.length === length && hashText(value) === hash;

const applyOperations = (value, operations, direction) => {
  const ordered =
    direction === "undo" ? [...operations].reverse() : operations;
  let result = value;
  for (const operation of ordered) {
    const expected =
      direction === "undo" ? operation.inserted : operation.removed;
    const replacement =
      direction === "undo" ? operation.removed : operation.inserted;
    if (
      operation.start > result.length ||
      result.slice(operation.start, operation.start + expected.length) !==
        expected
    ) {
      return null;
    }
    result =
      result.slice(0, operation.start) +
      replacement +
      result.slice(operation.start + expected.length);
  }
  return result;
};

export const createNotepadHistory = ({
  mergeDelay = NOTEPAD_HISTORY_MERGE_DELAY_MS,
  limit = NOTEPAD_HISTORY_LIMIT,
} = {}) => {
  let undoStack = [];
  let redoStack = [];
  let mergeBlocked = true;

  const record = (rawAction) => {
    const action = sanitizeNewAction(rawAction);
    if (!action) return false;

    const previous = undoStack.at(-1);
    if (
      !mergeBlocked &&
      previous &&
      canMergeNotepadEdits(previous, action, mergeDelay)
    ) {
      previous.operations.push(...action.operations);
      previous.afterSelection = action.afterSelection;
      previous.afterLength = action.afterLength;
      previous.afterHash = action.afterHash;
      previous.timestamp = action.timestamp;
    } else {
      undoStack.push(action);
      if (undoStack.length > limit) {
        undoStack.splice(0, undoStack.length - limit);
      }
    }

    redoStack = [];
    mergeBlocked = false;
    return true;
  };

  const undo = (currentValue) => {
    const action = undoStack.at(-1);
    // Refuse to apply a transaction to an unexpected document revision. This
    // protects against stale popup messages changing unrelated current text.
    if (
      !action ||
      !matchesDocument(currentValue, action.afterLength, action.afterHash)
    ) {
      return null;
    }
    const value = applyOperations(currentValue, action.operations, "undo");
    if (
      value === null ||
      !matchesDocument(value, action.beforeLength, action.beforeHash)
    ) {
      return null;
    }

    undoStack.pop();
    redoStack.push(action);
    mergeBlocked = true;
    return {
      value,
      selection: { ...action.beforeSelection },
      action: cloneAction(action),
    };
  };

  const redo = (currentValue) => {
    const action = redoStack.at(-1);
    if (
      !action ||
      !matchesDocument(currentValue, action.beforeLength, action.beforeHash)
    ) {
      return null;
    }
    const value = applyOperations(currentValue, action.operations, "redo");
    if (
      value === null ||
      !matchesDocument(value, action.afterLength, action.afterHash)
    ) {
      return null;
    }

    redoStack.pop();
    undoStack.push(action);
    mergeBlocked = true;
    return {
      value,
      selection: { ...action.afterSelection },
      action: cloneAction(action),
    };
  };

  const breakGroup = () => {
    mergeBlocked = true;
  };

  const clear = () => {
    undoStack = [];
    redoStack = [];
    mergeBlocked = true;
  };

  const exportState = (present) => ({
    present,
    undo: undoStack.map(cloneAction),
    redo: redoStack.map(cloneAction),
  });

  const importState = (state, currentValue) => {
    if (!state || state.present !== currentValue) return false;
    if (!Array.isArray(state.undo) || !Array.isArray(state.redo)) return false;

    const importedUndo = state.undo.map(sanitizeSerializedAction);
    const importedRedo = state.redo.map(sanitizeSerializedAction);
    if (importedUndo.some((action) => !action)) return false;
    if (importedRedo.some((action) => !action)) return false;
    if (
      importedUndo.length &&
      !matchesDocument(
        currentValue,
        importedUndo.at(-1).afterLength,
        importedUndo.at(-1).afterHash,
      )
    ) {
      return false;
    }
    if (
      importedRedo.length &&
      !matchesDocument(
        currentValue,
        importedRedo.at(-1).beforeLength,
        importedRedo.at(-1).beforeHash,
      )
    ) {
      return false;
    }

    undoStack = importedUndo.slice(-limit);
    redoStack = importedRedo.slice(-limit);
    mergeBlocked = true;
    return true;
  };

  return {
    record,
    undo,
    redo,
    breakGroup,
    clear,
    exportState,
    importState,
    get canUndo() {
      return undoStack.length > 0;
    },
    get canRedo() {
      return redoStack.length > 0;
    },
    get undoCount() {
      return undoStack.length;
    },
    get redoCount() {
      return redoStack.length;
    },
  };
};
