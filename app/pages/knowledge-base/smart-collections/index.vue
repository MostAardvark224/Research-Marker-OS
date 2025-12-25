<template>
  <div
    class="min-h-screen bg-[#020204] text-white font-sans overflow-hidden flex flex-col"
  >
    <nav class="border-b border-white/5 bg-[#020204]/80 backdrop-blur-md z-50">
      <div
        class="max-w-[1920px] mx-auto px-6 py-4 flex items-center justify-between"
      >
        <div class="flex items-center gap-2">
          <div
            class="w-5 h-5 bg-gradient-to-tr from-white to-slate-500 transform rotate-45 rounded-sm"
          ></div>
          <span class="font-bold tracking-tight">Research Marker</span>
        </div>

        <NuxtLink
          to="/dashboard"
          class="text-xs font-semibold uppercase tracking-widest text-slate-500 hover:text-white transition-colors flex items-center gap-2"
        >
          <Icon name="uil:arrow-left" />
          Back to Index
        </NuxtLink>
      </div>
    </nav>

    <div class="flex flex-1 overflow-hidden relative">
      <div
        class="absolute top-0 right-0 w-[600px] h-[600px] bg-purple-600/10 blur-[120px] rounded-full opacity-30 pointer-events-none"
      ></div>
      <div
        class="absolute bottom-0 left-0 w-[500px] h-[500px] bg-blue-600/5 blur-[100px] rounded-full opacity-20 pointer-events-none"
      ></div>

      <main
        class="flex-1 p-8 lg:p-12 overflow-y-auto relative custom-scrollbar flex flex-col"
      >
        <div
          v-if="hasData"
          class="max-w-7xl mx-auto w-full relative z-10 animate-fade-in"
        >
          {{ data }}
        </div>

        <div
          v-else
          class="flex-1 flex flex-col items-center justify-center text-center relative z-10 max-w-2xl mx-auto"
        >
          <div class="relative mb-8 group">
            <div
              class="absolute inset-0 bg-purple-500/20 blur-xl rounded-full group-hover:bg-purple-500/30 transition-all duration-700"
            ></div>
            <div
              class="relative w-24 h-24 rounded-2xl bg-gradient-to-b from-white/10 to-transparent border border-white/10 flex items-center justify-center backdrop-blur-sm"
            >
              <Icon
                name="carbon:network-4"
                class="text-5xl text-purple-300 opacity-80"
              />
            </div>

            <div
              class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 border border-white/5 rounded-full animate-[spin_10s_linear_infinite]"
            ></div>
            <div
              class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-40 h-40 border border-dashed border-white/5 rounded-full animate-[spin_15s_linear_infinite_reverse]"
            ></div>
          </div>

          <h1 class="text-4xl md:text-5xl font-bold tracking-tight mb-6">
            Initialize your
            <span
              class="block mt-2 text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 animate-gradient"
            >
              Smart Collection
            </span>
          </h1>

          <div class="flex flex-col items-center w-full max-w-md">
            <button
              @click="RunSmartCollection()"
              :disabled="isInitializing"
              class="group relative w-full overflow-hidden rounded-xl bg-white text-black font-semibold py-4 px-8 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-70 disabled:pointer-events-none mb-6"
            >
              <div
                class="absolute inset-0 bg-gradient-to-r from-purple-200 via-white to-purple-200 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
              ></div>
              <span class="relative flex items-center justify-center gap-2">
                <Icon
                  v-if="isInitializing"
                  name="line-md:loading-twotone-loop"
                  class="text-xl"
                />
                <Icon v-else name="uil:processor" class="text-xl" />
                {{
                  isInitializing
                    ? "Constructing Graph..."
                    : "Initialize Smart Collection"
                }}
              </span>
            </button>

            <div class="w-full space-y-3">
              <div
                class="flex items-start gap-3 p-4 rounded-lg bg-blue-500/5 border border-blue-500/10 text-left"
              >
                <Icon
                  name="uil:info-circle"
                  class="text-blue-400 text-xl shrink-0 mt-0.5"
                />
                <div class="text-xs text-slate-400">
                  <strong class="text-slate-300 block mb-0.5"
                    >Minimum Data Recommended</strong
                  >
                  For the most effective graph generation and clustering, we
                  recommend having at least
                  <span class="text-blue-300 font-medium">15+ annotations</span>
                  in your index before initializing.
                </div>
              </div>

              <div
                class="flex items-start gap-3 p-4 rounded-lg bg-yellow-500/5 border border-yellow-500/10 text-left"
              >
                <Icon
                  name="uil:clock"
                  class="text-yellow-500/60 text-xl shrink-0 mt-0.5"
                />
                <div class="text-xs text-slate-400">
                  <strong class="text-slate-300 block mb-0.5"
                    >Time intensive process</strong
                  >
                  Initialization involves deep-layer semantic embedding.
                  Depending on your dataset size, this may take
                  <span class="text-yellow-500/80">3-5 minutes</span> to
                  complete.
                </div>
              </div>

              <div
                class="flex items-start gap-3 p-4 rounded-lg bg-green-500/5 border border-green-500/10 text-left"
              >
                <Icon
                  name="mdi:cog-play"
                  class="text-green-500/60 text-xl shrink-0 mt-0.5"
                />
                <div class="text-xs text-slate-400">
                  <strong class="text-slate-300 block mb-0.5"
                    >Runs In The Background</strong
                  >
                  The creation process will
                  <span class="text-green-500/80">run in the background</span>,
                  so feel free to navigate away from this page. However, don't
                  close the application.
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
const {
  public: { apiBaseURL },
} = useRuntimeConfig();

/*
Getting data logic (ONLY FOR INIT SMART COLLECTION BUTTON, Logic for when a user requests an update after graph is built is a different topic):
- this runs when component is mounted

Send a request to the polling endpoint.
- if response == suceeded: hit data endpoint and render
- if response == queued: means that job is underway. Keep hitting this endpoint every 10 secs and eventually it will return suceeded and render.
- if response == not initialized: send post request to endpoint and then continuously poll.

General - separate each call into a func so that its easy to manage from one command center
*/

const data = ref(null);

// Computed property to check if the collection exists
// once this is true run rendering log
const hasData = computed(() => {
  return data.value && Object.keys(data.value).length > 0;
});

const poll_state = ref("");
// Helper to pause execution
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function pollBackend() {
  try {
    const res = await $fetch(`${apiBaseURL}/poll-smart-collection/`);
    poll_state.value = res.state;
  } catch (err) {
    alert("Failed to poll backend:", err);
    window.location.reload();
    return;
  }
}

const POLL_INTERVAL = 10000; // 10 seconds
const MAX_DURATION = 10 * 60 * 1000; // 10 minutes in ms

// polling backend every 10s until we get poll_state.value == suceeded
// 10 min timeout
async function continuouslyPollBackend() {
  store.setInitializing(true);
  const startTime = Date.now();

  while (poll_state.value !== "success") {
    if (Date.now() - startTime > MAX_DURATION) {
      store.setInitializing(false);
      alert("The operation timed out after 10 minutes.");
      return;
    }

    await sleep(POLL_INTERVAL);
    await pollBackend();
  }

  // get data now, because assumed that polling has succeeded
  if (poll_state.value == "success") {
    await getData();
    store.setInitializing(false);
  }
}

async function RunSmartCollection() {
  store.setInitializing(true);
  try {
    await $fetch(`${apiBaseURL}/smart-collection/`, {
      method: "POST",
    });
  } catch (err) {
    store.setInitializing(false);
    alert("Failed to start collection:", err);
    return;
  }

  await continuouslyPollBackend();
  store.setInitializing(false);
}

async function getData() {
  try {
    const res = await $fetch(`${apiBaseURL}/smart-collection/`);
    data.value = res.data;
  } catch (err) {
    alert("Failed to fetch data:", err);
    return;
  } finally {
    store.setInitializing(false);
  }
}

// runs logic from notes at beginning of script
async function initDataLogic() {
  if (isInitializing.value) {
    await continuouslyPollBackend();
    return;
  }

  await pollBackend();
  if (poll_state.value == "success") {
    await getData();
  } else if (poll_state.value == "queued") {
    await continuouslyPollBackend();
  } else if (poll_state.value != "not initialized") {
    console.log(`poll state value when error: ${poll_state.value}`);
    alert("issue with data logic in onMounted component.");
  }
}

onMounted(() => {
  initDataLogic();
});

// pinia store for initializing state
import { useSmartCollectionsStore } from "~~/stores/useSmartCollectionsStore";
import { storeToRefs } from "pinia";

const store = useSmartCollectionsStore();

const { isInitializing } = storeToRefs(store);
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

@keyframes gradient {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

.animate-gradient {
  background-size: 200% auto;
  animation: gradient 8s ease infinite;
}

.animate-fade-in {
  animation: fadeIn 0.5s ease-out forwards;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
