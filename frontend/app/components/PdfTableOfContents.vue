<script setup>
import {
  findActivePdfOutlineItem,
  findPdfOutlinePath,
  getExpandablePdfOutlineIds,
} from "../utils/pdfOutline.js";

const props = defineProps({
  items: { type: Array, default: () => [] },
  currentPage: { type: Number, default: 1 },
  documentId: { type: [String, Number], required: true },
  loading: { type: Boolean, default: false },
  error: { type: String, default: "" },
  totalPages: { type: Number, default: 0 },
});

const emit = defineEmits(["navigate", "items-updated"]);
const {
  public: { apiBaseURL },
} = useRuntimeConfig();
const expandedIds = ref(new Set());
const hasRestoredExpansion = ref(false);
const storageKey = computed(() => `annotateTocExpanded:${props.documentId}`);
const documentState = ref(null);
const serverItems = ref(null);
const isEditing = ref(false);
const draftItems = ref([]);
const actionError = ref("");
const isSaving = ref(false);
const isSubmitting = ref(false);
let pollTimer = null;

const displayedItems = computed(() =>
  isEditing.value
    ? draftItems.value
    : serverItems.value === null
      ? props.items
      : serverItems.value,
);
const tocStatus = computed(() => documentState.value?.toc_status || "not_started");
const isProcessing = computed(() => ["queued", "processing"].includes(tocStatus.value));
const runButtonLabel = computed(() => {
  if (isProcessing.value) return "Scraping…";
  if (tocStatus.value === "failed") return "Retry scrape";
  if (tocStatus.value === "succeeded") return "Re-run scrape";
  return "Run scraper";
});

const activeItem = computed(() =>
  findActivePdfOutlineItem(displayedItems.value, props.currentPage),
);
const activePath = computed(
  () =>
    findPdfOutlinePath(displayedItems.value, activeItem.value?.id) || [],
);
const activePathIds = computed(() => new Set(activePath.value));

function persistExpandedIds() {
  try {
    localStorage.setItem(storageKey.value, JSON.stringify([...expandedIds.value]));
  } catch {
    // Expansion state is optional.
  }
}

function restoreExpandedIds() {
  if (hasRestoredExpansion.value || !displayedItems.value.length) return;
  hasRestoredExpansion.value = true;

  try {
    const stored = JSON.parse(localStorage.getItem(storageKey.value) || "null");
    if (Array.isArray(stored)) {
      expandedIds.value = new Set(stored.filter((id) => typeof id === "string"));
      return;
    }
  } catch {
    // Fall through to a useful first-open default.
  }

  expandedIds.value = new Set(
    displayedItems.value.filter((item) => item.children?.length).map((item) => item.id),
  );
}

function toggleItem(itemId) {
  const next = new Set(expandedIds.value);
  if (next.has(itemId)) next.delete(itemId);
  else next.add(itemId);
  expandedIds.value = next;
  persistExpandedIds();
}

function expandAll() {
  expandedIds.value = new Set(getExpandablePdfOutlineIds(displayedItems.value));
  persistExpandedIds();
}

function collapseAll() {
  expandedIds.value = new Set();
  persistExpandedIds();
}

watch(
  displayedItems,
  () => restoreExpandedIds(),
  { immediate: true },
);

watch(
  activePath,
  (path) => {
    if (path.length < 2) return;
    const next = new Set(expandedIds.value);
    let changed = false;
    for (const id of path.slice(0, -1)) {
      if (!next.has(id)) {
        next.add(id);
        changed = true;
      }
    }
    if (changed) {
      expandedIds.value = next;
      persistExpandedIds();
    }
  },
  { immediate: true },
);

const cloneItems = (items) => JSON.parse(JSON.stringify(items || []));

function findItemLocation(items, itemId) {
  for (let index = 0; index < items.length; index += 1) {
    if (items[index].id === itemId) return { item: items[index], items, index };
    const childLocation = findItemLocation(items[index].children || [], itemId);
    if (childLocation) return childLocation;
  }
  return null;
}

function createDraftItem() {
  return {
    id: `manual-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: "New section",
    page: props.currentPage || 1,
    children: [],
  };
}

function handleEditAction(action) {
  const location = findItemLocation(draftItems.value, action.id);
  if (!location) return;

  if (action.type === "update") {
    location.item[action.field] =
      action.field === "page" ? Number(action.value) : action.value;
  } else if (action.type === "add-child") {
    location.item.children ||= [];
    location.item.children.push(createDraftItem());
    const next = new Set(expandedIds.value);
    next.add(location.item.id);
    expandedIds.value = next;
  } else if (action.type === "delete") {
    location.items.splice(location.index, 1);
  } else if (action.type === "move") {
    const destination = location.index + action.direction;
    if (destination < 0 || destination >= location.items.length) return;
    const [item] = location.items.splice(location.index, 1);
    location.items.splice(destination, 0, item);
  }
}

function beginEditing() {
  actionError.value = "";
  draftItems.value = cloneItems(displayedItems.value);
  if (!draftItems.value.length) draftItems.value.push(createDraftItem());
  isEditing.value = true;
}

function cancelEditing() {
  isEditing.value = false;
  draftItems.value = [];
  actionError.value = "";
}

function addRootItem() {
  draftItems.value.push(createDraftItem());
}

async function saveEdits() {
  if (isSaving.value) return;
  actionError.value = "";
  isSaving.value = true;
  try {
    const document = await $fetch(
      `${apiBaseURL}/documents/${props.documentId}/table-of-contents/`,
      { method: "PUT", body: { toc_data: draftItems.value } },
    );
    documentState.value = document;
    serverItems.value = cloneItems(document.toc_data);
    isEditing.value = false;
    emit("items-updated", cloneItems(document.toc_data));
  } catch (error) {
    actionError.value = error?.data?.error || error?.message || "Could not save the table of contents.";
  } finally {
    isSaving.value = false;
  }
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

async function fetchDocumentState() {
  try {
    const document = await $fetch(
      `${apiBaseURL}/documents/${props.documentId}/table-of-contents/`,
    );
    documentState.value = document;
    if (document.toc_status === "succeeded" || document.toc_data?.length) {
      serverItems.value = cloneItems(document.toc_data);
      emit("items-updated", cloneItems(document.toc_data));
    }
    return document;
  } catch (error) {
    actionError.value = error?.data?.error || "Could not load table of contents status.";
    return null;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    const document = await fetchDocumentState();
    if (!document || !["queued", "processing"].includes(document.toc_status)) {
      stopPolling();
    }
  }, 2000);
}

async function runScraper() {
  if (isProcessing.value || isSubmitting.value) return;
  if (
    tocStatus.value === "succeeded" &&
    displayedItems.value.length &&
    !window.confirm(
      "Re-running the scraper will replace the current table of contents, including manual edits. Continue?",
    )
  ) {
    return;
  }
  actionError.value = "";
  isSubmitting.value = true;
  try {
    const response = await $fetch(
      `${apiBaseURL}/documents/${props.documentId}/table-of-contents/`,
      { method: "POST" },
    );
    documentState.value = response.document;
    startPolling();
  } catch (error) {
    actionError.value = error?.data?.error || error?.message || "Could not run the table of contents scraper.";
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(async () => {
  const document = await fetchDocumentState();
  if (document && ["queued", "processing"].includes(document.toc_status)) startPolling();
});

onUnmounted(stopPolling);
</script>

<template>
  <div class="flex h-full min-h-0 flex-col">
    <div
      v-if="displayedItems.length || isEditing"
      class="flex shrink-0 items-center justify-between border-b border-slate-800 px-3 py-2"
    >
      <div class="min-w-0">
        <p class="text-[10px] text-slate-500">PDF page numbers</p>
        <p v-if="documentState?.toc_source" class="truncate text-[9px] text-slate-600">
          Source: {{ documentState.toc_source === 'manual' ? 'edited' : documentState.toc_source }}
        </p>
      </div>
      <div class="flex items-center gap-1">
        <template v-if="isEditing">
          <button type="button" class="rounded px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-800" @click="addRootItem">Add chapter</button>
          <button type="button" class="rounded px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-800" @click="cancelEditing">Cancel</button>
          <button type="button" class="rounded bg-indigo-600 px-2 py-1 text-[10px] text-white disabled:opacity-50" :disabled="isSaving" @click="saveEdits">
            {{ isSaving ? 'Saving…' : 'Save' }}
          </button>
        </template>
        <button
          v-else
          type="button"
          class="rounded px-2 py-1 text-[10px] text-slate-500 hover:bg-slate-800 hover:text-slate-200"
          @click="beginEditing"
        >
          Edit
        </button>
        <button
          v-if="!isEditing"
          type="button"
          class="rounded px-2 py-1 text-[10px] text-slate-500 hover:bg-slate-800 hover:text-slate-200"
          @click="collapseAll"
        >
          Collapse all
        </button>
        <button
          v-if="!isEditing"
          type="button"
          class="rounded px-2 py-1 text-[10px] text-slate-500 hover:bg-slate-800 hover:text-slate-200"
          @click="expandAll"
        >
          Expand all
        </button>
      </div>
    </div>

    <div class="flex shrink-0 items-center gap-2 border-b border-slate-800 px-3 py-2">
      <span class="min-w-0 flex-1 truncate text-[10px] text-slate-500">
        {{ isProcessing ? 'Reading embedded PDF chapters…' : tocStatus === 'failed' ? 'Last scrape failed' : tocStatus === 'succeeded' ? 'Scraper completed' : 'Scraper has not run' }}
      </span>
      <button
        type="button"
        class="shrink-0 rounded bg-slate-800 px-2 py-1 text-[10px] text-slate-300 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="isProcessing || isSubmitting || isEditing"
        @click="runScraper"
      >
        {{ runButtonLabel }}
      </button>
    </div>

    <div v-if="loading" class="flex flex-1 items-center justify-center gap-2 text-xs text-slate-500">
      <Icon name="svg-spinners:ring-resize" class="h-4 w-4" />
      Reading PDF contents…
    </div>
    <div v-else-if="(error || documentState?.toc_error) && !displayedItems.length" class="m-3 rounded-md border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-300">
      {{ error || documentState?.toc_error }}
    </div>
    <div
      v-else-if="!displayedItems.length"
      class="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center text-slate-600"
    >
      <Icon name="ph:list-dashes" class="h-7 w-7 opacity-60" />
      <p class="text-xs leading-5">No table of contents entries were found. Run the scraper again or add chapters manually.</p>
      <button type="button" class="rounded-md bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700" @click="beginEditing">Add manually</button>
    </div>
    <ul v-else class="min-h-0 flex-1 overflow-y-auto px-1.5 py-2">
      <PdfTocItem
        v-for="(item, index) in displayedItems"
        :key="item.id"
        :item="item"
        :index="index"
        :sibling-count="displayedItems.length"
        :expanded-ids="expandedIds"
        :active-item-id="activeItem?.id || null"
        :active-path-ids="activePathIds"
        :editable="isEditing"
        :max-page="totalPages"
        @toggle="toggleItem"
        @navigate="emit('navigate', $event)"
        @edit-action="handleEditAction"
      />
    </ul>
    <p v-if="actionError" class="shrink-0 border-t border-red-500/20 px-3 py-2 text-[10px] text-red-300">
      {{ actionError }}
    </p>
  </div>
</template>
