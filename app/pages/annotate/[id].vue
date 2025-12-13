<script setup>
import { select } from "#build/ui";
import "pdfjs-dist/web/pdf_viewer.css";

const route = useRoute();
const id = route.params.id;

const loading = ref(true);
const error = ref(null);

let pdfjsLib = null;
let AnnotationFactory = null;
let TextLayerClass = null;
let pdfDoc = null;
let pdfBytes = null;
let factory = null;
const savedHighlights = ref([]);
const stickyNoteData = ref([]);
let saveNotepadDebounce = null;
const notepadData = ref("");

const pageContainerRefs = ref([]);
const canvasRefs = ref([]);
const textLayerRefs = ref([]);
const mainScrollContainer = ref(null);

// General State
const isSidebarOpen = ref(true);
const sidebarWidth = ref(320);
const currentPage = ref(1);
const totalPages = ref(0);
const zoomLevel = ref(100);
const isAnnotationsHidden = ref(false);
const isColorPickerOpen = ref(false);
const selectedColor = ref("#f59e0b");
const isResizing = ref(false);
const isManualScrolling = ref(false);

async function fetchAnnotations() {
  try {
    const data = await $fetch(`/api/annotations/${id}/`, { method: "GET" });
    if (data) {
      if (data.highlight_data) savedHighlights.value = data.highlight_data;
      if (data.notepad) notepadData.value = data.notepad;
      if (data.sticky_note_data) stickyNoteData.value = data.sticky_note_data;
    }
  } catch (e) {
    console.warn("No existing annotations found or failed to fetch", e);
  }
}

const handleTextSelection = async () => {
  if (activeTool.value !== "highlighter") return;

  const selection = window.getSelection();
  if (
    !selection ||
    selection.rangeCount === 0 ||
    selection.toString().trim() === ""
  )
    return;

  const range = selection.getRangeAt(0);
  const selectedText = selection.toString();

  let container = range.commonAncestorContainer;
  while (container && !container.classList?.contains("textLayer")) {
    container = container.parentNode;
  }

  if (!container) return;

  const pageIndex = parseInt(container.getAttribute("data-page-number"));

  const pageRect = container.getBoundingClientRect();
  const rawRects = range.getClientRects();

  const highlightRects = [];

  const scale = zoomLevel.value / 100;

  for (const rect of rawRects) {
    highlightRects.push({
      x: (rect.left - pageRect.left) / scale,
      y: (rect.top - pageRect.top) / scale,
      width: rect.width / scale,
      height: rect.height / scale,
    });
  }

  const newHighlight = {
    id: crypto.randomUUID(),
    page: pageIndex,
    text: selectedText,
    color: selectedColor.value,
    rects: highlightRects,
  };

  savedHighlights.value.push(newHighlight);
  renderHighlight(newHighlight, container);
  selection.removeAllRanges();

  await saveHighlightToBackend();
};

const renderHighlight = (highlight, textLayerElement) => {
  if (!textLayerElement) {
    textLayerElement = textLayerRefs.value[highlight.page - 1];
  }
  if (!textLayerElement) return;

  highlight.rects.forEach((rect) => {
    const div = document.createElement("div");
    div.classList.add("custom-highlight");
    div.dataset.id = highlight.id;

    // Style of highlight
    div.style.position = "absolute";
    div.style.backgroundColor = highlight.color;
    div.style.pointerEvents = "none";
    div.style.mixBlendMode = "darken";

    div.style.left = `calc(${rect.x}px * var(--scale-factor))`;
    div.style.top = `calc(${rect.y}px * var(--scale-factor))`;
    div.style.width = `calc(${rect.width}px * var(--scale-factor))`;
    div.style.height = `calc(${rect.height}px * var(--scale-factor))`;

    textLayerElement.appendChild(div);
  });
};

// Saving to backend
async function saveHighlightToBackend() {
  try {
    await $fetch("/api/annotations/", {
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

// Sidebar stat
const sidebarActiveTab = ref("stickyNotes");
function changeSidebarTab(tabName) {
  sidebarActiveTab.value = tabName;
}

// Sidebar functions
// Notepad
watch(notepadData, () => {
  if (saveNotepadDebounce) clearTimeout(saveNotepadDebounce);

  // prevents server overload, 3s debounce
  saveNotepadDebounce = setTimeout(() => {
    saveNotepadToBackend();
  }, 3000);
});

async function saveNotepadToBackend() {
  try {
    await fetch("/api/annotations/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        document: id,
        highlight_data: savedHighlights.value,
        notepad: notepadData.value,
        sticky_note_data: stickyNoteData.value,
      }),
    });
  } catch (e) {
    console.error("Failed to save notepad data", e);
  }
}

// Sticky Notes
async function saveStickyNoteToBackend() {
  try {
    await fetch("/api/annotations/", {
      method: "POST",
      body: {
        document: id,
        notepad: notepadData.value,
      },
    });
  } catch (e) {
    console.error("Failed to save notepad data", e);
  }
}

const selectColor = (color) => {
  selectedColor.value = color;
};

// Top toolbar state
const activeTool = ref("cursor");
function changeActiveTool(newToolButton) {
  activeTool.value = newToolButton;
  console.log("Active tool changed to:", newToolButton);
}

// For border transition
const sliderStyle = computed(() => {
  if (sidebarActiveTab.value === "stickyNotes") {
    return {
      left: "0%",
      width: "50%",
    };
  } else if (sidebarActiveTab.value === "notepad") {
    return {
      left: "50%",
      width: "50%",
    };
  }
  return { left: "0%", width: "50%" };
});

const colors = [
  "#ef4444",
  "#f59e0b",
  "#10b981",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
];

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
  if (newWidth >= 200 && newWidth <= window.innerWidth * 0.5) {
    sidebarWidth.value = newWidth;
  }
};

const stopResize = () => {
  isResizing.value = false;
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  window.removeEventListener("mousemove", handleResize);
  window.removeEventListener("mouseup", stopResize);
};

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value;
};

const zoomIn = () => {
  if (zoomLevel.value < 500) zoomLevel.value += 10;
};
const zoomOut = () => {
  if (zoomLevel.value > 50) zoomLevel.value -= 10;
};

const scrollToPage = (pageNumber) => {
  if (pageNumber < 1 || pageNumber > totalPages.value) return;
  const el = pageContainerRefs.value[pageNumber - 1];
  if (el) {
    isManualScrolling.value = true;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    currentPage.value = pageNumber;
    setTimeout(() => {
      isManualScrolling.value = false;
    }, 1000);
  }
};

const changePage = (diff) => {
  const newPage = currentPage.value + diff;
  scrollToPage(newPage);
};

async function renderPage(pageNum) {
  if (!pdfDoc) return;

  const canvas = canvasRefs.value[pageNum - 1];
  const textLayerDiv = textLayerRefs.value[pageNum - 1];

  if (!canvas) return;

  try {
    const page = await pdfDoc.getPage(pageNum);
    const scale = zoomLevel.value / 100;
    const viewport = page.getViewport({ scale });

    const outputScale = window.devicePixelRatio || 1;

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
    };

    await page.render(renderContext).promise;

    if (textLayerDiv) {
      textLayerDiv.innerHTML = "";

      textLayerDiv.style.width = cssWidth;
      textLayerDiv.style.height = cssHeight;

      textLayerDiv.style.setProperty("--scale-factor", scale);
      textLayerDiv.style.setProperty("--total-scale-factor", scale);
      textLayerDiv.setAttribute("data-page-number", pageNum);

      const textContent = await page.getTextContent();

      const textLayer = new pdfjsLib.TextLayer({
        textContentSource: textContent,
        container: textLayerDiv,
        viewport: viewport,
      });
      await textLayer.render();

      const pageHighlights = savedHighlights.value.filter(
        (h) => h.page === pageNum
      );
      pageHighlights.forEach((h) => renderHighlight(h, textLayerDiv));

      if (searchQuery.value.trim() !== "") {
        const query = searchQuery.value.trim();
        // escape special regex characters in the query just in case
        const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const regex = new RegExp(`(${escapedQuery})`, "gi");

        const spans = textLayerDiv.querySelectorAll("span");

        spans.forEach((span) => {
          if (regex.test(span.textContent)) {
            span.innerHTML = span.textContent.replace(
              regex,
              `<mark class="bg-yellow-500/40 text-transparent rounded-sm">$1</mark>`
            );
          }
        });
      }
    }
  } catch (err) {
    console.error(`Error rendering page ${pageNum}:`, err);
  }
}
async function renderAllPages() {
  if (!pdfDoc) return;
  const promises = [];
  for (let i = 1; i <= totalPages.value; i++) {
    promises.push(renderPage(i));
  }
  await Promise.all(promises);
}

async function loadPdf(data) {
  try {
    const loadingTask = pdfjsLib.getDocument(data);
    pdfDoc = await loadingTask.promise;
    totalPages.value = pdfDoc.numPages;

    await pdfDoc.getDownloadInfo();

    await nextTick();
    await renderAllPages();
    setupIntersectionObserver();
    extractAllText();
  } catch (err) {
    console.error("Error loading PDF doc:", err);
    error.value = "Failed to parse PDF document.";
  }
}

let observer = null;

function setupIntersectionObserver() {
  if (observer) observer.disconnect();

  const options = {
    root: mainScrollContainer.value,
    rootMargin: "-20% 0px -60% 0px",
    threshold: 0,
  };

  observer = new IntersectionObserver((entries) => {
    if (isManualScrolling.value) return;

    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const index = pageContainerRefs.value.indexOf(entry.target);
        if (index !== -1) {
          currentPage.value = index + 1;
        }
      }
    });
  }, options);

  pageContainerRefs.value.forEach((el) => {
    if (el) observer.observe(el);
  });
}

async function fetchPaper() {
  loading.value = true;
  error.value = null;
  try {
    const res = await fetch(`/api/get-paper/${id}/`, { method: "GET" });
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
  } catch (err) {
    console.error("Error fetching paper:", err);
    error.value = err.message;
    loading.value = false;
  }
}

watch(zoomLevel, async () => {
  await nextTick();
  await renderAllPages();
});

onMounted(async () => {
  try {
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

    document.addEventListener("mouseup", handleTextSelection);
  } catch (err) {
    console.error("Failed to load PDF libraries:", err);
    error.value = "Failed to initialize PDF viewer.";
    loading.value = false;
  }
});

onUnmounted(() => {
  document.removeEventListener("mouseup", handleTextSelection);
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
    renderAllPages();
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

  renderAllPages();
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
  }, 300); // 300ms debounce
});
</script>

<template>
  <div
    class="flex h-screen w-full flex-col overflow-hidden bg-slate-950 text-slate-300 font-sans selection:bg-indigo-500/30"
  >
    <header
      class="relative flex h-16 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900 px-4 shadow-sm z-20"
    >
      <div class="flex items-center gap-4">
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
              v-model="currentPage"
              @change="scrollToPage(currentPage)"
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
        class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-30 ml-4"
      >
        <div
          class="flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-800/50 p-1 shadow-sm"
        >
          <button class="tool-btn" title="Undo">
            <Icon name="ph:arrow-u-up-left" class="h-5 w-5" />
          </button>
          <button class="tool-btn" title="Redo">
            <Icon name="ph:arrow-u-up-right" class="h-5 w-5" />
          </button>

          <div class="mx-1 h-5 w-px bg-slate-600/50"></div>

          <button
            id="cursor"
            @click="changeActiveTool('cursor')"
            class="tool-btn"
            :class="{ 'active-tool': activeTool === 'cursor' }"
            title="Select Cursor"
          >
            <Icon name="ph:cursor" class="text-[16px]" />
          </button>
          <button
            id="highlighter"
            @click="changeActiveTool('highlighter')"
            :class="{ 'active-tool': activeTool === 'highlighter' }"
            class="tool-btn"
            title="Highlight Text"
          >
            <Icon name="ph:highlighter" class="text-[16px]" />
          </button>

          <button
            id="stickyNote"
            @click="changeActiveTool('stickyNote')"
            :class="{ 'active-tool': activeTool === 'stickyNote' }"
            class="tool-btn"
            title="Sticky Note"
          >
            <Icon name="ph:note" class="text-[16px]" />
          </button>
          <button
            id="deleteAnnotation"
            @click="changeActiveTool('deleteAnnotation')"
            class="tool-btn"
            :class="{ 'active-tool': activeTool === 'deleteAnnotation' }"
            title="Delete Annotation"
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
              class="text-[16px]"
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
            v-model.number="zoomLevel"
            min="50"
            max="500"
            aria-label="Zoom Level"
            class="w-7 text-center text-[14px] font-medium text-slate-300 select-none bg-transparent outline-none border-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
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

    <div class="flex flex-1 overflow-hidden relative">
      <main
        ref="mainScrollContainer"
        class="flex-1 overflow-auto bg-slate-950 p-8 flex flex-col items-start gap-4"
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
            >
              <canvas
                :ref="(el) => (canvasRefs[page - 1] = el)"
                class="block"
              ></canvas>
              <div
                :ref="(el) => (textLayerRefs[page - 1] = el)"
                class="textLayer absolute inset-0 mix-blend-multiply opacity-50"
              ></div>
            </div>
          </div>

          <div class="h-36 w-full shrink-0"></div>
        </template>
      </main>

      <div
        v-if="isSidebarOpen"
        class="w-1 cursor-col-resize hover:bg-indigo-500/50 active:bg-indigo-500 transition-colors bg-slate-800 z-30"
        @mousedown.prevent="startResize"
      ></div>

      <aside
        class="border-l border-slate-800 bg-slate-900 transition-none flex flex-col shrink-0"
        :style="{ width: isSidebarOpen ? `${sidebarWidth}px` : '0px' }"
        :class="{ 'border-none opacity-0 overflow-hidden': !isSidebarOpen }"
      >
        <div
          class="relative h-12 border-b border-slate-800 flex items-center px-2 shrink-0"
        >
          <div
            class="absolute bottom-0 h-0.5 bg-indigo-500 transition-all duration-300 ease-in-out"
            :style="sliderStyle"
          ></div>

          <div
            @click="changeSidebarTab('stickyNotes')"
            class="flex-1 text-center py-2 text-sm font-medium transition-colors z-10"
            :class="{
              'text-slate-200': sidebarActiveTab === 'stickyNotes',
              'text-slate-500 hover:text-slate-300 cursor-pointer':
                sidebarActiveTab !== 'stickyNotes',
            }"
          >
            Sticky Notes
          </div>
          <div
            @click="changeSidebarTab('notepad')"
            class="flex-1 text-center py-2 text-sm font-medium transition-colors z-10"
            :class="{
              'text-slate-200': sidebarActiveTab === 'notepad',
              'text-slate-500 hover:text-slate-300 cursor-pointer':
                sidebarActiveTab !== 'notepad',
            }"
          >
            Notepad
          </div>
        </div>

        <div
          v-show="sidebarActiveTab === 'stickyNotes'"
          class="flex-1 p-6 flex flex-col items-center justify-center text-slate-600"
        >
          <span class="text-sm italic opacity-50">Sticky Notes content</span>
        </div>
        <div
          v-show="sidebarActiveTab === 'notepad'"
          class="flex-1 p-4 overflow-y-auto"
        >
          <textarea
            v-model="notepadData"
            placeholder="Start typing your notes here..."
            class="w-full h-full bg-slate-800 text-slate-200 p-3 rounded-lg border border-slate-700 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm resize-none transition-colors"
          ></textarea>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
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

:deep(.textLayer span) {
  color: transparent;
  outline: none;
  transform-origin: 0% 0%;
}

:deep(.textLayer ::selection) {
  background: rgba(99, 102, 241, 0.4);
  color: transparent;
}
</style>
