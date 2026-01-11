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
            <span class="text-[10px] text-slate-400 font-mono">v1</span>
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
                      class="block font-mono text-xs text-indigo-300 mb-1 tracking-wide"
                    >
                      {{ env.key }}
                    </label>
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
                      :placeholder="`Enter ${env.key}...`"
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
                  Configure sources for your automated research feed. Make sure
                  to set your scholar inbox login environment variable in the
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

          <div v-else-if="activeTab === 'ai'" class="space-y-6 max-w-xl">
            <div class="space-y-3">No AI Preferences available yet.</div>
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

const activeTab = ref("general");
const tabs = [
  { id: "general", label: "General", icon: "uil:setting" },
  { id: "scholar", label: "Scholar Inbox", icon: "uil:envelope-alt" },
  { id: "ai", label: "AI Preferences", icon: "uil:robot" },
];

const activeTabLabel = computed(
  () => tabs.find((t) => t.id === activeTab.value)?.label
);
const activeTabDescription = computed(() => {
  switch (activeTab.value) {
    case "general":
      return "Customize interface & environment variables.";
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

const envMetadata = {};

const computedEnvList = computed(() => {
  return envPotentialList.value.map((key) => {
    const meta = envMetadata[key] || {};
    return {
      key: key,
      description: meta.description || "",
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
  } catch (error) {
    console.error("Failed to load user preferences:", error);
  }
}

onMounted(() => {
  loadEnvVars();
  loadUserPreferences();
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
        ai: {},
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
