<script setup>
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

const pageContainerRefs = ref([]);
const canvasRefs = ref([]);
const textLayerRefs = ref([]);
const mainScrollContainer = ref(null);

// State
const isSidebarOpen = ref(true);
const sidebarWidth = ref(320);
const currentPage = ref(1);
const totalPages = ref(0);
const zoomLevel = ref(100);
const isAnnotationsHidden = ref(false);
const isColorPickerOpen = ref(false);
const selectedColor = ref("#ef4444");
const isResizing = ref(false);
const isManualScrolling = ref(false);

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
  if (zoomLevel.value < 300) zoomLevel.value += 10;
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

      const textContent = await page.getTextContent();
      const textLayer = new pdfjsLib.TextLayer({
        textContentSource: textContent,
        container: textLayerDiv,
        viewport: viewport,
        textDivs: [],
      });
      await textLayer.render();
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

    await nextTick();
    await renderAllPages();
    setupIntersectionObserver();
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

    try {
      const annotModule = await import("annotpdf");
      AnnotationFactory = annotModule.AnnotationFactory;
    } catch (e) {
      console.warn("Could not load annotpdf", e);
    }

    await fetchPaper();
  } catch (err) {
    console.error("Failed to load PDF libraries:", err);
    error.value = "Failed to initialize PDF viewer.";
    loading.value = false;
  }
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
        <button class="icon-btn" title="Search Document">
          <Icon name="ph:magnifying-glass" class="h-5 w-5" />
        </button>

        <div class="h-5 w-px bg-slate-700/50"></div>

        <div class="flex items-center gap-2">
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
        class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden md:flex"
      >
        <div
          class="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/50 p-1 shadow-sm"
        >
          <button class="tool-btn" title="Undo">
            <Icon name="ph:arrow-u-up-left" class="h-5 w-5" />
          </button>
          <button class="tool-btn" title="Redo">
            <Icon name="ph:arrow-u-up-right" class="h-5 w-5" />
          </button>

          <div class="mx-1 h-5 w-px bg-slate-600/50"></div>

          <button class="tool-btn active-tool" title="Select Cursor">
            <Icon name="ph:cursor" class="h-5 w-5" />
          </button>
          <button class="tool-btn" title="Highlight Text">
            <Icon name="ph:highlighter" class="h-5 w-5" />
          </button>
          <button class="tool-btn" title="Draw">
            <Icon name="ph:pencil-simple" class="h-5 w-5" />
          </button>
          <button class="tool-btn" title="Sticky Note">
            <Icon name="ph:note" class="h-5 w-5" />
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
              class="absolute top-full left-1/2 mt-2 -translate-x-1/2 flex flex-col gap-2 rounded-lg border border-slate-700 bg-slate-800 p-2 shadow-xl z-50"
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
          class="flex items-center rounded-md border border-slate-700 bg-slate-800"
        >
          <button
            class="p-1.5 hover:bg-slate-700 hover:text-white transition-colors"
            @click="zoomOut"
          >
            <Icon name="ph:minus" class="h-3.5 w-3.5" />
          </button>
          <span
            class="w-12 text-center text-xs font-medium text-slate-300 select-none"
            >{{ zoomLevel }}%</span
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
        class="flex-1 overflow-y-auto overflow-x-hidden bg-slate-950 p-8 flex flex-col items-center gap-2"
      >
        <div
          v-if="loading"
          class="text-slate-500 flex flex-col items-center mt-20"
        >
          <Icon name="ph:spinner" class="h-8 w-8 animate-spin mb-2" />
          <p>Loading PDF...</p>
        </div>

        <div
          v-else-if="error"
          class="text-red-400 flex flex-col items-center mt-20"
        >
          <Icon name="ph:warning" class="h-8 w-8 mb-2" />
          <p>{{ error }}</p>
        </div>

        <template v-else>
          <div
            v-for="page in totalPages"
            :key="page"
            class="flex flex-col items-center"
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
          class="h-12 border-b border-slate-800 flex items-center px-2 shrink-0"
        >
          <div
            class="flex-1 text-center py-2 text-sm font-medium text-slate-200 border-b-2 border-indigo-500"
          >
            Notes
          </div>
          <div
            class="flex-1 text-center py-2 text-sm font-medium text-slate-500 hover:text-slate-300 cursor-pointer"
          >
            Info
          </div>
        </div>

        <div
          class="flex-1 p-6 flex flex-col items-center justify-center text-slate-600"
        >
          <span class="text-sm italic opacity-50">No content available</span>
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
  line-height: 1;
  text-size-adjust: none;
  transform-origin: 0% 0%;
  opacity: 1;
}

:deep(.textLayer span) {
  color: transparent;
  position: absolute;
  white-space: pre;
  cursor: text;
  transform-origin: 0% 0%;

  box-sizing: content-box;
  letter-spacing: normal;
  word-spacing: normal;
  line-height: 1;
  margin: 0;
  padding: 0;
  border: none;
  outline: none;
}

:deep(.textLayer ::selection) {
  background: rgba(99, 102, 241, 0.4);
  color: transparent;
}
</style>
