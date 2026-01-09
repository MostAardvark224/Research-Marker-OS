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
                Before fetching, ensure your
                <code
                  class="bg-indigo-500/20 px-1 py-0.5 rounded text-indigo-300"
                  >SCHOLAR_INBOX_PERSONAL_LOGIN</code
                >
                environment variable is set. See GitHub documentation.
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
              This will trigger a manual fetch for your scholar-inbox daily
              digest. The fetch may take a couple minutes.
            </p>
          </div>

          <div class="w-full max-w-[240px] space-y-2">
            <div class="flex justify-between items-center px-1">
              <span class="text-xs font-medium text-slate-400"
                >Papers to fetch</span
              >
              <span
                class="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20"
              >
                {{ paperCount }}
              </span>
            </div>
            <input
              v-model.number="paperCount"
              type="range"
              min="0"
              max="10"
              step="1"
              class="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-indigo-500 hover:bg-white/20 transition-colors"
            />
            <div
              class="flex justify-between text-[10px] text-slate-600 font-medium px-1"
            >
              <span>0</span>
              <span>5</span>
              <span>10</span>
            </div>
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
            <p class="text-[10px] text-slate-500 leading-tight">
              This will trigger a fetch even if you have auto-imported your
              daily digest.
            </p>
          </div>
        </div>
      </main>

      <footer class="px-6 py-3 border-t border-white/5 bg-white/[0.02]">
        <div class="flex items-center justify-center gap-2 text-slate-300">
          <Icon name="uil:layer-group" class="text-sm" />
          <span class="text-[10px] font-medium uppercase tracking-widest">
            More fine-grained control features coming soon
          </span>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup>
const emit = defineEmits(["close"]);
const isLoading = ref(false);
const paperCount = ref(5);

const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const fetchDigest = async () => {
  if (isLoading.value) return;
  isLoading.value = true;

  try {
    const res = await $fetch(`${apiBaseURL}/fetch-scholar-inbox-papers/`, {
      method: "POST",
      body: { amount_to_import: paperCount.value },
    });
    emit("close");
  } catch (error) {
    console.error("Error fetching digest:", error);
  } finally {
    isLoading.value = false;
  }
};
</script>
