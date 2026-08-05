<template>
  <div
    class="min-h-screen bg-[#020204] text-white font-sans overflow-hidden flex flex-col"
  >
    <nav class="border-b border-white/5 bg-[#020204]/80 backdrop-blur-md z-50">
      <div
        class="relative max-w-[1920px] mx-auto px-6 py-4 flex items-center justify-center"
      >
        <div class="absolute left-6 flex items-center gap-2">
          <div
            class="w-5 h-5 bg-gradient-to-tr from-white to-slate-500 transform rotate-45 rounded-sm"
          ></div>
          <span class="font-bold tracking-tight">Research Marker</span>
        </div>

        <NuxtLink
          to="/"
          class="inline-flex items-center gap-2.5 rounded-xl border border-indigo-400/30 bg-indigo-500 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-indigo-500/30 transition-all hover:bg-indigo-400 hover:shadow-indigo-400/40 active:scale-[0.98]"
        >
          <Icon name="uil:arrow-left" class="text-lg shrink-0" />
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
          v-if="isInitializing || requestError || jobStatus?.warnings?.length"
          class="fixed right-6 top-20 z-[80] w-[min(420px,calc(100vw-3rem))] rounded-xl border border-white/10 bg-[#08080c]/95 p-4 shadow-2xl backdrop-blur-md"
        >
          <template v-if="isInitializing">
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="text-sm font-medium text-white">Updating Smart Collection</p>
                <p class="mt-1 text-xs capitalize text-slate-400">
                  {{ jobStatus?.stage || "queued" }} · {{ jobStatus?.processed_items || 0 }} /
                  {{ jobStatus?.total_items || 0 }}
                </p>
              </div>
              <button
                @click="cancelSmartCollection"
                class="rounded-lg border border-white/10 px-2.5 py-1 text-[11px] text-slate-400 hover:border-red-400/30 hover:text-red-300"
              >
                Cancel
              </button>
            </div>
            <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div
                class="h-full rounded-full bg-purple-500 transition-all duration-500"
                :style="{ width: `${jobStatus?.progress || 0}%` }"
              ></div>
            </div>
          </template>
          <template v-else-if="requestError">
            <p class="text-sm font-medium text-red-300">Smart Collection failed</p>
            <p class="mt-1 text-xs leading-relaxed text-slate-400">{{ requestError }}</p>
            <button
              @click="RunSmartCollection"
              class="mt-3 rounded-lg border border-red-400/20 bg-red-400/10 px-3 py-1.5 text-xs text-red-200 hover:bg-red-400/15"
            >
              Retry
            </button>
          </template>
          <template v-else>
            <p class="text-sm font-medium text-amber-300">Collection completed with warnings</p>
            <p
              v-for="warning in jobStatus.warnings"
              :key="warning"
              class="mt-1 text-xs leading-relaxed text-slate-400"
            >
              {{ warning }}
            </p>
          </template>
        </div>

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
                          <template v-if="subName !== '__direct__'">
                            <button
                              @click="toggleNode(majorName + subName)"
                              class="w-full flex items-center gap-2 py-1 text-xs font-medium text-slate-400 hover:text-white transition-colors text-left group/sub"
                            >
                              <Icon
                                name="uil:angle-right"
                                class="transition-transform duration-200 text-slate-600 group-hover/sub:text-white"
                                :class="{
                                  'rotate-90':
                                    expandedNodes[majorName + subName],
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
                          </template>

                          <template v-else>
                            <div
                              class="mt-1 ml-2 pl-3 border-l border-white/5 space-y-0.5 mb-2"
                            >
                              <div
                                v-for="paper in papers"
                                :key="paper.id"
                                @click="focusOnPaper(paper.id)"
                                class="group/paper flex items-start gap-2 py-1 cursor-pointer"
                              >
                                <div
                                  class="mt-1.5 w-1 h-1 rounded-full bg-purple-500/50 group-hover/paper:bg-purple-400 transition-colors shrink-0"
                                ></div>
                                <span
                                  class="text-[11px] text-slate-400 leading-snug group-hover/paper:text-white transition-colors line-clamp-2"
                                >
                                  {{ paper.title }}
                                </span>
                              </div>
                            </div>
                          </template>
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
                  to="/"
                  class="flex w-full items-center justify-center gap-2.5 rounded-xl border border-indigo-400/30 bg-indigo-500 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-500/30 transition-all hover:bg-indigo-400 hover:shadow-indigo-400/40 active:scale-[0.98]"
                >
                  <Icon name="uil:arrow-left" class="text-lg shrink-0" />
                  Back to Index
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
                :disabled="isInitializing"
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

            <div
              class="absolute right-4 top-1/2 z-20 flex -translate-y-1/2 flex-col items-center gap-3 rounded-2xl border border-white/10 bg-[#050508]/90 px-2.5 py-4 shadow-2xl shadow-black/40 backdrop-blur-md"
            >
              <button
                @click="zoomIn"
                class="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-white/70 transition-colors hover:border-purple-500/40 hover:bg-purple-500/10 hover:text-white"
                title="Zoom In"
              >
                <Icon name="uil:plus" class="text-base" />
              </button>

              <div class="flex h-48 flex-col items-center gap-2">
                <span class="text-[10px] font-mono text-slate-500">
                  {{ Math.round(zoomScale * 100) }}%
                </span>
                <input
                  :value="zoomScale"
                  @input="setZoomLevel(Number($event.target.value))"
                  type="range"
                  :min="ZOOM_MIN"
                  :max="ZOOM_MAX"
                  :step="0.1"
                  class="zoom-range h-36 w-2 cursor-pointer accent-purple-500"
                  aria-label="Graph zoom level"
                />
              </div>

              <button
                @click="zoomOut"
                class="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-white/70 transition-colors hover:border-purple-500/40 hover:bg-purple-500/10 hover:text-white"
                title="Zoom Out"
              >
                <Icon name="uil:minus" class="text-base" />
              </button>
            </div>

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

const data = ref(null);
const graphColors = ref(null);
const requestError = ref("");

// Computed property to check if the collection exists
// once this is true run rendering log
const hasData = computed(() => {
  return data.value && Object.keys(data.value).length > 0;
});

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let pollingActive = true;

const errorMessage = (error, fallback) =>
  error?.data?.message || error?.message || fallback;

async function pollBackend() {
  if (!activeJobId.value) return null;
  try {
    const res = await $fetch(
      `${apiBaseURL}/smart-collection/jobs/${activeJobId.value}/`,
    );
    store.setJob(res.job);
    return res.job;
  } catch (error) {
    requestError.value = errorMessage(error, "Could not check Smart Collection progress.");
    return null;
  }
}

async function continuouslyPollBackend() {
  let interval = 1500;
  while (pollingActive && activeJobId.value) {
    const job = await pollBackend();
    if (!job) return;
    if (job.status === "completed") {
      await getData();
      return;
    }
    if (job.status === "failed") {
      requestError.value =
        job.error?.message || "Smart Collection generation failed.";
      return;
    }
    if (job.status === "cancelled") return;
    await sleep(interval);
    interval = Math.min(5000, interval + 500);
  }
}

async function RunSmartCollection() {
  requestError.value = "";
  try {
    const res = await $fetch(`${apiBaseURL}/smart-collection/`, {
      method: "POST",
    });
    store.setJob(res.job);
  } catch (error) {
    requestError.value = errorMessage(error, "Failed to start Smart Collection.");
    return;
  }
  await continuouslyPollBackend();
}

async function getData() {
  try {
    const res = await $fetch(`${apiBaseURL}/smart-collection/`);
    graphColors.value = res.colors || {};
    data.value = res.data;
    readingRecs.value = res.recommendations || {};
    if (res.active_job) store.setJob(res.active_job);
  } catch (error) {
    requestError.value = errorMessage(error, "Failed to fetch Smart Collection data.");
    return;
  }
}

async function initDataLogic() {
  await getData();
  if (activeJobId.value && isInitializing.value) await continuouslyPollBackend();
}

onMounted(async () => {
  pollingActive = true;
  initDataLogic();
});

async function updateSmartCollection() {
  if (isInitializing.value) return;
  await RunSmartCollection();
}

async function cancelSmartCollection() {
  if (!activeJobId.value) return;
  try {
    const res = await $fetch(
      `${apiBaseURL}/smart-collection/jobs/${activeJobId.value}/`,
      { method: "DELETE" },
    );
    store.setJob(res.job);
  } catch (error) {
    requestError.value = errorMessage(error, "Could not cancel Smart Collection.");
  }
}

import { useSmartCollectionsStore } from "~~/stores/useSmartCollectionsStore";
import { storeToRefs } from "pinia";

const store = useSmartCollectionsStore();

const { isInitializing, activeJobId, jobStatus } = storeToRefs(store);

onUnmounted(() => {
  pollingActive = false;
});

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
  if (!data.value) {
    console.log("no graph explorer data");
    return {};
  }

  let hierarchy = {};

  if (data.value) {
    data.value.forEach((paper) => {
      const subKey = paper.sub_topic ? paper.sub_topic : "__direct__";

      if (paper.major_topic && paper.doc_title) {
        if (!hierarchy[paper.major_topic]) {
          hierarchy[paper.major_topic] = {};
        }

        if (!hierarchy[paper.major_topic][subKey]) {
          hierarchy[paper.major_topic][subKey] = [];
        }

        hierarchy[paper.major_topic][subKey].push({
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
  } catch (error) {
    requestError.value = errorMessage(error, "Failed to fetch recommendations.");
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
    readingRecs.value = res.recommendations || {};
  } catch (error) {
    requestError.value = errorMessage(error, "Failed to generate recommendations.");
  } finally {
    isRegenerating.value = false;
  }
}

async function regenerateRecommendations() {
  await newRecommendations();
}

// GRAPH LOGIC

const getTopicColor = (majorTopic, level) => {
  // level options: major, sub, paper
  if (graphColors.value && graphColors.value[majorTopic]) {
    return graphColors.value[majorTopic][level];
  }

  // Fallback
  if (level === "major") return "#e2e8f0";
  if (level === "sub") return "#c084fc";
  return "#60a5fa";
};

const graphContainer = ref(null);
let svg, g, zoom; // D3 variables
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 20;
const zoomScale = ref(1);

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
    similar:
      typeof d.similar_papers === "string"
        ? JSON.parse(d.similar_papers || "[]")
        : d.similar_papers || [],
  }));

  const paperMap = new Map(papers.map((p) => [p.id, p]));
  const links = [];

  papers.forEach((source) => {
    if (source.similar && source.similar.length > 0) {
      source.similar.forEach((targetId) => {
        const target = paperMap.get(targetId);
        // Only draw if target exists in current dataset
        if (target) {
          links.push({
            source: source,
            target: target,
            id: `${source.id}-${target.id}`,
          });
        }
      });
    }
  });

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
    if (!subMap[p.sub])
      subMap[p.sub] = {
        xSum: 0,
        ySum: 0,
        count: 0,
        major: p.major,
        label: p.sub,
      };

    subMap[p.sub].xSum += p.x;
    subMap[p.sub].ySum += p.y;
    subMap[p.sub].count++;
  });

  const subClusters = Object.keys(subMap).map((key) => ({
    label: subMap[key].label,
    major: subMap[key].major,
    x: subMap[key].xSum / subMap[key].count,
    y: subMap[key].ySum / subMap[key].count,
  }));

  return { papers, majorClusters, subClusters, links };
};

const initGraph = () => {
  if (!graphContainer.value || !data.value) return;

  d3.select(graphContainer.value).selectAll("*").remove();

  const { clientWidth: width, clientHeight: height } = graphContainer.value;
  const { papers, majorClusters, subClusters, links } = processGraphData(
    data.value
  );

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

  // lines between similar papers
  const linkGroup = g
    .append("g")
    .attr("class", "layer-links")
    .style("opacity", 1);

  linkGroup
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("x1", (d) => xScale(d.source.x))
    .attr("y1", (d) => yScale(d.source.y))
    .attr("x2", (d) => xScale(d.target.x))
    .attr("y2", (d) => yScale(d.target.y))
    .attr("stroke", "#ffffff")
    .attr("stroke-width", 0.5)
    .attr("stroke-opacity", 0.15);

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
    .attr("opacity", 0.6)
    .attr("fill", (d) => getTopicColor(d.major, "paper"))
    .style(
      "filter",
      (d) => `drop-shadow(0 0 2px ${getTopicColor(d.major, "paper")})`
    ); //glow

  // Titles
  paperGroup
    .selectAll("text")
    .data(papers)
    .join("text")
    .attr("x", (d) => xScale(d.x))
    .attr("y", (d) => yScale(d.y) - 8)
    .text((d) => d.title)
    .attr("text-anchor", "middle")
    .attr("font-size", "6px")
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
    .attr("fill", (d) => getTopicColor(d.major, "sub"))
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
    .attr("fill", (d) => getTopicColor(d.label, "major"))
    .style("text-shadow", "0 4px 12px rgba(0,0,0,0.9)");

  // zoom logic
  zoom = d3
    .zoom()
    .scaleExtent([ZOOM_MIN, ZOOM_MAX]) // Max zoom out / Max zoom in
    .on("zoom", (event) => {
      const { transform } = event;
      g.attr("transform", transform);
      zoomScale.value = Number(transform.k.toFixed(2));
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
  const linkLayer = g.select(".layer-links");

  // Smooth transitions using opacity
  majorLayer
    .transition()
    .duration(200)
    .style("opacity", k < 1.8 ? 1 : 0);
  subLayer
    .transition()
    .duration(200)
    .style("opacity", k >= 1.8 ? 1 : 0);
  paperText
    .transition()
    .duration(200)
    .style("opacity", k >= 1.8 ? 1 : 0);
  linkLayer
    .transition()
    .duration(200)
    .style("opacity", k >= 1.8 ? 1 : 0);
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

const setZoomLevel = (scale) => {
  if (!svg || !zoom || !graphContainer.value) return;

  const clampedScale = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, scale));
  const { clientWidth: width, clientHeight: height } = graphContainer.value;

  svg
    .transition()
    .duration(150)
    .call(zoom.scaleTo, clampedScale, [width / 2, height / 2]);
};

const zoomIn = () => {
  setZoomLevel(zoomScale.value + 0.5);
};

const zoomOut = () => {
  setZoomLevel(zoomScale.value - 0.5);
};

onMounted(() => {
  if (hasData.value) {
    nextTick(() => initGraph());
  }
});

watch([data, graphColors], ([newData, newColors]) => {
  if (
    newData &&
    Object.keys(newData).length > 0 &&
    newColors &&
    Object.keys(newColors).length > 0
  ) {
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

.zoom-range {
  writing-mode: vertical-lr;
  direction: rtl;
}

.zoom-range::-webkit-slider-runnable-track {
  width: 0.35rem;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.12);
}

.zoom-range::-webkit-slider-thumb {
  margin-left: -0.25rem;
}
</style>
