<template>
  <div
    class="min-h-screen bg-[#020204] text-white selection:bg-indigo-500/30 font-sans flex flex-col relative overflow-hidden"
  >
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div
        class="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[size:40px_40px] bg-[position:center_bottom] [mask-image:radial-gradient(ellipse_100%_50%_at_50%_10%,#000_70%,transparent_110%)]"
      ></div>
      <div
        class="absolute top-0 left-0 w-[1000px] h-[500px] bg-indigo-600/10 blur-[120px] rounded-full opacity-50"
      ></div>
    </div>

    <nav
      class="flex-none flex items-center justify-between max-w-4xl mx-auto px-6 py-6 z-50 w-full"
    >
      <div class="flex items-center gap-2">
        <div
          class="w-6 h-6 bg-gradient-to-tr from-white to-slate-500 transform rotate-45 rounded-sm"
        ></div>
        <div class="flex flex-col leading-none">
          <span class="font-bold text-lg tracking-tight">Research Marker</span>
          <span
            class="text-[10px] uppercase tracking-wider text-slate-500 font-medium mt-0.5"
            >Settings</span
          >
        </div>
      </div>
    </nav>

    <main
      class="flex-1 flex flex-col relative z-10 w-full max-w-4xl mx-auto px-6 py-8"
    >
      <div class="mb-10">
        <h1 class="text-3xl md:text-4xl font-semibold tracking-tight mb-3">
          Environment
          <span
            class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-400"
            >Configuration</span
          >
        </h1>
        <p class="text-slate-400 text-base leading-relaxed max-w-2xl">
          Manage your local API keys and path configurations. These settings are
          stored locally on your machine and are never synced to the cloud.
          <span class="text-slate-300 block mt-2">
            You don't have to set these now. You can configure them in your
            settings at any time.
          </span>
        </p>
      </div>

      <div class="flex flex-col gap-6">
        <div
          v-for="env in computedEnvList"
          :key="env.key"
          class="group relative rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] p-6 transition-all duration-300"
        >
          <div class="flex flex-col md:flex-row md:items-start gap-6">
            <div class="flex-1 min-w-0">
              <label
                class="block font-mono text-sm text-indigo-300 mb-1 tracking-wide"
              >
                {{ env.key }}
              </label>
              <p
                v-if="env.description"
                class="text-sm text-slate-400 leading-relaxed"
              >
                {{ env.description }}
              </p>
            </div>

            <div class="w-full md:w-[55%] relative">
              <div class="relative">
                <input
                  v-model="formValues[env.key]"
                  :type="env.type"
                  :placeholder="`Enter ${env.key}...`"
                  class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-700 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 focus:bg-white/[0.03] outline-none transition-all font-mono"
                  spellcheck="false"
                />

                <div class="absolute right-3 top-1/2 -translate-y-1/2">
                  <div
                    v-if="formValues[env.key]"
                    class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]"
                  ></div>
                  <div v-else class="w-2 h-2 rounded-full bg-slate-700"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          class="flex items-center justify-end gap-4 mt-4 pt-6 border-t border-white/5"
        >
          <button
            @click="handleSkip"
            class="px-6 py-2.5 rounded-lg text-slate-400 text-sm font-medium hover:text-white hover:bg-white/5 transition-colors"
          >
            Continue without saving
          </button>

          <button
            @click="handleSave"
            class="bg-white text-black px-8 py-2.5 rounded-lg text-sm font-semibold hover:bg-slate-200 transition-colors shadow-[0_0_20px_rgba(255,255,255,0.1)]"
          >
            Save Changes
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const potentialList = ref([]);
const formValues = ref({});

import { storeToRefs } from "pinia";
import { useEnvStateStore } from "~~/stores/useEnvStateStore";

const envStateStore = useEnvStateStore();

// metadata for specific keys
const envMetadata = {
  GEMINI_API_KEY: {
    description:
      "Required for the AI Analysis and semantic linking features. You can get a free trial key from Google as well.",
    type: "text",
  },
  SCHOLAR_INBOX_PERSONAL_LOGIN: {
    description:
      "Required for scraping your daily digest. Copy and paste your magic login link from your Scholar Inbox settings. Scholar Inbox is a free daily research digest tool, available at https://scholar-inbox.com/ (we are not affiliated with this in any way.)",
    type: "text",
  },
};

try {
  const res = await $fetch(`${apiBaseURL}/env-vars/`);
  potentialList.value = res.potential_list || [];

  potentialList.value.forEach((key) => {
    formValues.value[key] = "";
  });
} catch (error) {
  console.error("Failed to check env vars:", error);
}

const computedEnvList = computed(() => {
  return potentialList.value.map((key) => {
    const meta = envMetadata[key] || {};
    return {
      key: key,
      description: meta.description || "", // Empty if no description exists
      type: meta.type || "text",
    };
  });
});

const handleSave = async () => {
  try {
    const res = await $fetch(`${apiBaseURL}/env-vars/`, {
      method: "PUT",
      body: {
        variables: formValues.value,
      },
    });
  } catch (error) {
    console.log(`error saving ${error}`);
  } finally {
    envStateStore.setExists(true);
    await navigateTo("/dashboard");
  }
};

const handleSkip = async () => {
  console.log("Skipping setup");
  try {
    const res = await $fetch(`${apiBaseURL}/env-vars/`, {
      method: "PUT",
      body: {
        variables: { exists: true },
      },
    });
  } catch (error) {
    console.log(`error saving ${error}`);
  } finally {
    envStateStore.setExists(true);
    await navigateTo("/dashboard");
  }
};
</script>
