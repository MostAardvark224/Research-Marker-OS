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
            Scholar Inbox
          </h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Daily Research Digest (See GitHub docs for more info).
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
        <div
          class="p-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 relative overflow-hidden group"
        >
          <div
            class="absolute top-0 right-0 -mt-4 -mr-4 w-24 h-24 bg-indigo-500/20 rounded-full blur-2xl group-hover:bg-indigo-500/30 transition-colors duration-500"
          ></div>

          <div class="relative flex gap-3">
            <Icon
              name="material-symbols:info-outline"
              class="text-indigo-400 text-lg flex-shrink-0 mt-0.5"
            />
            <div class="space-y-1">
              <h4 class="text-sm font-medium text-indigo-100">
                Configuration Required
              </h4>
              <p class="text-xs text-indigo-200/70 leading-snug">
                Before fetching, add your
                <span class="font-medium text-indigo-200"
                  >Scholar Inbox API Key</span
                >
                in Settings → Scholar Inbox. Find the key under Settings in
                Scholar Inbox.
              </p>
            </div>
          </div>
        </div>

        <div class="flex flex-col items-center justify-center py-2 space-y-5">
          <div class="text-center space-y-1 max-w-xs mx-auto">
            <div
              class="w-11 h-11 mx-auto rounded-full bg-white/5 flex items-center justify-center mb-2 border border-white/10"
            >
              <Icon name="uil:newspaper" class="text-xl text-slate-300" />
            </div>
            <h3 class="text-sm font-medium text-slate-200">Ready to read?</h3>
            <p class="text-xs text-slate-400 leading-snug">
              Fetches your latest Scholar Inbox digest and imports the top
              arXiv papers into your library.
            </p>
          </div>

          <div
            class="w-full max-w-xs rounded-xl border border-white/10 bg-white/[0.03] p-4 shadow-inner"
          >
            <label for="manual-scholar-paper-count" class="block">
              <div class="mb-3 flex items-start justify-between gap-4">
                <div>
                  <span class="block text-sm font-medium text-slate-200">
                    Papers to import
                  </span>
                  <span class="mt-0.5 block text-[11px] text-slate-500">
                    Imports your highest-ranked papers
                  </span>
                </div>
                <span
                  class="rounded-md border border-indigo-500/20 bg-indigo-500/10 px-2 py-1 text-[10px] font-semibold text-indigo-300"
                >
                  1–100
                </span>
              </div>

              <div class="relative">
                <input
                  id="manual-scholar-paper-count"
                  v-model.number="paperCount"
                  type="number"
                  inputmode="numeric"
                  min="1"
                  max="100"
                  step="1"
                  class="scholar-paper-count-input w-full rounded-lg border border-white/10 bg-[#09090c] px-4 py-3 pr-20 text-xl font-semibold text-white outline-none transition-colors focus:border-indigo-500/60 focus:ring-2 focus:ring-indigo-500/10"
                  @blur="paperCount = normalizePaperCount(paperCount)"
                  @keydown.enter="$event.target.blur()"
                />
                <span
                  class="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-500"
                >
                  papers
                </span>
              </div>
            </label>
          </div>

          <div class="w-full max-w-xs text-center space-y-2">
            <button
              @click="fetchDigest"
              :disabled="isLoading"
              class="w-full flex items-center justify-center gap-2 px-5 py-2 rounded-lg text-sm font-medium bg-white text-black hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-[0_0_20px_rgba(255,255,255,0.1)]"
            >
              <Icon
                v-if="isLoading"
                name="eos-icons:loading"
                class="text-lg animate-spin"
              />
              <Icon
                v-else
                name="material-symbols:download-rounded"
                class="text-lg"
              />
              <span>{{
                isLoading ? "Fetching Digest..." : "Fetch Today's Digest"
              }}</span>
            </button>
            <p
              v-if="statusMessage"
              class="text-[11px] leading-snug"
              :class="statusError ? 'text-red-300' : 'text-slate-400'"
            >
              {{ statusMessage }}
            </p>
            <p class="text-[10px] text-slate-500 leading-tight">
              Uses the Scholar Inbox API. Your key is stored locally with your
              other application settings.
            </p>
          </div>
        </div>
      </main>

      <footer class="px-6 py-3 border-t border-white/5 bg-white/[0.02]">
        <div class="flex items-center justify-center gap-2 text-slate-300">
          <Icon name="uil:layer-group" class="text-sm" />
          <span class="text-[10px] font-medium uppercase tracking-widest">
            Papers are saved to the Scholar Inbox folder
          </span>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup>
const emit = defineEmits(["close", "imported"]);
const isLoading = ref(false);
const paperCount = ref(5);
const statusMessage = ref("");
const statusError = ref(false);

const {
  public: { apiBaseURL },
} = useRuntimeConfig();

function applyScholarPrefs(scholarPrefs) {
  if (!scholarPrefs) return;

  if (scholarPrefs.amount_to_import === "All") {
    paperCount.value = 100;
    return;
  }

  if (
    typeof scholarPrefs.amount_to_import === "number" &&
    scholarPrefs.amount_to_import > 0
  ) {
    paperCount.value = normalizePaperCount(scholarPrefs.amount_to_import);
  }
}

function normalizePaperCount(value) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return 5;
  return Math.min(100, Math.max(1, parsed));
}

onMounted(async () => {
  try {
    const res = await $fetch(`${apiBaseURL}/user-preferences/`);
    applyScholarPrefs(res.user_preferences?.scholar_inbox);
  } catch (error) {
    console.error("Failed to load Scholar Inbox preferences:", error);
  }
});

const fetchDigest = async () => {
  if (isLoading.value) return;
  isLoading.value = true;
  statusMessage.value = "";
  statusError.value = false;

  try {
    paperCount.value = normalizePaperCount(paperCount.value);
    const amount_to_import = paperCount.value;
    const res = await $fetch(`${apiBaseURL}/fetch-scholar-inbox-papers/`, {
      method: "POST",
      body: { amount_to_import },
    });

    const imported = res?.imported ?? 0;
    const skipped = res?.skipped ?? 0;
    const unmatched = res?.unmatched ?? 0;
    const message = res?.message || "Scholar Inbox fetch completed.";

    statusMessage.value = message;
    statusError.value = false;

    if (imported > 0) {
      const extras = [];
      if (skipped > 0) extras.push(`${skipped} skipped`);
      if (unmatched > 0) extras.push(`${unmatched} without arXiv URLs`);
      alert(
        extras.length
          ? `${message}\n(${extras.join(", ")})`
          : message,
      );
      emit("imported");
      emit("close");
      return;
    }

    alert(message);
    if (res?.digest_found) {
      emit("close");
    }
  } catch (error) {
    const message =
      error?.data?.error ||
      error?.data?.message ||
      "Failed to fetch Scholar Inbox digest.";
    console.error("Error fetching digest:", error);
    statusMessage.value = message;
    statusError.value = true;
    alert(message);
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
.scholar-paper-count-input {
  appearance: textfield;
  -moz-appearance: textfield;
}

.scholar-paper-count-input::-webkit-inner-spin-button,
.scholar-paper-count-input::-webkit-outer-spin-button {
  margin: 0;
  appearance: none;
}
</style>
