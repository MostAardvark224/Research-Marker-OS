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
          class="fixed inset-0 z-50 flex bg-[#020204] animate-fade-in"
        >
          <aside
            class="relative z-20 flex h-screen shrink-0 flex-col border-r border-white/10 bg-[#050508] transition-all duration-300 ease-in-out group/sidebar"
            :class="[isSidebarOpen ? 'w-[30%]' : 'w-0 border-r-0']"
          >
            <button
              @click="toggleSidebar"
              class="absolute -right-3 top-16 z-50 flex h-6 w-6 cursor-pointer items-center justify-center rounded-full border border-white/10 bg-[#050508] text-white/40 shadow-xl backdrop-blur-sm transition-all hover:scale-110 hover:border-purple-500 hover:text-white"
              :class="{ 'opacity-0 pointer-events-none': !isSidebarOpen }"
              title="Collapse Sidebar"
            >
              <Icon name="uil:angle-left" class="text-sm" />
            </button>

            <button
              v-if="!isSidebarOpen"
              @click="toggleSidebar"
              class="absolute -right-8 top-16 z-50 flex h-8 w-8 cursor-pointer items-center justify-center rounded-r-lg border-y border-r border-white/10 bg-[#050508] text-white/40 shadow-xl transition-all hover:w-10 hover:text-purple-400"
              title="Expand Sidebar"
            >
              <Icon name="uil:angle-right" class="text-lg" />
            </button>

            <div
              v-show="isSidebarOpen"
              class="flex h-full w-full flex-col overflow-hidden"
            >
              <div class="flex flex-col border-b border-white/5 bg-[#050508]">
                <div class="flex items-center gap-3 px-6 py-6">
                  <div
                    class="h-8 w-8 shrink-0 rounded-md bg-gradient-to-tr from-purple-500 to-blue-500 shadow-lg shadow-purple-500/20"
                  ></div>
                  <div class="flex flex-col animate-fade-in">
                    <span class="text-sm font-bold tracking-wide"
                      >Research Marker</span
                    >
                    <span
                      class="text-[10px] uppercase tracking-wider text-slate-500"
                    >
                      By Amay Babel
                    </span>
                  </div>
                </div>

                <div class="flex items-center px-4 gap-1">
                  <button
                    v-for="tab in tabs"
                    :key="tab.id"
                    @click="setActiveTab(tab.id)"
                    class="relative flex flex-1 items-center justify-center gap-2 rounded-md py-2.5 text-xs font-medium transition-all"
                    :class="[
                      activeTab === tab.id
                        ? 'bg-white/5 text-white shadow-sm'
                        : 'text-slate-500 hover:bg-white/5 hover:text-slate-300',
                    ]"
                  >
                    <Icon :name="tab.icon" class="text-base" />
                    <!-- {{ tab.label }} -->

                    <div
                      v-if="activeTab === tab.id"
                      class="absolute -bottom-[1px] left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-purple-500 to-transparent opacity-50"
                    ></div>
                  </button>
                </div>
              </div>

              <div
                class="flex-1 overflow-y-auto overflow-x-hidden px-6 py-6 relative"
              >
                <div
                  v-if="activeTab === 'graph'"
                  class="animate-fade-in h-full flex flex-col"
                >
                  <h2
                    class="text-lg font-medium text-purple-400 mb-4 flex items-center gap-2 shrink-0"
                  >
                    <Icon name="uil:sitemap" /> Graph Explorer
                  </h2>

                  <div
                    class="flex-1 overflow-y-auto custom-scrollbar -mr-2 pr-2"
                  >
                    <div
                      v-for="(subTopics, majorName) in graphExplorerData"
                      :key="majorName"
                      class="mb-4"
                    >
                      <button
                        @click="toggleNode(majorName)"
                        class="w-full flex items-center gap-2 text-sm font-semibold text-slate-200 hover:text-purple-300 transition-colors text-left group"
                      >
                        <Icon
                          name="uil:angle-right"
                          class="transition-transform duration-200 text-slate-500 group-hover:text-purple-400"
                          :class="{ 'rotate-90': expandedNodes[majorName] }"
                        />
                        <Icon name="uil:folder" class="text-purple-500/50" />
                        {{ majorName }}
                        <span
                          class="ml-auto text-[10px] text-slate-600 font-mono"
                        >
                          {{ Object.keys(subTopics).length }}
                        </span>
                      </button>

                      <div
                        v-show="expandedNodes[majorName]"
                        class="mt-1 ml-2 pl-3 border-l border-white/5 space-y-1"
                      >
                        <div
                          v-for="(papers, subName) in subTopics"
                          :key="majorName + subName"
                        >
                          <button
                            @click="toggleNode(majorName + subName)"
                            class="w-full flex items-center gap-2 py-1 text-xs font-medium text-slate-400 hover:text-white transition-colors text-left group/sub"
                          >
                            <Icon
                              name="uil:angle-right"
                              class="transition-transform duration-200 text-slate-600 group-hover/sub:text-white"
                              :class="{
                                'rotate-90': expandedNodes[majorName + subName],
                              }"
                            />
                            {{ subName }}
                          </button>

                          <div
                            v-show="expandedNodes[majorName + subName]"
                            class="mt-1 ml-2 pl-3 border-l border-white/5 space-y-0.5"
                          >
                            <div
                              v-for="paper in papers"
                              :key="paper.id"
                              @click="focusOnPaper(paper.id)"
                              class="group/paper flex items-start gap-2 py-1 cursor-pointer"
                            >
                              <div
                                class="mt-1.5 w-1 h-1 rounded-full bg-slate-700 group-hover/paper:bg-blue-400 transition-colors shrink-0"
                              ></div>
                              <span
                                class="text-[11px] text-slate-500 leading-snug group-hover/paper:text-slate-300 transition-colors line-clamp-2"
                              >
                                {{ paper.title }}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div
                      v-if="Object.keys(graphExplorerData).length === 0"
                      class="text-center mt-10 text-slate-600 text-xs italic"
                    >
                      No graph data available.
                      <br />Initialize collection to view structure.
                    </div>
                  </div>
                </div>
                <div
                  v-else-if="activeTab === 'chat'"
                  class="animate-fade-in h-full"
                >
                  <h2
                    class="text-lg font-medium text-purple-400 mb-4 flex items-center gap-2"
                  >
                    <Icon name="uil:comment-alt-lines" /> Research Chat
                  </h2>
                </div>

                <div
                  v-else-if="activeTab === 'recs'"
                  class="animate-fade-in h-full flex flex-col"
                >
                  <div class="flex items-center justify-between mb-4 shrink-0">
                    <h2
                      class="text-lg font-medium text-purple-400 flex items-center gap-2"
                    >
                      <Icon name="uil:lightbulb-alt" /> Recommendations
                    </h2>

                    <button
                      @click="regenerateRecommendations"
                      :disabled="isRegenerating"
                      class="p-1.5 rounded-md hover:bg-white/10 text-slate-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed group relative"
                      title="Regenerate Recommendations"
                    >
                      <Icon
                        name="uil:refresh"
                        class="text-lg transition-transform duration-700"
                        :class="{ 'animate-spin': isRegenerating }"
                      />
                    </button>
                  </div>

                  <div
                    class="flex-1 overflow-y-auto custom-scrollbar -mr-2 pr-2"
                  >
                    <div
                      v-if="isRegenerating"
                      class="h-40 flex flex-col items-center justify-center text-slate-500 gap-3"
                    >
                      <Icon name="svg-spinners:3-dots-fade" class="text-2xl" />
                      <span class="text-xs">Analyzing knowledge graph...</span>
                    </div>

                    <div
                      v-else-if="!hasRecs"
                      class="text-center mt-10 text-slate-600 text-xs italic"
                    >
                      No recommendations yet.
                      <br />Click the refresh button to generate insights.
                    </div>

                    <div v-else class="space-y-6 pb-6">
                      <div
                        v-for="(details, topicName) in readingRecs"
                        :key="topicName"
                        class="group relative pl-4 border-l-2 border-white/10 hover:border-purple-500/50 transition-colors"
                      >
                        <h3
                          class="text-sm font-semibold text-slate-200 mb-1 group-hover:text-purple-300 transition-colors"
                        >
                          {{ topicName }}
                        </h3>

                        <p class="text-xs text-slate-400 mb-3 leading-relaxed">
                          {{ details.overview }}
                        </p>

                        <div class="space-y-2">
                          <div
                            class="flex items-start gap-2 bg-white/5 rounded-md p-2 hover:bg-white/10 transition-colors cursor-default"
                          >
                            <Icon
                              name="uil:file-alt"
                              class="text-blue-400 mt-0.5 shrink-0 text-xs"
                            />
                            <span
                              class="text-[11px] text-slate-300 font-medium leading-tight"
                            >
                              {{ details.paper1 }}
                            </span>
                          </div>

                          <div
                            class="flex items-start gap-2 bg-white/5 rounded-md p-2 hover:bg-white/10 transition-colors cursor-default"
                          >
                            <Icon
                              name="uil:file-alt"
                              class="text-blue-400 mt-0.5 shrink-0 text-xs"
                            />
                            <span
                              class="text-[11px] text-slate-300 font-medium leading-tight"
                            >
                              {{ details.paper2 }}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div
                class="mt-auto flex w-full flex-col gap-4 p-6 shrink-0 border-t border-white/5"
              >
                <NuxtLink
                  to="/dashboard"
                  class="flex h-10 w-full items-center justify-start gap-3 overflow-hidden whitespace-nowrap rounded-lg px-3 text-white/40 transition-all hover:bg-white/5 hover:text-white"
                >
                  <Icon name="uil:arrow-left" class="text-xl shrink-0" />
                  <span class="text-xs font-semibold uppercase tracking-widest">
                    Back to Index
                  </span>
                </NuxtLink>
              </div>
            </div>
          </aside>
          <div
            class="flex-1 flex flex-col relative overflow-hidden bg-[#020204]"
          >
            <header
              class="h-14 border-b border-white/5 flex items-center justify-between px-6 bg-[#020204]/90 backdrop-blur-sm z-10 absolute top-0 left-0 right-0 pointer-events-none"
            >
              <div class="flex items-center gap-3 pointer-events-auto">
                <h2 class="font-semibold text-sm tracking-wide text-white">
                  Knowledge Graph
                </h2>
                <span
                  class="px-2 py-0.5 mt-1 rounded-full bg-purple-500/10 text-purple-400 text-[10px] font-medium border border-purple-500/20"
                  >Beta</span
                >
              </div>
              <button
                @click="updateSmartCollection()"
                class="pointer-events-auto flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-slate-300 hover:text-white hover:border-white/20 transition-all group"
              >
                <Icon
                  name="uil:sync"
                  class="text-sm text-slate-400 group-hover:text-white transition-colors"
                  :class="{ 'animate-spin': isInitializing }"
                />
                Update Collection
              </button>
            </header>

            <div
              ref="graphContainer"
              class="w-full h-full cursor-grab active:cursor-grabbing"
            ></div>

            <div class="absolute bottom-6 right-6 flex flex-col gap-2 z-10">
              <button
                @click="resetZoom"
                class="w-10 h-10 rounded-lg bg-[#1e1e24] hover:bg-[#2a2a35] text-white flex items-center justify-center border border-white/10 transition-colors shadow-xl"
                title="Reset View"
              >
                <Icon name="uil:focus-target" class="text-lg" />
              </button>
            </div>
          </div>
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
                  <span class="text-blue-300 font-medium"
                    >20-25+ annotations</span
                  >
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
import * as d3 from "d3";
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

  poll_state.value = "queued"; // state resetter
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

  if (data.value) {
    await getRecommendations();
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

// logic for updating smart collection
async function updateSmartCollection() {
  if (isInitializing.value) {
    await continuouslyPollBackend();
    return;
  }

  await RunSmartCollection();
}

// pinia store for initializing state
import { useSmartCollectionsStore } from "~~/stores/useSmartCollectionsStore";
import { storeToRefs } from "pinia";

const store = useSmartCollectionsStore();

const { isInitializing } = storeToRefs(store);

// sidebar logic
const isSidebarOpen = ref(true);

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value;
};

watch(isSidebarOpen, () => {
  setTimeout(() => {
    // Recalculate SVG scales for new width
    initGraph();
  }, 320);
});

const activeTab = ref("graph");

const tabs = [
  { id: "graph", label: "Graph Explorer", icon: "uil:sitemap" },
  // { id: "chat", label: "Research Chat", icon: "uil:comment-alt-lines" },
  { id: "recs", label: "Recommendations", icon: "uil:lightbulb-alt" },
];

const setActiveTab = (id) => {
  if (!isSidebarOpen.value) {
    isSidebarOpen.value = true;
  }
  activeTab.value = id;
};

/*
graph explorer logic
data object will look like this
{
  major : {
    sub : {
      paper titles
    }
  }
}
*/

const expandedNodes = ref({});

const toggleNode = (key) => {
  expandedNodes.value[key] = !expandedNodes.value[key];
};

const graphExplorerData = computed(() => {
  if (!data.value) return {};

  let hierarchy = {};

  if (data.value) {
    data.value.forEach((paper) => {
      if (paper.major_topic && paper.sub_topic && paper.doc_title) {
        if (!hierarchy[paper.major_topic]) {
          hierarchy[paper.major_topic] = {};
        }

        if (!hierarchy[paper.major_topic][paper.sub_topic]) {
          hierarchy[paper.major_topic][paper.sub_topic] = [];
        }

        hierarchy[paper.major_topic][paper.sub_topic].push({
          id: paper.id,
          title: paper.doc_title,
        });
      }
    });
  }

  return hierarchy;
});

// when a paper title is clicked in sidebar, this takes user to that point on the screen
const focusOnPaper = (paperId) => {
  // safety checks
  if (!svg || !zoom || !data.value || !graphContainer.value) return;

  const paper = data.value.find((p) => p.id === paperId);
  if (!paper) return;

  const { clientWidth: width, clientHeight: height } = graphContainer.value;

  // clean data for domain calculation
  const { papers } = processGraphData(data.value);

  const xExtent = d3.extent(papers, (d) => d.x);
  const yExtent = d3.extent(papers, (d) => d.y);

  const xPadding = (xExtent[1] - xExtent[0]) * 0.1;
  const yPadding = (yExtent[1] - yExtent[0]) * 0.1;

  const xScale = d3
    .scaleLinear()
    .domain([xExtent[0] - xPadding, xExtent[1] + xPadding])
    .range([0, width]);

  const yScale = d3
    .scaleLinear()
    .domain([yExtent[0] - yPadding, yExtent[1] + yPadding])
    .range([height, 0]);

  // calculate target coordinates on screen
  const targetX = xScale(paper.x_coordinate);
  const targetY = yScale(paper.y_coordinate);
  const targetScale = 6; // zoom scale

  svg
    .transition()
    .duration(1500)
    .call(
      zoom.transform,
      d3.zoomIdentity
        .translate(width / 2, height / 2)
        .scale(targetScale) // Zoom level
        .translate(-targetX, -targetY)
    );
};

// research chat

/* recommendations 
This section gives the user recommendations on NEW topics that they should into based on current knowledge.

note to self: need to format json obj to look nice to the user
- also implement the regen button
*/

// getting recs
const readingRecs = ref({});
const isRegenerating = ref(false);
const hasRecs = computed(() => {
  return readingRecs.value && Object.keys(readingRecs.value).length > 0;
});

async function getRecommendations() {
  try {
    const res = await $fetch(`${apiBaseURL}/reading-recommendations/`);
    readingRecs.value =
      typeof res.recommendations === "string"
        ? JSON.parse(res.recommendations)
        : res.recommendations;
  } catch {
    console.error("Failed to fetch recs", err);
  }
}

// regenerating recs
async function newRecommendations() {
  if (isRegenerating.value) return;

  isRegenerating.value = true;
  try {
    const res = await $fetch(`${apiBaseURL}/reading-recommendations/`, {
      method: "POST",
    });
    await getRecommendations();
  } catch {
    console.error("Failed to generate new recs", err);
  } finally {
    isRegenerating.value = false;
  }
}

async function regenerateRecommendations() {
  await newRecommendations();
  await getRecommendations();
}

// GRAPH LOGIC

const graphContainer = ref(null);
let svg, g, zoom; // D3 variables

// calculating geometric centers of major and sub clusters
const processGraphData = (rawData) => {
  if (!rawData) return { papers: [], majorClusters: [], subClusters: [] };

  const papers = rawData.map((d) => ({
    id: d.id,
    title: d.doc_title,
    x: d.x_coordinate,
    y: d.y_coordinate,
    major: d.major_topic,
    sub: d.sub_topic,
  }));

  // calculating centers for major and sub
  const majorMap = {};
  papers.forEach((p) => {
    if (!majorMap[p.major]) majorMap[p.major] = { xSum: 0, ySum: 0, count: 0 };
    majorMap[p.major].xSum += p.x;
    majorMap[p.major].ySum += p.y;
    majorMap[p.major].count++;
  });

  const majorClusters = Object.keys(majorMap).map((key) => ({
    label: key,
    x: majorMap[key].xSum / majorMap[key].count,
    y: majorMap[key].ySum / majorMap[key].count,
  }));

  const subMap = {};
  papers.forEach((p) => {
    if (!subMap[p.sub]) subMap[p.sub] = { xSum: 0, ySum: 0, count: 0 };
    subMap[p.sub].xSum += p.x;
    subMap[p.sub].ySum += p.y;
    subMap[p.sub].count++;
  });

  const subClusters = Object.keys(subMap).map((key) => ({
    label: key,
    x: subMap[key].xSum / subMap[key].count,
    y: subMap[key].ySum / subMap[key].count,
  }));

  return { papers, majorClusters, subClusters };
};

const initGraph = () => {
  if (!graphContainer.value || !data.value) return;

  d3.select(graphContainer.value).selectAll("*").remove();

  const { clientWidth: width, clientHeight: height } = graphContainer.value;
  const { papers, majorClusters, subClusters } = processGraphData(data.value);

  svg = d3
    .select(graphContainer.value)
    .append("svg")
    .attr("width", "100%")
    .attr("height", "100%")
    .attr("viewBox", [0, 0, width, height])
    .style("background-color", "#020204");

  const xExtent = d3.extent(papers, (d) => d.x);
  const yExtent = d3.extent(papers, (d) => d.y);

  const xPadding = (xExtent[1] - xExtent[0]) * 0.1;
  const yPadding = (yExtent[1] - yExtent[0]) * 0.1;

  const xScale = d3
    .scaleLinear()
    .domain([xExtent[0] - xPadding, xExtent[1] + xPadding])
    .range([0, width]);

  const yScale = d3
    .scaleLinear()
    .domain([yExtent[0] - yPadding, yExtent[1] + yPadding])
    .range([height, 0]);

  g = svg.append("g");

  // render layers

  // Layer 1: Papers (Visible at High Zoom)
  const paperGroup = g.append("g").attr("class", "layer-papers");

  // Dots
  paperGroup
    .selectAll("circle")
    .data(papers)
    .join("circle")
    .attr("cx", (d) => xScale(d.x))
    .attr("cy", (d) => yScale(d.y))
    .attr("r", 3)
    .attr("fill", "#60a5fa") // Blue-400
    .attr("opacity", 0.6);

  // Titles
  paperGroup
    .selectAll("text")
    .data(papers)
    .join("text")
    .attr("x", (d) => xScale(d.x))
    .attr("y", (d) => yScale(d.y) - 8)
    .text((d) => d.title)
    .attr("text-anchor", "middle")
    .attr("font-size", "4px")
    .attr("fill", "#94a3b8")
    .style("opacity", 0);

  // layer 2: sub topics (visible at medium zoom)
  const subGroup = g.append("g").attr("class", "layer-sub").style("opacity", 0);

  subGroup
    .selectAll("text")
    .data(subClusters)
    .join("text")
    .attr("x", (d) => xScale(d.x))
    .attr("y", (d) => yScale(d.y))
    .text((d) => d.label)
    .attr("text-anchor", "middle")
    .attr("font-size", "12px")
    .attr("font-weight", "600")
    .attr("fill", "#c084fc")
    .style("text-shadow", "0 2px 4px rgba(0,0,0,0.8)");

  // layer 3: major topics (visible at low zoom/default)
  const majorGroup = g
    .append("g")
    .attr("class", "layer-major")
    .style("opacity", 1);

  majorGroup
    .selectAll("text")
    .data(majorClusters)
    .join("text")
    .attr("x", (d) => xScale(d.x))
    .attr("y", (d) => yScale(d.y))
    .text((d) => d.label)
    .attr("text-anchor", "middle")
    .attr("font-size", "24px")
    .attr("font-weight", "bold")
    .attr("fill", "#e2e8f0")
    .style("text-shadow", "0 4px 12px rgba(0,0,0,0.9)");

  // zoom logic
  zoom = d3
    .zoom()
    .scaleExtent([0.5, 20]) // Max zoom out / Max zoom in
    .on("zoom", (event) => {
      const { transform } = event;
      g.attr("transform", transform);
      updateSemanticZoom(transform.k);
    });

  svg.call(zoom).on("dblclick.zoom", null); // Disable double click zoom

  // Initial Zoom to fit content
  resetZoom();
};

// Controls visibility based on zoom level (k)
const updateSemanticZoom = (k) => {
  const subLayer = g.select(".layer-sub");
  const majorLayer = g.select(".layer-major");

  const paperText = g.selectAll(".layer-papers text");

  // Transition Logic
  // Major: visible < 1.5
  // Sub: visible 1.5 -> 3.5
  // Papers: visible > 3.5

  // Smooth transitions using opacity
  majorLayer
    .transition()
    .duration(200)
    .style("opacity", k < 3.0 ? 1 : 0.1);
  subLayer
    .transition()
    .duration(200)
    .style("opacity", k >= 1.8 ? 1 : 0);
  paperText
    .transition()
    .duration(200)
    .style("opacity", k >= 4.0 ? 1 : 0);
};

const resetZoom = () => {
  if (!svg || !zoom || !graphContainer.value) return;
  // Reset to identity (scale 1) centered
  // might have calculate exact bounds to fit
  const { clientWidth: width, clientHeight: height } = graphContainer.value;

  svg
    .transition()
    .duration(750)
    .call(
      zoom.transform,
      d3.zoomIdentity
        .translate(width / 2, height / 2)
        .scale(1)
        .translate(-width / 2, -height / 2)
    );

  // Since domain is mapped to range, scale 1 fits the view exactly
};

onMounted(() => {
  if (hasData.value) {
    nextTick(() => initGraph());
  }
});

watch(hasData, (newVal) => {
  if (newVal) {
    nextTick(() => initGraph());
  }
});
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

.animate-fade-in {
  animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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
</style>
