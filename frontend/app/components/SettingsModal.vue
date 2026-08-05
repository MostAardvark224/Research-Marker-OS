<template>
  <div
    class="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
  >
    <div
      class="absolute inset-0 bg-black/60 backdrop-blur-sm"
      @click="$emit('close')"
    ></div>

    <div
      class="relative flex flex-col md:flex-row w-full max-w-4xl max-h-[85vh] bg-[#020204] border border-white/10 rounded-2xl shadow-2xl overflow-hidden selection:bg-indigo-500/30"
    >
      <aside
        class="w-full md:w-60 border-b md:border-b-0 md:border-r border-white/10 bg-white/[0.02] flex flex-col flex-shrink-0"
      >
        <div
          class="p-5 border-b border-white/5 flex items-center justify-between md:block"
        >
          <div>
            <h2 class="font-semibold text-lg tracking-tight">Settings</h2>
            <p class="text-xs text-slate-500 mt-1 hidden md:block">
              Manage workspace
            </p>
          </div>
          <button @click="$emit('close')" class="md:hidden text-slate-400">
            <Icon name="material-symbols:close" class="text-xl" />
          </button>
        </div>

        <nav class="flex-1 overflow-y-auto p-2 space-y-1">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            :class="[
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
              activeTab === tab.id
                ? 'bg-indigo-500/10 text-indigo-400 shadow-[inset_0px_1px_0px_rgba(255,255,255,0.05)] border border-indigo-500/20'
                : 'text-slate-400 hover:text-white hover:bg-white/5 border border-transparent',
            ]"
          >
            <Icon :name="tab.icon" class="text-lg" />
            {{ tab.label }}
          </button>
        </nav>

        <div class="p-3 border-t border-white/5 hidden md:block">
          <div
            class="flex items-center gap-3 px-3 py-2 rounded-lg bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-white/5"
          >
            <div
              class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"
            ></div>
            <span class="text-[10px] text-slate-400 font-mono">v{{ appVersionLabel }}</span>
          </div>
        </div>
      </aside>

      <main class="flex-1 flex flex-col min-w-0 bg-[#020204] overflow-hidden">
        <header
          class="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#020204] z-10"
        >
          <div>
            <h3 class="text-lg font-medium text-white">
              {{ activeTabLabel }}
            </h3>
            <p class="text-xs text-slate-500">
              {{ activeTabDescription }}
            </p>
          </div>
          <button
            @click="$emit('close')"
            class="hidden md:flex p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Icon name="material-symbols:close" class="text-xl" />
          </button>
        </header>

        <div class="flex-1 overflow-y-auto p-6 custom-scrollbar">
          <div v-if="activeTab === 'general'" class="space-y-6 max-w-2xl">
            <div class="p-4 rounded-xl border border-white/10 bg-white/[0.02] space-y-3">
              <div class="flex items-center justify-between gap-3">
                <label class="block font-mono text-xs text-indigo-300">
                  Paper context cache
                </label>
              </div>
              <p class="text-[11px] leading-relaxed text-slate-500">
                Clears locally generated page images, OCR cache, extracted text, and search
                chunks. Your PDFs, annotations, and chat history are kept. Context rebuilds when
                you open a paper again.
              </p>
              <button
                @click="clearPaperContext"
                :disabled="paperContextClearing"
                class="px-3 py-1.5 rounded-lg text-xs bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 disabled:opacity-50"
              >
                {{ paperContextClearing ? "Clearing…" : "Clear paper context" }}
              </button>
              <p
                v-if="paperContextMessage"
                class="text-[11px]"
                :class="paperContextError ? 'text-red-300' : 'text-emerald-300'"
              >
                {{ paperContextMessage }}
              </p>
            </div>

            <div
              class="p-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 mb-4"
            >
              <div class="flex gap-3">
                <Icon
                  name="material-symbols:info-outline"
                  class="text-indigo-400 text-lg flex-shrink-0"
                />
                <p class="text-xs text-indigo-200/80 leading-relaxed">
                  These settings are stored locally on your machine in a .env
                  file and are never synced to the cloud.
                </p>
              </div>
            </div>

            <div class="space-y-4">
              <div
                v-for="env in computedEnvList"
                :key="env.key"
                class="p-4 rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
              >
                <div class="space-y-3">
                  <div>
                    <label
                      class="block text-sm font-medium text-white mb-1 tracking-wide"
                    >
                      {{ env.label }}
                    </label>
                    <p
                      v-if="env.key !== env.label"
                      class="font-mono text-[10px] text-slate-600 mb-1"
                    >
                      {{ env.key }}
                    </p>
                    <p
                      v-if="env.description"
                      class="text-xs text-slate-500 leading-relaxed"
                    >
                      {{ env.description }}
                    </p>
                  </div>

                  <div class="relative group">
                    <input
                      v-model="envFormValues[env.key]"
                      :type="env.type"
                      :placeholder="env.placeholder || `Enter ${env.label}...`"
                      class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-700 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 focus:bg-white/[0.03] outline-none transition-all font-mono"
                      spellcheck="false"
                    />

                    <div
                      class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
                    >
                      <div
                        v-if="envFormValues[env.key]"
                        class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]"
                      ></div>
                      <div
                        v-else
                        class="w-1.5 h-1.5 rounded-full bg-slate-700"
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else-if="activeTab === 'scholar'" class="space-y-6 max-w-xl">
            <div
              class="p-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 mb-4"
            >
              <div class="flex gap-3">
                <Icon
                  name="material-symbols:info-outline"
                  class="text-indigo-400 text-lg flex-shrink-0"
                />
                <p class="text-xs text-indigo-200/80 leading-relaxed">
                  Configure automated imports from your Scholar Inbox Alert
                  Digest emails. Set your Gmail address and app password in the
                  General tab.
                </p>
              </div>
            </div>

            <div class="space-y-3">
              <h4
                class="text-xs font-bold text-slate-500 uppercase tracking-widest"
              >
                Preferences
              </h4>
              <div class="space-y-2">
                <label
                  class="flex items-center justify-between p-3 rounded-lg border border-white/10 bg-white/[0.02] cursor-pointer hover:border-white/20 transition-colors"
                >
                  <div class="flex items-center gap-3">
                    <span class="text-sm font-medium text-slate-200">
                      Auto Import Your Top Papers on Startup
                    </span>
                  </div>
                  <input
                    v-model="autoImportEnabled"
                    type="checkbox"
                    class="accent-indigo-500 w-4 h-4 rounded border-white/20 bg-white/5"
                  />
                </label>

                <div
                  v-if="autoImportEnabled"
                  class="p-3 rounded-lg border border-white/10 bg-white/[0.02] space-y-3 transition-opacity duration-300"
                >
                  <div class="flex items-center justify-between">
                    <span class="text-sm font-medium text-slate-200">
                      Import limit:
                    </span>
                    <span class="text-sm font-bold text-indigo-400">
                      {{ paperLimitDisplay }}
                    </span>
                  </div>

                  <input
                    v-model="paperLimitValue"
                    type="range"
                    min="0"
                    max="2"
                    step="1"
                    class="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                  />

                  <div
                    class="flex justify-between text-xs text-slate-500 font-medium pt-1"
                  >
                    <span>1</span>
                    <span>5</span>
                    <span>All</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else-if="activeTab === 'updates'" class="space-y-6 max-w-xl">
            <div
              class="p-4 rounded-xl border border-white/10 bg-white/[0.02] space-y-4"
            >
              <div class="flex items-start justify-between gap-4">
                <div>
                  <p class="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1">
                    Current Version
                  </p>
                  <p class="text-2xl font-semibold text-white">
                    v{{ updateState.currentVersion || "…" }}
                  </p>
                </div>
                <div
                  class="px-2.5 py-1 rounded-full text-[10px] font-medium border"
                  :class="updateStatusBadgeClass"
                >
                  {{ updateStatusBadgeLabel }}
                </div>
              </div>

              <p class="text-sm text-slate-400 leading-relaxed">
                {{ statusMessage }}
              </p>

              <div
                v-if="isDownloading"
                class="space-y-2"
              >
                <div class="h-2 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    class="h-full rounded-full bg-indigo-500 transition-all duration-300"
                    :style="{ width: `${downloadProgress}%` }"
                  ></div>
                </div>
                <p class="text-[11px] text-slate-500 text-right">
                  {{ downloadProgress }}%
                </p>
              </div>

              <div class="flex flex-wrap items-center gap-3 pt-1">
                <button
                  @click="checkForUpdates()"
                  :disabled="isChecking || isDownloading || isReadyToInstall"
                  class="px-4 py-2 rounded-lg text-sm font-medium bg-white/5 hover:bg-white/10 border border-white/10 text-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {{ isChecking ? "Checking…" : "Check for updates" }}
                </button>

                <button
                  v-if="isReadyToInstall"
                  @click="installUpdate()"
                  class="px-4 py-2 rounded-lg text-sm font-medium bg-indigo-500 text-white hover:bg-indigo-400 transition-colors shadow-lg shadow-indigo-500/20"
                >
                  Install & Restart
                </button>
              </div>
            </div>

            <div
              v-if="!isDesktopApp"
              class="p-3 rounded-lg border border-amber-500/20 bg-amber-500/5"
            >
              <div class="flex gap-3">
                <Icon
                  name="material-symbols:info-outline"
                  class="text-amber-400 text-lg flex-shrink-0"
                />
                <p class="text-xs text-amber-200/80 leading-relaxed">
                  Automatic updates are only available in the Research Marker desktop app.
                  Download the latest release from GitHub if you are running in a browser.
                </p>
              </div>
            </div>

            <div
              v-else
              class="p-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5"
            >
              <div class="flex gap-3">
                <Icon
                  name="material-symbols:info-outline"
                  class="text-indigo-400 text-lg flex-shrink-0"
                />
                <p class="text-xs text-indigo-200/80 leading-relaxed">
                  Updates download automatically in the background. When a new version is ready,
                  click <strong class="text-indigo-100">Install & Restart</strong> to apply it.
                  The app also checks for updates every few hours and on startup.
                </p>
              </div>
            </div>
          </div>

          <div v-else-if="activeTab === 'ai'" class="space-y-6 max-w-xl">
            <div
              class="p-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 mb-4"
            >
              <div class="flex gap-3">
                <Icon
                  name="material-symbols:info-outline"
                  class="text-indigo-400 text-lg flex-shrink-0"
                />
                <p class="text-xs text-indigo-200/80 leading-relaxed">
                  Model lists are fetched live from each provider API and cached
                  for one hour. Add API keys in General, then refresh here.
                </p>
              </div>
            </div>

            <div class="flex items-center justify-between">
              <span class="text-xs text-slate-500">
                {{ aiModelsLoading ? "Refreshing model lists..." : "Live provider catalogs" }}
              </span>
              <button
                @click="fetchAiModels({ refresh: true })"
                :disabled="aiModelsLoading"
                class="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 disabled:opacity-50"
              >
                Refresh models
              </button>
            </div>

            <div class="space-y-4">
              <label class="block">
                <span class="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">
                  Default Provider
                </span>
                <select
                  v-model="defaultAiProvider"
                  class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 outline-none"
                >
                  <option
                    v-for="provider in aiProviders"
                    :key="provider.id"
                    :value="provider.id"
                  >
                    {{ provider.label }}
                  </option>
                </select>
              </label>

              <div class="p-4 rounded-xl border border-purple-500/20 bg-purple-500/5 space-y-4">
                <div>
                  <h4 class="text-sm font-medium text-white">Smart Collections</h4>
                  <p class="mt-1 text-[11px] leading-relaxed text-slate-500">
                    Embeddings build the graph. A separate generation model labels topics and
                    creates recommendations. Claude can label collections but does not provide
                    embeddings.
                  </p>
                </div>

                <div class="grid gap-3 sm:grid-cols-2">
                  <label class="block space-y-1.5">
                    <span class="text-[11px] font-mono text-purple-300">Embedding provider</span>
                    <select
                      v-model="smartCollectionEmbeddingProvider"
                      class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-purple-500/50"
                    >
                      <option
                        v-for="provider in embeddingProviders"
                        :key="provider.id"
                        :value="provider.id"
                      >
                        {{ provider.label }}{{ provider.configured ? "" : " — configure first" }}
                      </option>
                    </select>
                  </label>

                  <label class="block space-y-1.5">
                    <span class="text-[11px] font-mono text-purple-300">Embedding model</span>
                    <select
                      v-if="selectedEmbeddingProvider?.models?.length"
                      v-model="smartCollectionEmbeddingModels[smartCollectionEmbeddingProvider]"
                      class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-purple-500/50"
                    >
                      <option
                        v-for="model in selectedEmbeddingProvider.models"
                        :key="model"
                        :value="model"
                      >
                        {{ model }}
                      </option>
                    </select>
                    <input
                      v-else
                      v-model="smartCollectionEmbeddingModels[smartCollectionEmbeddingProvider]"
                      placeholder="Embedding model ID"
                      class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-purple-500/50 font-mono"
                    />
                  </label>

                  <label class="block space-y-1.5">
                    <span class="text-[11px] font-mono text-purple-300">Label provider</span>
                    <select
                      v-model="smartCollectionGenerationProvider"
                      class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-purple-500/50"
                    >
                      <option
                        v-for="provider in smartCollectionGenerationProviders"
                        :key="provider.id"
                        :value="provider.id"
                      >
                        {{ provider.label }}
                      </option>
                    </select>
                  </label>

                  <label class="block space-y-1.5">
                    <span class="text-[11px] font-mono text-purple-300">Label model</span>
                    <select
                      v-if="selectedGenerationProvider?.models?.length"
                      v-model="smartCollectionGenerationModel"
                      class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-purple-500/50"
                    >
                      <option
                        v-for="model in selectedGenerationProvider.models"
                        :key="model"
                        :value="model"
                      >
                        {{ model }}
                      </option>
                    </select>
                    <input
                      v-else
                      v-model="smartCollectionGenerationModel"
                      placeholder="Generation model ID"
                      class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-purple-500/50 font-mono"
                    />
                    <p
                      v-if="smartCollectionGenerationProvider === 'codex' && !selectedGenerationProvider?.ready"
                      class="text-[11px] text-amber-300/90"
                    >
                      Connect Codex above before using it for Smart Collection labels.
                    </p>
                  </label>
                </div>
              </div>

              <div
                v-for="provider in aiProviders"
                :key="provider.id"
                class="p-4 rounded-xl border border-white/10 bg-white/[0.02] space-y-2"
              >
                <div class="flex items-center justify-between gap-3">
                  <label class="block font-mono text-xs text-indigo-300">
                    {{ provider.id === "codex" ? "Codex connection" : `${provider.label} Model` }}
                  </label>
                  <span
                    v-if="provider.error"
                    class="text-[10px] text-amber-400 truncate"
                    :title="provider.error"
                  >
                    {{ provider.error }}
                  </span>
                </div>
                <div v-if="provider.id === 'codex'" class="space-y-3">
                  <div class="flex items-center gap-2 text-xs">
                    <span
                      class="h-2 w-2 rounded-full"
                      :class="codexStatus.subscription_usable ? 'bg-emerald-400' : codexStatus.state === 'runtime_error' ? 'bg-red-400' : 'bg-amber-400'"
                    />
                    <span class="text-slate-300">{{ codexStatusLabel }}</span>
                    <span v-if="codexStatus.plan_type" class="text-slate-500">
                      · {{ codexStatus.plan_type }}
                    </span>
                  </div>
                  <p v-if="codexStatus.message" class="text-xs text-amber-300/90">
                    {{ codexStatus.message }}
                  </p>
                  <p v-if="codexLogin.user_code" class="rounded-lg bg-black/30 px-3 py-2 text-xs text-slate-300">
                    Device code:
                    <strong class="ml-1 font-mono tracking-widest text-white">{{ codexLogin.user_code }}</strong>
                  </p>
                  <div v-if="codexRateLimits" class="text-[11px] text-slate-400">
                    <template v-if="codexRateLimits.rateLimits?.primary">
                      {{ codexRateLimits.rateLimits.primary.usedPercent }}% of the current
                      Codex window used
                    </template>
                    <template v-else>Rate-limit details are not currently available.</template>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <button
                      v-if="!codexStatus.subscription_usable"
                      @click="startCodexLogin('browser')"
                      :disabled="codexBusy"
                      class="px-3 py-1.5 rounded-lg text-xs bg-indigo-500/20 text-indigo-200 border border-indigo-500/30 disabled:opacity-50"
                    >
                      Sign in with ChatGPT
                    </button>
                    <button
                      v-if="!codexStatus.subscription_usable"
                      @click="startCodexLogin('device_code')"
                      :disabled="codexBusy"
                      class="px-3 py-1.5 rounded-lg text-xs bg-white/5 text-slate-300 border border-white/10 disabled:opacity-50"
                    >
                      Use device code
                    </button>
                    <button
                      @click="refreshCodexStatus(true)"
                      :disabled="codexBusy"
                      class="px-3 py-1.5 rounded-lg text-xs bg-white/5 text-slate-300 border border-white/10 disabled:opacity-50"
                    >
                      Restart Codex
                    </button>
                    <button
                      v-if="codexStatus.subscription_usable"
                      @click="logoutCodex"
                      :disabled="codexBusy"
                      class="px-3 py-1.5 rounded-lg text-xs bg-white/5 text-slate-300 border border-white/10 disabled:opacity-50"
                    >
                      Sign out
                    </button>
                  </div>
                  <p class="text-[11px] leading-relaxed text-slate-500">
                    Codex credentials are managed by Codex. Research Marker does not read or
                    store your ChatGPT tokens.
                  </p>
                  <div v-if="codexStatus.subscription_usable && provider.models?.length" class="space-y-2">
                    <label class="block font-mono text-xs text-indigo-300">
                      Codex model
                    </label>
                    <select
                      v-model="aiModels.codex"
                      class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 outline-none"
                    >
                      <option
                        v-for="model in provider.models"
                        :key="model"
                        :value="model"
                      >
                        {{ model }}
                      </option>
                    </select>
                  </div>
                </div>
                <template v-else>
                  <select
                    v-if="provider.models?.length"
                    v-model="aiModels[provider.id]"
                    class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 outline-none"
                  >
                    <option
                      v-for="model in provider.models"
                      :key="model"
                      :value="model"
                    >
                      {{ model }}
                    </option>
                  </select>
                  <input
                    v-model="aiModels[provider.id]"
                    class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-4 py-2 text-xs text-slate-300 placeholder-slate-700 focus:border-indigo-500/50 outline-none font-mono"
                    :placeholder="
                      provider.id === 'custom'
                        ? 'Model id your server expects (e.g. llama3.2)...'
                        : `Custom ${provider.label} model id...`
                    "
                    spellcheck="false"
                  />
                </template>
              </div>
            </div>
          </div>
        </div>

        <footer
          class="flex-shrink-0 p-4 border-t border-white/5 flex items-center justify-end gap-3 bg-[#020204]"
        >
          <button
            @click="$emit('close')"
            class="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            @click="saveSettings()"
            class="px-5 py-2 rounded-lg text-sm font-medium bg-white text-black hover:bg-slate-200 transition-colors"
          >
            Save Changes
          </button>
        </footer>
      </main>
    </div>
  </div>
</template>

<script setup>
const {
  public: { apiBaseURL },
} = useRuntimeConfig();
const emit = defineEmits(["close"]);

const {
  aiProviders,
  embeddingProviders,
  aiModels,
  selectedAiProvider: defaultAiProvider,
  selectedProviderModels,
  initializeAiModels,
  fetchAiModels,
  aiModelsLoading,
} = useAiModels();

const smartCollectionEmbeddingProvider = ref("gemini");
const smartCollectionEmbeddingModels = ref({
  gemini: "gemini-embedding-2",
  openai: "text-embedding-3-small",
  custom: "",
});
const smartCollectionGenerationProvider = ref("gemini");
const smartCollectionGenerationModel = ref("gemini-flash-latest");
const selectedEmbeddingProvider = computed(() =>
  embeddingProviders.value.find(
    (provider) => provider.id === smartCollectionEmbeddingProvider.value,
  ),
);
const smartCollectionGenerationProviders = computed(() => aiProviders.value);
const selectedGenerationProvider = computed(() =>
  smartCollectionGenerationProviders.value.find(
    (provider) => provider.id === smartCollectionGenerationProvider.value,
  ),
);

watch(smartCollectionGenerationProvider, () => {
  const provider = selectedGenerationProvider.value;
  if (!provider) return;
  if (!provider.models?.includes(smartCollectionGenerationModel.value)) {
    smartCollectionGenerationModel.value =
      provider.default_chat_model || provider.models?.[0] || "";
  }
});

const {
  isDesktopApp,
  updateState,
  isChecking,
  isDownloading,
  isReadyToInstall,
  statusMessage,
  downloadProgress,
  checkForUpdates,
  installUpdate,
  initializeUpdater,
  teardownUpdater,
} = useAppUpdater();

const activeTab = ref("general");
const tabs = [
  { id: "general", label: "General", icon: "uil:setting" },
  { id: "updates", label: "Updates", icon: "uil:sync" },
  { id: "scholar", label: "Scholar Inbox", icon: "uil:envelope-alt" },
  { id: "ai", label: "AI Preferences", icon: "uil:robot" },
];

const codexStatus = ref({ state: "not_connected" });
const codexRateLimits = ref(null);
const codexLogin = ref({});
const codexBusy = ref(false);
const paperContextClearing = ref(false);
const paperContextMessage = ref("");
const paperContextError = ref(false);
let codexStatusPoll = null;

const codexStatusLabel = computed(() => {
  const labels = {
    not_installed: "Not installed",
    not_connected: "Runtime stopped",
    authentication_required: "Sign-in required",
    authentication_expired: "Authentication expired",
    api_key_mode: "API-key mode blocked",
    runtime_error: "Runtime error",
    connected: codexStatus.value.subscription_usable
      ? `Connected${codexStatus.value.email ? ` as ${codexStatus.value.email}` : ""}`
      : "Runtime connected",
  };
  return labels[codexStatus.value.state] || "Checking Codex";
});

async function openCodexAuthUrl(url) {
  if (!url) return;
  if (window.electronAPI?.openCodexAuthUrl) {
    const result = await window.electronAPI.openCodexAuthUrl(url);
    if (!result?.ok) throw new Error(result?.reason || "Could not open sign-in page.");
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

async function loadCodexRateLimits() {
  if (!codexStatus.value.subscription_usable) {
    codexRateLimits.value = null;
    return;
  }
  try {
    const response = await $fetch(`${apiBaseURL}/codex/rate-limits/`);
    codexRateLimits.value = response.rate_limits;
  } catch {
    codexRateLimits.value = null;
  }
}

async function refreshCodexStatus(restart = false) {
  codexBusy.value = true;
  try {
    codexStatus.value = await $fetch(`${apiBaseURL}/codex/status/`, {
      method: restart ? "POST" : "GET",
      body: restart ? { action: "restart" } : undefined,
    });
    if (codexStatus.value.subscription_usable) {
      codexLogin.value = {};
      if (codexStatusPoll) {
        clearInterval(codexStatusPoll);
        codexStatusPoll = null;
      }
      await loadCodexRateLimits();
      await fetchAiModels();
    }
  } catch (error) {
    codexStatus.value = {
      state: "runtime_error",
      message: error?.data?.message || error?.message || "Codex is unavailable.",
    };
  } finally {
    codexBusy.value = false;
  }
}

async function startCodexLogin(mode) {
  codexBusy.value = true;
  try {
    const status = await $fetch(`${apiBaseURL}/codex/status/`, {
      method: "POST",
      body: { action: "connect" },
    });
    codexStatus.value = status;
    if (status.state === "not_installed") {
      throw new Error(
        status.message ||
          "Codex is not installed. Run `pip install -r requirements.txt` in the backend folder and restart.",
      );
    }
    const response = await $fetch(`${apiBaseURL}/codex/login/`, {
      method: "POST",
      body: { mode },
    });
    codexLogin.value = response;
    await openCodexAuthUrl(response.auth_url || response.verification_url);
    if (codexStatusPoll) clearInterval(codexStatusPoll);
    codexStatusPoll = setInterval(() => refreshCodexStatus(), 1500);
  } catch (error) {
    codexStatus.value = {
      state: "runtime_error",
      message: error?.data?.message || error?.message || "Codex sign-in could not start.",
    };
  } finally {
    codexBusy.value = false;
  }
}

async function logoutCodex() {
  codexBusy.value = true;
  try {
    await $fetch(`${apiBaseURL}/codex/logout/`, { method: "POST" });
    codexLogin.value = {};
    codexRateLimits.value = null;
    await refreshCodexStatus();
    await fetchAiModels();
  } finally {
    codexBusy.value = false;
  }
}

async function clearPaperContext() {
  if (
    !confirm(
      "Clear all locally cached paper context? Page images and extracted text will be removed and rebuilt when you open papers again.",
    )
  ) {
    return;
  }

  paperContextClearing.value = true;
  paperContextMessage.value = "";
  paperContextError.value = false;
  try {
    const result = await $fetch(`${apiBaseURL}/paper-context/clear/`, {
      method: "POST",
      body: { include_ai_sessions: true },
    });
    paperContextMessage.value = `Cleared ${result.pages_removed || 0} cached pages and ${result.chunks_removed || 0} search chunks.`;
  } catch (error) {
    paperContextError.value = true;
    paperContextMessage.value =
      error?.data?.message || error?.message || "Could not clear paper context.";
  } finally {
    paperContextClearing.value = false;
  }
}

const appVersionLabel = computed(
  () => updateState.value.currentVersion || "…",
);

const updateStatusBadgeLabel = computed(() => {
  switch (updateState.value.status) {
    case "checking":
      return "Checking";
    case "available":
    case "downloading":
      return "Downloading";
    case "downloaded":
      return "Ready";
    case "up-to-date":
      return "Up to date";
    case "error":
      return "Error";
    case "unavailable":
      return "N/A";
    default:
      return "Desktop";
  }
});

const updateStatusBadgeClass = computed(() => {
  switch (updateState.value.status) {
    case "downloaded":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    case "available":
    case "downloading":
    case "checking":
      return "border-indigo-500/30 bg-indigo-500/10 text-indigo-300";
    case "up-to-date":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    case "error":
      return "border-red-500/30 bg-red-500/10 text-red-300";
    default:
      return "border-white/10 bg-white/5 text-slate-400";
  }
});

const activeTabLabel = computed(
  () => tabs.find((t) => t.id === activeTab.value)?.label
);
const activeTabDescription = computed(() => {
  switch (activeTab.value) {
    case "general":
      return "Customize interface & environment variables.";
    case "updates":
      return "Check for and install app updates.";
    case "scholar":
      return "Manage feeds & keywords.";
    case "ai":
      return "Manage AI-related settings.";
    default:
      return "";
  }
});

const envPotentialList = ref([]);
const envFormValues = ref({});

const envMetadata = {
  GEMINI_API_KEY: {
    description:
      "Used for Gemini chat, embeddings / Smart Collections, and Gemini Vision OCR.",
    type: "password",
  },
  ANTHROPIC_API_KEY: {
    description: "Used for Claude chat models.",
    type: "password",
  },
  OPENAI_API_KEY: {
    description: "Used for OpenAI chat models and OpenAI Vision OCR.",
    type: "password",
  },
  OPENROUTER_API_KEY: {
    description: "Used for OpenRouter chat models.",
    type: "password",
  },
  CUSTOM_AI_BASE_URL: {
    label: "Custom Server Base URL",
    description:
      "OpenAI-compatible API root for a local or self-hosted model server (Ollama, LM Studio, vLLM, etc.). Examples: http://localhost:11434/v1 or http://127.0.0.1:1234/v1.",
    placeholder: "http://localhost:11434/v1",
    type: "text",
  },
  CUSTOM_AI_API_KEY: {
    label: "Custom Server API Key",
    description:
      "Optional Bearer token for your custom server. Leave blank if the server does not require authentication.",
    type: "password",
  },
  MISTRAL_API_KEY: {
    description: "Used for Mistral OCR in the OCR tab.",
    type: "password",
  },
  scholar_inbox_email: {
    label: "Scholar Inbox Email",
    description:
      "The Gmail address that receives your Scholar Inbox Alert Digest emails.",
    placeholder: "you@gmail.com",
    type: "email",
  },
  gmail_app_password: {
    label: "Gmail App Password",
    description:
      "A Gmail App Password for IMAP access — not your regular Gmail password. Create one in Google Account → Security → 2-Step Verification → App passwords.",
    placeholder: "xxxx xxxx xxxx xxxx",
    type: "password",
  },
};

const computedEnvList = computed(() => {
  return envPotentialList.value.map((key) => {
    const meta = envMetadata[key] || {};
    return {
      key: key,
      label: meta.label || key,
      description: meta.description || "",
      placeholder: meta.placeholder || "",
      type: meta.type || "text",
    };
  });
});

// loading previous env vars state
async function loadEnvVars() {
  try {
    const res = await $fetch(`${apiBaseURL}/env-vars/`);
    envPotentialList.value = res.potential_list || [];

    envPotentialList.value.forEach((key) => {
      if (res.variables && res.variables[key]) {
        envFormValues.value[key] = res.variables[key];
      } else if (!envFormValues.value[key]) {
        envFormValues.value[key] = "";
      }
    });
  } catch (error) {
    console.error("Failed to load env vars:", error);
  }
}

const autoImportEnabled = ref(false);
const paperLimitValue = ref(0);
const last_import_date = ref(null);

const paperLimitDisplay = computed(() => {
  if (paperLimitValue.value == 0) return "1 Papers";
  if (paperLimitValue.value == 1) return "5 Papers";
  if (paperLimitValue.value == 2) return "All Papers";
  return "N/A";
});

const amount_to_import = computed(() => {
  if (!autoImportEnabled.value) return 0;
  if (paperLimitValue.value == 0) return 1;
  if (paperLimitValue.value == 1) return 5;
  if (paperLimitValue.value == 2) return "All";
  return 0;
});

async function loadUserPreferences() {
  try {
    const res = await $fetch(`${apiBaseURL}/user-preferences/`);
    const scholarPrefs = res.user_preferences?.scholar_inbox;

    if (scholarPrefs) {
      autoImportEnabled.value = scholarPrefs.auto_import;
      last_import_date.value = scholarPrefs.last_import_date;

      if (scholarPrefs.amount_to_import === 5) {
        paperLimitValue.value = 1;
      } else if (scholarPrefs.amount_to_import === "All") {
        paperLimitValue.value = 2;
      } else {
        paperLimitValue.value = 0;
      }
    }

    const aiPrefs = res.user_preferences?.ai;
    if (aiPrefs) {
      defaultAiProvider.value = aiPrefs.default_provider || defaultAiProvider.value;
      aiModels.value = {
        ...aiModels.value,
        ...(aiPrefs.models || {}),
      };
      const smartCollections = aiPrefs.smart_collections || {};
      smartCollectionEmbeddingProvider.value =
        smartCollections.embedding_provider || smartCollectionEmbeddingProvider.value;
      smartCollectionEmbeddingModels.value = {
        ...smartCollectionEmbeddingModels.value,
        ...(smartCollections.embedding_models || {}),
      };
      smartCollectionGenerationProvider.value =
        smartCollections.generation_provider || smartCollectionGenerationProvider.value;
      const legacyGeminiModels = {
        "gemini-2.5-flash": "gemini-flash-latest",
        "gemini-2.5-flash-lite": "gemini-flash-lite-latest",
        "gemini-2.0-flash": "gemini-flash-latest",
        "gemini-2.0-flash-001": "gemini-flash-latest",
      };
      const savedGenerationModel =
        smartCollections.generation_model || smartCollectionGenerationModel.value;
      smartCollectionGenerationModel.value =
        legacyGeminiModels[savedGenerationModel] || savedGenerationModel;
    }
  } catch (error) {
    console.error("Failed to load user preferences:", error);
  }
}

onMounted(async () => {
  initializeUpdater();
  loadEnvVars();
  loadUserPreferences();
  await initializeAiModels();
  await refreshCodexStatus();
});

onUnmounted(() => {
  teardownUpdater();
  if (codexStatusPoll) clearInterval(codexStatusPoll);
});

async function saveSettings() {
  try {
    const prefsPayload = {
      user_preferences: {
        general: {},
        scholar_inbox: {
          auto_import: autoImportEnabled.value,
          last_import_date: last_import_date.value,
          amount_to_import: amount_to_import.value,
        },
        ai: {
          default_provider: defaultAiProvider.value,
          models: aiModels.value,
          smart_collections: {
            embedding_provider: smartCollectionEmbeddingProvider.value,
            embedding_models: smartCollectionEmbeddingModels.value,
            generation_provider: smartCollectionGenerationProvider.value,
            generation_model: smartCollectionGenerationModel.value,
          },
        },
      },
    };

    const prefsReq = $fetch(`${apiBaseURL}/user-preferences/`, {
      method: "PUT",
      body: { preferences: prefsPayload },
    });

    const envReq = $fetch(`${apiBaseURL}/env-vars/`, {
      method: "PUT",
      body: {
        variables: envFormValues.value,
      },
    });

    await Promise.all([prefsReq, envReq]);

    emit("close");
  } catch (error) {
    console.error("Failed to save settings:", error);
  }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
