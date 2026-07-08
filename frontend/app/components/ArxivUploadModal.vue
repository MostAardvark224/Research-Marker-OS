<template>
  <div
    class="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
  >
    <div
      class="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
      @click="$emit('close')"
    ></div>

    <div
      class="relative w-full max-w-md bg-[#020204] border border-white/10 rounded-xl shadow-2xl overflow-hidden"
    >
      <header
        class="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#020204]"
      >
        <div>
          <h2 class="font-semibold text-lg tracking-tight text-white">
            Import from arXiv
          </h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Paste an arXiv link and add the PDF to your library.
          </p>
        </div>
        <button
          @click="$emit('close')"
          class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
        >
          <Icon name="material-symbols:close" class="text-xl" />
        </button>
      </header>

      <main class="p-4 space-y-4">
        <div class="space-y-2">
          <label class="text-xs font-medium text-slate-400">arXiv link</label>
          <input
            v-model="arxivUrl"
            type="url"
            placeholder="https://arxiv.org/abs/2301.12345"
            class="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            @blur="lookupMetadata"
          />
          <p v-if="metadataError" class="text-xs text-red-400">
            {{ metadataError }}
          </p>
          <p v-else-if="isLookingUp" class="text-xs text-slate-500">
            Looking up paper metadata...
          </p>
        </div>

        <div class="space-y-2">
          <div class="flex items-center justify-between gap-3">
            <label class="text-xs font-medium text-slate-400">Title</label>
            <label class="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
              <input
                v-model="useArxivTitle"
                type="checkbox"
                class="accent-indigo-500 w-4 h-4 rounded border-white/20 bg-white/5"
              />
              Use arXiv title
            </label>
          </div>
          <input
            v-model="title"
            type="text"
            :disabled="useArxivTitle"
            placeholder="Paper title"
            class="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 disabled:opacity-60"
          />
        </div>

        <div class="space-y-2">
          <label class="text-xs font-medium text-slate-400">Folder</label>
          <select
            v-model="selectedFolderId"
            class="w-full rounded-lg border border-white/10 bg-[#020204] px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
          >
            <option value="">Unassigned</option>
            <option
              v-for="folder in flattenedFolders"
              :key="folder.id"
              :value="folder.id"
            >
              {{ folder.label }}
            </option>
          </select>
        </div>

        <div class="space-y-3 rounded-lg border border-white/10 bg-white/[0.02] p-3">
          <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
            <input
              v-model="skipOcr"
              type="checkbox"
              class="accent-indigo-500 w-4 h-4 rounded border-white/20 bg-white/5"
            />
            Skip OCR processing
          </label>

          <div v-if="!skipOcr" class="space-y-2">
            <div class="rounded-lg border border-white/10 p-1 flex">
              <button
                type="button"
                class="flex-1 rounded-md px-2 py-1.5 text-[11px] font-medium transition-colors"
                :class="ocrMode === 'local' ? 'bg-indigo-500 text-white' : 'text-slate-400'"
                @click="ocrMode = 'local'"
              >
                Local
              </button>
              <button
                type="button"
                class="flex-1 rounded-md px-2 py-1.5 text-[11px] font-medium transition-colors"
                :class="ocrMode === 'byok' ? 'bg-indigo-500 text-white' : 'text-slate-400'"
                @click="ocrMode = 'byok'"
              >
                Cloud (BYOK)
              </button>
            </div>

            <select
              v-if="ocrMode === 'byok'"
              v-model="selectedByokProvider"
              class="w-full rounded-lg border border-white/10 bg-[#020204] px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            >
              <option
                v-for="provider in byokProviders"
                :key="provider.id"
                :value="provider.id"
              >
                {{ provider.label }}
              </option>
            </select>

            <p v-if="selectedProviderUnavailable" class="text-xs text-red-400">
              Add API key in Settings first.
            </p>
          </div>
        </div>

        <button
          @click="importPaper"
          :disabled="isImporting || !arxivUrl.trim() || selectedProviderUnavailable"
          class="w-full flex items-center justify-center gap-2 px-5 py-2 rounded-lg text-sm font-medium bg-white text-black hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
        >
          <Icon
            v-if="isImporting"
            name="eos-icons:loading"
            class="text-lg animate-spin"
          />
          <Icon
            v-else
            name="material-symbols:download-rounded"
            class="text-lg"
          />
          <span>{{ isImporting ? "Importing..." : "Import Paper" }}</span>
        </button>
      </main>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  folders: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["close", "imported"]);

const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const {
  byokProviders,
  fetchOcrProviders,
  isProviderAvailable,
} = useOcrProviders();

const arxivUrl = ref("");
const title = ref("");
const useArxivTitle = ref(true);
const selectedFolderId = ref("");
const skipOcr = ref(true);
const ocrMode = ref("local");
const selectedByokProvider = ref("mistral");
const isLookingUp = ref(false);
const isImporting = ref(false);
const metadataError = ref("");

const activeOcrProvider = computed(() =>
  ocrMode.value === "local" ? "paddleocr" : selectedByokProvider.value
);

const selectedProviderUnavailable = computed(
  () => !skipOcr.value && !isProviderAvailable(activeOcrProvider.value)
);

const flattenedFolders = computed(() => {
  const result = [];

  function walk(folderList, depth = 0) {
    for (const folder of folderList) {
      result.push({
        id: folder.id,
        label: `${"— ".repeat(depth)}${folder.name}`,
      });
      if (folder.subfolders?.length) {
        walk(folder.subfolders, depth + 1);
      }
    }
  }

  walk(props.folders);
  return result;
});

watch(useArxivTitle, (enabled) => {
  if (enabled) {
    lookupMetadata();
  }
});

onMounted(async () => {
  await fetchOcrProviders();
  if (
    byokProviders.value.length &&
    !byokProviders.value.some((provider) => provider.id === selectedByokProvider.value)
  ) {
    selectedByokProvider.value = byokProviders.value[0].id;
  }
});

async function lookupMetadata() {
  const value = arxivUrl.value.trim();
  metadataError.value = "";

  if (!value) {
    return;
  }

  isLookingUp.value = true;

  try {
    const metadata = await $fetch(`${apiBaseURL}/arxiv-paper-metadata/`, {
      method: "POST",
      body: { arxiv_url: value },
    });

    if (useArxivTitle.value) {
      title.value = metadata.title || "";
    } else if (!title.value.trim()) {
      title.value = metadata.title || "";
    }
  } catch (error) {
    metadataError.value =
      error?.data?.error || "Could not look up that arXiv paper.";
  } finally {
    isLookingUp.value = false;
  }
}

async function importPaper() {
  if (isImporting.value || !arxivUrl.value.trim()) {
    return;
  }

  if (selectedProviderUnavailable.value) {
    alert("Add your cloud OCR API key in Settings before importing with OCR.");
    return;
  }

  isImporting.value = true;

  try {
    const body = {
      arxiv_url: arxivUrl.value.trim(),
      use_arxiv_title: useArxivTitle.value,
      title: title.value.trim(),
      skip_ocr: skipOcr.value,
      ocr_provider: activeOcrProvider.value,
    };

    if (selectedFolderId.value !== "") {
      body.folder_id = selectedFolderId.value;
    }

    await $fetch(`${apiBaseURL}/import-arxiv-paper/`, {
      method: "POST",
      body,
    });

    emit("imported");
    emit("close");
  } catch (error) {
    const message =
      error?.data?.error || "Failed to import paper from arXiv.";
    console.error("Error importing arXiv paper:", error);
    alert(message);
  } finally {
    isImporting.value = false;
  }
}
</script>
