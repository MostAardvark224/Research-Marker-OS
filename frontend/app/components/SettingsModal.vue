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

              <div
                v-for="provider in aiProviders"
                :key="provider.id"
                class="p-4 rounded-xl border border-white/10 bg-white/[0.02] space-y-2"
              >
                <div class="flex items-center justify-between gap-3">
                  <label class="block font-mono text-xs text-indigo-300">
                    {{ provider.label }} Model
                  </label>
                  <span
                    v-if="provider.error"
                    class="text-[10px] text-amber-400 truncate"
                    :title="provider.error"
                  >
                    {{ provider.error }}
                  </span>
                </div>
                <select
                  v-model="aiModels[provider.id]"
                  class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 outline-none"
                  :disabled="!provider.models?.length"
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
                  :placeholder="`Custom ${provider.label} model id...`"
                  spellcheck="false"
                />
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
  aiModels,
  selectedAiProvider: defaultAiProvider,
  selectedProviderModels,
  initializeAiModels,
  fetchAiModels,
  aiModelsLoading,
} = useAiModels();

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
});

onUnmounted(() => {
  teardownUpdater();
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
