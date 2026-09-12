<template>
  <section ref="rootEl" class="relative flex h-full min-h-0 flex-col overflow-hidden bg-[#08080d]">
    <div class="flex items-center justify-between border-b border-slate-800 bg-slate-900 px-4 py-2 shrink-0">
      <div class="flex gap-1">
        <button
          @mousedown.prevent
          @click="performNotepadUndo"
          class="toolbar-btn"
          :disabled="!canUndoNotepad"
          title="Undo (Ctrl+Z)"
          aria-label="Undo notepad edit"
        >
          <Icon name="ph:arrow-u-up-left" class="w-4 h-4" />
        </button>
        <button
          @mousedown.prevent
          @click="performNotepadRedo"
          class="toolbar-btn"
          :disabled="!canRedoNotepad"
          title="Redo (Ctrl+Shift+Z)"
          aria-label="Redo notepad edit"
        >
          <Icon name="ph:arrow-u-up-right" class="w-4 h-4" />
        </button>
        <div class="mx-1 w-px bg-slate-700"></div>
        <button
          @mousedown.prevent
          @click="insertFormat('bold')"
          class="toolbar-btn"
          title="Bold (Ctrl+B)"
        >
          <Icon name="ph:text-b" class="w-4 h-4" />
        </button>
        <button
          @mousedown.prevent
          @click="insertFormat('italic')"
          class="toolbar-btn"
          title="Italic (Ctrl+I)"
        >
          <Icon name="ph:text-italic" class="w-4 h-4" />
        </button>
        <button
          @mousedown.prevent
          @click="insertFormat('math-inline')"
          class="toolbar-btn"
          title="Inline Math (Ctrl+K)"
        >
          <Icon name="ph:function" class="w-4 h-4" />
        </button>
        <button
          @mousedown.prevent
          @click="insertFormat('math-block')"
          class="toolbar-btn"
          title="Block Math (Ctrl+Shift+K)"
        >
          <Icon name="ph:sigma" class="w-4 h-4" />
        </button>
        <div class="group relative">
          <button
            @mousedown.prevent
            @click="insertFormat('code-block')"
            class="toolbar-btn"
            aria-label="Insert code block"
            aria-describedby="notepad-code-block-tip"
            title="Code block (Ctrl+Shift+C)"
          >
            <Icon name="ph:code-block" class="w-4 h-4" />
          </button>
          <div
            id="notepad-code-block-tip"
            role="tooltip"
            class="pointer-events-none absolute left-1/2 top-full z-50 mt-2 hidden w-52 -translate-x-1/2 rounded-md border border-slate-700 bg-slate-950 px-2.5 py-2 text-[10px] leading-relaxed text-slate-400 shadow-xl group-hover:block group-focus-within:block"
          >
            Add a language after the opening fence for highlighting, such
            as <code class="text-slate-200">```js</code> or
            <code class="text-slate-200">```python</code>.
          </div>
        </div>
        <button
          @mousedown.prevent
          @click="insertFormat('quote')"
          class="toolbar-btn"
          title="Important quote (Ctrl+G)"
          aria-label="Insert important quote"
        >
          <Icon name="ph:exclamation-mark" class="w-4 h-4" />
        </button>
        <button
          @mousedown.prevent
          @click="insertFormat('citation')"
          class="toolbar-btn"
          title="Page citation (Ctrl+P)"
          aria-label="Insert page citation"
        >
          <Icon name="ph:link" class="w-4 h-4" />
        </button>
        <button
          @mousedown.prevent
          @click="openNotepadPaperPicker()"
          class="toolbar-btn"
          title="Link another paper's page (Ctrl+Shift+P)"
          aria-label="Link another paper's page"
        >
          <Icon name="ph:files" class="w-4 h-4" />
        </button>
      </div>
    </div>

    <div
      v-if="notepadPaperAutocomplete && !showNotepadPaperPicker"
      class="absolute left-4 right-4 top-12 z-50 overflow-hidden rounded-lg border border-slate-700 bg-slate-950 shadow-2xl"
    >
      <button
        v-for="(paper, index) in notepadPaperSuggestions"
        :key="paper.id"
        type="button"
        class="flex w-full items-center gap-2 border-b border-slate-800 px-3 py-2 text-left text-xs last:border-0"
        :class="index === notepadPaperSuggestionIndex ? 'bg-indigo-500/15 text-white' : 'text-slate-400 hover:bg-slate-900'"
        @mousedown.prevent="chooseNotepadPaperSuggestion(paper)"
      >
        <Icon name="ph:file-pdf" class="shrink-0 text-indigo-400" />
        <span class="truncate">{{ paper.title }}</span>
        <span class="ml-auto shrink-0 text-[10px] text-slate-600">{{ paper.page_count || '?' }} pages</span>
      </button>
      <p v-if="!notepadPaperSuggestions.length" class="px-3 py-2.5 text-xs text-red-400">
        No paper matches “{{ notepadPaperAutocomplete.query }}”.
      </p>
    </div>

    <div
      v-if="notepadPaperLinkErrors.length"
      class="shrink-0 border-b border-red-500/20 bg-red-500/5 px-3 py-2 text-[10px] text-red-400"
    >
      {{ notepadPaperLinkErrors[0].message }}
    </div>

    <div
      class="notepad-live-editor flex-1 overflow-y-auto p-3 relative custom-scrollbar"
      role="textbox"
      aria-label="Markdown notepad"
      aria-multiline="true"
    >
      <textarea
        v-if="isNotepadSelectingAll"
        :ref="setNotepadTextareaRef"
        :value="notepadData"
        class="notepad-document-editor"
        aria-label="Complete Markdown note selected"
        @input="handleNotepadDocumentInput"
        @beforeinput="handleNotepadBeforeInput(null, $event)"
        @mouseup="finishNotepadDocumentSelection"
        @keyup="finishNotepadDocumentSelection"
        @blur="blurNotepadDocumentSelection"
        @pointerdown="notepadHistory.breakGroup()"
        @keydown.tab="handleNotepadTab(null, $event)"
        @keydown.escape.prevent="
          leaveNotepadDocumentSelection($event.currentTarget.selectionStart)
        "
      ></textarea>

      <template v-else>
        <div
          v-for="(line, lineIndex) in notepadLines"
          :key="lineIndex"
          class="notepad-line"
          :data-code-line-number="getNotepadCodeLineNumber(lineIndex)"
          :class="{
            'notepad-line--active': activeNotepadLine === lineIndex,
            'notepad-line--quote': /^\s*>\s/.test(line),
            'notepad-line--code':
              notepadCodeFenceLines[lineIndex]?.insideFence,
            'notepad-line--code-opening':
              notepadCodeFenceLines[lineIndex]?.isOpening,
            'notepad-line--code-closing':
              notepadCodeFenceLines[lineIndex]?.isFence &&
              !notepadCodeFenceLines[lineIndex]?.isOpening,
            'notepad-line--code-fence-hidden':
              notepadCodeFenceLines[lineIndex]?.isFence &&
              !isNotepadCodeBlockActive(lineIndex),
            'notepad-line--code-collapsed-start':
              isCollapsedCodeBlockEdge(lineIndex, 'start'),
            'notepad-line--code-collapsed-end':
              isCollapsedCodeBlockEdge(lineIndex, 'end'),
          }"
        >
          <textarea
            v-if="activeNotepadLine === lineIndex"
            :ref="setNotepadTextareaRef"
            :value="line"
            rows="1"
            :placeholder="
              lineIndex === 0 && notepadData === ''
                ? '# Notes — Markdown and $LaTeX$ supported'
                : ''
            "
            class="notepad-line-editor"
            @input="updateNotepadLine(lineIndex, $event)"
            @beforeinput="handleNotepadBeforeInput(lineIndex, $event)"
            @focus="activeNotepadLine = lineIndex"
            @click="updateNotepadPaperAutocomplete(lineIndex, $event.currentTarget.value, $event.currentTarget.selectionStart)"
            @pointerdown="notepadHistory.breakGroup()"
            @keydown="handleNotepadLineKeydown(lineIndex, $event)"
          ></textarea>
          <div
            v-else
            class="notepad-rendered-line"
            role="button"
            tabindex="0"
            :aria-label="`Edit line ${lineIndex + 1}`"
            v-html="renderNotepadLine(line, lineIndex)"
            @click="handleNotepadRenderedLineClick($event, lineIndex)"
            @keydown.enter.prevent="activateNotepadLine(lineIndex)"
            @keydown.space.prevent="activateNotepadLine(lineIndex)"
          ></div>
        </div>
      </template>
    </div>

    <div class="h-6 bg-slate-900 border-t border-slate-800 flex items-center justify-end px-2 shrink-0">
      <span class="text-[10px] text-slate-500 font-mono">
        Line {{ activeNotepadLine + 1 }} • Ctrl+Shift+P links another paper
      </span>
    </div>

    <PaperPageLinkPicker
      v-if="showNotepadPaperPicker"
      :papers="papers"
      :exclude-paper-id="excludePaperId"
      :initial-title="notepadPickerInitialTitle"
      @close="closeNotepadPaperPicker"
      @insert="insertNotepadPaperPageLink"
    />
  </section>
</template>

<script setup>
import { marked } from "marked";
import markedKatex from "marked-katex-extension";
import DOMPurify from "dompurify";
import "katex/dist/katex.min.css";
import { codeToTokensBase } from "shiki";
import {
  createNotepadHistory,
  isMergeableNotepadInputType,
} from "../utils/notepadHistory.js";
import {
  findPaperTitleAutocomplete,
  openPaperPageWindow,
  paperPageSource,
  parsePaperPageHref,
  renderPaperPageLinks,
} from "../utils/paperPageLinks.js";

marked.use(markedKatex({ throwOnError: false, output: "html" }));
marked.use({ breaks: true, gfm: true });

// This is the single implementation of the line-by-line markdown notepad,
// shared by the standalone note-taker (pages/notes/[id].vue) and the PDF
// viewer's sidebar notepad tab (pages/annotate/[id].vue) — same keyboard
// shortcuts, undo/redo, syntax highlighting, and cross-paper links in both
// places, on purpose: keeping one copy avoids the two drifting apart.
//
// It only owns its own document text + undo history; anything page-specific
// (combined-annotation saving, the PDF viewer's cross-window BroadcastChannel
// sync) lives in the host page instead, wired through the v-model, the
// "save" event, and the exposed methods below (used only by the PDF viewer,
// to mirror undo/redo history across its pop-out sidebar window).

const props = defineProps({
  modelValue: { type: String, default: "" },
  papers: { type: Array, default: () => [] },
  excludePaperId: { type: [String, Number], default: null },
  // Whether `papers` reflects a finished load — while false, paper-link
  // errors are suppressed so an empty/incomplete list doesn't flash bogus
  // "no such paper" errors before the real list arrives.
  papersReady: { type: Boolean, default: true },
});
const emit = defineEmits(["update:modelValue", "save"]);

const rootEl = ref(null);
const notepadData = ref(props.modelValue);
watch(
  () => props.modelValue,
  (value) => {
    if (value !== notepadData.value) notepadData.value = value;
  },
);
// Sync flush keeps a host page's own `notepadData` watcher (if it has one,
// e.g. for autosave or cross-window sync) observing changes on the same
// tick as the edit itself, rather than a render cycle later.
watch(notepadData, (value) => emit("update:modelValue", value), {
  flush: "sync",
});

const notepadTextarea = ref(null);
const activeNotepadLine = ref(0);
const isNotepadSelectingAll = ref(false);
const notepadHistory = createNotepadHistory();
const notepadHistorySignal = ref(0);
const canUndoNotepad = computed(() => {
  notepadHistorySignal.value;
  return notepadHistory.canUndo;
});
const canRedoNotepad = computed(() => {
  notepadHistorySignal.value;
  return notepadHistory.canRedo;
});

const notifyNotepadHistoryChanged = () => {
  notepadHistorySignal.value += 1;
};

const notepadLines = computed(() => notepadData.value.split("\n"));
const notepadCodeFenceLines = computed(() => {
  let insideFence = false;
  let language = "";
  let blockStart = null;

  return notepadLines.value.map((line, lineIndex) => {
    const fence = line.match(/^\s*```([^`]*)$/);
    if (!fence) {
      return { insideFence, isFence: false, language, blockStart };
    }

    if (insideFence) {
      const state = {
        insideFence: true,
        isFence: true,
        isOpening: false,
        language,
        blockStart,
      };
      insideFence = false;
      language = "";
      blockStart = null;
      return state;
    }

    insideFence = true;
    language = fence[1].trim();
    blockStart = lineIndex;
    return {
      insideFence: true,
      isFence: true,
      isOpening: true,
      language,
      blockStart,
    };
  });
});

watch(notepadLines, (lines) => {
  if (activeNotepadLine.value >= lines.length) {
    activeNotepadLine.value = Math.max(0, lines.length - 1);
  }
});

const setNotepadTextareaRef = (element) => {
  // Vue may clear the old row ref after assigning the newly active row.
  // Ignoring that transient null keeps keyboard focus on the live editor.
  if (!element) return;
  notepadTextarea.value = element;
  nextTick(resizeNotepadEditor);
};

const escapeNotepadCode = (line) =>
  line
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const highlightedNotepadCodeLines = shallowRef({});
let syntaxHighlightRequest = 0;
let syntaxHighlightDebounce = null;

const renderShikiTokens = (tokens) =>
  tokens
    .map((token) => {
      const color = /^#[\da-f]{3,8}$/i.test(token.color || "")
        ? ` style="color:${token.color}"`
        : "";
      return `<span${color}>${escapeNotepadCode(token.content)}</span>`;
    })
    .join("");

const refreshNotepadSyntaxHighlighting = async () => {
  const requestId = ++syntaxHighlightRequest;
  const highlightedLines = {};
  const lines = notepadLines.value;
  const fenceStates = notepadCodeFenceLines.value;

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const fenceState = fenceStates[lineIndex];
    if (!fenceState?.isOpening) continue;

    const closingIndex = fenceStates.findIndex(
      (state, candidateIndex) =>
        candidateIndex > lineIndex &&
        state?.isFence &&
        !state.isOpening &&
        state.blockStart === fenceState.blockStart,
    );
    const blockEnd = closingIndex === -1 ? lines.length : closingIndex;
    const code = lines.slice(lineIndex + 1, blockEnd).join("\n");

    try {
      const tokenLines = await codeToTokensBase(code, {
        lang: fenceState.language || "text",
        theme: "github-dark-default",
      });
      tokenLines.forEach((tokens, tokenLineIndex) => {
        highlightedLines[lineIndex + 1 + tokenLineIndex] =
          renderShikiTokens(tokens);
      });
    } catch {
      // Unknown language names remain readable as escaped plain code.
    }

    lineIndex = blockEnd;
  }

  if (requestId === syntaxHighlightRequest) {
    highlightedNotepadCodeLines.value = highlightedLines;
  }
};

const scheduleNotepadSyntaxHighlighting = () => {
  if (!import.meta.client) return;
  if (syntaxHighlightDebounce) clearTimeout(syntaxHighlightDebounce);
  syntaxHighlightDebounce = setTimeout(refreshNotepadSyntaxHighlighting, 120);
};

watch(notepadData, scheduleNotepadSyntaxHighlighting, { immediate: true });

const isNotepadCodeBlockActive = (lineIndex) => {
  const lineState = notepadCodeFenceLines.value[lineIndex];
  const activeLineState = notepadCodeFenceLines.value[activeNotepadLine.value];
  return (
    lineState?.insideFence &&
    activeLineState?.insideFence &&
    lineState.blockStart === activeLineState.blockStart
  );
};

const isCollapsedCodeBlockEdge = (lineIndex, edge) => {
  const lineState = notepadCodeFenceLines.value[lineIndex];
  if (
    !lineState?.insideFence ||
    lineState.isFence ||
    isNotepadCodeBlockActive(lineIndex)
  ) {
    return false;
  }

  const neighborIndex = edge === "start" ? lineIndex - 1 : lineIndex + 1;
  const neighbor = notepadCodeFenceLines.value[neighborIndex];
  return (
    neighbor?.isFence &&
    (edge === "start" ? neighbor.isOpening : !neighbor.isOpening)
  );
};

const getNotepadCodeLineNumber = (lineIndex) => {
  const lineState = notepadCodeFenceLines.value[lineIndex];
  if (!lineState?.insideFence || lineState.isFence) return null;
  return lineIndex - lineState.blockStart;
};

const notepadPaperLinkResult = computed(() =>
  renderPaperPageLinks(notepadData.value, props.papers),
);
const notepadPaperLinkErrors = computed(() =>
  props.papersReady ? notepadPaperLinkResult.value.errors : [],
);

const renderNotepadLine = (line, lineIndex) => {
  const codeFenceState = notepadCodeFenceLines.value[lineIndex];
  if (codeFenceState?.isFence) {
    return isNotepadCodeBlockActive(lineIndex)
      ? `<code class="notepad-code-fence-source">${escapeNotepadCode(line)}</code>`
      : "";
  }

  if (codeFenceState?.insideFence) {
    const highlighted = highlightedNotepadCodeLines.value[lineIndex];
    return `<pre class="notepad-code-block-line"><code>${highlighted || escapeNotepadCode(line) || "&#8203;"}</code></pre>`;
  }

  if (!line) return "&nbsp;";
  const citationMarkdown = line.replace(
    /~\[(\d+)\]~/g,
    (_match, page) => `[\\[${page}\\]](#notepad-page-${page})`,
  );
  const paperLinkMarkdown = renderPaperPageLinks(
    citationMarkdown,
    props.papers,
  ).markdown;
  const html = marked.parse(paperLinkMarkdown);
  return DOMPurify.sanitize(html, {
    ADD_TAGS: [
      "math",
      "semantics",
      "mrow",
      "mi",
      "mo",
      "mn",
      "msup",
      "mfrac",
      "msqrt",
      "mtext",
      "annotation",
      "annotation-xml",
    ],
    ADD_ATTR: ["xmlns", "display", "class", "style", "aria-hidden"],
  });
};

function resizeNotepadEditor() {
  const textarea = notepadTextarea.value;
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.max(32, textarea.scrollHeight)}px`;
}

const focusNotepadLine = (lineIndex, column = null) => {
  const lastLineIndex = Math.max(0, notepadLines.value.length - 1);
  activeNotepadLine.value = Math.min(
    lastLineIndex,
    Math.max(0, lineIndex),
  );
  nextTick(() => {
    const textarea = notepadTextarea.value;
    if (!textarea) return;
    textarea.focus();
    const cursor = Math.min(
      textarea.value.length,
      column === null ? textarea.value.length : Math.max(0, column),
    );
    textarea.setSelectionRange(cursor, cursor);
    resizeNotepadEditor();
    textarea.closest(".notepad-line")?.scrollIntoView({ block: "nearest" });
  });
};

const getNotepadPositionFromOffset = (offset) => {
  const safeOffset = Math.min(
    notepadData.value.length,
    Math.max(0, Number(offset) || 0),
  );
  const beforeCursor = notepadData.value.slice(0, safeOffset);
  const linesBeforeCursor = beforeCursor.split("\n");
  return {
    line: linesBeforeCursor.length - 1,
    column: linesBeforeCursor.at(-1)?.length ?? 0,
  };
};

const getNotepadLineStart = (lineIndex) =>
  notepadLines.value
    .slice(0, Math.max(0, lineIndex))
    .reduce((offset, line) => offset + line.length + 1, 0);

const setNotepadSelection = (selection, { scroll = true } = {}) => {
  const start = Math.min(
    notepadData.value.length,
    Math.max(0, Number(selection?.start) || 0),
  );
  const end = Math.min(
    notepadData.value.length,
    Math.max(start, Number(selection?.end) || start),
  );
  const direction = selection?.direction === "backward" ? "backward" : "forward";
  const startPosition = getNotepadPositionFromOffset(start);
  const endPosition = getNotepadPositionFromOffset(end);
  const spansLines = startPosition.line !== endPosition.line;

  isNotepadSelectingAll.value = spansLines;
  activeNotepadLine.value = startPosition.line;
  nextTick(() => {
    const textarea = notepadTextarea.value;
    if (!textarea) return;
    textarea.focus({ preventScroll: true });

    if (spansLines) {
      textarea.setSelectionRange(start, end, direction);
      resizeNotepadEditor();
      if (scroll) {
        const editor = textarea.closest(".notepad-live-editor");
        const lineHeight =
          textarea.scrollHeight / Math.max(1, notepadLines.value.length);
        if (editor) {
          editor.scrollTop = Math.max(
            0,
            startPosition.line * lineHeight - editor.clientHeight / 3,
          );
        }
      }
      return;
    }

    const lineStart = getNotepadLineStart(startPosition.line);
    textarea.setSelectionRange(start - lineStart, end - lineStart, direction);
    resizeNotepadEditor();
    if (scroll) {
      textarea.closest(".notepad-line")?.scrollIntoView({ block: "nearest" });
    }
  });
};

const setNotepadCursorFromOffset = (offset) => {
  setNotepadSelection({ start: offset, end: offset, direction: "forward" });
};

const beginNotepadSelectAll = () => {
  isNotepadSelectingAll.value = true;
  nextTick(() => {
    const textarea = notepadTextarea.value;
    if (!textarea) return;
    textarea.focus({ preventScroll: true });
    textarea.select();
    resizeNotepadEditor();
  });
};

const leaveNotepadDocumentSelection = (offset, { focus = true } = {}) => {
  const position = getNotepadPositionFromOffset(offset);
  isNotepadSelectingAll.value = false;
  activeNotepadLine.value = position.line;
  if (focus) {
    focusNotepadLine(position.line, position.column);
  }
};

const getNotepadDocumentSelection = (lineIndex, textarea) => {
  const documentOffset = lineIndex === null ? 0 : getNotepadLineStart(lineIndex);
  return {
    start: documentOffset + textarea.selectionStart,
    end: documentOffset + textarea.selectionEnd,
    direction:
      textarea.selectionDirection === "backward" ? "backward" : "forward",
  };
};

const inferNotepadSelectionBeforeInput = (before, after) => {
  let prefixLength = 0;
  const sharedLength = Math.min(before.length, after.length);
  while (
    prefixLength < sharedLength &&
    before[prefixLength] === after[prefixLength]
  ) {
    prefixLength += 1;
  }

  let suffixLength = 0;
  while (
    suffixLength < sharedLength - prefixLength &&
    before[before.length - 1 - suffixLength] ===
      after[after.length - 1 - suffixLength]
  ) {
    suffixLength += 1;
  }

  return {
    start: prefixLength,
    end: before.length - suffixLength,
    direction: "forward",
  };
};

let pendingNotepadInput = null;

const commitNotepadEdit = (
  after,
  {
    before = notepadData.value,
    beforeSelection,
    afterSelection,
    inputType = "unknown",
    forceNewGroup = false,
  } = {},
) => {
  if (before === after) return false;
  const recorded = notepadHistory.record({
    before,
    after,
    beforeSelection,
    afterSelection,
    inputType,
    forceNewGroup,
    timestamp: Date.now(),
  });
  if (!recorded) return false;

  notepadData.value = after;
  notifyNotepadHistoryChanged();
  return true;
};

const handleNotepadBeforeInput = (lineIndex, event) => {
  if (event.inputType === "historyUndo" || event.inputType === "historyRedo") {
    event.preventDefault();
    pendingNotepadInput = null;
    if (event.inputType === "historyUndo") void performNotepadUndo();
    else void performNotepadRedo();
    return;
  }

  pendingNotepadInput = {
    target: event.currentTarget,
    before: notepadData.value,
    beforeSelection: getNotepadDocumentSelection(
      lineIndex,
      event.currentTarget,
    ),
  };
};

const handleNotepadDocumentInput = (event) => {
  const before = notepadData.value;
  const after = event.currentTarget.value;
  const afterSelection = getNotepadDocumentSelection(null, event.currentTarget);
  const beforeSelection =
    pendingNotepadInput?.target === event.currentTarget &&
    pendingNotepadInput.before === before
      ? pendingNotepadInput.beforeSelection
      : inferNotepadSelectionBeforeInput(before, after);
  pendingNotepadInput = null;
  commitNotepadEdit(after, {
    before,
    beforeSelection,
    afterSelection,
    inputType: event.inputType,
    forceNewGroup: !isMergeableNotepadInputType(event.inputType),
  });
  const cursorPosition = getNotepadPositionFromOffset(afterSelection.end);
  updateNotepadPaperAutocomplete(
    cursorPosition.line,
    after.split("\n")[cursorPosition.line] || "",
    cursorPosition.column,
  );
  leaveNotepadDocumentSelection(afterSelection.end);
};

const finishNotepadDocumentSelection = (event) => {
  const textarea = event.currentTarget;
  if (textarea.selectionStart !== textarea.selectionEnd) return;
  leaveNotepadDocumentSelection(textarea.selectionStart);
};

const blurNotepadDocumentSelection = (event) => {
  notepadHistory.breakGroup();
  leaveNotepadDocumentSelection(event.currentTarget.selectionStart, {
    focus: false,
  });
};

const activateNotepadLine = (lineIndex) => {
  notepadHistory.breakGroup();
  focusNotepadLine(lineIndex);
};

const handleNotepadRenderedLineClick = (event, lineIndex) => {
  const paperLink = event.target.closest?.(
    'a[href^="#research-marker-paper-"]',
  );
  const paperTarget = parsePaperPageHref(paperLink?.getAttribute("href"));
  if (paperTarget) {
    event.preventDefault();
    event.stopPropagation();
    void openPaperPageWindow(paperTarget.paperId, paperTarget.page);
    return;
  }

  // Page citations (~[N]~) point at a PDF page, which only makes sense in
  // the annotate viewer; the standalone note-taker has no PDF to jump to, so
  // clicking one here just starts editing the line like any other click.
  activateNotepadLine(lineIndex);
};

const notepadPaperAutocomplete = ref(null);
const notepadPaperSuggestionIndex = ref(0);
const showNotepadPaperPicker = ref(false);
const notepadPickerInitialTitle = ref("");
const notepadPickerReplacement = ref(null);
const availablePaperLinkDocuments = computed(() =>
  props.papers.filter(
    (paper) => String(paper.id) !== String(props.excludePaperId ?? ""),
  ),
);
const notepadPaperSuggestions = computed(() => {
  const query = String(notepadPaperAutocomplete.value?.query || "")
    .trim()
    .toLocaleLowerCase();
  return availablePaperLinkDocuments.value
    .filter((paper) => !query || paper.title.toLocaleLowerCase().includes(query))
    .slice(0, 7);
});

const updateNotepadPaperAutocomplete = (lineIndex, value, cursor) => {
  const match = findPaperTitleAutocomplete(value, cursor);
  notepadPaperAutocomplete.value = match
    ? {
        ...match,
        lineIndex,
        start: getNotepadLineStart(lineIndex) + match.start,
        end: getNotepadLineStart(lineIndex) + match.end,
      }
    : null;
  notepadPaperSuggestionIndex.value = 0;
};

const openNotepadPaperPicker = (initialTitle = "", replacement = null) => {
  const textarea = notepadTextarea.value;
  let range = replacement;
  if (!range && textarea) {
    range = getNotepadDocumentSelection(
      isNotepadSelectingAll.value ? null : activeNotepadLine.value,
      textarea,
    );
    if (!initialTitle && range.start !== range.end) {
      initialTitle = notepadData.value.slice(range.start, range.end);
    }
  }
  notepadPickerInitialTitle.value = initialTitle;
  notepadPickerReplacement.value = range;
  showNotepadPaperPicker.value = true;
  notepadPaperAutocomplete.value = null;
};

const closeNotepadPaperPicker = () => {
  showNotepadPaperPicker.value = false;
  notepadPickerReplacement.value = null;
  nextTick(() => notepadTextarea.value?.focus({ preventScroll: true }));
};

const chooseNotepadPaperSuggestion = (paper) => {
  openNotepadPaperPicker(paper.title, notepadPaperAutocomplete.value);
};

const insertNotepadPaperPageLink = ({ paper, page }) => {
  const replacement = notepadPickerReplacement.value;
  const start = replacement?.start ?? notepadData.value.length;
  const end = replacement?.end ?? start;
  const source = paperPageSource(paper, page);
  const before = notepadData.value;
  const after = `${before.slice(0, start)}${source}${before.slice(end)}`;
  const cursor = start + source.length;
  commitNotepadEdit(after, {
    before,
    beforeSelection: { start, end, direction: "forward" },
    afterSelection: { start: cursor, end: cursor, direction: "forward" },
    inputType: "insert-paper-page-link",
    forceNewGroup: true,
  });
  closeNotepadPaperPicker();
  setNotepadCursorFromOffset(cursor);
};

const updateNotepadLine = (lineIndex, event) => {
  const before = notepadData.value;
  const value = event.target.value;
  const cursor = event.target.selectionStart;
  const selectionEnd = event.target.selectionEnd;
  const replacementLines = value.split("\n");
  const lines = [...notepadLines.value];
  const lineStart = getNotepadLineStart(lineIndex);
  lines.splice(lineIndex, 1, ...replacementLines);
  const after = lines.join("\n");
  const afterSelection = {
    start: lineStart + cursor,
    end: lineStart + selectionEnd,
    direction:
      event.target.selectionDirection === "backward" ? "backward" : "forward",
  };
  const beforeSelection =
    pendingNotepadInput?.target === event.currentTarget &&
    pendingNotepadInput.before === before
      ? pendingNotepadInput.beforeSelection
      : inferNotepadSelectionBeforeInput(before, after);
  pendingNotepadInput = null;
  commitNotepadEdit(after, {
    before,
    beforeSelection,
    afterSelection,
    inputType: event.inputType,
    forceNewGroup: !isMergeableNotepadInputType(event.inputType),
  });
  updateNotepadPaperAutocomplete(lineIndex, value, cursor);

  if (replacementLines.length > 1) {
    const beforeCursor = value.slice(0, cursor).split("\n");
    focusNotepadLine(
      lineIndex + beforeCursor.length - 1,
      beforeCursor.at(-1)?.length ?? 0,
    );
  } else {
    nextTick(() => {
      const textarea = notepadTextarea.value;
      if (!textarea || activeNotepadLine.value !== lineIndex) return;
      textarea.focus({ preventScroll: true });
      textarea.setSelectionRange(cursor, selectionEnd);
      resizeNotepadEditor();
    });
  }
};

const splitNotepadLine = (lineIndex, event) => {
  event.preventDefault();
  const textarea = event.currentTarget;
  const before = notepadData.value;
  const lineStart = getNotepadLineStart(lineIndex);
  const line = notepadLines.value[lineIndex] ?? "";
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const lines = [...notepadLines.value];
  lines.splice(lineIndex, 1, line.slice(0, start), line.slice(end));
  const after = lines.join("\n");
  const afterCursor = lineStart + start + 1;
  commitNotepadEdit(after, {
    before,
    beforeSelection: getNotepadDocumentSelection(lineIndex, textarea),
    afterSelection: {
      start: afterCursor,
      end: afterCursor,
      direction: "forward",
    },
    inputType: "insertParagraph",
    forceNewGroup: true,
  });
  focusNotepadLine(lineIndex + 1, 0);
};

// Appends a fresh empty line after the current last line and moves there,
// leaving the last line's own text untouched — used whenever Down arrow,
// Right arrow, or Ctrl/Cmd+Enter reach "there is no next line yet".
const appendNotepadLine = (event) => {
  event.preventDefault();
  const before = notepadData.value;
  const after = `${before}\n`;
  const afterCursor = after.length;
  commitNotepadEdit(after, {
    before,
    beforeSelection: {
      start: before.length,
      end: before.length,
      direction: "forward",
    },
    afterSelection: {
      start: afterCursor,
      end: afterCursor,
      direction: "forward",
    },
    inputType: "insertParagraph",
    forceNewGroup: true,
  });
  focusNotepadLine(notepadLines.value.length - 1, 0);
};

const mergeNotepadLineBackward = (lineIndex, event) => {
  const textarea = event.currentTarget;
  if (
    lineIndex === 0 ||
    textarea.selectionStart !== 0 ||
    textarea.selectionEnd !== 0
  ) {
    return;
  }

  event.preventDefault();
  const before = notepadData.value;
  const beforeSelection = getNotepadDocumentSelection(lineIndex, textarea);
  const lines = [...notepadLines.value];
  const previousLineStart = lines
    .slice(0, lineIndex - 1)
    .reduce((offset, line) => offset + line.length + 1, 0);
  const previousLength = lines[lineIndex - 1].length;
  lines.splice(
    lineIndex - 1,
    2,
    lines[lineIndex - 1] + lines[lineIndex],
  );
  const after = lines.join("\n");
  const afterCursor = previousLineStart + previousLength;
  commitNotepadEdit(after, {
    before,
    beforeSelection,
    afterSelection: {
      start: afterCursor,
      end: afterCursor,
      direction: "forward",
    },
    inputType: "deleteContentBackward",
  });
  focusNotepadLine(lineIndex - 1, previousLength);
};

const mergeNotepadLineForward = (lineIndex, event) => {
  const textarea = event.currentTarget;
  const line = notepadLines.value[lineIndex] ?? "";
  if (
    lineIndex >= notepadLines.value.length - 1 ||
    textarea.selectionStart !== line.length ||
    textarea.selectionEnd !== line.length
  ) {
    return;
  }

  event.preventDefault();
  const before = notepadData.value;
  const beforeSelection = getNotepadDocumentSelection(lineIndex, textarea);
  const lines = [...notepadLines.value];
  const lineStart = lines
    .slice(0, lineIndex)
    .reduce((offset, item) => offset + item.length + 1, 0);
  lines.splice(lineIndex, 2, lines[lineIndex] + lines[lineIndex + 1]);
  const after = lines.join("\n");
  const afterCursor = lineStart + line.length;
  commitNotepadEdit(after, {
    before,
    beforeSelection,
    afterSelection: {
      start: afterCursor,
      end: afterCursor,
      direction: "forward",
    },
    inputType: "deleteContentForward",
  });
  focusNotepadLine(lineIndex, line.length);
};

const moveNotepadCursorVertically = (lineIndex, direction, event) => {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  const nextLine = lineIndex + direction;
  if (nextLine < 0) return;
  if (nextLine >= notepadLines.value.length) {
    // Down arrow past the last line creates one to move into, rather than
    // doing nothing just because it hasn't been "created" yet.
    if (direction > 0) appendNotepadLine(event);
    return;
  }
  event.preventDefault();
  focusNotepadLine(nextLine, event.currentTarget.selectionStart);
};

// Ctrl/Cmd+Enter is pure cursor navigation: jump to the start of the next
// line without splitting or otherwise editing the text, unlike plain Enter.
const jumpNotepadCursorToNextLineStart = (lineIndex, event) => {
  event.preventDefault();
  notepadHistory.breakGroup();
  const nextLineIndex = lineIndex + 1;
  if (nextLineIndex >= notepadLines.value.length) {
    appendNotepadLine(event);
    return;
  }
  focusNotepadLine(nextLineIndex, 0);
};

// Each line lives in its own textarea, so Left/Right arrow at a line
// boundary can't naturally cross into the neighboring line — do it manually.
const moveNotepadCursorToPreviousLineEnd = (lineIndex, event) => {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (lineIndex <= 0) return;
  const textarea = event.currentTarget;
  if (textarea.selectionStart !== 0 || textarea.selectionEnd !== 0) return;
  event.preventDefault();
  const previousLine = notepadLines.value[lineIndex - 1] ?? "";
  focusNotepadLine(lineIndex - 1, previousLine.length);
};

const moveNotepadCursorToNextLineStart = (lineIndex, event) => {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  const textarea = event.currentTarget;
  const line = notepadLines.value[lineIndex] ?? "";
  if (
    textarea.selectionStart !== line.length ||
    textarea.selectionEnd !== line.length
  ) {
    return;
  }
  // On the last line there's no next line to jump to, so create one.
  if (lineIndex >= notepadLines.value.length - 1) {
    appendNotepadLine(event);
    return;
  }
  event.preventDefault();
  focusNotepadLine(lineIndex + 1, 0);
};

const NOTEPAD_TAB_SIZE = 2;

const handleNotepadTab = (lineIndex, event) => {
  event.preventDefault();
  const textarea = event.currentTarget;
  const beforeSelection = getNotepadDocumentSelection(lineIndex, textarea);
  const value = textarea.value;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  let updatedValue = value;
  let selectionStart = start;
  let selectionEnd = end;

  if (!event.shiftKey && start === end) {
    const currentLineStart = value.lastIndexOf("\n", start - 1) + 1;
    const column = start - currentLineStart;
    const spaces = " ".repeat(
      NOTEPAD_TAB_SIZE - (column % NOTEPAD_TAB_SIZE),
    );
    updatedValue = value.slice(0, start) + spaces + value.slice(end);
    selectionStart = start + spaces.length;
    selectionEnd = selectionStart;
  } else {
    const selectedLineStart = value.lastIndexOf("\n", start - 1) + 1;
    const endProbe = end > start && value[end - 1] === "\n" ? end - 1 : end;
    const followingNewline = value.indexOf("\n", endProbe);
    const selectedLineEnd =
      followingNewline === -1 ? value.length : followingNewline;
    const selectedLines = value
      .slice(selectedLineStart, selectedLineEnd)
      .split("\n");

    const transformedLines = selectedLines.map((selectedLine) => {
      if (!event.shiftKey) return " ".repeat(NOTEPAD_TAB_SIZE) + selectedLine;
      if (selectedLine.startsWith("\t")) return selectedLine.slice(1);
      const spacesToRemove =
        selectedLine.match(new RegExp(`^ {1,${NOTEPAD_TAB_SIZE}}`))?.[0]
          .length ?? 0;
      return selectedLine.slice(spacesToRemove);
    });
    const transformedSelection = transformedLines.join("\n");
    updatedValue =
      value.slice(0, selectedLineStart) +
      transformedSelection +
      value.slice(selectedLineEnd);

    if (start === end) {
      const removed = selectedLines[0].length - transformedLines[0].length;
      selectionStart = Math.max(selectedLineStart, start - removed);
      selectionEnd = selectionStart;
    } else {
      selectionStart = selectedLineStart;
      selectionEnd = selectedLineStart + transformedSelection.length;
    }
  }

  if (updatedValue === value) return;

  const before = notepadData.value;
  const documentOffset =
    lineIndex === null
      ? 0
      : notepadLines.value
          .slice(0, lineIndex)
          .reduce((offset, line) => offset + line.length + 1, 0);
  let after = updatedValue;

  if (lineIndex !== null) {
    const lines = [...notepadLines.value];
    lines.splice(lineIndex, 1, ...updatedValue.split("\n"));
    after = lines.join("\n");
  }

  commitNotepadEdit(after, {
    before,
    beforeSelection,
    afterSelection: {
      start: documentOffset + selectionStart,
      end: documentOffset + selectionEnd,
      direction:
        textarea.selectionDirection === "backward" ? "backward" : "forward",
    },
    inputType: event.shiftKey ? "formatOutdent" : "formatIndent",
    forceNewGroup: true,
  });

  nextTick(() => {
    const editor = notepadTextarea.value;
    if (!editor) return;
    editor.focus({ preventScroll: true });
    editor.setSelectionRange(selectionStart, selectionEnd);
    resizeNotepadEditor();
  });
};

const handleNotepadLineKeydown = (lineIndex, event) => {
  if (
    notepadPaperAutocomplete.value?.lineIndex === lineIndex &&
    !showNotepadPaperPicker.value
  ) {
    if (
      (event.key === "ArrowDown" || event.key === "ArrowUp") &&
      notepadPaperSuggestions.value.length
    ) {
      event.preventDefault();
      const change = event.key === "ArrowDown" ? 1 : -1;
      notepadPaperSuggestionIndex.value =
        (notepadPaperSuggestionIndex.value +
          change +
          notepadPaperSuggestions.value.length) %
        notepadPaperSuggestions.value.length;
      return;
    }
    if (event.key === "Enter" && notepadPaperSuggestions.value.length) {
      event.preventDefault();
      chooseNotepadPaperSuggestion(
        notepadPaperSuggestions.value[notepadPaperSuggestionIndex.value],
      );
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      notepadPaperAutocomplete.value = null;
      return;
    }
  }

  if (
    [
      "ArrowLeft",
      "ArrowRight",
      "ArrowUp",
      "ArrowDown",
      "Home",
      "End",
      "PageUp",
      "PageDown",
    ].includes(event.key)
  ) {
    notepadHistory.breakGroup();
  }

  switch (event.key) {
    case "Tab":
      handleNotepadTab(lineIndex, event);
      break;
    case "Enter":
      if (event.ctrlKey || event.metaKey) {
        jumpNotepadCursorToNextLineStart(lineIndex, event);
      } else {
        splitNotepadLine(lineIndex, event);
      }
      break;
    case "Backspace":
      mergeNotepadLineBackward(lineIndex, event);
      break;
    case "Delete":
      mergeNotepadLineForward(lineIndex, event);
      break;
    case "ArrowUp":
      moveNotepadCursorVertically(lineIndex, -1, event);
      break;
    case "ArrowDown":
      moveNotepadCursorVertically(lineIndex, 1, event);
      break;
    case "ArrowLeft":
      moveNotepadCursorToPreviousLineEnd(lineIndex, event);
      break;
    case "ArrowRight":
      moveNotepadCursorToNextLineStart(lineIndex, event);
      break;
  }
};

const selectActiveNotepadLine = () => {
  if (!isNotepadSelectingAll.value) {
    notepadTextarea.value?.select();
    return;
  }

  const offset = notepadTextarea.value?.selectionStart ?? 0;
  leaveNotepadDocumentSelection(offset);
  nextTick(() => notepadTextarea.value?.select());
};

// Formatting Helper
const insertFormat = (format) => {
  const textarea = notepadTextarea.value;
  if (!textarea) return;

  const lineStart = isNotepadSelectingAll.value
    ? 0
    : notepadLines.value
        .slice(0, activeNotepadLine.value)
        .reduce((offset, line) => offset + line.length + 1, 0);
  const start = lineStart + textarea.selectionStart;
  const end = lineStart + textarea.selectionEnd;
  const text = notepadData.value;
  const selection = text.substring(start, end);
  const hasSelection = start !== end;

  let insertion = "";
  let newCursorPos = end;

  switch (format) {
    case "bold":
      insertion = `**${selection}**`;
      newCursorPos = hasSelection ? start + insertion.length : start + 2;
      break;
    case "italic":
      insertion = `*${selection}*`;
      newCursorPos = hasSelection ? start + insertion.length : start + 1;
      break;
    case "math-inline":
      insertion = `$${selection}$`;
      newCursorPos = hasSelection ? start + insertion.length : start + 1;
      break;
    case "math-block":
      insertion = `$$\n${selection}\n$$`;
      newCursorPos = hasSelection ? start + insertion.length : start + 3;
      break;
    case "code-block": {
      insertion = `\`\`\`\n${selection}\n\`\`\``;
      newCursorPos = hasSelection ? start + insertion.length : start + 4;
      break;
    }
    case "quote": {
      insertion = `> ${selection}`;
      newCursorPos = start + insertion.length;
      break;
    }
    case "citation": {
      insertion = `~[${selection}]~`;
      newCursorPos = hasSelection ? start + insertion.length : start + 2;
      break;
    }
  }

  const after = text.substring(0, start) + insertion + text.substring(end);
  commitNotepadEdit(after, {
    before: text,
    beforeSelection: {
      start,
      end,
      direction:
        textarea.selectionDirection === "backward" ? "backward" : "forward",
    },
    afterSelection: {
      start: newCursorPos,
      end: newCursorPos,
      direction: "forward",
    },
    inputType: `format-${format}`,
    forceNewGroup: true,
  });

  isNotepadSelectingAll.value = false;
  setNotepadCursorFromOffset(newCursorPos);
};

const performNotepadUndo = async () => {
  const result = notepadHistory.undo(notepadData.value);
  if (!result) return;

  notepadData.value = result.value;
  notifyNotepadHistoryChanged();
  setNotepadSelection(result.selection);
  emit("save");
};

const performNotepadRedo = async () => {
  const result = notepadHistory.redo(notepadData.value);
  if (!result) return;

  notepadData.value = result.value;
  notifyNotepadHistoryChanged();
  setNotepadSelection(result.selection);
  emit("save");
};

// keyboard shortcuts, scoped to this editor instance
const handleKeyboardShortcuts = (event) => {
  const isNotepadFocused = Boolean(
    (rootEl.value?.contains(event.target) &&
      event.target?.closest?.(".notepad-live-editor")) ||
      document.activeElement === notepadTextarea.value,
  );
  if (!isNotepadFocused) return;

  const hasCommandModifier = (event.ctrlKey || event.metaKey) && !event.altKey;
  const key = event.key.toLowerCase();

  if (
    hasCommandModifier &&
    ((key === "z" && !event.shiftKey) || (key === "y" && !event.shiftKey))
  ) {
    event.preventDefault();
    if (key === "z") void performNotepadUndo();
    else void performNotepadRedo();
    return;
  }
  if (hasCommandModifier && key === "z" && event.shiftKey) {
    event.preventDefault();
    void performNotepadRedo();
    return;
  }

  // Select the complete note, including lines currently rendered as Markdown.
  if (hasCommandModifier && event.shiftKey && key === "a") {
    event.preventDefault();
    beginNotepadSelectAll();
    return;
  }
  // Each live textarea represents one line, so Ctrl/Cmd+A selects that line.
  if (hasCommandModifier && !event.shiftKey && key === "a") {
    event.preventDefault();
    selectActiveNotepadLine();
    return;
  }

  if (hasCommandModifier && event.shiftKey && key === "p") {
    event.preventDefault();
    openNotepadPaperPicker();
    return;
  }

  if (hasCommandModifier && !event.shiftKey && key === "s") {
    event.preventDefault();
    emit("save");
    return;
  }

  const format = hasCommandModifier
    ? {
        "plain:b": "bold",
        "plain:i": "italic",
        "plain:k": "math-inline",
        "shift:k": "math-block",
        "shift:c": "code-block",
        "plain:g": "quote",
        "plain:p": "citation",
      }[`${event.shiftKey ? "shift" : "plain"}:${key}`]
    : null;

  if (format) {
    event.preventDefault();
    insertFormat(format);
  }
};

onMounted(() => document.addEventListener("keydown", handleKeyboardShortcuts));
onBeforeUnmount(() =>
  document.removeEventListener("keydown", handleKeyboardShortcuts),
);

// Exposed only for hosts that need to mirror undo/redo history somewhere
// external (the PDF viewer syncs it across its pop-out sidebar window).
// Getter functions, not raw refs/computeds, so a host's own computed that
// calls e.g. `canUndo()` still tracks this component's reactive state
// correctly regardless of Vue's ref-unwrapping rules for exposed instances.
defineExpose({
  undo: performNotepadUndo,
  redo: performNotepadRedo,
  canUndo: () => canUndoNotepad.value,
  canRedo: () => canRedoNotepad.value,
  resize: resizeNotepadEditor,
  focus: () => notepadTextarea.value?.focus({ preventScroll: true }),
  exportHistoryState: () => notepadHistory.exportState(notepadData.value),
  importHistoryState: (state, presentValue) => {
    const imported = notepadHistory.importState(state, presentValue);
    if (!imported) notepadHistory.clear();
    notifyNotepadHistoryChanged();
    return imported;
  },
});
</script>

<style scoped>
.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  color: #94a3b8;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background-color: #334155;
  color: #f8fafc;
}

.toolbar-btn:disabled {
  cursor: not-allowed;
  opacity: 0.35;
}

.toolbar-btn:disabled:hover {
  background-color: transparent;
  color: #94a3b8;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 999px;
}

.notepad-line {
  min-height: 2rem;
  border-left: 2px solid transparent;
  border-radius: 0.25rem;
}

.notepad-line--active {
  border-left-color: rgb(99 102 241 / 0.8);
  background: rgb(30 41 59 / 0.55);
}

.notepad-line--quote {
  border-left-color: rgb(245 158 11 / 0.9);
  background: rgb(245 158 11 / 0.06);
}

.notepad-line--code {
  border-left-color: rgb(100 116 139 / 0.8);
  border-radius: 0;
  background: rgb(30 35 45 / 0.96);
}

.notepad-line--code[data-code-line-number] {
  display: grid;
  grid-template-columns: 2.75rem minmax(0, 1fr);
}

.notepad-line--code[data-code-line-number]::before {
  content: attr(data-code-line-number);
  padding: 0.15rem 0.65rem 0.15rem 0;
  border-right: 1px solid rgb(71 85 105 / 0.55);
  color: rgb(100 116 139);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.75rem;
  line-height: 1.8667;
  text-align: right;
  user-select: none;
}

.notepad-line--code.notepad-line--active[data-code-line-number]::before {
  padding-top: 0.35rem;
  padding-bottom: 0.35rem;
}

.notepad-line--code-opening {
  border-radius: 0.35rem 0.35rem 0 0;
}

.notepad-line--code-closing {
  border-radius: 0 0 0.35rem 0.35rem;
}

.notepad-line--code-collapsed-start {
  border-radius: 0.35rem 0.35rem 0 0;
}

.notepad-line--code-collapsed-end {
  border-radius: 0 0 0.35rem 0.35rem;
}

.notepad-line--code-collapsed-start.notepad-line--code-collapsed-end {
  border-radius: 0.35rem;
}

.notepad-line--code-fence-hidden {
  display: none;
}

.notepad-line-editor {
  display: block;
  width: 100%;
  min-height: 2rem;
  padding: 0.35rem 0.65rem;
  overflow: hidden;
  resize: none;
  border: 0;
  outline: none;
  background: transparent;
  color: rgb(226 232 240);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.875rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.notepad-line-editor::placeholder {
  color: rgb(71 85 105);
}

.notepad-document-editor {
  display: block;
  width: 100%;
  min-height: 100%;
  padding: 0.35rem 0.65rem;
  overflow: hidden;
  resize: none;
  border: 0;
  outline: none;
  background: rgb(15 23 42 / 0.45);
  color: rgb(226 232 240);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.875rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.notepad-rendered-line {
  min-height: 2rem;
  padding: 0.35rem 0.65rem;
  cursor: text;
  color: rgb(203 213 225);
  font-size: 0.875rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
  transition: background-color 120ms ease;
}

.notepad-rendered-line:hover,
.notepad-rendered-line:focus-visible {
  background: rgb(30 41 59 / 0.4);
  outline: none;
}

.notepad-rendered-line :deep(p),
.notepad-rendered-line :deep(ul),
.notepad-rendered-line :deep(ol),
.notepad-rendered-line :deep(blockquote) {
  margin: 0;
}

.notepad-rendered-line :deep(blockquote) {
  border-radius: 0 0.25rem 0.25rem 0;
  background: rgb(245 158 11 / 0.08);
  padding: 0.45rem 0.75rem;
  color: rgb(241 245 249);
}

.notepad-rendered-line :deep(ul),
.notepad-rendered-line :deep(ol) {
  padding-left: 1.25rem;
}

.notepad-rendered-line :deep(ul) {
  list-style-type: disc;
}

.notepad-rendered-line :deep(ol) {
  list-style-type: decimal;
}

.notepad-rendered-line :deep(li) {
  display: list-item;
}

.notepad-rendered-line :deep(h1),
.notepad-rendered-line :deep(h2),
.notepad-rendered-line :deep(h3),
.notepad-rendered-line :deep(h4),
.notepad-rendered-line :deep(h5),
.notepad-rendered-line :deep(h6) {
  margin: 0;
  color: rgb(165 180 252);
  font-weight: 700;
  line-height: 1.35;
}

.notepad-rendered-line :deep(h1) { font-size: 1.5rem; }
.notepad-rendered-line :deep(h2) { font-size: 1.3rem; }
.notepad-rendered-line :deep(h3) { font-size: 1.15rem; }
.notepad-rendered-line :deep(h4),
.notepad-rendered-line :deep(h5),
.notepad-rendered-line :deep(h6) { font-size: 1rem; }

.notepad-rendered-line :deep(strong) {
  color: rgb(241 245 249);
  font-weight: 700;
}

.notepad-rendered-line :deep(code) {
  border-radius: 0.2rem;
  background: rgb(30 41 59);
  padding: 0.1rem 0.3rem;
  color: rgb(252 211 77);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.notepad-line--code .notepad-rendered-line {
  min-width: 0;
  padding-top: 0.15rem;
  padding-bottom: 0.15rem;
}

.notepad-line--code .notepad-line-editor {
  min-width: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.notepad-rendered-line :deep(.notepad-code-block-line) {
  margin: 0;
  max-width: 100%;
  overflow-x: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.notepad-rendered-line :deep(.notepad-code-block-line code) {
  display: block;
  background: transparent;
  padding: 0;
  color: rgb(226 232 240);
  white-space: inherit;
  overflow-wrap: inherit;
}

.notepad-rendered-line :deep(.notepad-code-fence-source) {
  display: block;
  background: transparent;
  padding: 0;
  color: rgb(148 163 184);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8rem;
}

.notepad-rendered-line :deep(a) {
  color: rgb(129 140 248);
  text-decoration: underline;
}

.notepad-rendered-line :deep(a[href^="#notepad-page-"]) {
  display: inline-flex;
  align-items: center;
  border-radius: 0.25rem;
  background: rgb(79 70 229 / 0.2);
  padding: 0.05rem 0.3rem;
  color: rgb(165 180 252);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8em;
  font-weight: 600;
  text-decoration: none;
}

.notepad-rendered-line :deep(a[href^="#notepad-page-"]:hover) {
  background: rgb(79 70 229 / 0.35);
  color: rgb(224 231 255);
}

.notepad-rendered-line :deep(a[href^="#research-marker-paper-"]) {
  display: inline-flex;
  align-items: center;
  border-radius: 0.3rem;
  border: 1px solid rgb(34 211 238 / 0.2);
  background: rgb(34 211 238 / 0.08);
  padding: 0.05rem 0.35rem;
  color: rgb(103 232 249);
  font-size: 0.86em;
  font-weight: 600;
  text-decoration: none;
}

.notepad-rendered-line :deep(a[href^="#research-marker-paper-"]:hover) {
  border-color: rgb(34 211 238 / 0.45);
  background: rgb(34 211 238 / 0.15);
}

.notepad-rendered-line :deep(.paper-page-link-error) {
  color: rgb(248 113 113);
  text-decoration: wavy underline;
  text-decoration-color: rgb(239 68 68);
}

.notepad-rendered-line :deep(.katex-display) {
  margin: 0;
}

:deep(.katex-display) {
  display: block;
  max-width: 100%;
  margin: 0.5em 0;
  overflow-x: auto !important;
  overflow-y: hidden;
  padding-bottom: 6px;
}

:deep(.katex) {
  font-size: 1.1em;
}

:deep(p .katex),
:deep(span .katex) {
  display: inline-block;
  max-width: 100%;
}

:deep(.katex-display)::-webkit-scrollbar {
  height: 4px;
  background: transparent;
}

:deep(.katex-display)::-webkit-scrollbar-thumb {
  background-color: #475569;
  border-radius: 4px;
}

:deep(.katex-display)::-webkit-scrollbar-track {
  background: transparent;
}
</style>
