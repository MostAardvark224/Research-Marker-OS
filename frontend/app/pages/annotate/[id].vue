<script setup>
import { select } from "#build/ui";
import "pdfjs-dist/web/pdf_viewer.css";
import katex from "katex";
import "katex/dist/katex.min.css";
import { marked } from "marked";
import markedKatex from "marked-katex-extension";
import DOMPurify from "dompurify";

marked.use(markedKatex({ throwOnError: false, output: "html" }));
marked.use({ breaks: true, gfm: true });

const {
  public: { apiBaseURL },
} = useRuntimeConfig();

// General States
const route = useRoute();
const id = route.params.id;
const isSidebarPopout = route.query.sidebarPopout === "1";
const canPopOutSidebar =
  typeof window !== "undefined" && Boolean(window.electronAPI?.popOutSidebar);
const DEFAULT_ZOOM = 200;
const MAX_CANVAS_DEVICE_PIXEL_RATIO = 2.25;
const RENDERED_PAGE_BUFFER = 2;

const loading = ref(true);
const error = ref(null);
const paperTitle = ref("");

useHead({
  title: () =>
    paperTitle.value
      ? `${paperTitle.value} | Research Marker`
      : "Research Marker",
});

let pdfjsLib = null;
let AnnotationFactory = null;
let TextLayerClass = null;
let pdfDoc = null;
let pdfBytes = null;
let factory = null;
const savedHighlights = ref([]);
const stickyNoteData = ref([]);
const notepadData = ref("");

const undoStack = ref([]);
const redoStack = ref([]);

const activeStickyNoteId = ref(null);
const stickyNoteTextareaRefs = new Map();

const setStickyNoteTextareaRef = (noteId, element) => {
  if (element) {
    stickyNoteTextareaRefs.set(noteId, element);
  } else {
    stickyNoteTextareaRefs.delete(noteId);
  }
};

const focusStickyNoteEditor = async (noteId) => {
  await nextTick();
  const textarea = stickyNoteTextareaRefs.get(noteId);
  if (!textarea) return;

  textarea.focus();
  const cursorPosition = textarea.value.length;
  textarea.setSelectionRange(cursorPosition, cursorPosition);
};

const pageContainerRefs = ref([]);
const canvasRefs = ref([]);
const textLayerRefs = ref([]);
const mainScrollContainer = ref(null);

const textSelectionMenu = reactive({
  visible: false,
  x: 0,
  y: 0,
  text: "",
  page: null,
  highlightData: null,
});

const closeTextSelectionMenu = () => {
  textSelectionMenu.visible = false;
};

const handleDocumentPointerDown = (event) => {
  if (!event.target.closest?.(".pdf-selection-menu")) {
    closeTextSelectionMenu();
  }
};

const SIDEBAR_WIDTH_MIN = 200;
const SIDEBAR_WIDTH_DEFAULT = 320;
const storedSidebarOpen = (() => {
  try {
    const v = localStorage.getItem("annotateSidebarOpen");
    if (v === null) return true;
    return v === "1" || v === "true";
  } catch {
    return true;
  }
})();
const storedSidebarWidth = (() => {
  try {
    const v = parseInt(localStorage.getItem("annotateSidebarWidth") || "", 10);
    if (!Number.isFinite(v)) return SIDEBAR_WIDTH_DEFAULT;
    const max =
      typeof window !== "undefined"
        ? Math.floor(window.innerWidth * 0.5)
        : Infinity;
    return Math.min(max, Math.max(SIDEBAR_WIDTH_MIN, v));
  } catch {
    return SIDEBAR_WIDTH_DEFAULT;
  }
})();
const isSidebarOpen = ref(storedSidebarOpen);
const isSidebarPoppedOut = ref(false);
const sidebarWidth = ref(storedSidebarWidth);
const persistSidebarOpen = () => {
  try {
    localStorage.setItem(
      "annotateSidebarOpen",
      isSidebarOpen.value ? "1" : "0",
    );
  } catch {
    /* ignore */
  }
};
const persistSidebarWidth = () => {
  try {
    localStorage.setItem("annotateSidebarWidth", String(sidebarWidth.value));
  } catch {
    /* ignore */
  }
};

const currentPage = ref(1);
const pageNumberInput = ref(1);
let pageNumberInputOrigin = 1;
const lastPage = route.query.page;
const zoomFromQuery = route.query.zoom;
onMounted(() => {
  if (lastPage) {
    currentPage.value = parseInt(lastPage);
  }

  if (zoomFromQuery) {
    const zoomVal = parseInt(zoomFromQuery);
    if (!isNaN(zoomVal) && zoomVal >= 50 && zoomVal <= 500) {
      zoomLevel.value = zoomVal;
      inputZoomLevel.value = zoomVal;
    }
  }
});

const totalPages = ref(0);
const zoomLevel = ref(DEFAULT_ZOOM);
const inputZoomLevel = ref(DEFAULT_ZOOM);
let zoomDebounce = null;
const isAnnotationsHidden = ref(false);
const isColorPickerOpen = ref(false);
const selectedColor = ref("#f59e0b");
const isResizing = ref(false);
const isManualScrolling = ref(false);

const renderTasks = {};
const pageProxies = {};
const activeRenderSignatures = new Map();
const renderedPageSignatures = new Map();
const queuedPageRenders = new Map();

let isProcessingRenderQueue = false;
let isUserScrolling = false;
let scrollEndDebounce = null;

const queuePageRender = (pageNum, force = false) => {
  const existingForce = queuedPageRenders.get(pageNum) || false;
  queuedPageRenders.set(pageNum, existingForce || force);
};

const getNextQueuedPage = () => {
  let nextPage = null;
  let bestDistance = Number.POSITIVE_INFINITY;

  queuedPageRenders.forEach((_force, pageNum) => {
    const distance = Math.abs(pageNum - currentPage.value);
    if (distance < bestDistance) {
      bestDistance = distance;
      nextPage = pageNum;
    }
  });

  return nextPage;
};

const waitForFrame = () =>
  new Promise((resolve) => {
    requestAnimationFrame(() => resolve());
  });

const isPageNearViewport = (pageNum) =>
  visiblePages.value.has(pageNum) ||
  Math.abs(pageNum - currentPage.value) <= RENDERED_PAGE_BUFFER;

const releasePageRender = (pageNum) => {
  if (renderTasks[pageNum]) {
    renderTasks[pageNum].cancel?.();
    delete renderTasks[pageNum];
  }

  const canvas = canvasRefs.value[pageNum - 1];
  if (canvas) {
    const context = canvas.getContext("2d");
    context?.clearRect(0, 0, canvas.width, canvas.height);
    canvas.width = 0;
    canvas.height = 0;
    canvas.removeAttribute("style");
  }

  const textLayerDiv = textLayerRefs.value[pageNum - 1];
  if (textLayerDiv) {
    textLayerDiv.replaceChildren();
    textLayerDiv.onclick = null;
    textLayerDiv.removeAttribute("style");
    textLayerDiv.removeAttribute("data-page-number");
  }

  // Release pdf.js internal per-page caches (operator lists, decoded images,
  // glyph data). Without this, pdf.js retains this data for every page ever
  // rendered even after the canvas bitmap is freed. The page re-parses on the
  // next render, which already coincides with re-drawing its canvas.
  const pageProxy = pageProxies[pageNum];
  if (pageProxy) {
    pageProxy.cleanup?.();
    delete pageProxies[pageNum];
  }

  renderedPageSignatures.delete(pageNum);
  activeRenderSignatures.delete(pageNum);
};

const cleanupRenderedPages = () => {
  Array.from(renderedPageSignatures.keys()).forEach((pageNum) => {
    if (!isPageNearViewport(pageNum)) {
      releasePageRender(pageNum);
    }
  });
};

const releaseAllRenderedPages = () => {
  Object.keys(renderTasks).forEach((pageNum) => releasePageRender(Number(pageNum)));
  Array.from(renderedPageSignatures.keys()).forEach((pageNum) =>
    releasePageRender(pageNum),
  );
  // Free any proxies that were fetched but not tracked by a render/signature.
  Object.keys(pageProxies).forEach((pageNum) => {
    pageProxies[pageNum]?.cleanup?.();
    delete pageProxies[pageNum];
  });
};

const processRenderQueue = async () => {
  if (isProcessingRenderQueue || isUserScrolling) return;
  isProcessingRenderQueue = true;

  try {
    while (queuedPageRenders.size > 0) {
      if (isUserScrolling) break;

      const nextPage = getNextQueuedPage();
      if (nextPage === null) break;

      const force = queuedPageRenders.get(nextPage) || false;
      queuedPageRenders.delete(nextPage);

      await renderPage(nextPage, force);
      await waitForFrame();
    }
  } finally {
    isProcessingRenderQueue = false;
    cleanupRenderedPages();
  }

  if (!isUserScrolling && queuedPageRenders.size > 0) {
    setTimeout(() => {
      processRenderQueue();
    }, 0);
  }
};

const handleMainScroll = () => {
  closeTextSelectionMenu();
  isUserScrolling = true;
  if (scrollEndDebounce) clearTimeout(scrollEndDebounce);
  scrollEndDebounce = setTimeout(() => {
    isUserScrolling = false;
    cleanupRenderedPages();
    processRenderQueue();
  }, 80);
};

// KaTeX rendering for sticky notes.
const renderContent = (text) => {
  if (!text) return "";

  const regex = /(\$\$[\s\S]*?\$\$)|(\$[^\$]*?\$)|(\n)/g;

  return text.replace(regex, (match, displayMath, inlineMath, newline) => {
    if (newline) {
      return "<br />";
    }

    const mathContent = displayMath || inlineMath;
    const isDisplayMode = !!displayMath;

    const rawTex = isDisplayMode
      ? mathContent.slice(2, -2)
      : mathContent.slice(1, -1);

    try {
      return katex.renderToString(rawTex, {
        displayMode: isDisplayMode,
        throwOnError: false,
      });
    } catch (e) {
      return match;
    }
  });
};

const notepadTextarea = ref(null);
const activeNotepadLine = ref(0);
const isNotepadSelectingAll = ref(false);
const notepadLines = computed(() => notepadData.value.split("\n"));

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

const renderNotepadLine = (line) => {
  if (!line) return "&nbsp;";
  const citationMarkdown = line.replace(
    /~\[(\d+)\]~/g,
    (_match, page) => `[\\[${page}\\]](#notepad-page-${page})`,
  );
  const html = marked.parse(citationMarkdown);
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

const resizeNotepadEditor = () => {
  const textarea = notepadTextarea.value;
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.max(32, textarea.scrollHeight)}px`;
};

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
  });
};

const setNotepadCursorFromOffset = (offset) => {
  const beforeCursor = notepadData.value.slice(0, Math.max(0, offset));
  const linesBeforeCursor = beforeCursor.split("\n");
  focusNotepadLine(
    linesBeforeCursor.length - 1,
    linesBeforeCursor.at(-1)?.length ?? 0,
  );
};

const getNotepadPositionFromOffset = (offset) => {
  const beforeCursor = notepadData.value.slice(0, Math.max(0, offset));
  const linesBeforeCursor = beforeCursor.split("\n");
  return {
    line: linesBeforeCursor.length - 1,
    column: linesBeforeCursor.at(-1)?.length ?? 0,
  };
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

const handleNotepadDocumentInput = (event) => {
  const offset = event.currentTarget.selectionStart;
  notepadData.value = event.currentTarget.value;
  leaveNotepadDocumentSelection(offset);
};

const finishNotepadDocumentSelection = (event) => {
  const textarea = event.currentTarget;
  if (textarea.selectionStart !== textarea.selectionEnd) return;
  leaveNotepadDocumentSelection(textarea.selectionStart);
};

const blurNotepadDocumentSelection = (event) => {
  leaveNotepadDocumentSelection(event.currentTarget.selectionStart, {
    focus: false,
  });
};

const activateNotepadLine = (lineIndex) => {
  focusNotepadLine(lineIndex);
};

const handleNotepadRenderedLineClick = (event, lineIndex) => {
  const citation = event.target.closest?.('a[href^="#notepad-page-"]');
  if (!citation) {
    activateNotepadLine(lineIndex);
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  const match = citation.getAttribute("href")?.match(/^#notepad-page-(\d+)$/);
  if (!match) return;

  navigateToPageWithHistory(Number(match[1]));
};

const updateNotepadLine = (lineIndex, event) => {
  const value = event.target.value;
  const cursor = event.target.selectionStart;
  const selectionEnd = event.target.selectionEnd;
  const replacementLines = value.split("\n");
  const lines = [...notepadLines.value];
  lines.splice(lineIndex, 1, ...replacementLines);
  notepadData.value = lines.join("\n");

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
  const line = notepadLines.value[lineIndex] ?? "";
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const lines = [...notepadLines.value];
  lines.splice(lineIndex, 1, line.slice(0, start), line.slice(end));
  notepadData.value = lines.join("\n");
  focusNotepadLine(lineIndex + 1, 0);
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
  const lines = [...notepadLines.value];
  const previousLength = lines[lineIndex - 1].length;
  lines.splice(
    lineIndex - 1,
    2,
    lines[lineIndex - 1] + lines[lineIndex],
  );
  notepadData.value = lines.join("\n");
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
  const lines = [...notepadLines.value];
  lines.splice(lineIndex, 2, lines[lineIndex] + lines[lineIndex + 1]);
  notepadData.value = lines.join("\n");
  focusNotepadLine(lineIndex, line.length);
};

const moveNotepadCursorVertically = (lineIndex, direction, event) => {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  const nextLine = lineIndex + direction;
  if (nextLine < 0 || nextLine >= notepadLines.value.length) return;
  event.preventDefault();
  focusNotepadLine(nextLine, event.currentTarget.selectionStart);
};

const handleNotepadLineKeydown = (lineIndex, event) => {
  switch (event.key) {
    case "Enter":
      splitNotepadLine(lineIndex, event);
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
  }
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

  let insertion = "";
  let newCursorPos = end;

  switch (format) {
    case "bold":
      insertion = `**${text.substring(start, end) || "bold"}**`;
      newCursorPos = start + insertion.length;
      break;
    case "italic":
      insertion = `*${text.substring(start, end) || "italic"}*`;
      newCursorPos = start + insertion.length;
      break;
    case "math-inline":
      insertion = `$${text.substring(start, end) || ""}$`;
      newCursorPos = start + insertion.length - 1;
      break;
    case "math-block":
      insertion = `$$\n${text.substring(start, end) || ""}\n$$`;
      newCursorPos = start + insertion.length - 3;
      break;
    case "quote": {
      const quote = text.substring(start, end);
      insertion = `> ${quote}`;
      newCursorPos = start + insertion.length;
      break;
    }
    case "citation": {
      const selection = text.substring(start, end);
      const page = /^\d+$/.test(selection) ? selection : currentPage.value;
      insertion = `~[${page}]~`;
      newCursorPos = start + insertion.length;
      break;
    }
  }

  // Update State
  notepadData.value =
    text.substring(0, start) + insertion + text.substring(end);

  isNotepadSelectingAll.value = false;
  setNotepadCursorFromOffset(newCursorPos);
};

// keyboard shortcuts
const handleKeyboardShortcuts = (e) => {
  // Check if user is typing in an input/textarea
  const isTyping = ["INPUT", "TEXTAREA"].includes(
    document.activeElement.tagName,
  );
  const isNotepadFocused = document.activeElement === notepadTextarea.value;

  if (isNotepadFocused) {
    // Select the complete note, including lines currently rendered as Markdown.
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
      e.preventDefault();
      beginNotepadSelectAll();
    }
    // Bold: Ctrl + B or Cmd + B
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
      e.preventDefault();
      insertFormat("bold");
    }
    // Italic: Ctrl + I or Cmd + I
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "i") {
      e.preventDefault();
      insertFormat("italic");
    }
    // Inline Math: Ctrl + M
    else if (
      (e.ctrlKey || e.metaKey) &&
      !e.shiftKey &&
      e.key.toLowerCase() === "m"
    ) {
      e.preventDefault();
      insertFormat("math-inline");
    }
    // Block Math: Ctrl + Shift + M
    else if (
      (e.ctrlKey || e.metaKey) &&
      e.shiftKey &&
      e.key.toLowerCase() === "m"
    ) {
      e.preventDefault();
      insertFormat("math-block");
    }
    return; // wont trigger tool shortcuts while typing
  }

  // viewing pdf
  if (!isTyping) {
    // Prevent interfering with browser shortcuts
    switch (e.key.toLowerCase()) {
      case "v":
      case "escape":
        changeActiveTool("cursor");
        break;
      case "h":
        changeActiveTool("highlighter");
        break;
      case "s":
        changeActiveTool("stickyNote");
        break;
      case "d":
        changeActiveTool("deleteAnnotation");
        break;
    }
  }
};

const READER_KEY_SCROLL_STEP = 80;

const focusPdfReader = (e) => {
  if (e.button !== 0) return;

  const interactiveElement = e.target.closest?.(
    "a, button, input, select, textarea, [contenteditable='true'], [tabindex]",
  );
  if (interactiveElement && interactiveElement !== e.currentTarget) return;

  e.currentTarget.focus({ preventScroll: true });
};

const isTextEntryTarget = (target) =>
  target instanceof Element &&
  Boolean(
    target.closest(
      "input, textarea, select, [contenteditable='true'], [role='textbox']",
    ),
  );

const restoreReaderFocusAfterInteraction = (e) => {
  if (isTextEntryTarget(e.target)) return;

  nextTick(() => {
    if (isTextEntryTarget(document.activeElement)) return;
    mainScrollContainer.value?.focus({ preventScroll: true });
  });
};

const handleReaderArrowNavigation = (e) => {
  if (
    document.activeElement !== mainScrollContainer.value ||
    e.altKey ||
    e.ctrlKey ||
    e.metaKey
  ) {
    return;
  }

  const scrollOffset = {
    ArrowUp: { top: -READER_KEY_SCROLL_STEP },
    ArrowDown: { top: READER_KEY_SCROLL_STEP },
    ArrowLeft: { left: -READER_KEY_SCROLL_STEP },
    ArrowRight: { left: READER_KEY_SCROLL_STEP },
  }[e.key];

  if (!scrollOffset) return;

  e.preventDefault();
  mainScrollContainer.value.scrollBy({ ...scrollOffset, behavior: "auto" });
};

/**
 * Merge fragmented Range.getClientRects() boxes into contiguous bars.
 * Mixed fonts (bold/mono/math) produce separate client rects with small
 * vertical offsets and gaps; without this, highlights look broken up.
 */
const mergeHighlightRects = (rects) => {
  const minSize = 0.5;
  const lineTolerance = 5; // same line if vertical centers are this close
  const maxGap = 3; // horizontally merge if gap is at most this

  const valid = rects.filter(
    (r) => r.width >= minSize && r.height >= minSize,
  );
  if (valid.length <= 1) return valid.map((r) => ({ ...r }));

  const sorted = [...valid].sort((a, b) => a.y - b.y || a.x - b.x);

  // Cluster into lines by vertical-center proximity
  const lines = [];
  for (const rect of sorted) {
    const cy = rect.y + rect.height / 2;
    let line = lines.find((l) => Math.abs(l.centerY - cy) <= lineTolerance);
    if (!line) {
      line = { centerY: cy, rects: [] };
      lines.push(line);
    }
    line.rects.push(rect);
    line.centerY =
      line.rects.reduce((sum, r) => sum + r.y + r.height / 2, 0) /
      line.rects.length;
  }

  const merged = [];
  for (const line of lines) {
    const row = [...line.rects].sort((a, b) => a.x - b.x);
    let current = { ...row[0] };

    for (let i = 1; i < row.length; i++) {
      const next = row[i];
      const currentRight = current.x + current.width;
      const gap = next.x - currentRight;

      if (gap <= maxGap) {
        const left = Math.min(current.x, next.x);
        const right = Math.max(currentRight, next.x + next.width);
        const top = Math.min(current.y, next.y);
        const bottom = Math.max(
          current.y + current.height,
          next.y + next.height,
        );
        current = {
          x: left,
          y: top,
          width: right - left,
          height: bottom - top,
        };
      } else {
        merged.push(current);
        current = { ...next };
      }
    }
    merged.push(current);
  }

  return merged;
};

// Highlight Events
const getHighlightDataFromSelection = (selection) => {
  if (!selection?.rangeCount || !selection.toString().trim()) return null;

  const range = selection.getRangeAt(0);
  let container = range.commonAncestorContainer;
  while (container && !container.classList?.contains("textLayer")) {
    container = container.parentNode;
  }
  if (!container) return null;

  const page = parseInt(container.getAttribute("data-page-number"), 10);
  if (!Number.isFinite(page)) return null;

  const pageRect = container.getBoundingClientRect();
  const scale = zoomLevel.value / 100;
  const rects = mergeHighlightRects(
    Array.from(range.getClientRects()).map((rect) => ({
      x: (rect.left - pageRect.left) / scale,
      y: (rect.top - pageRect.top) / scale,
      width: rect.width / scale,
      height: rect.height / scale,
    })),
  );

  if (!rects.length) return null;
  return { text: selection.toString(), page, rects };
};

const saveSelectionHighlight = async ({ text, page, rects }) => {
  const newHighlight = {
    id: crypto.randomUUID(),
    type: "highlight",
    page,
    text,
    color: selectedColor.value,
    rects,
  };

  savedHighlights.value.push(newHighlight);
  undoStack.value.push({ type: "add", data: newHighlight });
  redoStack.value = [];

  renderHighlight(newHighlight, textLayerRefs.value[page - 1]);
  await saveAnnotationsToBackend();
};

const handleTextSelection = async (event) => {
  // A secondary click should preserve the current selection for the copy menu.
  if (
    event?.button !== 0 ||
    event.target.closest?.(".pdf-selection-menu")
  ) {
    return;
  }

  // Always capture selection for @selection chat context
  const selectionRaw = window.getSelection();
  const selText = selectionRaw?.toString().trim();
  if (selText && selectionRaw.rangeCount) {
    capturedSelection.value = selText;
    let selectionContainer = selectionRaw.getRangeAt(0).commonAncestorContainer;
    while (selectionContainer && !selectionContainer.classList?.contains("textLayer")) {
      selectionContainer = selectionContainer.parentNode;
    }
    capturedSelectionPage.value = selectionContainer
      ? parseInt(selectionContainer.getAttribute("data-page-number"), 10)
      : currentPage.value;
  }

  if (activeTool.value !== "highlighter") return;

  const selection = window.getSelection();
  if (
    !selection ||
    selection.rangeCount === 0 ||
    selection.toString().trim() === ""
  )
    return;

  const highlightData = getHighlightDataFromSelection(selection);
  if (!highlightData) return;

  selection.removeAllRanges();
  await saveSelectionHighlight(highlightData);
};

const selectionIntersectsTextLayer = (selection) => {
  if (!selection?.rangeCount) return false;

  for (let rangeIndex = 0; rangeIndex < selection.rangeCount; rangeIndex += 1) {
    const range = selection.getRangeAt(rangeIndex);
    for (const textLayer of textLayerRefs.value) {
      if (textLayer?.isConnected && range.intersectsNode(textLayer)) return true;
    }
  }

  return false;
};

const handleTextContextMenu = (event) => {
  const selection = window.getSelection();
  const selectedText = selection?.toString().trim();

  if (!selectedText || !selectionIntersectsTextLayer(selection)) {
    closeTextSelectionMenu();
    return;
  }

  event.preventDefault();
  const highlightData = getHighlightDataFromSelection(selection);
  const targetTextLayer = event.target.closest?.(".textLayer");
  textSelectionMenu.text = selection.toString();
  textSelectionMenu.page =
    highlightData?.page ||
    parseInt(targetTextLayer?.getAttribute("data-page-number"), 10) ||
    currentPage.value;
  textSelectionMenu.highlightData = highlightData;
  textSelectionMenu.x = Math.max(
    8,
    Math.min(event.clientX, window.innerWidth - 172),
  );
  textSelectionMenu.y = Math.max(
    8,
    Math.min(event.clientY, window.innerHeight - 112),
  );
  textSelectionMenu.visible = true;
};

const copySelectedPdfText = async () => {
  const text = textSelectionMenu.text;
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // execCommand remains useful in Electron and in browsers where the async
    // Clipboard API is unavailable or denied.
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  } finally {
    closeTextSelectionMenu();
  }
};

const addSelectedPdfTextToChat = async () => {
  const text = textSelectionMenu.text.trim();
  if (!text) return;

  capturedSelection.value = text;
  capturedSelectionPage.value = textSelectionMenu.page || currentPage.value;

  if (!/(^|\s)@selection(?=\s|$)/i.test(chatInput.value)) {
    const spacer = chatInput.value && !/\s$/.test(chatInput.value) ? " " : "";
    chatInput.value += `${spacer}@selection `;
  }

  ensureSidebarOpen();
  changeSidebarTab("chat");
  closeTextSelectionMenu();

  await nextTick();
  const input = chatInputRef.value;
  input?.focus();
  input?.setSelectionRange(chatInput.value.length, chatInput.value.length);
  syncChatInputMirror();
};

const highlightSelectedPdfText = async () => {
  const highlightData = textSelectionMenu.highlightData;
  if (!highlightData) return;

  closeTextSelectionMenu();
  window.getSelection()?.removeAllRanges();
  await saveSelectionHighlight(highlightData);
};

// Converts a #rgb / #rrggbb color into an rgba() string with the given alpha
const hexToRgba = (hex, alpha) => {
  if (typeof hex !== "string" || !hex.startsWith("#")) return hex;
  let r = 0;
  let g = 0;
  let b = 0;
  if (hex.length === 4) {
    r = parseInt(hex[1] + hex[1], 16);
    g = parseInt(hex[2] + hex[2], 16);
    b = parseInt(hex[3] + hex[3], 16);
  } else if (hex.length >= 7) {
    r = parseInt(hex.slice(1, 3), 16);
    g = parseInt(hex.slice(3, 5), 16);
    b = parseInt(hex.slice(5, 7), 16);
  }
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

// Shows the highlight on the pdf
const renderHighlight = (highlight, textLayerElement) => {
  if (!textLayerElement) {
    textLayerElement = textLayerRefs.value[highlight.page - 1];
  }
  if (!textLayerElement) return;

  // Merge on render too so older fragmented highlights display cleanly
  mergeHighlightRects(highlight.rects).forEach((rect) => {
    const div = document.createElement("div");
    div.classList.add("custom-highlight");
    div.dataset.id = highlight.id;

    div.style.position = "absolute";
    div.style.backgroundColor = hexToRgba(highlight.color, 0.4);
    div.style.pointerEvents = "auto";
    div.style.cursor = "pointer";
    div.style.mixBlendMode = "multiply";

    div.style.left = `calc(${rect.x}px * var(--scale-factor))`;
    div.style.top = `calc(${rect.y}px * var(--scale-factor))`;
    div.style.width = `calc(${rect.width}px * var(--scale-factor))`;
    div.style.height = `calc(${rect.height}px * var(--scale-factor))`;

    div.addEventListener("click", (e) => {
      handleAnnotationClick(e, highlight);
    });

    textLayerElement.appendChild(div);
  });
};

// Deleting Highlights
const handleAnnotationClick = async (event, annotation) => {
  event.stopPropagation();

  if (activeTool.value === "deleteAnnotation") {
    if (annotation.type === "highlight") {
      const pageIndex = annotation.page - 1;
      const textLayer = textLayerRefs.value[pageIndex];
      if (textLayer) {
        const elements = textLayer.querySelectorAll(
          `[data-id="${annotation.id}"]`,
        );
        elements.forEach((el) => el.remove());
      }

      savedHighlights.value = savedHighlights.value.filter(
        (h) => h.id !== annotation.id,
      );

      undoStack.value.push({ type: "delete", data: annotation });
      redoStack.value = [];
    } else if (annotation.type === "stickyNote") {
      const pageIndex = annotation.page - 1;
      const textLayer = textLayerRefs.value[pageIndex];
      if (textLayer) {
        const el = textLayer.querySelector(`[data-id="${annotation.id}"]`);
        if (el) el.remove();
      }
      stickyNoteData.value = stickyNoteData.value.filter(
        (s) => s.id !== annotation.id,
      );
      if (activeStickyNoteId.value === annotation.id) {
        activeStickyNoteId.value = null;
      }

      undoStack.value.push({ type: "delete", data: annotation });
      redoStack.value = [];
    }

    await saveAnnotationsToBackend();
  } else if (annotation.type === "stickyNote") {
    activeStickyNoteId.value = annotation.id;
    changeSidebarTab("stickyNotes");
    ensureSidebarOpen();
  }
};

// Prevent placing a new sticky when a drag ends on the page
let suppressNextLayerClick = false;

// Sticky Note Events
const handleLayerClick = async (event, pageNum) => {
  if (suppressNextLayerClick) {
    suppressNextLayerClick = false;
    return;
  }

  if (activeStickyNoteId.value !== null) {
    activeStickyNoteId.value = null;
  }

  if (activeTool.value !== "stickyNote") return;

  const textLayer = textLayerRefs.value[pageNum - 1];
  if (!textLayer) return;

  const rect = textLayer.getBoundingClientRect();
  const scale = zoomLevel.value / 100;

  const x = (event.clientX - rect.left) / scale;
  const y = (event.clientY - rect.top) / scale;

  const newSticky = {
    id: crypto.randomUUID(),
    type: "stickyNote",
    page: pageNum,
    x: x,
    y: y,
    content: "",
    tag: "",
    color: selectedColor.value,
    timestamp: new Date().toISOString(),
  };

  stickyNoteData.value.push(newSticky);

  undoStack.value.push({ type: "add", data: newSticky });
  redoStack.value = [];

  renderStickyNote(newSticky, textLayer);

  activeStickyNoteId.value = newSticky.id;
  changeSidebarTab("stickyNotes");
  ensureSidebarOpen();
  await focusStickyNoteEditor(newSticky.id);

  await saveAnnotationsToBackend();
};

// Sticky note tags
const tagOptions = [
  { label: "Select Tag", value: "" }, // Default state
  { label: "Definition", value: "definition", color: "text-blue-400" },
  { label: "Question", value: "question", color: "text-amber-400" },
  { label: "Insight", value: "insight", color: "text-purple-400" },
  { label: "Data Point", value: "data-point", color: "text-orange-400" },
  { label: "Evidence", value: "evidence", color: "text-emerald-400" },
  { label: "Critique", value: "critique", color: "text-rose-400" },
  { label: "Follow-up", value: "follow-up", color: "text-sky-400" },
];
const activeDropdownId = ref(null);

const toggleDropdown = (noteId) => {
  if (activeDropdownId.value === noteId) {
    activeDropdownId.value = null;
  } else {
    activeDropdownId.value = noteId;
  }
};

const setNoteTag = (note, option) => {
  note.tag = option.value; // Assigns value to the data model
  activeDropdownId.value = null;
};

const getTagLabel = (tagValue) => {
  const option = tagOptions.find((opt) => opt.value === tagValue);
  return option ? option.label : "Select Tag";
};

const getTagColor = (tagValue) => {
  const option = tagOptions.find((opt) => opt.value === tagValue);
  return option ? option.color : "text-slate-500";
};

// Shows the sticky note on the pdf
const renderStickyNote = (note, textLayerElement) => {
  if (!textLayerElement) {
    textLayerElement = textLayerRefs.value[note.page - 1];
  }
  if (!textLayerElement) return;

  // styling
  const iconDiv = document.createElement("div");
  iconDiv.dataset.id = note.id;
  iconDiv.classList.add("sticky-note-icon");
  iconDiv.style.position = "absolute";
  iconDiv.style.left = `calc(${note.x}px * var(--scale-factor))`;
  iconDiv.style.top = `calc(${note.y}px * var(--scale-factor))`;
  iconDiv.style.width = "36px";
  iconDiv.style.height = "36px";
  iconDiv.style.transform = "translate(-50%, -50%)";
  iconDiv.style.cursor = "grab";
  iconDiv.style.pointerEvents = "auto";
  iconDiv.style.zIndex = "20";
  iconDiv.style.touchAction = "none";
  iconDiv.style.filter =
    "drop-shadow(0 4px 3px rgb(0 0 0 / 0.07)) drop-shadow(0 2px 2px rgb(0 0 0 / 0.06))";
  iconDiv.title = "Drag to move";

  // svg icon
  iconDiv.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" style="width: 100%; height: 100%;">
            <rect x="16" y="16" width="224" height="224" rx="12" ry="12"
                  fill="${note.color}"
                  stroke="rgba(0,0,0,0.1)" stroke-width="4" />

            <g stroke="rgba(0,0,0,0.2)" stroke-width="12" stroke-linecap="round">
                <line x1="48" y1="88" x2="208" y2="88" />
                <line x1="48" y1="136" x2="208" y2="136" />
                <line x1="48" y1="184" x2="176" y2="184" />
            </g>
        </svg>
    `;

  iconDiv.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();

    if (activeTool.value === "deleteAnnotation") {
      handleAnnotationClick(e, note);
      return;
    }

    startStickyNoteDrag(e, note, iconDiv);
  });
  textLayerElement.appendChild(iconDiv);
};

const startStickyNoteDrag = (event, note, iconDiv) => {
  const textLayer = textLayerRefs.value[note.page - 1];
  if (!textLayer) return;

  const originX = note.x;
  const originY = note.y;
  let latestX = originX;
  let latestY = originY;
  let didMove = false;

  const scale = zoomLevel.value / 100;
  const startClientX = event.clientX;
  const startClientY = event.clientY;

  iconDiv.style.cursor = "grabbing";
  iconDiv.style.zIndex = "50";
  document.body.style.userSelect = "none";
  document.body.style.cursor = "grabbing";

  const setIconPosition = (x, y) => {
    iconDiv.style.left = `calc(${x}px * var(--scale-factor))`;
    iconDiv.style.top = `calc(${y}px * var(--scale-factor))`;
  };

  const isOutsidePage = (clientX, clientY) => {
    const rect = textLayer.getBoundingClientRect();
    return (
      clientX < rect.left ||
      clientX > rect.right ||
      clientY < rect.top ||
      clientY > rect.bottom
    );
  };

  const onMove = (e) => {
    if (
      !didMove &&
      (Math.abs(e.clientX - startClientX) > 4 ||
        Math.abs(e.clientY - startClientY) > 4)
    ) {
      didMove = true;
    }

    const rect = textLayer.getBoundingClientRect();
    latestX = (e.clientX - rect.left) / scale;
    latestY = (e.clientY - rect.top) / scale;
    setIconPosition(latestX, latestY);
    iconDiv.style.opacity = isOutsidePage(e.clientX, e.clientY) ? "0.4" : "1";
  };

  const cleanup = () => {
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    window.removeEventListener("pointercancel", onUp);
    iconDiv.style.cursor = "grab";
    iconDiv.style.zIndex = "20";
    iconDiv.style.opacity = "1";
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
  };

  const onUp = async (e) => {
    cleanup();

    if (!didMove) {
      setIconPosition(originX, originY);
      activeStickyNoteId.value = note.id;
      changeSidebarTab("stickyNotes");
      ensureSidebarOpen();
      return;
    }

    suppressNextLayerClick = true;

    if (isOutsidePage(e.clientX, e.clientY)) {
      setIconPosition(originX, originY);
      return;
    }

    const stored = stickyNoteData.value.find((s) => s.id === note.id);
    if (stored) {
      stored.x = latestX;
      stored.y = latestY;
    }
    note.x = latestX;
    note.y = latestY;
    setIconPosition(latestX, latestY);

    await saveAnnotationsToBackend();
  };

  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp);
  window.addEventListener("pointercancel", onUp);
};

// undo/redo functions
const performUndo = async () => {
  const action = undoStack.value.pop();
  if (!action) return;

  if (action.type === "navigate") {
    scrollToPage(action.fromPage);
    redoStack.value.push(action);
    return;
  }

  if (action.type === "add") {
    if (action.data.type === "highlight") {
      savedHighlights.value = savedHighlights.value.filter(
        (h) => h.id !== action.data.id,
      );
      const pageIndex = action.data.page - 1;
      const textLayer = textLayerRefs.value[pageIndex];
      if (textLayer) {
        textLayer
          .querySelectorAll(`[data-id="${action.data.id}"]`)
          .forEach((el) => el.remove());
      }
    } else if (action.data.type === "stickyNote") {
      stickyNoteData.value = stickyNoteData.value.filter(
        (s) => s.id !== action.data.id,
      );
      const pageIndex = action.data.page - 1;
      const textLayer = textLayerRefs.value[pageIndex];
      if (textLayer) {
        const el = textLayer.querySelector(`[data-id="${action.data.id}"]`);
        if (el) el.remove();
      }
      if (activeStickyNoteId.value === action.data.id)
        activeStickyNoteId.value = null;
    }
    redoStack.value.push(action);
  } else if (action.type === "delete") {
    // Inverse of Delete is Add
    if (action.data.type === "highlight") {
      savedHighlights.value.push(action.data);
      const textLayer = textLayerRefs.value[action.data.page - 1];
      if (textLayer) renderHighlight(action.data, textLayer);
    } else if (action.data.type === "stickyNote") {
      stickyNoteData.value.push(action.data);
      const textLayer = textLayerRefs.value[action.data.page - 1];
      if (textLayer) renderStickyNote(action.data, textLayer);
    }
    redoStack.value.push(action);
  }
  await saveAnnotationsToBackend();
};

const performRedo = async () => {
  const action = redoStack.value.pop();
  if (!action) return;

  if (action.type === "navigate") {
    scrollToPage(action.toPage);
    undoStack.value.push(action);
    return;
  }

  if (action.type === "add") {
    if (action.data.type === "highlight") {
      savedHighlights.value.push(action.data);
      const textLayer = textLayerRefs.value[action.data.page - 1];
      if (textLayer) renderHighlight(action.data, textLayer);
    } else if (action.data.type === "stickyNote") {
      stickyNoteData.value.push(action.data);
      const textLayer = textLayerRefs.value[action.data.page - 1];
      if (textLayer) renderStickyNote(action.data, textLayer);
    }
    undoStack.value.push(action);
  } else if (action.type === "delete") {
    if (action.data.type === "highlight") {
      savedHighlights.value = savedHighlights.value.filter(
        (h) => h.id !== action.data.id,
      );
      const pageIndex = action.data.page - 1;
      const textLayer = textLayerRefs.value[pageIndex];
      if (textLayer) {
        textLayer
          .querySelectorAll(`[data-id="${action.data.id}"]`)
          .forEach((el) => el.remove());
      }
    } else if (action.data.type === "stickyNote") {
      stickyNoteData.value = stickyNoteData.value.filter(
        (s) => s.id !== action.data.id,
      );
      const pageIndex = action.data.page - 1;
      const textLayer = textLayerRefs.value[pageIndex];
      if (textLayer) {
        const el = textLayer.querySelector(`[data-id="${action.data.id}"]`);
        if (el) el.remove();
      }
      if (activeStickyNoteId.value === action.data.id)
        activeStickyNoteId.value = null;
    }
    undoStack.value.push(action);
  }
  await saveAnnotationsToBackend();
};

// general function to update annotations to backend
async function saveAnnotationsToBackend() {
  try {
    await $fetch(`${apiBaseURL}/annotations/`, {
      method: "POST",
      body: {
        document: id,
        highlight_data: savedHighlights.value,
        notepad: notepadData.value,
        sticky_note_data: stickyNoteData.value,
      },
    });
  } catch (e) {
    console.error("Failed to save annotation", e);
  }
}

// Gets annotations from backend and loads into state vars
async function fetchAnnotations() {
  try {
    const data = await $fetch(`${apiBaseURL}/annotations/${id}/`, {
      method: "GET",
    });
    if (data) {
      if (data.highlight_data) savedHighlights.value = data.highlight_data;
      if (data.notepad) notepadData.value = data.notepad;
      if (data.sticky_note_data) stickyNoteData.value = data.sticky_note_data;
    }
  } catch (e) {
    console.warn("No existing annotations found or failed to fetch", e);
  }
}

// Tool bar helper functions
const selectColor = (color) => {
  selectedColor.value = color;
};

const activeTool = ref("cursor");
function changeActiveTool(newToolButton) {
  activeTool.value = newToolButton;
  activeStickyNoteId.value = null;
  console.log("Active tool changed to:", newToolButton);
}

// Sidebar state
const sidebarTabs = [
  { id: "stickyNotes", label: "Sticky Notes", icon: "ph:note" },
  { id: "highlights", label: "Highlights", icon: "ph:highlighter" },
  { id: "notepad", label: "Notepad", icon: "ph:notebook" },
  { id: "chat", label: "Chat", icon: "ph:chat-circle-dots" },
  { id: "ocr", label: "OCR", icon: "ph:text-aa" },
];
const SIDEBAR_TAB_IDS = new Set(sidebarTabs.map((t) => t.id));
const storedSidebarTab = (() => {
  try {
    const v = localStorage.getItem("annotateSidebarActiveTab") || "";
    return SIDEBAR_TAB_IDS.has(v) ? v : "stickyNotes";
  } catch {
    return "stickyNotes";
  }
})();
const sidebarActiveTab = ref(storedSidebarTab);
const persistSidebarActiveTab = () => {
  try {
    localStorage.setItem("annotateSidebarActiveTab", sidebarActiveTab.value);
  } catch {
    /* ignore */
  }
};
function changeSidebarTab(tabName) {
  sidebarActiveTab.value = tabName;
  persistSidebarActiveTab();
  if (tabName !== "chat") showChatHistory.value = false;
  if (tabName === "notepad") nextTick(resizeNotepadEditor);
}
const activeSidebarTabLabel = computed(
  () => sidebarTabs.find((t) => t.id === sidebarActiveTab.value)?.label ?? "",
);
const activeHighlightId = ref(null);
const highlightsByPage = computed(() =>
  [...savedHighlights.value].sort((a, b) => {
    if (a.page !== b.page) return a.page - b.page;
    const ay = a.rects?.[0]?.y ?? 0;
    const by = b.rects?.[0]?.y ?? 0;
    return ay - by;
  }),
);

// Sidebar scale applies to the complete panel, including its rail and controls.
const SIDEBAR_FONT_MIN = 0.85;
const SIDEBAR_FONT_MAX = 1.4;
const SIDEBAR_FONT_STEP = 0.1;
const storedSidebarFont = (() => {
  try {
    const v = parseFloat(localStorage.getItem("annotateSidebarFontScale") || "");
    return Number.isFinite(v) ? v : 1;
  } catch {
    return 1;
  }
})();
const sidebarFontScale = ref(
  Math.min(SIDEBAR_FONT_MAX, Math.max(SIDEBAR_FONT_MIN, storedSidebarFont)),
);
const persistSidebarFontScale = () => {
  try {
    localStorage.setItem(
      "annotateSidebarFontScale",
      String(sidebarFontScale.value),
    );
  } catch {
    /* ignore */
  }
};
const increaseSidebarFont = () => {
  sidebarFontScale.value = Math.min(
    SIDEBAR_FONT_MAX,
    Math.round((sidebarFontScale.value + SIDEBAR_FONT_STEP) * 10) / 10,
  );
  persistSidebarFontScale();
};
const decreaseSidebarFont = () => {
  sidebarFontScale.value = Math.max(
    SIDEBAR_FONT_MIN,
    Math.round((sidebarFontScale.value - SIDEBAR_FONT_STEP) * 10) / 10,
  );
  persistSidebarFontScale();
};
const sidebarScaleStyle = computed(() => ({
  transform: `scale(${sidebarFontScale.value})`,
  width: `${100 / sidebarFontScale.value}%`,
  height: `${100 / sidebarFontScale.value}%`,
}));

let sidebarSyncChannel = null;
let isApplyingSidebarSync = false;

const cloneForSidebarSync = (value) => JSON.parse(JSON.stringify(value));

const postSidebarState = () => {
  if (!sidebarSyncChannel || isApplyingSidebarSync) return;
  sidebarSyncChannel.postMessage({
    type: "state",
    activeTab: sidebarActiveTab.value,
    fontScale: sidebarFontScale.value,
    highlights: cloneForSidebarSync(savedHighlights.value),
    stickyNotes: cloneForSidebarSync(stickyNoteData.value),
    notepad: notepadData.value,
    currentPage: currentPage.value,
    capturedSelection: capturedSelection.value,
    capturedSelectionPage: capturedSelectionPage.value,
  });
};

const applySidebarState = async (message) => {
  isApplyingSidebarSync = true;
  if (SIDEBAR_TAB_IDS.has(message.activeTab)) {
    sidebarActiveTab.value = message.activeTab;
    persistSidebarActiveTab();
  }
  if (Number.isFinite(message.fontScale)) {
    sidebarFontScale.value = Math.min(
      SIDEBAR_FONT_MAX,
      Math.max(SIDEBAR_FONT_MIN, message.fontScale),
    );
    persistSidebarFontScale();
  }
  if (Array.isArray(message.highlights)) {
    savedHighlights.value = message.highlights;
  }
  if (Array.isArray(message.stickyNotes)) {
    stickyNoteData.value = message.stickyNotes;
  }
  if (typeof message.notepad === "string") {
    notepadData.value = message.notepad;
  }
  if (isSidebarPopout && Number.isInteger(message.currentPage)) {
    currentPage.value = message.currentPage;
  }
  if (isSidebarPopout && typeof message.capturedSelection === "string") {
    capturedSelection.value = message.capturedSelection;
    capturedSelectionPage.value = Number.isInteger(message.capturedSelectionPage)
      ? message.capturedSelectionPage
      : null;
  }

  if (!isSidebarPopout) {
    await nextTick();
    Array.from(visiblePages.value).forEach((pageNum) => {
      queuePageRender(pageNum, true);
    });
    processRenderQueue();
  }
  await nextTick();
  isApplyingSidebarSync = false;
};

const setupSidebarSync = () => {
  if (typeof BroadcastChannel === "undefined") return;
  sidebarSyncChannel = new BroadcastChannel(`annotate-sidebar-${id}`);
  sidebarSyncChannel.addEventListener("message", (event) => {
    if (event.data?.type === "request-state") {
      postSidebarState();
    } else if (event.data?.type === "state") {
      applySidebarState(event.data);
    }
  });
  sidebarSyncChannel.postMessage({ type: "request-state" });
};

// --- Chat Tab ---
const chatMessages = ref([]);
const chatInput = ref("");
const chatId = ref(null);
const chatLoading = ref(false);
const chatInputRef = ref(null);
const chatMirrorRef = ref(null);
const showAtMenu = ref(false);
const chatScrollContainer = ref(null);
const capturedSelection = ref("");
const capturedSelectionPage = ref(null);
const showChatHistory = ref(false);
const savedChats = ref([]);
const isDeletingChat = ref(false);

const {
  aiProviders,
  selectedAiProvider,
  selectedAiModel,
  selectedProvider,
  selectedProviderModels,
  selectedProviderModelHint,
  selectedProviderHasModels,
  initializeAiModels,
} = useAiModels();

const paperContextMenuOptions = [
  { tag: "@page", label: "Current Page", desc: "Use the visible page", icon: "ph:book-open" },
  { tag: "@pages", label: "Page Range", desc: "Add pages, e.g. @pages 2, 5-7", icon: "ph:books" },
  { tag: "@current", label: "Current Context", desc: "Use the current reader page", icon: "ph:eye" },
  { tag: "@selection", label: "Selection", desc: "Use currently selected PDF text", icon: "ph:text-select" },
];
const legacyContextMenuOptions = [
  { tag: "@paper", label: "This Paper", desc: "Include full PDF + all annotations", icon: "ph:file-pdf" },
  { tag: "@highlights", label: "Highlights", desc: "All highlights in this paper", icon: "ph:highlighter" },
  { tag: "@sticky", label: "Sticky Notes", desc: "All sticky notes in this paper", icon: "ph:note" },
  { tag: "@notepad", label: "Notepad", desc: "Your notepad for this paper", icon: "ph:notebook" },
];
const atMenuOptions = computed(() =>
  selectedAiProvider.value === "codex"
    ? paperContextMenuOptions
    : [...paperContextMenuOptions, ...legacyContextMenuOptions],
);

const renderChatContent = (text) => {
  if (!text) return "";
  const html = marked.parse(text);
  return DOMPurify.sanitize(html, {
    ADD_TAGS: ["math", "semantics", "mrow", "mi", "mo", "mn", "msup", "mfrac", "msqrt", "mtext", "annotation", "annotation-xml"],
    ADD_ATTR: ["xmlns", "display", "class", "style", "aria-hidden"],
  });
};

const scrollChatToBottom = () => {
  nextTick(() => {
    if (chatScrollContainer.value) {
      chatScrollContainer.value.scrollTop = chatScrollContainer.value.scrollHeight;
    }
  });
};

const syncChatInputMirror = () => {
  const input = chatInputRef.value;
  const mirror = chatMirrorRef.value;
  if (!input || !mirror) return;
  mirror.scrollTop = input.scrollTop;
  mirror.scrollLeft = input.scrollLeft;
};

const handleChatInput = () => {
  syncChatInputMirror();
  const input = chatInput.value;
  const el = chatInputRef.value;
  const cursorPos = el ? el.selectionStart : input.length;
  const textBeforeCursor = input.slice(0, cursorPos);
  showAtMenu.value = /@\w*$/.test(textBeforeCursor);
};

const toggleAtMenu = () => {
  showAtMenu.value = !showAtMenu.value;
  nextTick(() => chatInputRef.value?.focus());
};

const insertAtTag = (tag) => {
  const input = chatInput.value;
  const el = chatInputRef.value;
  const cursorPos = el ? el.selectionStart : input.length;
  const before = input.slice(0, cursorPos).replace(/@\w*$/, tag + " ");
  const after = input.slice(cursorPos);
  chatInput.value = before + after;
  showAtMenu.value = false;
  nextTick(() => {
    el?.focus();
    const newPos = before.length;
    el?.setSelectionRange(newPos, newPos);
    syncChatInputMirror();
  });
};

const buildContextFromInput = (rawInput) => {
  let prompt = rawInput;
  const contextParts = [];

  // Legacy @paper is normalized into a paper-scoped request. The backend now
  // retrieves a bounded PaperContext instead of attaching the whole PDF.
  if (/@paper\b/.test(rawInput)) {
    prompt = prompt.replace(/@paper\b/g, "this paper");
  }

  // @highlights
  if (/@highlights\b/.test(rawInput)) {
    const hlText = savedHighlights.value
      .map((h) => `[Page ${h.page}] "${h.text}"`)
      .join("\n");
    if (hlText) contextParts.push(`--- Highlights ---\n${hlText}\n---`);
    else contextParts.push("--- Highlights ---\n(No highlights yet)\n---");
    prompt = prompt.replace(/@highlights\b/g, "");
  }

  // @sticky
  if (/@sticky\b/.test(rawInput)) {
    const stickyText = stickyNoteData.value
      .map((s) => `[Page ${s.page}, Tag: ${s.tag || "none"}]\n${s.content || "(empty)"}`)
      .join("\n\n");
    if (stickyText) contextParts.push(`--- Sticky Notes ---\n${stickyText}\n---`);
    else contextParts.push("--- Sticky Notes ---\n(No sticky notes yet)\n---");
    prompt = prompt.replace(/@sticky\b/g, "");
  }

  // @notepad
  if (/@notepad\b/.test(rawInput)) {
    if (notepadData.value) contextParts.push(`--- Notepad ---\n${notepadData.value}\n---`);
    else contextParts.push("--- Notepad ---\n(Notepad is empty)\n---");
    prompt = prompt.replace(/@notepad\b/g, "");
  }

  prompt = prompt.trim();
  if (contextParts.length > 0) {
    prompt += `\n\n[Context from PDF viewer]\n${contextParts.join("\n\n")}`;
  }

  return { prompt };
};

let chatAbortController = null;
const chatProvider = ref(null);

const acceptChatDraft = () => {
  chatInput.value = "";
  capturedSelection.value = "";
  capturedSelectionPage.value = null;
  showAtMenu.value = false;
};

const formatCodexStreamError = (event) => {
  const message = event?.message?.trim();
  const technical = event?.details?.technical_message?.trim();
  if (message && technical && technical !== message) {
    return `${message} (${technical})`;
  }
  return message || technical || "Codex generation failed.";
};

const streamCodexMessage = async (rawInput, onAccepted) => {
  if (!chatId.value || chatProvider.value !== "codex") {
    const conversation = await $fetch(`${apiBaseURL}/codex/conversations/`, {
      method: "POST",
      body: {
        document_id: Number(id),
        title: rawInput.slice(0, 80),
      },
    });
    chatId.value = conversation.id;
    chatProvider.value = "codex";
  }

  chatAbortController = new AbortController();
  const response = await fetch(
    `${apiBaseURL}/codex/conversations/${chatId.value}/stream/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: rawInput,
        model: selectedAiModel.value,
        current_page: currentPage.value,
        selected_text: capturedSelection.value,
        selected_text_page: capturedSelectionPage.value,
      }),
      signal: chatAbortController.signal,
    },
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.message || `Codex request failed (${response.status}).`);
  }

  acceptChatDraft();
  onAccepted?.();
  const assistantMessage = reactive({
    role: "model",
    content: "",
    citations: [],
    timestamp: new Date().toISOString(),
  });
  chatMessages.value.push(assistantMessage);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "delta") {
        assistantMessage.content += event.text || "";
        scrollChatToBottom();
      } else if (event.type === "completed") {
        assistantMessage.citations = event.citations || [];
      } else if (event.type === "error") {
        throw new Error(formatCodexStreamError(event));
      } else if (event.type === "cancelled") {
        assistantMessage.content ||= "Generation cancelled.";
      }
    }
    if (done) break;
  }
};

const sendChatMessage = async () => {
  const rawInput = chatInput.value.trim();
  if (!rawInput || chatLoading.value || !selectedProviderHasModels.value) return;

  const userMessage = {
    role: "user",
    content: rawInput,
    timestamp: new Date().toISOString(),
  };
  chatMessages.value.push(userMessage);
  scrollChatToBottom();
  chatLoading.value = true;
  let draftAccepted = false;

  try {
    if (selectedAiProvider.value === "codex") {
      await streamCodexMessage(rawInput, () => {
        draftAccepted = true;
      });
    } else {
      const { prompt } = buildContextFromInput(rawInput);
      const data = await $fetch(`${apiBaseURL}/ask-ai/`, {
        method: "POST",
        body: {
          prompt,
          ...(chatId.value && chatProvider.value !== "codex"
            ? { chat_id: chatId.value }
            : {}),
          document_id: Number(id),
          current_page: currentPage.value,
          selected_text: capturedSelection.value,
          selected_text_page: capturedSelectionPage.value,
          model_provider: selectedAiProvider.value,
          model: selectedAiModel.value,
        },
      });
      chatId.value = data.chat_id;
      chatProvider.value = selectedAiProvider.value;
      acceptChatDraft();
      draftAccepted = true;
      chatMessages.value.push({
        role: "model",
        content: data.model_response,
        citations: data.citations || [],
        timestamp: new Date().toISOString(),
      });
    }
  } catch (error) {
    if (!draftAccepted && chatInput.value.trim() !== rawInput) {
      chatInput.value = rawInput;
    }
    if (error?.name !== "AbortError") {
      chatMessages.value.push({
        role: "model",
        content:
          error?.data?.message ||
          error?.message ||
          "The model could not complete this request.",
        timestamp: new Date().toISOString(),
        isError: true,
      });
    }
    console.error("Chat error:", error);
  } finally {
    chatAbortController = null;
    chatLoading.value = false;
    scrollChatToBottom();
  }
};

const cancelChatGeneration = async () => {
  if (!chatLoading.value) return;
  if (selectedAiProvider.value === "codex" && chatId.value) {
    await $fetch(`${apiBaseURL}/codex/conversations/${chatId.value}/cancel/`, {
      method: "POST",
    }).catch(() => {});
  }
  chatAbortController?.abort();
};

const clearChat = () => {
  chatMessages.value = [];
  chatId.value = null;
  chatProvider.value = null;
};

const fetchSavedChats = async () => {
  try {
    const res = await $fetch(`${apiBaseURL}/chatlogs/`, { method: "GET" });
    savedChats.value = res
      .filter((chat) => !chat.document || Number(chat.document) === Number(id))
      .sort((a, b) => b.id - a.id);
  } catch (error) {
    console.error("Error fetching chats:", error);
  }
};

const toggleChatHistory = () => {
  showChatHistory.value = !showChatHistory.value;
  if (showChatHistory.value) fetchSavedChats();
};

const loadChat = async (idToLoad) => {
  try {
    chatLoading.value = true;
    const res = await $fetch(`${apiBaseURL}/chatlogs/${idToLoad}/`, {
      method: "GET",
    });
    chatId.value = res.id;
    chatProvider.value = res.provider || "legacy";
    chatMessages.value = (res.content || []).map((msg) => ({
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp,
      citations: msg.citations || [],
    }));
    showChatHistory.value = false;
    scrollChatToBottom();
  } catch (error) {
    console.error("Error loading chat:", error);
  } finally {
    chatLoading.value = false;
  }
};

const deleteChat = async (idToDelete, event) => {
  if (event) event.stopPropagation();
  if (!confirm("Are you sure you want to delete this chat log?")) return;

  try {
    isDeletingChat.value = true;
    await $fetch(`${apiBaseURL}/chatlogs/${idToDelete}/`, {
      method: "DELETE",
    });
    savedChats.value = savedChats.value.filter((c) => c.id !== idToDelete);
    if (chatId.value === idToDelete) {
      clearChat();
    }
  } catch (error) {
    console.error("Error deleting chat:", error);
  } finally {
    isDeletingChat.value = false;
  }
};

const startNewChat = () => {
  clearChat();
  showChatHistory.value = false;
  nextTick(() => chatInputRef.value?.focus());
};

// Splits user message into plain text and @tag parts for display
const parseChatInputParts = (text) => {
  if (!text) return [{ type: "text", text: "" }];

  const parts = [];
  const regex = /@(?:pages?|current|paper|highlights|sticky|notepad|selection)\b/g;
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

  return parts.length ? parts : [{ type: "text", text: "" }];
};

// Sidebar functions
// Notepad
let saveNotepadDebounce = null;
watch(notepadData, () => {
  if (isApplyingSidebarSync) return;
  if (saveNotepadDebounce) clearTimeout(saveNotepadDebounce);
  saveNotepadDebounce = setTimeout(() => {
    saveAnnotationsToBackend();
  }, 1500);
});

let saveStickyDebounce = null;
watch(
  stickyNoteData,
  () => {
    if (isApplyingSidebarSync) return;
    if (saveStickyDebounce) clearTimeout(saveStickyDebounce);
    saveStickyDebounce = setTimeout(() => {
      saveAnnotationsToBackend();
    }, 1500);
  },
  { deep: true },
);

watch(
  [
    savedHighlights,
    stickyNoteData,
    notepadData,
    sidebarActiveTab,
    sidebarFontScale,
    currentPage,
    capturedSelection,
    capturedSelectionPage,
  ],
  () => postSidebarState(),
  { deep: true },
);

const focusStickyNote = (noteId) => {
  const note = stickyNoteData.value.find((n) => n.id === noteId);
  if (!note) return;
  activeStickyNoteId.value = noteId;
  activeHighlightId.value = null;
  if (isSidebarPopout && window.electronAPI?.revealSidebarAnnotation) {
    window.electronAPI.revealSidebarAnnotation({
      documentId: String(id),
      type: "stickyNote",
      annotationId: noteId,
      page: note.page,
      y: note.y,
    });
    return;
  }
  scrollToPagePosition(note.page, note.y);
};

const focusHighlight = (highlightId) => {
  const highlight = savedHighlights.value.find((h) => h.id === highlightId);
  if (!highlight) return;
  activeHighlightId.value = highlightId;
  activeStickyNoteId.value = null;
  const y = highlight.rects?.[0]?.y ?? 0;
  if (isSidebarPopout && window.electronAPI?.revealSidebarAnnotation) {
    window.electronAPI.revealSidebarAnnotation({
      documentId: String(id),
      type: "highlight",
      annotationId: highlightId,
      page: highlight.page,
      y,
    });
    return;
  }
  scrollToPagePosition(highlight.page, y);
};

const deleteStickyNote = async (noteId) => {
  const note = stickyNoteData.value.find((n) => n.id === noteId);
  if (!note) return;

  const pageIndex = note.page - 1;
  const textLayer = textLayerRefs.value[pageIndex];
  if (textLayer) {
    const el = textLayer.querySelector(`[data-id="${noteId}"]`);
    if (el) el.remove();
  }

  stickyNoteData.value = stickyNoteData.value.filter((s) => s.id !== noteId);
  if (activeStickyNoteId.value === noteId) activeStickyNoteId.value = null;

  undoStack.value.push({ type: "delete", data: note });
  redoStack.value = [];

  await saveAnnotationsToBackend();
};

async function handleOcrCompleted() {
  await fetchPaper();
}

// Color wheel in tool bar
const colors = [
  "#ef4444",
  "#f59e0b",
  "#10b981",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
];

// Sidebar resizing (drag)
const startResize = () => {
  isResizing.value = true;
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  window.addEventListener("mousemove", handleResize);
  window.addEventListener("mouseup", stopResize);
};

const handleResize = (e) => {
  if (!isResizing.value) return;
  const newWidth = window.innerWidth - e.clientX;
  if (
    newWidth >= SIDEBAR_WIDTH_MIN &&
    newWidth <= window.innerWidth * 0.5
  ) {
    sidebarWidth.value = newWidth;
  }
};

const stopResize = () => {
  isResizing.value = false;
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  window.removeEventListener("mousemove", handleResize);
  window.removeEventListener("mouseup", stopResize);
  persistSidebarWidth();
};

const popOutSidebar = async () => {
  if (!window.electronAPI?.popOutSidebar) return;
  const result = await window.electronAPI.popOutSidebar(String(id));
  if (!result?.ok) return;
  isSidebarPoppedOut.value = true;
  isSidebarOpen.value = false;
  persistSidebarOpen();
};

const returnSidebarToViewer = async () => {
  if (window.electronAPI?.closeSidebarPopout) {
    await window.electronAPI.closeSidebarPopout();
  } else {
    window.close();
  }
};

const toggleSidebar = async () => {
  if (isSidebarPoppedOut.value) {
    await window.electronAPI?.focusSidebarPopout?.();
    return;
  }
  isSidebarOpen.value = !isSidebarOpen.value;
  persistSidebarOpen();
};

const ensureSidebarOpen = () => {
  if (isSidebarOpen.value) return;
  isSidebarOpen.value = true;
  persistSidebarOpen();
};

// zoom helpers
const zoomIn = () => {
  if (zoomLevel.value < 500) {
    const newLevel = zoomLevel.value + 10;
    zoomLevel.value = newLevel;
    inputZoomLevel.value = newLevel;
  }
};

const zoomOut = () => {
  if (zoomLevel.value > 50) {
    const newLevel = zoomLevel.value - 10;
    zoomLevel.value = newLevel;
    inputZoomLevel.value = newLevel;
  }
};

const handleZoomInput = () => {
  let val = parseInt(inputZoomLevel.value);
  if (isNaN(val)) val = 100;
  if (val < 50) val = 50;
  if (val > 500) val = 500;

  inputZoomLevel.value = val;
  zoomLevel.value = val; // triggers render
};

const scrollToPage = (pageNumber) => {
  scrollToPagePosition(pageNumber, 0, { align: "start" });
};

const navigateToPageWithHistory = (
  pageNumber,
  originPage = currentPage.value,
) => {
  const destination = Number(pageNumber);
  if (
    !Number.isInteger(destination) ||
    destination < 1 ||
    destination > totalPages.value
  ) {
    pageNumberInput.value = currentPage.value;
    return;
  }

  const origin = Number(originPage);
  if (origin === destination) return;

  undoStack.value.push({
    type: "navigate",
    fromPage: origin,
    toPage: destination,
  });
  redoStack.value = [];
  scrollToPage(destination);
};

const beginPageNumberEdit = () => {
  pageNumberInputOrigin = currentPage.value;
};

const commitPageNumberEdit = () => {
  const destination = Number(pageNumberInput.value);
  if (
    !Number.isInteger(destination) ||
    destination < 1 ||
    destination > totalPages.value
  ) {
    pageNumberInput.value = currentPage.value;
    return;
  }

  if (destination === pageNumberInputOrigin) {
    pageNumberInput.value = currentPage.value;
    return;
  }

  navigateToPageWithHistory(destination, pageNumberInputOrigin);
};

// Scroll so a specific unscaled page Y (sticky/highlight) lands in view
const scrollToPagePosition = (pageNumber, yUnscaled = 0, options = {}) => {
  if (pageNumber < 1 || pageNumber > totalPages.value) return;
  const pageEl = pageContainerRefs.value[pageNumber - 1];
  const scroller = mainScrollContainer.value;
  if (!pageEl || !scroller) return;

  const scale = zoomLevel.value / 100;
  const yScaled = Math.max(0, (yUnscaled || 0) * scale);
  const align = options.align || "center";

  isManualScrolling.value = true;
  currentPage.value = pageNumber;
  queuePageRender(pageNumber, true);
  processRenderQueue();

  const applyScroll = () => {
    const scrollerRect = scroller.getBoundingClientRect();
    const pageRect = pageEl.getBoundingClientRect();
    const absoluteTop =
      scroller.scrollTop + (pageRect.top - scrollerRect.top) + yScaled;

    let targetTop;
    if (align === "start") {
      targetTop = absoluteTop - 16;
    } else {
      // Keep the annotation roughly in the upper-middle of the viewport
      targetTop = absoluteTop - scroller.clientHeight * 0.35;
    }

    scroller.scrollTo({
      top: Math.max(0, targetTop),
      behavior: "smooth",
    });
  };

  // Wait a frame so page layout/render can settle when jumping far
  requestAnimationFrame(() => {
    applyScroll();
    // Retry once after render for pages that weren't laid out yet
    setTimeout(applyScroll, 120);
  });

  setTimeout(() => {
    isManualScrolling.value = false;
    cleanupRenderedPages();
  }, 1000);
};

const changePage = (diff) => {
  const newPage = currentPage.value + diff;
  scrollToPage(newPage);
};

async function renderPage(pageNum, force = false) {
  if (!pdfDoc) return;

  const canvas = canvasRefs.value[pageNum - 1];
  const textLayerDiv = textLayerRefs.value[pageNum - 1];

  if (!canvas) return;
  const renderSignature = `${zoomLevel.value}|${searchQuery.value.trim().toLowerCase()}`;

  if (!force && renderedPageSignatures.get(pageNum) === renderSignature) {
    return;
  }

  if (renderTasks[pageNum]) {
    const activeSignature = activeRenderSignatures.get(pageNum);
    if (!force && activeSignature === renderSignature) {
      return renderTasks[pageNum].promise;
    }
    renderTasks[pageNum].cancel();
  }

  try {
    const page = await pdfDoc.getPage(pageNum);
    pageProxies[pageNum] = page;
    const scale = zoomLevel.value / 100;
    const viewport = page.getViewport({ scale });

    const outputScale = Math.min(
      window.devicePixelRatio || 1,
      MAX_CANVAS_DEVICE_PIXEL_RATIO,
    );

    const context = canvas.getContext("2d");

    canvas.width = Math.floor(viewport.width * outputScale);
    canvas.height = Math.floor(viewport.height * outputScale);

    const cssWidth = viewport.width + "px";
    const cssHeight = viewport.height + "px";

    canvas.style.width = cssWidth;
    canvas.style.height = cssHeight;

    const transform =
      outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;

    const renderContext = {
      canvasContext: context,
      transform: transform,
      viewport: viewport,
      // Native PDF annotations may contain links, launch actions, file
      // attachments, forms, and media. Research Marker renders only passive
      // page content and its own separately managed annotation overlay.
      annotationMode: pdfjsLib.AnnotationMode.DISABLE,
    };

    const renderTask = page.render(renderContext);
    renderTasks[pageNum] = renderTask;
    activeRenderSignatures.set(pageNum, renderSignature);

    await renderTask.promise;

    if (textLayerDiv) {
      textLayerDiv.innerHTML = "";

      textLayerDiv.style.width = cssWidth;
      textLayerDiv.style.height = cssHeight;

      textLayerDiv.style.setProperty("--scale-factor", scale);
      textLayerDiv.style.setProperty("--total-scale-factor", scale);
      textLayerDiv.setAttribute("data-page-number", pageNum);

      // C=click listener for sticky note placement
      textLayerDiv.onclick = (e) => handleLayerClick(e, pageNum);

      const textContent = await page.getTextContent();

      const textLayer = new pdfjsLib.TextLayer({
        textContentSource: textContent,
        container: textLayerDiv,
        viewport: viewport,
      });
      await textLayer.render();

      const pageHighlights = savedHighlights.value.filter(
        (h) => h.page === pageNum,
      );
      pageHighlights.forEach((h) => renderHighlight(h, textLayerDiv));

      const pageStickyNotes = stickyNoteData.value.filter(
        (s) => s.page === pageNum,
      );
      pageStickyNotes.forEach((s) => renderStickyNote(s, textLayerDiv));

      if (searchQuery.value.trim() !== "") {
        const query = searchQuery.value.trim();
        const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const regex = new RegExp(`(${escapedQuery})`, "gi");

        const spans = textLayerDiv.querySelectorAll("span");

        spans.forEach((span) => {
          if (regex.test(span.textContent)) {
            span.innerHTML = span.textContent.replace(
              regex,
              `<mark class="bg-yellow-500/40 text-transparent rounded-sm">$1</mark>`,
            );
          }
        });
      }
    }
    renderedPageSignatures.set(pageNum, renderSignature);
  } catch (err) {
    if (err.name === "RenderingCancelledException") {
      return;
    }
    console.error(`Error rendering page ${pageNum}:`, err);
  } finally {
    delete renderTasks[pageNum];
    activeRenderSignatures.delete(pageNum);
  }
}
const pageSizes = ref([]);
async function loadPdf(data) {
  try {
    releaseAllRenderedPages();
    renderedPageSignatures.clear();
    activeRenderSignatures.clear();
    queuedPageRenders.clear();
    visiblePages.value.clear();
    pageTextContent.value = {};
    Object.values(renderTasks).forEach((task) => task.cancel?.());
    Object.keys(renderTasks).forEach((key) => delete renderTasks[key]);

    const loadingTask = pdfjsLib.getDocument({
      data,
      // Never allow PDF.js to generate executable code from PDF content.
      isEvalSupported: false,
      // XFA is an interactive form technology and is outside the passive
      // document feature set supported by this reader.
      enableXfa: false,
    });
    pdfDoc = await loadingTask.promise;
    totalPages.value = pdfDoc.numPages;

    const sizes = [];
    for (let i = 1; i <= pdfDoc.numPages; i++) {
      const page = await pdfDoc.getPage(i);
      const viewport = page.getViewport({ scale: 1 });
      sizes.push({ width: viewport.width, height: viewport.height });
      page.cleanup?.();
    }
    pageSizes.value = sizes;

    await pdfDoc.getDownloadInfo();

    await nextTick();

    if (currentPage.value > 1) {
      scrollToPage(currentPage.value);
    }
    setupIntersectionObserver();
    setTimeout(() => {
      setupCurrentPageObserver();
    }, 500);
    extractAllText();
  } catch (err) {
    console.error("Error loading PDF doc:", err);
    error.value = "Failed to parse PDF document.";
  }
}

let observer = null;
const visiblePages = ref(new Set());

function setupIntersectionObserver() {
  if (observer) observer.disconnect();

  const options = {
    root: mainScrollContainer.value,
    rootMargin: "50% 0px 50% 0px", // Increased margin so pages render slightly before they come into view
    threshold: 0,
  };

  observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      const pageIndex = pageContainerRefs.value.indexOf(entry.target);

      if (pageIndex === -1) return;

      const pageNum = pageIndex + 1;

      if (entry.isIntersecting) {
        visiblePages.value.add(pageNum);
        queuePageRender(pageNum);
        processRenderQueue();
      } else {
        visiblePages.value.delete(pageNum);
        cleanupRenderedPages();
      }
    });
  }, options);

  pageContainerRefs.value.forEach((el) => {
    if (el) observer.observe(el);
  });
}

let pageTrackingObserver = null;
function setupCurrentPageObserver() {
  if (pageTrackingObserver) pageTrackingObserver.disconnect();

  const options = {
    root: mainScrollContainer.value,
    rootMargin: "-50% 0px -50% 0px",
    threshold: 0,
  };

  pageTrackingObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      // Only update if intersecting and not programmatically scrolling
      if (entry.isIntersecting && !isManualScrolling.value) {
        const pageIndex = pageContainerRefs.value.indexOf(entry.target);

        if (pageIndex !== -1) {
          currentPage.value = pageIndex + 1;
          cleanupRenderedPages();
        }
      }
    });
  }, options);

  pageContainerRefs.value.forEach((el) => {
    if (el) pageTrackingObserver.observe(el);
  });
}

async function fetchPaper() {
  loading.value = true;
  error.value = null;
  try {
    const [res] = await Promise.all([
      fetch(`${apiBaseURL}/get-paper/${id}/`, {
        method: "GET",
      }),
      fetchPaperTitle(),
    ]);
    if (!res.ok) throw new Error("Failed to fetch PDF from server");

    const blob = await res.blob();
    const arrayBuffer = await blob.arrayBuffer();

    pdfBytes = new Uint8Array(arrayBuffer);
    if (AnnotationFactory) {
      factory = new AnnotationFactory(pdfBytes);
    }

    loading.value = false;
    await nextTick();
    await loadPdf(pdfBytes);
    await publishActivePaperContext();
  } catch (err) {
    console.error("Error fetching paper:", err);
    error.value = err.message;
    loading.value = false;
  }
}

async function fetchPaperTitle() {
  try {
    const paper = await $fetch(`${apiBaseURL}/documents/${id}/`);
    paperTitle.value = paper?.title?.trim() || "Untitled Paper";
  } catch (err) {
    console.warn("Failed to fetch paper title", err);
    paperTitle.value = "Untitled Paper";
  }
}

watch(zoomLevel, async (newZoom, oldZoom) => {
  if (zoomDebounce) clearTimeout(zoomDebounce);

  const scaleFactor = newZoom / oldZoom;
  const container = mainScrollContainer.value;

  if (container) {
    const viewportWidth = container.clientWidth;
    const viewportHeight = container.clientHeight;

    const centerX = container.scrollLeft + viewportWidth / 2;
    const centerY = container.scrollTop + viewportHeight / 2;

    await nextTick();

    container.scrollLeft = centerX * scaleFactor - viewportWidth / 2;
    container.scrollTop = centerY * scaleFactor - viewportHeight / 2;
  }

  zoomDebounce = setTimeout(async () => {
    Array.from(visiblePages.value).forEach((pageNum) => {
      queuePageRender(pageNum, true);
    });
    processRenderQueue();
  }, 150);
});

let removeSidebarClosedListener = null;
let removeRevealAnnotationListener = null;

onMounted(async () => {
  try {
    setupSidebarSync();

    if (!isSidebarPopout) {
      removeSidebarClosedListener =
        window.electronAPI?.onSidebarPopoutClosed?.((payload) => {
          if (String(payload?.documentId ?? "") !== String(id)) return;
          isSidebarPoppedOut.value = false;
          isSidebarOpen.value = true;
          persistSidebarOpen();
        }) ?? null;
      removeRevealAnnotationListener =
        window.electronAPI?.onRevealSidebarAnnotation?.((payload) => {
          if (String(payload?.documentId ?? "") !== String(id)) return;
          const page = Number(payload.page);
          const y = Number(payload.y) || 0;
          if (!Number.isInteger(page)) return;
          if (payload.type === "stickyNote") {
            activeStickyNoteId.value = payload.annotationId;
            activeHighlightId.value = null;
          } else if (payload.type === "highlight") {
            activeHighlightId.value = payload.annotationId;
            activeStickyNoteId.value = null;
          }
          scrollToPagePosition(page, y);
        }) ?? null;
    }

    await initializeAiModels();

    if (isSidebarPopout) {
      await Promise.all([fetchAnnotations(), fetchPaperTitle()]);
      loading.value = false;
      return;
    }

    const pdfjsModule = await import("pdfjs-dist");
    pdfjsLib = pdfjsModule;

    const workerModule = await import("pdfjs-dist/build/pdf.worker.mjs?url");
    pdfjsLib.GlobalWorkerOptions.workerSrc = workerModule.default;

    try {
      const viewerModule = await import("pdfjs-dist/web/pdf_viewer.mjs");
      TextLayerClass = viewerModule.TextLayer;
    } catch (e) {
      console.warn("Could not load TextLayer.", e);
    }

    await fetchAnnotations();
    await fetchPaper();

    mainScrollContainer.value?.addEventListener("scroll", handleMainScroll, {
      passive: true,
    });
    document.addEventListener("keydown", handleKeyboardShortcuts);
    document.addEventListener("mouseup", handleTextSelection);
    document.addEventListener("pointerdown", handleDocumentPointerDown);
    document.addEventListener("click", restoreReaderFocusAfterInteraction);
    mainScrollContainer.value?.focus({ preventScroll: true });
  } catch (err) {
    console.error("Failed to load PDF libraries:", err);
    error.value = "Failed to initialize PDF viewer.";
    loading.value = false;
  }
});

onUnmounted(() => {
  removeSidebarClosedListener?.();
  removeRevealAnnotationListener?.();
  sidebarSyncChannel?.close();
  sidebarSyncChannel = null;
  document.removeEventListener("mouseup", handleTextSelection);
  document.removeEventListener("pointerdown", handleDocumentPointerDown);
  document.removeEventListener("keydown", handleKeyboardShortcuts);
  document.removeEventListener("click", restoreReaderFocusAfterInteraction);
  mainScrollContainer.value?.removeEventListener("scroll", handleMainScroll);
  if (scrollEndDebounce) clearTimeout(scrollEndDebounce);
  if (zoomDebounce) clearTimeout(zoomDebounce);
  if (searchDebounce) clearTimeout(searchDebounce);
  if (pageUpdateDebounce) clearTimeout(pageUpdateDebounce);
  if (activeContextDebounce) clearTimeout(activeContextDebounce);
  if (saveNotepadDebounce) clearTimeout(saveNotepadDebounce);
  if (saveStickyDebounce) clearTimeout(saveStickyDebounce);
  if (observer) observer.disconnect();
  if (pageTrackingObserver) pageTrackingObserver.disconnect();
  releaseAllRenderedPages();
  pdfDoc?.destroy?.().catch((err) => {
    console.warn("Failed to destroy PDF document", err);
  });
  pdfDoc = null;
  pdfBytes = null;
  factory = null;
});

// Search Func
const searchQuery = ref("");
const searchResults = ref([]);
const currentMatchIndex = ref(-1);
const pageTextContent = ref({});
const isSearching = ref(false);
let searchDebounce = null;

async function extractAllText() {
  if (!pdfDoc) return;
  const numPages = pdfDoc.numPages;

  for (let i = 1; i <= numPages; i++) {
    try {
      const page = await pdfDoc.getPage(i);
      const textContent = await page.getTextContent();
      const pageStr = textContent.items.map((item) => item.str).join(" ");
      pageTextContent.value[i] = pageStr;

      // Text extraction touches every page; release the parse data for pages
      // that aren't near the viewport so it doesn't stay resident. Visible
      // pages keep their proxy (tracked in pageProxies) for rendering.
      if (!isPageNearViewport(i) && !pageProxies[i]) {
        page.cleanup?.();
      }
    } catch (e) {
      console.warn(`Could not extract text for page ${i}`);
    }
  }
}

function performSearch() {
  const query = searchQuery.value.toLowerCase().trim();
  console.log(query);
  searchResults.value = [];
  currentMatchIndex.value = -1;

  if (!query) {
    Array.from(visiblePages.value).forEach((pageNum) => {
      queuePageRender(pageNum, true);
    });
    processRenderQueue();
    return;
  }

  isSearching.value = true;

  for (const [pageNumStr, text] of Object.entries(pageTextContent.value)) {
    const pageNum = parseInt(pageNumStr);
    const lowerText = text.toLowerCase();

    if (lowerText.includes(query)) {
      searchResults.value.push({ page: pageNum });
    }
  }

  if (searchResults.value.length > 0) {
    currentMatchIndex.value = 0;
    scrollToPage(searchResults.value[0].page);
  }

  Array.from(visiblePages.value).forEach((pageNum) => {
    queuePageRender(pageNum, true);
  });
  queuePageRender(currentPage.value, true);
  processRenderQueue();
  isSearching.value = false;
}

const nextMatch = () => {
  if (searchResults.value.length === 0) return;

  if (currentMatchIndex.value < searchResults.value.length - 1) {
    currentMatchIndex.value++;
  } else {
    currentMatchIndex.value = 0;
  }

  scrollToPage(searchResults.value[currentMatchIndex.value].page);
};

const prevMatch = () => {
  if (searchResults.value.length === 0) return;

  if (currentMatchIndex.value > 0) {
    currentMatchIndex.value--;
  } else {
    currentMatchIndex.value = searchResults.value.length - 1;
  }

  scrollToPage(searchResults.value[currentMatchIndex.value].page);
};

watch(searchQuery, () => {
  console.log("Searching for:", searchQuery.value);
  if (searchDebounce) clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    performSearch();
    console.log("Searching for:", searchQuery.value);
  }, 3000); // 3s debounce to keep load off of backend
});

// Publish the open paper/page for Codex + Claude MCP (@page).
// Previously this only ran after a page *change* with a 5s debounce, so opening a
// paper and staying on page 1 never registered an active document.
async function publishActivePaperContext() {
  try {
    await $fetch(`${apiBaseURL}/paper-context/active/`, {
      method: "POST",
      body: {
        document_id: Number(id),
        document_title: paperTitle.value,
        current_page: currentPage.value,
      },
    });
  } catch (err) {
    console.warn("Failed to publish active paper context", err);
  }
}

async function postPage() {
  await Promise.all([
    $fetch(`${apiBaseURL}/documents/${id}/`, {
      method: "PATCH",
      body: {
        last_page: currentPage.value,
        zoom_level: zoomLevel.value,
      },
    }),
    publishActivePaperContext(),
  ]);
}

let pageUpdateDebounce = null;
let activeContextDebounce = null;
watch(currentPage, (page) => {
  pageNumberInput.value = page;

  if (activeContextDebounce) clearTimeout(activeContextDebounce);
  activeContextDebounce = setTimeout(() => {
    publishActivePaperContext();
  }, 300);

  if (pageUpdateDebounce) clearTimeout(pageUpdateDebounce);
  pageUpdateDebounce = setTimeout(() => {
    postPage();
  }, 5000);
});
</script>

<template>
  <div
    class="flex h-screen w-full flex-col overflow-hidden bg-slate-950 text-slate-300 font-sans selection:bg-indigo-500/30"
  >
    <header
      v-if="!isSidebarPopout"
      class="relative flex h-16 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900 px-4 shadow-sm z-20"
    >
      <div class="flex items-center gap-4">
        <NuxtLink
          to="/"
          class="flex items-center justify-center rounded-md p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
          title="Back to Dashboard"
        >
          <Icon name="ph:arrow-left" class="h-5 w-5" />
        </NuxtLink>

        <div class="h-5 w-px bg-slate-700/50"></div>

        <div class="hidden md:flex items-center gap-2" title="Search Document">
          <SearchBar v-model:search-query="searchQuery" />

          <div
            v-if="searchQuery"
            class="flex items-center gap-1 bg-slate-800 rounded-lg px-2 py-1 border border-slate-700"
          >
            <span class="text-xs text-slate-400 font-mono w-12 text-center">
              {{ searchResults.length > 0 ? currentMatchIndex + 1 : 0 }} /
              {{ searchResults.length }}
            </span>
            <div class="w-px h-4 bg-slate-700 mx-1"></div>
            <button
              @click="prevMatch"
              class="p-1 hover:text-white text-slate-400 transition-colors disabled:opacity-50"
              :disabled="searchResults.length === 0"
            >
              <Icon name="ph:caret-up" class="h-3.5 w-3.5" />
            </button>
            <button
              @click="nextMatch"
              class="p-1 hover:text-white text-slate-400 transition-colors disabled:opacity-50"
              :disabled="searchResults.length === 0"
            >
              <Icon name="ph:caret-down" class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <div class="h-5 w-px bg-slate-700/50"></div>

        <div class="hidden lg:flex items-center gap-1">
          <button
            class="icon-btn"
            :disabled="currentPage <= 1"
            @click="changePage(-1)"
          >
            <Icon name="ph:caret-left" class="h-4 w-4" />
          </button>

          <div
            class="flex items-center bg-slate-800 rounded border border-slate-700 overflow-hidden"
          >
            <input
              type="number"
              v-model="pageNumberInput"
              @focus="beginPageNumberEdit"
              @change="commitPageNumberEdit"
              :max="totalPages"
              min="1"
              class="w-10 bg-transparent py-1 text-center text-sm font-medium text-slate-200 outline-none focus:bg-slate-700 transition-colors [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            />
            <span
              class="border-l border-slate-700 bg-slate-800 px-2 text-xs text-slate-500 select-none"
            >
              / {{ totalPages || "-" }}
            </span>
          </div>

          <button
            class="icon-btn"
            :disabled="currentPage >= totalPages"
            @click="changePage(1)"
          >
            <Icon name="ph:caret-right" class="h-4 w-4" />
          </button>
        </div>
      </div>

      <div
        class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-30 ml-18 xl:md-4"
      >
        <div
          class="flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-800/50 p-1 shadow-sm"
        >
          <button
            class="tool-btn"
            title="Undo"
            @click="performUndo"
            :disabled="undoStack.length === 0"
          >
            <Icon name="ph:arrow-u-up-left" class="h-5 w-5" />
          </button>
          <button
            class="tool-btn"
            title="Redo"
            @click="performRedo"
            :disabled="redoStack.length === 0"
          >
            <Icon name="ph:arrow-u-up-right" class="h-5 w-5" />
          </button>

          <div class="mx-1 h-5 w-px bg-slate-600/50"></div>

          <button
            id="cursor"
            @click="changeActiveTool('cursor')"
            class="tool-btn"
            :class="{ 'active-tool': activeTool === 'cursor' }"
            title="Select Cursor (V)"
          >
            <Icon name="ph:cursor" class="text-[16px]" />
          </button>
          <button
            id="highlighter"
            @click="changeActiveTool('highlighter')"
            :class="{ 'active-tool': activeTool === 'highlighter' }"
            class="tool-btn"
            title="Highlight Text (H)"
          >
            <Icon name="ph:highlighter" class="text-[16px]" />
          </button>

          <button
            id="stickyNote"
            @click="changeActiveTool('stickyNote')"
            :class="{ 'active-tool': activeTool === 'stickyNote' }"
            class="tool-btn"
            title="Sticky Note (S)"
          >
            <Icon name="ph:note" class="text-[16px]" />
          </button>
          <button
            id="deleteAnnotation"
            @click="changeActiveTool('deleteAnnotation')"
            class="tool-btn"
            :class="{ 'active-tool': activeTool === 'deleteAnnotation' }"
            title="Delete Annotation (D)"
          >
            <Icon name="material-symbols:delete-outline" class="text-[16px]" />
          </button>

          <div class="relative mx-0.5">
            <button
              class="tool-btn flex items-center justify-center"
              title="Color Palette"
              @click="isColorPickerOpen = !isColorPickerOpen"
            >
              <div
                class="h-4 w-4 rounded-full border border-slate-500"
                :style="{ backgroundColor: selectedColor }"
              ></div>
            </button>

            <div
              v-if="isColorPickerOpen"
              class="absolute top-full mt-2 left-1/2 -translate-x-1/2 flex flex-col gap-2 rounded-lg border border-slate-700 bg-slate-800 p-2 shadow-xl z-50"
            >
              <button
                v-for="color in colors"
                :key="color"
                class="h-6 w-6 rounded-full border border-transparent hover:scale-110 transition-transform"
                :class="{
                  'ring-2 ring-indigo-400 ring-offset-2 ring-offset-slate-800':
                    selectedColor === color,
                }"
                :style="{ backgroundColor: color }"
                @click="selectColor(color)"
              ></button>
            </div>
          </div>

          <div class="mx-1 h-5 w-px bg-slate-600/50"></div>

          <button
            class="tool-btn"
            :class="{ 'text-indigo-400': isAnnotationsHidden }"
            @click="isAnnotationsHidden = !isAnnotationsHidden"
            title="Toggle Annotations"
          >
            <Icon
              :name="isAnnotationsHidden ? 'ph:eye-slash' : 'ph:eye'"
              class="h-5 w-5"
            />
          </button>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <div
          class="hidden md:flex items-center rounded-md border border-slate-700 bg-slate-800"
        >
          <button
            class="p-1.5 hover:bg-slate-700 hover:text-white transition-colors"
            @click="zoomOut"
          >
            <Icon name="ph:minus" class="h-3.5 w-3.5" />
          </button>
          <input
            type="number"
            v-model.number="inputZoomLevel"
            @keydown.enter="handleZoomInput"
            @blur="handleZoomInput"
            min="50"
            max="500"
            aria-label="Zoom Level"
            class="w-10 text-center text-[14px] font-medium text-slate-300 select-none bg-transparent outline-none border-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
          />
          <span
            class="text-[14px] font-medium text-slate-400 select-none pr-0.5"
            >%</span
          >
          <button
            class="p-1.5 hover:bg-slate-700 hover:text-white transition-colors"
            @click="zoomIn"
          >
            <Icon name="ph:plus" class="h-3.5 w-3.5" />
          </button>
        </div>

        <div class="h-5 w-px bg-slate-700/50"></div>

        <button
          @click="toggleSidebar"
          class="icon-btn active:bg-indigo-500/20"
          :class="{ 'bg-slate-800 text-indigo-400': isSidebarOpen }"
          title="Toggle Sidebar"
        >
          <Icon name="ph:sidebar-simple" class="h-5 w-5" />
        </button>
      </div>
    </header>

    <div
      v-if="!isSidebarPopout"
      class="flex h-9 shrink-0 items-center border-b border-slate-800 bg-slate-900/80 px-4 text-sm"
      :title="paperTitle || 'Untitled Paper'"
    >
      <Icon name="ph:file-pdf" class="mr-2 h-4 w-4 shrink-0 text-indigo-400" />
      <h1 class="truncate font-medium text-slate-200">
        {{ paperTitle || "Untitled Paper" }}
      </h1>
    </div>

    <div class="flex flex-1 overflow-hidden relative">
      <main
        v-if="!isSidebarPopout"
        ref="mainScrollContainer"
        tabindex="0"
        role="document"
        aria-label="PDF reader"
        @pointerdown="focusPdfReader"
        @contextmenu="handleTextContextMenu"
        @keydown="handleReaderArrowNavigation"
        class="flex-1 overflow-auto bg-slate-950 p-8 flex flex-col items-center gap-4 outline-none"
        :class="{ 'hide-annotations': isAnnotationsHidden }"
        style="overflow-anchor: none; scroll-behavior: auto"
      >
        <div
          v-if="loading"
          class="w-full text-slate-500 flex flex-col items-center mt-20"
        >
          <Icon name="ph:spinner" class="h-8 w-8 animate-spin mb-2" />
          <p>Loading PDF...</p>
        </div>

        <div
          v-else-if="error"
          class="w-full text-red-400 flex flex-col items-center mt-20"
        >
          <Icon name="ph:warning" class="h-8 w-8 mb-2" />
          <p>{{ error }}</p>
        </div>

        <template v-else>
          <div
            v-for="page in totalPages"
            :key="page"
            class="mx-auto flex flex-col items-center"
          >
            <div
              :ref="(el) => (pageContainerRefs[page - 1] = el)"
              class="relative shadow-2xl border border-slate-800 bg-white"
              :style="
                pageSizes[page - 1]
                  ? {
                      width: `${
                        pageSizes[page - 1].width * (zoomLevel / 100)
                      }px`,
                      height: `${
                        pageSizes[page - 1].height * (zoomLevel / 100)
                      }px`,
                      contain: 'layout style',
                    }
                  : {
                      contain: 'layout style',
                    }
              "
            >
              <canvas
                :ref="(el) => (canvasRefs[page - 1] = el)"
                class="block w-full h-full"
              ></canvas>
              <div
                :ref="(el) => (textLayerRefs[page - 1] = el)"
                class="textLayer absolute inset-0"
              ></div>
            </div>
          </div>

          <div class="h-36 w-full shrink-0"></div>
        </template>
      </main>

      <div
        v-if="!isSidebarPopout && isSidebarOpen"
        class="w-1 cursor-col-resize hover:bg-indigo-500/50 active:bg-indigo-500 transition-colors bg-slate-800 z-30"
        @mousedown.prevent="startResize"
      ></div>

      <aside
        class="border-l border-slate-800 bg-slate-900 transition-none flex flex-col shrink-0 overflow-hidden"
        :style="{
          width: isSidebarPopout
            ? '100%'
            : isSidebarOpen
              ? `${sidebarWidth}px`
              : '0px',
        }"
        :class="{
          'border-none opacity-0': !isSidebarPopout && !isSidebarOpen,
        }"
        aria-label="Annotation sidebar"
      >
        <div
          class="flex min-h-0 shrink-0 origin-top-left"
          :style="sidebarScaleStyle"
        >
          <!-- Compact vertical tab rail -->
          <nav
            class="w-9 shrink-0 border-r border-slate-800 bg-slate-950/90 flex flex-col items-center py-1.5 gap-0.5"
          >
            <button
              v-for="tab in sidebarTabs"
              :key="tab.id"
              type="button"
              @click="changeSidebarTab(tab.id)"
              class="relative w-7 h-7 rounded-md flex items-center justify-center transition-colors"
              :class="
                sidebarActiveTab === tab.id
                  ? 'bg-indigo-500/15 text-indigo-300'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/80'
              "
              :title="tab.label"
            >
              <span
                v-if="sidebarActiveTab === tab.id"
                class="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-indigo-400"
              ></span>
              <Icon :name="tab.icon" class="w-3.5 h-3.5" />
            </button>

            <div class="flex-1"></div>

            <button
              type="button"
              @click="decreaseSidebarFont"
              :disabled="sidebarFontScale <= SIDEBAR_FONT_MIN"
              class="w-7 h-7 rounded-md flex items-center justify-center text-slate-500 hover:text-slate-200 hover:bg-slate-800/80 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              title="Decrease font size"
            >
              <span class="text-[10px] font-semibold leading-none">A−</span>
            </button>
            <button
              type="button"
              @click="increaseSidebarFont"
              :disabled="sidebarFontScale >= SIDEBAR_FONT_MAX"
              class="w-7 h-7 rounded-md flex items-center justify-center text-slate-500 hover:text-slate-200 hover:bg-slate-800/80 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              title="Increase font size"
            >
              <span class="text-[12px] font-semibold leading-none">A+</span>
            </button>
          </nav>

          <!-- Panel content -->
          <div class="flex-1 flex flex-col min-w-0 min-h-0">
            <div
              class="h-9 border-b border-slate-800 flex items-center justify-between px-3 shrink-0 bg-slate-900/80"
            >
              <span class="text-xs font-medium text-slate-300 truncate">{{
                activeSidebarTabLabel
              }}</span>
              <div class="flex items-center gap-1 shrink-0">
                <button
                  v-if="isSidebarPopout || canPopOutSidebar"
                  type="button"
                  @click="isSidebarPopout ? returnSidebarToViewer() : popOutSidebar()"
                  class="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                  :title="
                    isSidebarPopout
                      ? 'Return sidebar to PDF viewer'
                      : 'Open sidebar in a separate window'
                  "
                  :aria-label="
                    isSidebarPopout
                      ? 'Return sidebar to PDF viewer'
                      : 'Open sidebar in a separate window'
                  "
                >
                  <Icon
                    :name="
                      isSidebarPopout
                        ? 'ph:arrow-line-left'
                        : 'ph:arrow-square-out'
                    "
                    class="w-3.5 h-3.5"
                  />
                </button>
                <template v-if="sidebarActiveTab === 'chat'">
                  <button
                    type="button"
                    @click="startNewChat"
                    class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                    title="New chat"
                  >
                    <Icon name="ph:plus" class="w-3.5 h-3.5" />
                    New
                  </button>
                  <button
                    type="button"
                    @click="toggleChatHistory"
                    class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors"
                    :class="
                      showChatHistory
                        ? 'bg-indigo-500/20 text-indigo-300'
                        : 'text-slate-400 hover:text-white hover:bg-slate-700'
                    "
                    title="Chat History"
                  >
                    <Icon
                      :name="showChatHistory ? 'uil:times' : 'uil:history'"
                      class="w-3.5 h-3.5"
                    />
                    History
                  </button>
                </template>
              </div>
            </div>

        <div
          v-show="sidebarActiveTab === 'stickyNotes'"
          class="flex-1 p-4 flex flex-col overflow-y-auto gap-3"
        >
          <div
            v-if="stickyNoteData.length === 0"
            class="flex flex-col items-center justify-center h-32 text-slate-600"
          >
            <span class="text-sm italic opacity-50"
              >Click on PDF to add note</span
            >
          </div>

          <div
            v-for="note in stickyNoteData"
            :key="note.id"
            class="bg-slate-800 p-3 rounded border border-slate-700 hover:border-slate-600 transition-colors"
            :class="{
              'ring-2 ring-indigo-500': activeStickyNoteId === note.id,
            }"
            @click="focusStickyNote(note.id)"
          >
            <div class="flex justify-between items-start mb-2">
              <div class="flex items-center gap-2 relative">
                <div
                  class="w-2 h-2 rounded-full"
                  :style="{ backgroundColor: note.color }"
                ></div>

                <span class="text-xs text-slate-400 mr-1"
                  >Page {{ note.page }}</span
                >

                <div class="relative">
                  <button
                    @click.stop="toggleDropdown(note.id)"
                    class="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-slate-600 bg-slate-900/50 hover:bg-slate-700 transition-all group"
                  >
                    <span
                      class="text-[10px] font-medium"
                      :class="getTagColor(note.tag)"
                    >
                      {{ getTagLabel(note.tag) }}
                    </span>
                    <Icon
                      name="ph:caret-down-bold"
                      class="w-2.5 h-2.5 text-slate-500 group-hover:text-slate-300 transition-colors"
                    />
                  </button>

                  <div
                    v-if="activeDropdownId === note.id"
                    class="absolute top-full left-0 mt-1 w-28 py-1 rounded-lg border border-slate-600 bg-slate-800 shadow-xl z-50 flex flex-col gap-0.5"
                  >
                    <button
                      v-for="option in tagOptions"
                      :key="option.value"
                      @click.stop="setNoteTag(note, option)"
                      class="text-left px-3 py-1.5 text-[11px] font-medium hover:bg-white/5 transition-colors"
                      :class="[
                        note.tag === option.value
                          ? 'bg-white/5 ' + option.color
                          : 'text-slate-400',
                      ]"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                </div>
              </div>

              <button
                @click.stop="deleteStickyNote(note.id)"
                class="text-slate-600 hover:text-red-400 transition-colors"
              >
                <Icon name="ph:trash" class="w-4 h-4" />
              </button>
            </div>

            <div class="relative w-full">
              <div
                v-if="activeStickyNoteId !== note.id"
                class="w-full bg-slate-900/50 text-slate-300 text-sm p-2 rounded border border-slate-700/50 min-h-[5rem] break-words prose prose-invert prose-p:my-0"
                v-html="
                  renderContent(note.content) ||
                  '<span class=\'opacity-50 italic\'>Empty note...</span>'
                "
              ></div>

              <textarea
                v-else
                :ref="(el) => setStickyNoteTextareaRef(note.id, el)"
                v-model="note.content"
                @click.stop
                class="w-full bg-slate-900/50 text-slate-300 text-sm p-2 rounded border border-slate-700/50 focus:outline-none focus:border-indigo-500/50 resize-none h-20 custom-scrollbar font-mono"
                placeholder="Type note... ($E=mc^2$)"
              ></textarea>
            </div>
          </div>
        </div>

        <!-- Highlights Tab -->
        <div
          v-show="sidebarActiveTab === 'highlights'"
          class="flex-1 p-4 flex flex-col overflow-y-auto gap-2"
        >
          <div
            v-if="highlightsByPage.length === 0"
            class="flex flex-col items-center justify-center h-32 text-slate-600"
          >
            <span class="text-sm italic opacity-50"
              >Select text to highlight</span
            >
          </div>

          <button
            v-for="highlight in highlightsByPage"
            :key="highlight.id"
            type="button"
            class="w-full text-left bg-slate-800 p-3 rounded border border-slate-700 hover:border-slate-600 transition-colors"
            :class="{
              'ring-2 ring-indigo-500': activeHighlightId === highlight.id,
            }"
            @click="focusHighlight(highlight.id)"
          >
            <div class="flex items-center gap-2 mb-2">
              <div
                class="w-2.5 h-2.5 rounded-sm shrink-0"
                :style="{ backgroundColor: highlight.color }"
              ></div>
              <span class="text-xs text-slate-400"
                >Page {{ highlight.page }}</span
              >
            </div>
            <p class="text-sm text-slate-300 leading-relaxed line-clamp-4">
              {{ highlight.text?.trim() || "Empty highlight" }}
            </p>
          </button>
        </div>

        <div
          v-show="sidebarActiveTab === 'notepad'"
          class="flex-1 flex flex-col h-full overflow-hidden"
        >
          <div
            class="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-slate-900 shrink-0"
          >
            <div class="flex gap-1">
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
                title="Inline Math (Ctrl+M)"
              >
                <Icon name="ph:function" class="w-4 h-4" />
              </button>
              <button
                @mousedown.prevent
                @click="insertFormat('math-block')"
                class="toolbar-btn"
                title="Block Math (Ctrl+Shift+M)"
              >
                <Icon name="ph:sigma" class="w-4 h-4" />
              </button>
              <button
                @mousedown.prevent
                @click="insertFormat('quote')"
                class="toolbar-btn"
                title="Important quote"
                aria-label="Insert important quote"
              >
                <Icon name="ph:exclamation-mark" class="w-4 h-4" />
              </button>
              <button
                @mousedown.prevent
                @click="insertFormat('citation')"
                class="toolbar-btn"
                title="Cite current page"
                aria-label="Insert current page citation"
              >
                <Icon name="ph:link" class="w-4 h-4" />
              </button>
            </div>
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
              @mouseup="finishNotepadDocumentSelection"
              @keyup="finishNotepadDocumentSelection"
              @blur="blurNotepadDocumentSelection"
              @keydown.escape.prevent="
                leaveNotepadDocumentSelection($event.currentTarget.selectionStart)
              "
            ></textarea>

            <template v-else>
              <div
                v-for="(line, lineIndex) in notepadLines"
                :key="lineIndex"
                class="notepad-line"
                :class="{
                  'notepad-line--active': activeNotepadLine === lineIndex,
                  'notepad-line--quote': /^\s*>\s/.test(line),
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
                  @focus="activeNotepadLine = lineIndex"
                  @keydown="handleNotepadLineKeydown(lineIndex, $event)"
                ></textarea>
                <div
                  v-else
                  class="notepad-rendered-line"
                  role="button"
                  tabindex="0"
                  :aria-label="`Edit line ${lineIndex + 1}`"
                  v-html="renderNotepadLine(line)"
                  @click="handleNotepadRenderedLineClick($event, lineIndex)"
                  @keydown.enter.prevent="activateNotepadLine(lineIndex)"
                  @keydown.space.prevent="activateNotepadLine(lineIndex)"
                ></div>
              </div>
            </template>
          </div>

          <div
            class="h-6 bg-slate-900 border-t border-slate-800 flex items-center justify-end px-2 shrink-0"
          >
            <span class="text-[10px] text-slate-500 font-mono">
              Line {{ activeNotepadLine + 1 }} • Live Markdown • KaTeX Ready
            </span>
          </div>
        </div>

        <!-- OCR Tab -->
        <OcrPanel
          v-show="sidebarActiveTab === 'ocr'"
          :document-id="id"
          @ocr-completed="handleOcrCompleted"
        />

        <!-- Chat Tab -->
        <div
          v-show="sidebarActiveTab === 'chat'"
          class="flex-1 flex flex-col overflow-hidden bg-slate-900/40 relative min-h-0"
        >
          <div
            ref="chatScrollContainer"
            class="flex-1 min-h-0 overflow-y-auto px-3 py-4 space-y-4 custom-scrollbar"
          >
            <div
              v-if="chatMessages.length === 0 && !chatLoading"
              class="flex flex-col items-center justify-center min-h-[220px] text-center px-3"
            >
              <div class="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-500/10 border border-indigo-500/20">
                <Icon name="ph:chat-circle-dots" class="w-6 h-6 text-indigo-400" />
              </div>
              <p class="text-sm font-medium text-slate-200 mb-1">Ask about this paper</p>
              <p class="text-[11px] text-slate-500 leading-relaxed max-w-[240px]">
                Type
                <span class="font-mono text-indigo-300/90">@…</span>
                to choose precise paper context — for example
                <span class="font-mono text-indigo-300/90">@page 4</span>,
                <span class="font-mono text-indigo-300/90">@pages 6-8</span>, or
                <span class="font-mono text-indigo-300/90">@selection</span>.
              </p>
              <div class="mt-4 grid w-full grid-cols-2 gap-1.5">
                <button
                  v-for="opt in atMenuOptions.slice(0, 4)"
                  :key="opt.tag"
                  @click="insertAtTag(opt.tag)"
                  class="rounded-lg border border-slate-700/70 bg-slate-800/60 px-2 py-2 text-left hover:border-indigo-500/40 hover:bg-slate-800 transition-colors"
                >
                  <p class="text-[10px] font-mono text-indigo-300">{{ opt.tag }}</p>
                </button>
              </div>
              <button
                type="button"
                @click="toggleChatHistory"
                class="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-slate-700/70 bg-slate-800/40 px-3 py-2 text-[11px] text-slate-400 hover:text-white hover:border-indigo-500/40 transition-colors"
              >
                <Icon name="uil:history" class="w-3.5 h-3.5" />
                Open chat history
              </button>
            </div>

            <template v-else>
              <div
                v-for="(msg, idx) in chatMessages"
                :key="idx"
                class="flex gap-2.5"
                :class="msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'"
              >
                <div
                  class="w-7 h-7 shrink-0 rounded-lg flex items-center justify-center"
                  :class="
                    msg.role === 'user'
                      ? 'bg-slate-800 border border-slate-700'
                      : 'bg-indigo-500/15 border border-indigo-500/25'
                  "
                >
                  <Icon
                    :name="msg.role === 'user' ? 'ph:user' : 'ph:robot'"
                    class="w-3.5 h-3.5"
                    :class="msg.role === 'user' ? 'text-slate-300' : 'text-indigo-400'"
                  />
                </div>

                <div
                  class="max-w-[88%] rounded-2xl px-3 py-2.5 text-xs leading-relaxed shadow-sm"
                  :class="{
                    'bg-gradient-to-br from-indigo-600/90 to-indigo-700/80 text-white rounded-tr-md': msg.role === 'user',
                    'bg-slate-800/90 text-slate-200 border border-slate-700/60 rounded-tl-md': msg.role === 'model' && !msg.isError,
                    'bg-red-950/40 text-red-300 border border-red-800/40 rounded-tl-md': msg.isError,
                  }"
                >
                  <div v-if="msg.role === 'user'" class="whitespace-pre-wrap break-words">
                    <template v-for="(part, i) in parseChatInputParts(msg.content)" :key="i">
                      <span
                        v-if="part.type === 'tag'"
                        class="chat-input-tag chat-input-tag--sent"
                      >{{ part.text }}</span>
                      <span v-else>{{ part.text }}</span>
                    </template>
                  </div>
                  <template v-else>
                    <div class="chat-prose" v-html="renderChatContent(msg.content)"></div>
                    <div
                      v-if="msg.citations?.some((citation) => citation.valid)"
                      class="mt-2 flex flex-wrap gap-1.5 border-t border-white/5 pt-2"
                    >
                      <button
                        v-for="citation in msg.citations.filter((item) => item.valid)"
                        :key="`${citation.page_start}-${citation.page_end}-${citation.quoted_or_paraphrased_text}`"
                        type="button"
                        @click="scrollToPage(citation.page_start)"
                        class="rounded-md border border-indigo-500/25 bg-indigo-500/10 px-2 py-1 text-[10px] font-medium text-indigo-200 hover:bg-indigo-500/20"
                        :title="citation.quoted_or_paraphrased_text"
                      >
                        {{
                          citation.page_start === citation.page_end
                            ? `p. ${citation.page_start}`
                            : `pp. ${citation.page_start}–${citation.page_end}`
                        }}
                      </button>
                    </div>
                  </template>
                </div>
              </div>

              <div v-if="chatLoading" class="flex gap-2.5">
                <div class="w-7 h-7 shrink-0 rounded-lg bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center">
                  <Icon name="ph:robot" class="w-3.5 h-3.5 text-indigo-400" />
                </div>
                <div class="rounded-2xl rounded-tl-md bg-slate-800/90 border border-slate-700/60 px-3 py-2.5 flex items-center gap-1.5">
                  <div class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce"></div>
                  <div class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:120ms]"></div>
                  <div class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:240ms]"></div>
                </div>
              </div>
            </template>
          </div>

          <!-- Chat history overlay (same /chatlogs/ API as knowledge-base) -->
          <div
            v-if="showChatHistory"
            class="absolute inset-0 bg-slate-950/98 backdrop-blur-sm z-40 flex flex-col"
          >
            <div class="p-3 border-b border-slate-800">
              <button
                type="button"
                @click="startNewChat"
                class="w-full py-2.5 rounded-xl border border-dashed border-slate-700 text-slate-400 hover:text-white hover:border-indigo-500/50 hover:bg-indigo-500/10 transition-all flex items-center justify-center gap-2 text-xs font-medium"
              >
                <Icon name="ph:plus" class="w-3.5 h-3.5" />
                Start New Chat
              </button>
            </div>

            <div class="flex-1 overflow-y-auto p-2 custom-scrollbar">
              <div v-if="savedChats.length === 0" class="text-center py-10">
                <p class="text-slate-500 text-xs">No saved chats found.</p>
              </div>

              <div
                v-for="chat in savedChats"
                :key="chat.id"
                @click="loadChat(chat.id)"
                class="group p-2.5 rounded-xl hover:bg-white/5 cursor-pointer transition-colors border border-transparent hover:border-white/5 flex justify-between items-center mb-1"
                :class="{
                  'bg-white/5 border-white/10': chat.id === chatId,
                }"
              >
                <div class="flex-1 min-w-0 pr-2">
                  <h4
                    class="text-xs text-slate-300 truncate group-hover:text-white transition-colors"
                  >
                    {{ chat.name }}
                  </h4>
                  <p class="text-[10px] text-slate-600 truncate mt-0.5">
                    {{ new Date(chat.updated_at).toLocaleDateString() }}
                  </p>
                </div>

                <button
                  type="button"
                  @click="deleteChat(chat.id, $event)"
                  class="p-1.5 rounded text-slate-600 hover:text-red-400 hover:bg-red-400/10 opacity-0 group-hover:opacity-100 transition-all"
                  title="Delete Chat"
                  :disabled="isDeletingChat"
                >
                  <Icon name="ph:trash" class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          <div class="shrink-0 border-t border-slate-800 bg-slate-900 p-2.5">
            <div class="rounded-xl border border-slate-700/80 bg-slate-950/80 overflow-hidden shadow-lg">
              <div class="border-b border-slate-800 bg-slate-900/60">
                <div class="grid grid-cols-2 gap-2 px-2.5 py-2">
                  <select
                    v-model="selectedAiProvider"
                    class="ai-select min-w-0 rounded-lg border border-slate-700 px-2 py-1.5 text-[10px] outline-none focus:border-indigo-500/50"
                  >
                    <option v-for="provider in aiProviders" :key="provider.id" :value="provider.id">
                      {{ provider.label }}
                    </option>
                  </select>
                  <select
                    v-if="selectedProviderModels.length"
                    v-model="selectedAiModel"
                    class="ai-select min-w-0 rounded-lg border border-slate-700 px-2 py-1.5 text-[10px] outline-none focus:border-indigo-500/50"
                  >
                    <option v-for="model in selectedProviderModels" :key="model" :value="model">
                      {{ model }}
                    </option>
                  </select>
                  <div
                    v-else-if="selectedAiProvider === 'codex' && !selectedProviderModels.length"
                    class="ai-select min-w-0 rounded-lg border border-slate-700 px-2 py-1.5 text-[10px] text-slate-400"
                  >
                    Connect Codex in Settings
                  </div>
                  <input
                    v-else
                    v-model="selectedAiModel"
                    type="text"
                    :disabled="!selectedProvider?.has_api_key"
                    :placeholder="
                      selectedAiProvider === 'custom'
                        ? 'Model id (e.g. llama3.2)'
                        : selectedProviderModelHint || 'No models available'
                    "
                    class="ai-select min-w-0 rounded-lg border border-slate-700 px-2 py-1.5 text-[10px] outline-none focus:border-indigo-500/50 font-mono disabled:cursor-not-allowed disabled:opacity-60"
                    spellcheck="false"
                  />
                </div>
                <p
                  v-if="selectedProviderModelHint"
                  class="px-2.5 pb-2 text-[10px] leading-relaxed text-amber-400/90"
                >
                  {{ selectedProviderModelHint }}
                </p>
              </div>

              <div
                v-if="showAtMenu"
                class="border-b border-slate-800 max-h-36 overflow-y-auto custom-scrollbar"
              >
                <button
                  v-for="opt in atMenuOptions"
                  :key="opt.tag"
                  @mousedown.prevent="insertAtTag(opt.tag)"
                  class="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-slate-800/80 transition-colors"
                >
                  <Icon :name="opt.icon" class="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                  <span class="text-[11px] font-mono text-slate-200">{{ opt.tag }}</span>
                  <span class="text-[10px] text-slate-500 truncate">{{ opt.desc }}</span>
                </button>
              </div>

              <div
                v-if="capturedSelection"
                class="flex items-center gap-2 border-b border-slate-800 bg-indigo-500/5 px-2.5 py-1.5"
              >
                <Icon name="ph:text-select" class="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                <span class="text-[10px] text-indigo-200 truncate flex-1">
                  "{{ capturedSelection.slice(0, 60) }}{{ capturedSelection.length > 60 ? '…' : '' }}"
                </span>
                <button @click="capturedSelection = ''" class="text-slate-500 hover:text-slate-300">
                  <Icon name="ph:x" class="w-3.5 h-3.5" />
                </button>
              </div>

              <div
                class="flex items-end gap-1 px-2 py-2 min-h-[52px]"
              >
                <button
                  type="button"
                  @click="toggleAtMenu"
                  class="mb-0.5 shrink-0 rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-indigo-400"
                  :class="{ 'bg-slate-800 text-indigo-400': showAtMenu }"
                  title="Add context"
                >
                  <Icon name="ph:at" class="w-4 h-4" />
                </button>

                <div class="relative flex-1 min-w-0">
                  <div
                    ref="chatMirrorRef"
                    aria-hidden="true"
                    class="chat-input-layer chat-input-mirror pointer-events-none absolute inset-0 overflow-hidden"
                  >
                    <template
                      v-for="(part, partIndex) in parseChatInputParts(chatInput)"
                      :key="partIndex"
                    >
                      <span v-if="part.type === 'tag'" class="chat-input-tag">{{
                        part.text
                      }}</span>
                      <span v-else class="text-slate-200">{{ part.text }}</span>
                    </template>
                  </div>
                  <textarea
                    ref="chatInputRef"
                    v-model="chatInput"
                    @input="handleChatInput"
                    @scroll="syncChatInputMirror"
                    @keydown.enter.exact.prevent="sendChatMessage"
                    @keydown.escape="showAtMenu = false"
                    rows="2"
                    placeholder="Ask about this paper… type @ for context tags"
                    class="chat-input-layer chat-input-textarea relative w-full min-h-[44px] max-h-28 resize-none border-0 bg-transparent text-transparent caret-slate-200 placeholder:text-slate-600 outline-none custom-scrollbar"
                  ></textarea>
                </div>

                <button
                  v-if="chatLoading"
                  @click="cancelChatGeneration"
                  class="mb-0.5 shrink-0 rounded-lg bg-red-500/15 p-2 text-red-300 transition-colors hover:bg-red-500/25"
                  title="Stop generation"
                >
                  <Icon name="ph:stop-fill" class="w-4 h-4" />
                </button>
                <button
                  v-else
                  @click="sendChatMessage"
                  :disabled="chatLoading || !chatInput.trim() || !selectedProviderHasModels"
                  class="mb-0.5 shrink-0 rounded-lg bg-indigo-600 p-2 text-white transition-colors hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Send"
                >
                  <Icon name="ph:paper-plane-tilt" class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
          </div>
        </div>
      </aside>
    </div>

    <div
      v-if="textSelectionMenu.visible"
      class="pdf-selection-menu fixed z-[100] min-w-40 rounded-md border border-slate-700 bg-slate-900 p-1 shadow-xl"
      :style="{ left: `${textSelectionMenu.x}px`, top: `${textSelectionMenu.y}px` }"
      role="menu"
      aria-label="Selected text actions"
      @contextmenu.prevent
      @pointerdown.prevent.stop
    >
      <button
        type="button"
        class="flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-left text-sm text-slate-200 hover:bg-slate-800 hover:text-white"
        role="menuitem"
        @click="copySelectedPdfText"
      >
        <Icon name="ph:copy" class="h-4 w-4" />
        Copy
      </button>
      <button
        type="button"
        class="flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-left text-sm text-slate-200 hover:bg-slate-800 hover:text-white"
        role="menuitem"
        @click="addSelectedPdfTextToChat"
      >
        <Icon name="ph:chat-circle" class="h-4 w-4" />
        Add to chat
      </button>
      <button
        type="button"
        class="flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-left text-sm text-slate-200 hover:bg-slate-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        role="menuitem"
        :disabled="!textSelectionMenu.highlightData"
        @click="highlightSelectedPdfText"
      >
        <Icon name="ph:highlighter" class="h-4 w-4" />
        Highlight
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-input-layer {
  padding: 0.5rem 0.25rem;
  font-family: inherit;
  font-size: 0.75rem;
  line-height: 1.625;
  letter-spacing: normal;
  white-space: pre-wrap;
  overflow-wrap: break-word;
  word-break: break-word;
}

.chat-input-mirror {
  color: transparent;
}

.chat-input-tag {
  background: rgba(99, 102, 241, 0.28);
  color: rgb(199 210 254);
  border-radius: 0.125rem;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}

.chat-input-tag--sent {
  display: inline-flex;
  align-items: center;
  margin: 0 1px;
  padding: 0.1rem 0.45rem;
  border-radius: 0.375rem;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.16);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.65rem;
  line-height: 1.2rem;
  color: #eef2ff;
  vertical-align: baseline;
}

.chat-input-textarea::placeholder {
  color: rgb(71 85 105);
}

.ai-select {
  background-color: #0f172a;
  color: #cbd5e1;
}

.ai-select option {
  background-color: #0f172a;
  color: #e2e8f0;
}

.icon-btn {
  border-radius: 0.25rem;
  padding: 0.5rem;
  color: #94a3b8;
  transition: all 150ms ease-in-out;
}

.icon-btn:hover {
  background-color: #1e293b;
  color: #f8fafc;
}

.icon-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.tool-btn {
  border-radius: 0.25rem;
  padding: 0.375rem;
  color: #94a3b8;
  transition: all 150ms ease-in-out;
  margin-left: 0.125rem;
  margin-right: 0.125rem;
}

.tool-btn:hover {
  background-color: #334155;
  color: #f8fafc;
}

.active-tool {
  background-color: rgba(99, 102, 241, 0.1);
  color: #818cf8;
}

.active-tool:hover {
  background-color: rgba(99, 102, 241, 0.2);
  color: #c7d2fe;
}

::-webkit-scrollbar {
  width: 14px;
  height: 14px;
}

::-webkit-scrollbar-track {
  background: #0f172a;
  border-left: 1px solid #1e293b;
}

::-webkit-scrollbar-thumb {
  background-color: #334155;
  border: 3px solid #0f172a;
  border-radius: 8px;
}

::-webkit-scrollbar-thumb:hover {
  background-color: #475569;
}

:deep(.textLayer) {
  position: absolute;
  text-align: initial;
  inset: 0;
  overflow: hidden;
  opacity: 1;
}

/* Hide Annotations Logic */
.hide-annotations :deep(.custom-highlight),
.hide-annotations :deep(.sticky-note-icon) {
  display: none !important;
}

:deep(.sticky-note-icon) {
  cursor: grab;
  transition: opacity 120ms ease;
}

:deep(.sticky-note-icon:hover) {
  filter: brightness(1.08)
    drop-shadow(0 4px 3px rgb(0 0 0 / 0.12))
    drop-shadow(0 2px 2px rgb(0 0 0 / 0.1));
}

:deep(.sticky-note-icon:active) {
  cursor: grabbing;
}

:deep(.textLayer span) {
  color: transparent;
  outline: none;
  transform-origin: 0% 0%;
}

:deep(.textLayer ::selection) {
  background: rgba(99, 102, 241, 0.4);
  color: transparent;
}

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

.prose {
  width: 100%;
  overflow-wrap: break-word;
  word-wrap: break-word;
  word-break: break-word;
  line-height: 1.6;
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

/* Chat prose styles */
.chat-prose :deep(p) {
  margin: 0.25rem 0;
  line-height: 1.6;
}

.chat-prose :deep(p:first-child) {
  margin-top: 0;
}

.chat-prose :deep(p:last-child) {
  margin-bottom: 0;
}

.chat-prose :deep(h1),
.chat-prose :deep(h2),
.chat-prose :deep(h3) {
  font-weight: 600;
  color: #c7d2fe;
  margin: 0.5rem 0 0.25rem;
}

.chat-prose :deep(h1) { font-size: 0.9rem; }
.chat-prose :deep(h2) { font-size: 0.85rem; }
.chat-prose :deep(h3) { font-size: 0.8rem; }

.chat-prose :deep(ul),
.chat-prose :deep(ol) {
  margin: 0.25rem 0;
  padding-left: 1.25rem;
}

.chat-prose :deep(li) {
  margin: 0.1rem 0;
}

.chat-prose :deep(strong) {
  color: #f1f5f9;
  font-weight: 600;
}

.chat-prose :deep(em) {
  color: #cbd5e1;
}

.chat-prose :deep(code) {
  background: #1e293b;
  color: #fbbf24;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-family: monospace;
  font-size: 0.75em;
}

.chat-prose :deep(pre) {
  background: #1e293b;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0.5rem 0;
}

.chat-prose :deep(pre code) {
  background: transparent;
  padding: 0;
  color: #94a3b8;
}

.chat-prose :deep(blockquote) {
  border-left: 2px solid #4f46e5;
  padding-left: 0.75rem;
  color: #94a3b8;
  margin: 0.25rem 0;
}

.chat-prose :deep(.katex-display) {
  display: block;
  max-width: 100%;
  margin: 0.5em 0;
  overflow-x: auto;
  overflow-y: hidden;
}

.chat-prose :deep(.katex) {
  font-size: 1em;
}
</style>
