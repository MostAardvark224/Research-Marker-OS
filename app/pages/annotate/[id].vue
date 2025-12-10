<template>
  <div
    class="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-gray-100"
  >
    <div
      class="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-lg border-b border-gray-200 shadow-sm"
    >
      <div class="max-w-7xl mx-auto px-6 py-4">
        <div class="flex items-center justify-between gap-4">
          <div class="flex items-center gap-3">
            <div class="flex bg-gray-100 rounded-xl p-1.5 shadow-inner">
              <button
                @click="currentTool = 'text'"
                :class="[
                  'px-5 py-2.5 rounded-lg font-semibold transition-all duration-200 flex items-center gap-2',
                  currentTool === 'text'
                    ? 'bg-white text-blue-600 shadow-md scale-105'
                    : 'text-gray-600 hover:text-gray-900',
                ]"
              >
                <span class="text-lg">📝</span>
                <span class="text-sm">Note</span>
              </button>
              <button
                @click="currentTool = 'highlight'"
                :class="[
                  'px-5 py-2.5 rounded-lg font-semibold transition-all duration-200 flex items-center gap-2',
                  currentTool === 'highlight'
                    ? 'bg-white text-yellow-600 shadow-md scale-105'
                    : 'text-gray-600 hover:text-gray-900',
                ]"
              >
                <span class="text-lg">🖍️</span>
                <span class="text-sm">Highlight</span>
              </button>
              <button
                @click="currentTool = 'draw'"
                :class="[
                  'px-5 py-2.5 rounded-lg font-semibold transition-all duration-200 flex items-center gap-2',
                  currentTool === 'draw'
                    ? 'bg-white text-purple-600 shadow-md scale-105'
                    : 'text-gray-600 hover:text-gray-900',
                ]"
              >
                <span class="text-lg">✏️</span>
                <span class="text-sm">Draw</span>
              </button>
            </div>

            <!-- Color Picker -->
            <div
              v-if="currentTool !== 'none'"
              class="flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm"
            >
              <span class="text-xs font-medium text-gray-600">Color:</span>
              <div class="flex gap-1.5">
                <button
                  v-for="color in colors"
                  :key="color.name"
                  @click="selectedColor = color"
                  :class="[
                    'w-7 h-7 rounded-full border-2 transition-all duration-200',
                    selectedColor.name === color.name
                      ? 'border-gray-900 scale-110 shadow-md'
                      : 'border-transparent hover:scale-105',
                  ]"
                  :style="{ backgroundColor: color.hex }"
                  :title="color.name"
                ></button>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-3">
            <div
              v-if="pdfDoc"
              class="flex items-center gap-2 bg-white rounded-lg px-4 py-2 shadow-sm"
            >
              <span class="text-sm font-medium text-gray-700">
                Total Pages: {{ totalPages }}
              </span>
            </div>

            <!-- Zoom Controls -->
            <div
              class="flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm"
            >
              <button
                @click="changeZoom(-0.25)"
                :disabled="scale <= 0.5"
                class="text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                title="Zoom Out"
              >
                <svg
                  class="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7"
                  />
                </svg>
              </button>
              <span
                class="text-sm font-medium text-gray-700 min-w-[50px] text-center"
              >
                {{ Math.round(scale * 100) }}%
              </span>
              <button
                @click="changeZoom(0.25)"
                :disabled="scale >= 3"
                class="text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                title="Zoom In"
              >
                <svg
                  class="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7"
                  />
                </svg>
              </button>
            </div>

            <!-- Download Button -->
            <button
              @click="downloadPdf"
              :disabled="!factory"
              class="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg font-semibold"
            >
              <svg
                class="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
              <span>Download</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content Area -->
    <div class="pt-28 pb-12 px-6">
      <div class="max-w-7xl mx-auto">
        <!-- Loading State -->
        <div
          v-if="loading"
          class="flex flex-col items-center justify-center py-20 gap-4"
        >
          <div class="relative">
            <div
              class="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"
            ></div>
          </div>
          <p class="text-gray-600 font-medium">Loading PDF...</p>
        </div>

        <!-- Error State -->
        <div
          v-else-if="error"
          class="flex flex-col items-center justify-center py-20 gap-4"
        >
          <div
            class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center"
          >
            <svg
              class="w-8 h-8 text-red-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </div>
          <p class="text-gray-800 font-semibold text-lg">Failed to load PDF</p>
          <p class="text-gray-600">{{ error }}</p>
          <button
            @click="fetchPaper"
            class="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Try Again
          </button>
        </div>

        <!-- PDF Canvas LOOP -->
        <div v-else class="flex flex-col items-center gap-8">
          <div
            v-for="pageNum in totalPages"
            :key="pageNum"
            class="relative group"
          >
            <!-- Canvas Container -->
            <div
              class="bg-white rounded-xl shadow-2xl overflow-hidden border border-gray-200"
            >
              <canvas
                :ref="(el) => setCanvasRef(el, pageNum)"
                @click="(e) => handleCanvasClick(e, pageNum)"
                @mousedown="(e) => handleMouseDown(e, pageNum)"
                @mousemove="(e) => handleMouseMove(e, pageNum)"
                @mouseup="(e) => handleMouseUp(e, pageNum)"
                @mouseleave="(e) => handleMouseUp(e, pageNum)"
                :class="[
                  'block',
                  currentTool === 'draw'
                    ? 'cursor-crosshair'
                    : 'cursor-pointer',
                ]"
              ></canvas>
            </div>

            <!-- Page Number Indicator -->
            <div
              class="absolute top-4 left-4 bg-gray-900/10 backdrop-blur-sm rounded px-2 py-1 pointer-events-none"
            >
              <span class="text-xs font-bold text-gray-500"
                >Page {{ pageNum }}</span
              >
            </div>
          </div>

          <!-- Annotation Counter -->
          <div
            v-if="annotationCount > 0"
            class="fixed bottom-8 right-8 bg-white/90 backdrop-blur-sm rounded-lg px-4 py-2 shadow-lg border border-gray-200 z-40"
          >
            <p class="text-sm font-semibold text-gray-700">
              {{ annotationCount }} annotation{{
                annotationCount !== 1 ? "s" : ""
              }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted, nextTick } from "vue";
import { useRoute } from "vue-router";
import "pdfjs-dist/web/pdf_viewer.css";

const route = useRoute();
const id = route.params.id;

// Holds references to all canvas elements
const canvasRefs = ref({});

const loading = ref(true);
const error = ref(null);
const currentTool = ref("text");

// Dynamically loaded libraries
let pdfjsLib = null;
let AnnotationFactory = null;

let pdfDoc = null;
let pdfBytes = null;
let factory = null;

const scale = ref(1.5);
const totalPages = ref(0);
const annotationCount = ref(0);

// Drawing state
const isDrawing = ref(false);
const drawingPath = ref([]);
const activeDrawingPage = ref(null);

const colors = [
  { name: "red", hex: "#EF4444" },
  { name: "yellow", hex: "#FBBF24" },
  { name: "green", hex: "#10B981" },
  { name: "blue", hex: "#3B82F6" },
  { name: "purple", hex: "#8B5CF6" },
  { name: "pink", hex: "#EC4899" },
];

const selectedColor = ref(colors[0]);

onMounted(async () => {
  try {
    const pdfjsModule = await import("pdfjs-dist");
    pdfjsLib = pdfjsModule;

    const workerModule = await import("pdfjs-dist/build/pdf.worker.mjs?url");
    pdfjsLib.GlobalWorkerOptions.workerSrc = workerModule.default;

    const annotModule = await import("annotpdf");
    AnnotationFactory = annotModule.AnnotationFactory;

    await fetchPaper();
  } catch (err) {
    console.error("Failed to load PDF libraries:", err);
    error.value = "Failed to initialize PDF viewer.";
    loading.value = false;
  }
});

// Helper to store refs in the map
const setCanvasRef = (el, pageNum) => {
  if (el) {
    canvasRefs.value[pageNum] = el;
  }
};

async function fetchPaper() {
  loading.value = true;
  error.value = null;
  try {
    const res = await fetch(`/api/get-paper/${id}/`, { method: "GET" });
    if (!res.ok) throw new Error("Failed to fetch PDF from server");

    const blob = await res.blob();
    const arrayBuffer = await blob.arrayBuffer();

    pdfBytes = new Uint8Array(arrayBuffer);
    factory = new AnnotationFactory(pdfBytes);

    // Stop loading here to allow DOM to render (v-else block)
    loading.value = false;

    await nextTick();

    await loadPdf(pdfBytes);
  } catch (err) {
    console.error("Error fetching paper:", err);
    error.value = err.message;
    loading.value = false;
  }
}

async function loadPdf(data) {
  const dataCopy = data.slice();
  const loadingTask = pdfjsLib.getDocument({ data: dataCopy });
  pdfDoc = await loadingTask.promise;

  // Update total pages so v-for generates the divs
  totalPages.value = pdfDoc.numPages;

  // Wait for Vue to render the v-for elements
  await nextTick();

  // Render every page
  await renderAllPages();
}

async function renderAllPages() {
  if (!pdfDoc) return;

  // Loop through all pages and render them
  for (let i = 1; i <= totalPages.value; i++) {
    await renderPage(i);
  }
}

async function renderPage(pageNum) {
  const canvas = canvasRefs.value[pageNum];
  if (!canvas) return;

  const page = await pdfDoc.getPage(pageNum);
  const viewport = page.getViewport({ scale: scale.value });
  const context = canvas.getContext("2d");

  canvas.height = viewport.height;
  canvas.width = viewport.width;

  const renderContext = {
    canvasContext: context,
    viewport: viewport,
  };

  await page.render(renderContext).promise;
}

function changeZoom(delta) {
  const newScale = scale.value + delta;
  if (newScale >= 0.5 && newScale <= 3) {
    scale.value = newScale;
    // Re-render all pages when zoom changes
    renderAllPages();
  }
}

// Events
async function handleCanvasClick(event, pageNum) {
  if (!factory || currentTool.value === "draw") return;

  const canvas = canvasRefs.value[pageNum];
  const { x, y } = getCanvasCoordinates(event, canvas);

  // Page index is zero-based, pdf.js is one-based
  const pageIndex = pageNum - 1;

  if (currentTool.value === "text") {
    factory.createFreeTextAnnotation({
      page: pageIndex,
      rect: [x, y - 20, x + 150, y],
      contents: "New Note",
      author: "User",
      color: selectedColor.value,
      fontSize: 12,
    });
  } else if (currentTool.value === "highlight") {
    factory.createHighlightAnnotation({
      page: pageIndex,
      rect: [x, y - 15, x + 100, y],
      contents: "Highlight",
      author: "User",
      color: selectedColor.value,
    });
  }

  annotationCount.value++;
  await updatePdfView();
}

function handleMouseDown(event, pageNum) {
  if (currentTool.value !== "draw") return;
  isDrawing.value = true;
  activeDrawingPage.value = pageNum; // Lock drawing to this page

  const canvas = canvasRefs.value[pageNum];
  const { x, y } = getCanvasCoordinates(event, canvas);
  drawingPath.value = [{ x, y }];
}

function handleMouseMove(event, pageNum) {
  if (
    !isDrawing.value ||
    currentTool.value !== "draw" ||
    activeDrawingPage.value !== pageNum
  )
    return;

  const canvas = canvasRefs.value[pageNum];
  const { x, y } = getCanvasCoordinates(event, canvas);
  drawingPath.value.push({ x, y });

  // Draw temporary preview
  const ctx = canvas.getContext("2d");
  ctx.strokeStyle = selectedColor.value.hex;
  ctx.lineWidth = 2 * scale.value;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  if (drawingPath.value.length > 1) {
    const prev = drawingPath.value[drawingPath.value.length - 2];
    const curr = drawingPath.value[drawingPath.value.length - 1];
    ctx.beginPath();
    ctx.moveTo(prev.x * scale.value, canvas.height - prev.y * scale.value);
    ctx.lineTo(curr.x * scale.value, canvas.height - curr.y * scale.value);
    ctx.stroke();
  }
}

async function handleMouseUp(event, pageNum) {
  if (
    !isDrawing.value ||
    currentTool.value !== "draw" ||
    activeDrawingPage.value !== pageNum ||
    drawingPath.value.length < 2
  ) {
    isDrawing.value = false;
    activeDrawingPage.value = null;
    drawingPath.value = [];
    return;
  }

  const pathPoints = drawingPath.value.map((p) => [p.x, p.y]);
  const pageIndex = pageNum - 1;

  factory.createInkAnnotation({
    page: pageIndex,
    inkList: [pathPoints],
    color: selectedColor.value,
    borderWidth: 2,
  });

  isDrawing.value = false;
  activeDrawingPage.value = null;
  drawingPath.value = [];
  annotationCount.value++;
  await updatePdfView();
}

function getCanvasCoordinates(event, canvasElement) {
  const rect = canvasElement.getBoundingClientRect();
  const domX = event.clientX - rect.left;
  const domY = event.clientY - rect.top;
  const x = domX / scale.value;
  const y = (canvasElement.height - domY) / scale.value;
  return { x, y };
}

async function updatePdfView() {
  const newPdfData = factory.write();
  pdfBytes = newPdfData;
  factory = new AnnotationFactory(pdfBytes);
  await loadPdf(pdfBytes);
}

function downloadPdf() {
  if (factory) {
    const timestamp = new Date().toISOString().slice(0, 10);
    factory.download(`annotated_paper_${timestamp}.pdf`);
  }
}
</script>
