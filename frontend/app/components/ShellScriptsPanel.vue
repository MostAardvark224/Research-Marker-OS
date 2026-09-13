<script setup>
const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const scripts = ref([]);
const runState = ref({ status: "idle", results: [] });
const loading = ref(true);
const actionError = ref("");
let pollTimer = null;

const isBusy = computed(() =>
  ["queued", "running"].includes(runState.value?.status),
);

function scriptName(path) {
  return path?.split(/[\\/]/).filter(Boolean).pop() || path;
}

function resultFor(path) {
  return (runState.value?.results || []).find((item) => item.path === path);
}

function stopPolling() {
  if (!pollTimer) return;
  clearInterval(pollTimer);
  pollTimer = null;
}

async function loadScripts({ quiet = false } = {}) {
  if (!quiet) loading.value = true;
  try {
    const response = await $fetch(`${apiBaseURL}/shell-scripts/`);
    scripts.value = response?.scripts || [];
    runState.value = response?.run || { status: "idle", results: [] };
    actionError.value = "";
    if (!isBusy.value) stopPolling();
    return response;
  } catch (error) {
    actionError.value =
      error?.data?.message || error?.message || "Could not load shell scripts.";
  } finally {
    if (!quiet) loading.value = false;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(() => loadScripts({ quiet: true }), 1000);
}

async function runScripts(paths) {
  if (isBusy.value || !paths.length) return;
  actionError.value = "";
  try {
    const response = await $fetch(`${apiBaseURL}/shell-scripts/`, {
      method: "POST",
      body: { paths },
    });
    runState.value = {
      ...response,
      status: "queued",
      results: [],
      summary: `Queued ${paths.length} shell script(s).`,
    };
    startPolling();
  } catch (error) {
    actionError.value =
      error?.data?.message || error?.message || "Could not run shell scripts.";
    await loadScripts({ quiet: true });
  }
}

onMounted(async () => {
  await loadScripts();
  if (isBusy.value) startPolling();
});

onUnmounted(stopPolling);
</script>

<template>
  <section class="flex min-h-0 flex-1 flex-col overflow-hidden bg-slate-950/30">
    <div class="flex items-center justify-between gap-2 border-b border-slate-800 px-3 py-3">
      <p class="text-[11px] leading-relaxed text-slate-500">
        Run trusted scripts saved in Settings.
      </p>
      <div class="flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          class="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white disabled:opacity-40"
          :disabled="loading || isBusy"
          title="Refresh scripts"
          @click="loadScripts()"
        >
          <Icon name="ph:arrows-clockwise" class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-md bg-indigo-500/15 px-2.5 py-1.5 text-[11px] font-medium text-indigo-300 transition-colors hover:bg-indigo-500/25 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="loading || isBusy || !scripts.length"
          @click="runScripts(scripts.map((script) => script.path))"
        >
          <Icon
            :name="isBusy ? 'ph:spinner' : 'ph:play'"
            class="h-3.5 w-3.5"
            :class="{ 'animate-spin': isBusy }"
          />
          {{ isBusy ? "Running…" : "Run all" }}
        </button>
      </div>
    </div>

    <div class="flex-1 space-y-2 overflow-y-auto p-3 custom-scrollbar">
      <div v-if="loading" class="flex h-28 items-center justify-center text-slate-500">
        <Icon name="ph:spinner" class="h-5 w-5 animate-spin" />
      </div>

      <div
        v-else-if="!scripts.length"
        class="flex h-28 flex-col items-center justify-center gap-2 text-center text-slate-600"
      >
        <Icon name="ph:terminal-window" class="h-7 w-7" />
        <p class="text-xs">No shell scripts saved.</p>
        <p class="text-[10px]">Add them under Settings → General.</p>
      </div>

      <template v-else>
      <article
        v-for="script in scripts"
        :key="script.path"
        class="rounded-lg border border-slate-800 bg-slate-900/70 p-3"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate text-xs font-medium text-slate-200" :title="script.path">
              {{ scriptName(script.path) }}
            </p>
            <p class="mt-0.5 break-all font-mono text-[9px] leading-relaxed text-slate-600">
              {{ script.path }}
            </p>
            <span
              v-if="script.run_on_startup"
              class="mt-1.5 inline-flex rounded border border-cyan-500/20 bg-cyan-500/10 px-1.5 py-0.5 text-[9px] text-cyan-300"
            >
              Runs on startup
            </span>
          </div>
          <button
            type="button"
            class="inline-flex shrink-0 items-center gap-1 rounded-md border border-slate-700 px-2 py-1 text-[10px] text-slate-300 transition-colors hover:border-indigo-500/40 hover:bg-indigo-500/10 hover:text-indigo-200 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="isBusy"
            @click="runScripts([script.path])"
          >
            <Icon name="ph:play" class="h-3 w-3" />
            Run
          </button>
        </div>

        <div
          v-if="resultFor(script.path)"
          class="mt-2 rounded-md border px-2 py-1.5"
          :class="
            resultFor(script.path).ok
              ? 'border-emerald-500/20 bg-emerald-500/5'
              : 'border-red-500/20 bg-red-500/5'
          "
        >
          <div class="flex items-center gap-1.5 text-[10px]">
            <Icon
              :name="resultFor(script.path).ok ? 'ph:check-circle' : 'ph:warning-circle'"
              :class="resultFor(script.path).ok ? 'text-emerald-400' : 'text-red-400'"
            />
            <span :class="resultFor(script.path).ok ? 'text-emerald-300' : 'text-red-300'">
              {{ resultFor(script.path).ok ? "Completed" : "Failed" }}
              <template v-if="resultFor(script.path).exit_code !== null">
                · exit {{ resultFor(script.path).exit_code }}
              </template>
            </span>
          </div>
          <pre class="mt-1 max-h-28 overflow-auto whitespace-pre-wrap break-words font-mono text-[9px] leading-relaxed text-slate-400 custom-scrollbar">{{ resultFor(script.path).message }}</pre>
        </div>
      </article>
      </template>

      <p
        v-if="runState?.summary && !isBusy"
        class="rounded-md border border-slate-800 bg-slate-900/50 px-2.5 py-2 text-[10px] text-slate-400"
      >
        {{ runState.summary }}
      </p>
      <p
        v-if="actionError"
        class="rounded-md border border-red-500/20 bg-red-500/5 px-2.5 py-2 text-[10px] text-red-300"
      >
        {{ actionError }}
      </p>
    </div>
  </section>
</template>
