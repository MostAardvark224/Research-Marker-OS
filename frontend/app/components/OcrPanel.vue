<script setup>
const props = defineProps({
  documentId: {
    type: [String, Number],
    required: true,
  },
});

const emit = defineEmits(["ocr-completed"]);

const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const {
  ocrProviders,
  ocrProvidersLoading,
  ocrProvidersError,
  localProviders,
  byokProviders,
  fetchOcrProviders,
  getProviderById,
  isProviderAvailable,
} = useOcrProviders();

const ocrMode = ref("local");
const selectedByokProvider = ref("mistral");
const documentState = ref(null);
const actionError = ref("");
const isSubmitting = ref(false);
let pollTimer = null;

const activeProviderId = computed(() =>
  ocrMode.value === "local" ? "paddleocr" : selectedByokProvider.value
);

const activeProvider = computed(() => getProviderById(activeProviderId.value));

const selectedProviderUnavailable = computed(
  () => ocrMode.value === "byok" && !isProviderAvailable(activeProviderId.value)
);

const isProcessing = computed(() =>
  ["queued", "processing"].includes(documentState.value?.ocr_status)
);

const statusMeta = computed(() => {
  const status = documentState.value?.ocr_status || "not_started";
  const map = {
    not_started: {
      label: "Not started",
      class: "border-slate-600/50 bg-slate-800/60 text-slate-300",
      icon: "ph:circle-dashed",
    },
    queued: {
      label: "Queued",
      class: "border-amber-500/30 bg-amber-500/10 text-amber-200",
      icon: "ph:hourglass-medium",
    },
    processing: {
      label: "Processing",
      class: "border-indigo-500/30 bg-indigo-500/10 text-indigo-200",
      icon: "ph:spinner",
    },
    succeeded: {
      label: "Succeeded",
      class: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
      icon: "ph:check-circle",
    },
    failed: {
      label: "Failed",
      class: "border-red-500/30 bg-red-500/10 text-red-200",
      icon: "ph:warning-circle",
    },
  };
  return map[status] || map.not_started;
});

const runButtonLabel = computed(() => {
  if (isProcessing.value) return "OCR in progress…";
  if (documentState.value?.ocr_status === "succeeded") return "Re-run OCR";
  if (documentState.value?.ocr_status === "failed") return "Retry OCR";
  return "Run OCR";
});

function syncModeFromDocument(doc) {
  if (!doc?.ocr_provider) return;
  const provider = getProviderById(doc.ocr_provider);
  if (!provider) return;
  ocrMode.value = provider.kind === "local" ? "local" : "byok";
  if (provider.kind === "byok") {
    selectedByokProvider.value = provider.id;
  }
}

async function fetchDocumentState() {
  try {
    const doc = await $fetch(`${apiBaseURL}/documents/${props.documentId}/`);
    documentState.value = doc;
    syncModeFromDocument(doc);
    return doc;
  } catch (error) {
    actionError.value = error?.data?.error || "Failed to load OCR status.";
    return null;
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    const doc = await fetchDocumentState();
    if (!doc) return;

    if (doc.ocr_status === "succeeded") {
      stopPolling();
      emit("ocr-completed");
    } else if (doc.ocr_status === "failed") {
      stopPolling();
    }
  }, 2000);
}

async function runOcr() {
  if (isProcessing.value || isSubmitting.value) return;
  if (selectedProviderUnavailable.value) {
    actionError.value = `Add your ${activeProvider.value?.label} API key in Settings first.`;
    return;
  }

  actionError.value = "";
  isSubmitting.value = true;

  try {
    const res = await $fetch(`${apiBaseURL}/documents/${props.documentId}/ocr/`, {
      method: "POST",
      body: {
        ocr_provider: activeProviderId.value,
      },
    });
    documentState.value = res.document;
    startPolling();
  } catch (error) {
    actionError.value =
      error?.data?.error || error?.message || "Failed to queue OCR.";
  } finally {
    isSubmitting.value = false;
  }
}

watch(
  () => props.documentId,
  async () => {
    stopPolling();
    await fetchDocumentState();
    if (isProcessing.value) startPolling();
  },
  { immediate: true }
);

onMounted(async () => {
  await fetchOcrProviders();
  if (byokProviders.value.length && !byokProviders.value.some((p) => p.id === selectedByokProvider.value)) {
    selectedByokProvider.value = byokProviders.value[0].id;
  }
  syncModeFromDocument(documentState.value);
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="flex flex-1 flex-col overflow-hidden">
    <div class="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
      <div>
        <h3 class="text-sm font-medium text-slate-200 mb-1">Text Recognition</h3>
        <p class="text-xs text-slate-500 leading-relaxed">
          Make scanned PDFs searchable. Local OCR runs on your device; cloud OCR uses your API keys.
        </p>
      </div>

      <div class="rounded-xl border border-slate-700/80 bg-slate-950/50 p-1 flex">
        <button
          type="button"
          class="flex-1 rounded-lg px-3 py-2 text-xs font-medium transition-colors"
          :class="
            ocrMode === 'local'
              ? 'bg-indigo-600/90 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          "
          @click="ocrMode = 'local'"
        >
          Local
        </button>
        <button
          type="button"
          class="flex-1 rounded-lg px-3 py-2 text-xs font-medium transition-colors"
          :class="
            ocrMode === 'byok'
              ? 'bg-indigo-600/90 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          "
          @click="ocrMode = 'byok'"
        >
          Cloud (BYOK)
        </button>
      </div>

      <div
        v-if="ocrMode === 'local'"
        class="rounded-xl border border-slate-700/60 bg-slate-900/40 p-3 space-y-2"
      >
        <div class="flex items-start gap-2">
          <Icon name="ph:cpu" class="w-4 h-4 text-indigo-400 mt-0.5 shrink-0" />
          <div>
            <p class="text-xs font-medium text-slate-200">
              {{ localProviders[0]?.label || "PaddleOCR Local" }}
            </p>
            <p class="text-[11px] text-slate-500 mt-1 leading-relaxed">
              {{ localProviders[0]?.description || "Bundled PaddleOCR ONNX models. Runs fully on-device." }}
            </p>
          </div>
        </div>
      </div>

      <div
        v-else
        class="rounded-xl border border-slate-700/60 bg-slate-900/40 p-3 space-y-2"
      >
        <label for="byokProvider" class="text-xs font-medium text-slate-300">
          Cloud OCR Provider
        </label>
        <select
          id="byokProvider"
          v-model="selectedByokProvider"
          :disabled="ocrProvidersLoading || byokProviders.length === 0"
          class="w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-2 text-xs text-slate-200 outline-none focus:border-indigo-500/50 disabled:opacity-60"
        >
          <option
            v-for="provider in byokProviders"
            :key="provider.id"
            :value="provider.id"
          >
            {{ provider.label }}
          </option>
        </select>
        <p v-if="activeProvider?.description" class="text-[11px] text-slate-500 leading-relaxed">
          {{ activeProvider.description }}
        </p>
        <p v-if="selectedProviderUnavailable" class="text-[11px] text-amber-400">
          Add {{ activeProvider?.label }} API key in Settings → General.
        </p>
      </div>

      <div class="rounded-xl border border-slate-700/60 bg-slate-900/40 p-3 space-y-3">
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs text-slate-400">Status</span>
          <span
            class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium"
            :class="statusMeta.class"
          >
            <Icon
              :name="statusMeta.icon"
              class="w-3.5 h-3.5"
              :class="{ 'animate-spin': documentState?.ocr_status === 'processing' }"
            />
            {{ statusMeta.label }}
          </span>
        </div>

        <div v-if="documentState?.searchable" class="flex items-center gap-2 text-[11px] text-emerald-300">
          <Icon name="ph:text-aa" class="w-3.5 h-3.5" />
          PDF is searchable
        </div>

        <div v-if="documentState?.ocr_provider" class="text-[11px] text-slate-500">
          Last provider:
          <span class="text-slate-300">{{ getProviderById(documentState.ocr_provider)?.label || documentState.ocr_provider }}</span>
        </div>

        <div
          v-if="documentState?.ocr_error"
          class="rounded-lg border border-red-800/40 bg-red-950/30 px-3 py-2 text-[11px] text-red-200 leading-relaxed"
        >
          {{ documentState.ocr_error }}
        </div>
      </div>

      <p v-if="ocrProvidersError" class="text-[11px] text-amber-400">
        {{ ocrProvidersError }}
      </p>
      <p v-if="actionError" class="text-[11px] text-red-300">
        {{ actionError }}
      </p>
    </div>

    <div class="shrink-0 border-t border-slate-800 p-3">
      <button
        type="button"
        class="w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="isProcessing || isSubmitting || selectedProviderUnavailable"
        @click="runOcr"
      >
        {{ runButtonLabel }}
      </button>
      <p class="mt-2 text-[10px] text-slate-500 text-center leading-relaxed">
        OCR may take a minute or two for longer documents.
      </p>
    </div>
  </div>
</template>
