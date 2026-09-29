<template>
  <div class="h-screen bg-[#020204] text-white font-sans overflow-hidden flex flex-col">
    <nav class="border-b border-white/5 bg-[#020204]/80 backdrop-blur-md z-50">
      <div class="relative max-w-[1920px] mx-auto px-6 py-4 flex items-center justify-center">
        <div class="absolute left-6 flex items-center gap-2">
          <div class="w-5 h-5 bg-gradient-to-tr from-white to-slate-500 transform rotate-45 rounded-sm"></div>
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

    <div class="flex min-h-0 flex-1 overflow-hidden relative">
      <div class="absolute top-0 right-0 w-[600px] h-[600px] bg-purple-600/10 blur-[120px] rounded-full opacity-30 pointer-events-none"></div>
      <div class="absolute bottom-0 left-0 w-[500px] h-[500px] bg-blue-600/5 blur-[100px] rounded-full opacity-20 pointer-events-none"></div>

      <main class="relative flex min-h-0 flex-1 flex-col overflow-hidden custom-scrollbar">
        <div
          v-if="isInitializing || requestError || stallWarning || jobStatus?.warnings?.length"
          class="fixed right-6 top-20 z-[80] w-[min(440px,calc(100vw-3rem))] rounded-xl border border-white/10 bg-[#08080c]/95 p-4 shadow-2xl backdrop-blur-md"
        >
          <template v-if="isInitializing">
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="text-sm font-medium text-white">Updating Smart Collection</p>
                <p class="mt-1 text-xs text-slate-400">
                  {{ jobStatus?.stage_label || jobStatus?.stage || "Queued" }}
                  · {{ jobStatus?.processed_items || 0 }} /
                  {{ jobStatus?.total_items || 0 }}
                </p>
              </div>
              <button
                class="rounded-lg border border-white/10 px-2.5 py-1 text-[11px] text-slate-400 hover:border-red-400/30 hover:text-red-300"
                @click="cancelSmartCollection"
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
            <p v-if="stallWarning" class="mt-3 text-xs leading-relaxed text-amber-300/90">
              {{ stallWarning }}
            </p>
          </template>
          <template v-else-if="requestError">
            <p class="text-sm font-medium text-red-300">Smart Collection failed</p>
            <p class="mt-1 text-xs leading-relaxed text-slate-400">{{ requestError }}</p>
            <button
              class="mt-3 rounded-lg border border-red-400/20 bg-red-400/10 px-3 py-1.5 text-xs text-red-200 hover:bg-red-400/15"
              @click="RunSmartCollection"
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

        <div v-if="hasData" class="flex h-full min-h-0 bg-[#020204] animate-fade-in">
          <aside
            class="relative z-20 flex h-full shrink-0 flex-col border-r border-white/10 bg-[#050508] transition-[width] duration-300"
            :class="isSidebarOpen ? 'w-[380px]' : 'w-0 border-r-0'"
          >
            <button
              class="absolute -right-3 top-16 z-50 flex h-6 w-6 items-center justify-center rounded-full border border-white/10 bg-[#050508] text-white/40 hover:border-purple-500 hover:text-white"
              :class="{ 'opacity-0 pointer-events-none': !isSidebarOpen }"
              title="Collapse sidebar"
              @click="toggleSidebar"
            >
              <Icon name="uil:angle-left" class="text-sm" />
            </button>
            <button
              v-if="!isSidebarOpen"
              class="absolute -right-8 top-16 z-50 flex h-8 w-8 items-center justify-center rounded-r-lg border-y border-r border-white/10 bg-[#050508] text-white/40 hover:text-purple-400"
              title="Expand sidebar"
              @click="toggleSidebar"
            >
              <Icon name="uil:angle-right" class="text-lg" />
            </button>

            <div v-show="isSidebarOpen" class="flex h-full w-full flex-col overflow-hidden">
              <div class="border-b border-white/5 px-5 pt-5 pb-3">
                <p class="text-[10px] uppercase tracking-[0.2em] text-slate-500">Workspace</p>
                <h1 class="mt-1 text-lg font-semibold">Smart Collection</h1>
                <p class="mt-1 text-[11px] text-slate-500">
                  {{ stats.paper_count || papers.length }} papers ·
                  {{ stats.topic_count || topics.length }} topics
                  <span v-if="stats.auto_imported"> · {{ stats.auto_imported }} auto-imported</span>
                </p>
                <input
                  v-model="searchQuery"
                  class="mt-3 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white placeholder:text-slate-600 focus:border-purple-500/40 focus:outline-none"
                  placeholder="Search papers and topics"
                />
              </div>

              <div class="flex items-center gap-1 px-3 pt-3">
                <button
                  v-for="tab in tabs"
                  :key="tab.id"
                  class="flex flex-1 items-center justify-center gap-1.5 rounded-md py-2 text-[11px] font-medium"
                  :class="
                    activeTab === tab.id
                      ? 'bg-white/10 text-white'
                      : 'text-slate-500 hover:bg-white/5 hover:text-slate-300'
                  "
                  @click="activeTab = tab.id"
                >
                  <Icon :name="tab.icon" class="text-sm" />
                  {{ tab.label }}
                </button>
              </div>

              <div class="min-h-0 flex-1 overflow-y-auto px-4 py-4 custom-scrollbar">
                <div v-if="activeTab === 'topics'" class="space-y-3">
                  <div
                    v-for="topic in filteredTopics"
                    :key="topic.name"
                    class="rounded-xl border border-white/10 bg-white/[0.03] p-3"
                    :class="{ 'border-purple-500/40 bg-purple-500/5': selectedTopic === topic.name }"
                  >
                    <button class="flex w-full items-start gap-2 text-left" @click="selectTopic(topic.name)">
                      <span
                        class="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
                        :style="{ background: topicColor(topic.name) }"
                      ></span>
                      <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-2">
                          <span class="truncate text-sm font-semibold">{{ topic.name }}</span>
                          <span class="ml-auto font-mono text-[10px] text-slate-500">{{ topic.count }}</span>
                        </div>
                        <div class="mt-1 h-1 overflow-hidden rounded-full bg-white/10">
                          <div
                            class="h-full rounded-full bg-purple-400"
                            :style="{ width: `${Math.round((topic.cohesion || 0) * 100)}%` }"
                          ></div>
                        </div>
                        <p class="mt-1 text-[10px] text-slate-500">
                          Cohesion {{ Math.round((topic.cohesion || 0) * 100) }}%
                          <span v-if="topic.thin_notes" class="text-amber-400"> · thin notes</span>
                        </p>
                      </div>
                    </button>

                    <div v-if="selectedTopic === topic.name" class="mt-3 space-y-2 border-t border-white/5 pt-3">
                      <div class="flex flex-wrap gap-1.5">
                        <button class="action-chip" @click="startRename(topic.name)">Rename</button>
                        <button class="action-chip" @click="saveTopicFolder(topic.name)">Save folder</button>
                        <button
                          v-if="selectedIds.length"
                          class="action-chip"
                          @click="moveSelected(topic.name)"
                        >
                          Move here
                        </button>
                      </div>
                      <div v-if="renamingTopic === topic.name" class="flex gap-2">
                        <input
                          v-model="renameValue"
                          class="flex-1 rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs"
                          @keyup.enter="commitRename"
                        />
                        <button class="action-chip" @click="commitRename">Save</button>
                      </div>
                      <div v-if="otherTopics(topic.name).length" class="flex gap-2">
                        <select
                          v-model="mergeTarget"
                          class="flex-1 rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs"
                        >
                          <option value="">Merge into…</option>
                          <option v-for="name in otherTopics(topic.name)" :key="name" :value="name">
                            {{ name }}
                          </option>
                        </select>
                        <button class="action-chip" :disabled="!mergeTarget" @click="mergeSelectedTopic(topic.name)">
                          Merge
                        </button>
                      </div>
                      <label
                        v-for="paper in papersForTopic(topic.name)"
                        :key="paper.id"
                        class="flex cursor-pointer items-start gap-2 rounded-lg px-1 py-1 hover:bg-white/5"
                      >
                        <input v-model="selectedIds" type="checkbox" :value="paper.id" class="mt-1" />
                        <button class="min-w-0 flex-1 text-left" @click.prevent="selectPaper(paper)">
                          <span class="line-clamp-2 text-[11px] text-slate-300">{{ paper.doc_title }}</span>
                          <span class="mt-0.5 inline-flex items-center gap-1 text-[10px] uppercase tracking-wide" :class="roleClass(paper.role)">
                            {{ paper.role || "core" }}
                            <span class="text-slate-600">· {{ Math.round((paper.centrality || 0) * 100) }}%</span>
                          </span>
                        </button>
                        <button class="text-slate-500 hover:text-white" title="Open paper" @click.prevent="openPaper(paper)">
                          <Icon name="uil:external-link-alt" />
                        </button>
                      </label>
                    </div>
                  </div>
                </div>

                <div v-else-if="activeTab === 'gaps'" class="space-y-3">
                  <p class="text-[11px] text-slate-500">
                    Ghost nodes are papers your library is missing. Import one to fill the hole.
                  </p>
                  <div
                    v-for="ghost in ghosts"
                    :key="ghost.id"
                    class="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3"
                    :class="{ 'border-amber-300/50': selectedGhost?.id === ghost.id }"
                  >
                    <button class="w-full text-left" @click="selectGhost(ghost)">
                      <p class="text-sm font-medium text-amber-100">{{ ghost.title }}</p>
                      <p class="mt-1 text-[11px] text-slate-400">{{ ghost.overview || ghost.cluster }}</p>
                    </button>
                    <div class="mt-3 flex gap-2">
                      <button class="action-chip" @click="focusGhost(ghost)">Show on graph</button>
                      <button
                        v-if="ghost.document_id"
                        class="action-chip"
                        @click="navigateTo(`/annotate/${ghost.document_id}`)"
                      >
                        Open
                      </button>
                      <button
                        v-else
                        class="action-chip bg-amber-500/20 text-amber-100"
                        :disabled="importingId === ghost.arxiv_id"
                        @click="importCandidate(ghost)"
                      >
                        {{ importingId === ghost.arxiv_id ? "Importing…" : "Import" }}
                      </button>
                    </div>
                  </div>
                  <p v-if="!ghosts.length" class="pt-8 text-center text-xs text-slate-600">
                    No knowledge-gap ghosts yet. Update the collection to generate them.
                  </p>
                </div>

                <div v-else class="space-y-4">
                  <div class="flex items-center justify-between">
                    <p class="text-[11px] text-slate-500">Adjacent reading with one-click import.</p>
                    <button class="action-chip" :disabled="isRegenerating" @click="regenerateRecommendations">
                      <Icon name="uil:refresh" :class="{ 'animate-spin': isRegenerating }" />
                      Refresh
                    </button>
                  </div>
                  <div
                    v-for="item in readingRecs"
                    :key="item.id || item.topic"
                    class="rounded-xl border border-white/10 bg-white/[0.03] p-3"
                  >
                    <h3 class="text-sm font-semibold text-slate-100">{{ item.topic }}</h3>
                    <p class="mt-1 text-xs leading-relaxed text-slate-400">{{ item.overview }}</p>
                    <p v-if="item.query" class="mt-1 text-[10px] text-slate-600">arXiv · {{ item.query }}</p>
                    <p v-if="!(item.candidates || []).length" class="mt-2 text-[11px] text-slate-500">
                      No matching papers were found for this gap.
                    </p>
                    <div class="mt-3 space-y-2">
                      <div
                        v-for="candidate in item.candidates || []"
                        :key="candidate.arxiv_id || candidate.title"
                        class="rounded-lg bg-white/5 p-2"
                      >
                        <p class="text-[11px] font-medium text-slate-200">{{ candidate.title }}</p>
                        <p v-if="candidate.authors" class="mt-0.5 text-[10px] text-slate-500">{{ candidate.authors }}</p>
                        <div class="mt-2 flex flex-wrap gap-1.5">
                          <span v-if="candidate.imported" class="badge-imported">Imported</span>
                          <span v-else-if="candidate.already_in_library" class="badge-imported">In library</span>
                          <button
                            v-if="candidate.document_id"
                            class="action-chip"
                            @click="navigateTo(`/annotate/${candidate.document_id}`)"
                          >
                            Open
                          </button>
                          <button
                            v-else-if="candidate.arxiv_id"
                            class="action-chip"
                            :disabled="importingId === candidate.arxiv_id"
                            @click="importCandidate(candidate)"
                          >
                            {{ importingId === candidate.arxiv_id ? "Importing…" : "Import" }}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <p v-if="!readingRecs.length" class="pt-8 text-center text-xs text-slate-600">
                    No recommendations yet.
                  </p>
                </div>
              </div>
            </div>
          </aside>

          <div class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <header class="pointer-events-none absolute inset-x-0 top-0 z-10 flex h-14 items-center justify-between px-5">
              <div class="pointer-events-auto flex items-center gap-3">
                <h2 class="text-sm font-semibold tracking-wide">Knowledge Graph</h2>
                <span class="rounded-full border border-purple-500/20 bg-purple-500/10 px-2 py-0.5 text-[10px] font-medium text-purple-300">
                  {{ isolatedTopic || "All topics" }}
                </span>
              </div>
              <div class="pointer-events-auto flex items-center gap-2">
                <button class="toolbar-btn" :class="{ 'border-purple-400/40 text-white': showHeatmap }" @click="showHeatmap = !showHeatmap">
                  Heatmap
                </button>
                <button class="toolbar-btn" :class="{ 'border-amber-400/40 text-amber-100': showGhosts }" @click="showGhosts = !showGhosts">
                  Ghosts
                </button>
                <button class="toolbar-btn" :disabled="isInitializing" @click="updateSmartCollection">
                  <Icon name="uil:sync" :class="{ 'animate-spin': isInitializing }" />
                  Update
                </button>
              </div>
            </header>

            <SmartCollectionGraph
              ref="graphRef"
              v-model:zoom-scale="zoomScale"
              class="min-h-0 w-full flex-1"
              :papers="papers"
              :ghosts="ghosts"
              :heatmap="heatmap"
              :colors="graphColors"
              :selected-id="selectedPaper?.id"
              :selected-ghost-id="selectedGhost?.id || ''"
              :isolated-topic="isolatedTopic"
              :show-heatmap="showHeatmap"
              :show-ghosts="showGhosts"
              :focus-request="focusRequest"
              @select-paper="selectPaper"
              @open-paper="openPaper"
              @select-ghost="selectGhost"
              @background="clearSelection"
            />

            <div class="absolute right-4 top-1/2 z-20 flex -translate-y-1/2 flex-col items-center gap-3 rounded-2xl border border-white/10 bg-[#050508]/90 px-2.5 py-4">
              <button class="zoom-btn" title="Zoom in" @click="graphRef?.setZoomLevel(zoomScale + 0.5)">
                <Icon name="uil:plus" />
              </button>
              <span class="text-[10px] font-mono text-slate-500">{{ Math.round(zoomScale * 100) }}%</span>
              <button class="zoom-btn" title="Zoom out" @click="graphRef?.setZoomLevel(zoomScale - 0.5)">
                <Icon name="uil:minus" />
              </button>
              <button class="zoom-btn" title="Reset view" @click="graphRef?.resetZoom()">
                <Icon name="uil:focus-target" />
              </button>
            </div>

            <div class="absolute bottom-5 left-5 z-20 max-h-[45%] max-w-md overflow-y-auto rounded-2xl border border-white/10 bg-[#050508]/95 p-4 shadow-2xl custom-scrollbar">
              <div class="mb-3 flex flex-wrap gap-3 text-[10px] uppercase tracking-wide text-slate-500">
                <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-indigo-300 ring-2 ring-indigo-400/70"></span>Pillar</span>
                <span class="inline-flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-slate-300"></span>Core</span>
                <span class="inline-flex items-center gap-1.5"><span class="h-1.5 w-1.5 rounded-full border border-dashed border-slate-400"></span>Niche</span>
                <span class="inline-flex items-center gap-1.5 text-amber-400">◇ Ghost gap</span>
              </div>
              <div v-if="selectedPaper">
                <p class="text-sm font-semibold">{{ selectedPaper.doc_title }}</p>
                <p class="mt-1 text-[11px] text-slate-400">
                  {{ selectedPaper.major_topic }} ·
                  <span :class="roleClass(selectedPaper.role)">{{ selectedPaper.role }}</span>
                  · centrality {{ Math.round((selectedPaper.centrality || 0) * 100) }}%
                </p>
                <p v-if="selectedPaper.excerpt" class="mt-2 line-clamp-3 text-[11px] text-slate-500">
                  {{ selectedPaper.excerpt }}
                </p>
                <div class="mt-3 flex flex-wrap gap-2">
                  <button class="action-chip" @click="openPaper(selectedPaper)">Open paper</button>
                  <select
                    class="rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs"
                    @change="movePaperTo($event.target.value, selectedPaper)"
                  >
                    <option value="">Move to topic…</option>
                    <option v-for="topic in topics" :key="topic.name" :value="topic.name">
                      {{ topic.name }}
                    </option>
                  </select>
                </div>
              </div>
              <div v-else-if="selectedGhost">
                <p class="text-sm font-semibold text-amber-100">{{ selectedGhost.title }}</p>
                <p class="mt-1 text-[11px] text-slate-400">{{ selectedGhost.overview }}</p>
                <button
                  class="action-chip mt-3"
                  :disabled="importingId === selectedGhost.arxiv_id"
                  @click="importCandidate(selectedGhost)"
                >
                  Import this paper
                </button>
              </div>
              <p v-else class="text-[11px] text-slate-500">
                Click a paper to inspect it. Pillars sit at the center of a topic; niches sit on the fringe. The heatmap shows influence.
              </p>
            </div>
          </div>
        </div>

        <div
          v-else
          class="flex flex-1 flex-col items-center justify-center px-8 text-center relative z-10 max-w-2xl mx-auto"
        >
          <div class="relative mb-8 group">
            <div class="absolute inset-0 bg-purple-500/20 blur-xl rounded-full group-hover:bg-purple-500/30 transition-all duration-700"></div>
            <div class="relative w-24 h-24 rounded-2xl bg-gradient-to-b from-white/10 to-transparent border border-white/10 flex items-center justify-center backdrop-blur-sm">
              <Icon name="carbon:network-4" class="text-5xl text-purple-300 opacity-80" />
            </div>
          </div>
          <h1 class="text-4xl md:text-5xl font-bold tracking-tight mb-6">
            Initialize your
            <span class="block mt-2 text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 animate-gradient">
              Smart Collection
            </span>
          </h1>
          <button
            class="group relative w-full max-w-md overflow-hidden rounded-xl bg-white text-black font-semibold py-4 px-8 transition-all hover:scale-[1.01] disabled:opacity-70 mb-6"
            :disabled="isInitializing"
            @click="RunSmartCollection()"
          >
            <span class="relative flex items-center justify-center gap-2">
              <Icon :name="isInitializing ? 'line-md:loading-twotone-loop' : 'uil:processor'" class="text-xl" />
              {{ isInitializing ? jobStatus?.stage_label || "Constructing Graph..." : "Initialize Smart Collection" }}
            </span>
          </button>
          <div class="w-full max-w-md space-y-3 text-left">
            <div class="rounded-lg border border-blue-500/10 bg-blue-500/5 p-4 text-xs text-slate-400">
              Clusters now use UMAP + HDBSCAN, so related papers form usable topics instead of a pretty but empty graph.
            </div>
            <div class="rounded-lg border border-yellow-500/10 bg-yellow-500/5 p-4 text-xs text-slate-400">
              Initialization embeds notes, labels topics, and searches arXiv for knowledge-gap ghosts. It runs in the background.
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { storeToRefs } from "pinia";
import { useSmartCollectionsStore } from "~~/stores/useSmartCollectionsStore";
import { useNotificationStore } from "~~/stores/useNotificationStore";

const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const store = useSmartCollectionsStore();
const notifications = useNotificationStore();
const { isInitializing, activeJobId, jobStatus } = storeToRefs(store);

const papers = ref([]);
const graphColors = ref({});
const topics = ref([]);
const ghosts = ref([]);
const heatmap = ref({});
const stats = ref({});
const readingRecs = ref([]);
const requestError = ref("");
const requestErrorCode = ref("");
const stallWarning = ref("");
const isSidebarOpen = ref(true);
const activeTab = ref("topics");
const searchQuery = ref("");
const selectedTopic = ref("");
const isolatedTopic = ref("");
const selectedPaper = ref(null);
const selectedGhost = ref(null);
const selectedIds = ref([]);
const renamingTopic = ref("");
const renameValue = ref("");
const mergeTarget = ref("");
const showHeatmap = ref(true);
const showGhosts = ref(true);
const zoomScale = ref(1);
const graphRef = ref(null);
const focusRequest = ref(null);
const isRegenerating = ref(false);
const importingId = ref("");
let pollingActive = true;
let stallNoticeShown = false;

const tabs = [
  { id: "topics", label: "Topics", icon: "uil:sitemap" },
  { id: "gaps", label: "Gaps", icon: "uil:question-circle" },
  { id: "recs", label: "Reading", icon: "uil:lightbulb-alt" },
];

const hasData = computed(() => Array.isArray(papers.value) && papers.value.length > 0);

const filteredTopics = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return (topics.value || []).filter((topic) => {
    if (!query) return true;
    if (topic.name.toLowerCase().includes(query)) return true;
    return papersForTopic(topic.name).some((paper) =>
      (paper.doc_title || "").toLowerCase().includes(query)
    );
  });
});

const QUEUED_STALL_MS = 45_000;
const RUNNING_STALL_MS = 150_000;
const errorMessage = (error, fallback) => error?.data?.message || error?.message || fallback;
const errorCode = (error) => error?.data?.error || "";

function normalizeRecommendations(raw) {
  if (!raw) return [];
  if (Array.isArray(raw.items)) return raw.items;
  if (Array.isArray(raw)) return raw;
  return Object.entries(raw).map(([topic, details]) => ({
    id: topic,
    topic,
    overview: details?.overview || "",
    candidates: [details?.paper1, details?.paper2]
      .filter(Boolean)
      .map((title) => ({ title, arxiv_id: "", imported: false })),
  }));
}

function applyCollection(res) {
  papers.value = res.data || res.papers || [];
  graphColors.value = res.colors || {};
  topics.value = res.topics || [];
  ghosts.value = res.ghosts || [];
  heatmap.value = res.heatmap || {};
  stats.value = res.stats || {};
  readingRecs.value = normalizeRecommendations(res.recommendations);
  if (res.active_job) store.setJob(res.active_job);
}

function topicColor(name) {
  return graphColors.value?.[name]?.major || "#a78bfa";
}

function roleClass(role) {
  if (role === "pillar") return "text-indigo-300";
  if (role === "niche") return "text-slate-400";
  return "text-purple-200";
}

function papersForTopic(name) {
  const query = searchQuery.value.trim().toLowerCase();
  return papers.value.filter((paper) => {
    if (paper.major_topic !== name) return false;
    if (!query) return true;
    return (paper.doc_title || "").toLowerCase().includes(query);
  });
}

function otherTopics(name) {
  return topics.value.map((topic) => topic.name).filter((item) => item !== name);
}

function toggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value;
}

function selectTopic(name) {
  selectedTopic.value = selectedTopic.value === name ? "" : name;
  isolatedTopic.value = selectedTopic.value;
  if (selectedTopic.value) activeTab.value = "topics";
}

function selectPaper(paper) {
  selectedPaper.value = paper;
  selectedGhost.value = null;
  isolatedTopic.value = paper.major_topic || isolatedTopic.value;
  focusRequest.value = {
    x: paper.x_coordinate,
    y: paper.y_coordinate,
    scale: 5,
    nonce: Date.now(),
  };
}

function openPaper(paper) {
  if (!paper?.document_id) return;
  navigateTo(`/annotate/${paper.document_id}`);
}

function selectGhost(ghost) {
  selectedGhost.value = ghost;
  selectedPaper.value = null;
  activeTab.value = "gaps";
  focusGhost(ghost);
}

function focusGhost(ghost) {
  focusRequest.value = { x: ghost.x, y: ghost.y, scale: 4, nonce: Date.now() };
}

function clearSelection() {
  selectedPaper.value = null;
  selectedGhost.value = null;
}

function startRename(name) {
  renamingTopic.value = name;
  renameValue.value = name;
}

async function patchCollection(body) {
  const res = await $fetch(`${apiBaseURL}/smart-collection/`, {
    method: "PATCH",
    body,
  });
  applyCollection(res);
  return res;
}

async function commitRename() {
  if (!renamingTopic.value || !renameValue.value.trim()) return;
  try {
    await patchCollection({
      action: "rename_topic",
      from: renamingTopic.value,
      to: renameValue.value.trim(),
    });
    selectedTopic.value = renameValue.value.trim();
    isolatedTopic.value = selectedTopic.value;
    renamingTopic.value = "";
    notifications.notify({ title: "Topic renamed", type: "success", durationMs: 4000 });
  } catch (error) {
    reportFailure(errorMessage(error, "Could not rename topic."), { code: errorCode(error) });
  }
}

async function saveTopicFolder(name) {
  try {
    const res = await patchCollection({ action: "save_folder", topic: name });
    notifications.notify({
      title: "Folder created",
      message: `${res.folder?.count || 0} papers saved to “${res.folder?.name || name}”.`,
      type: "success",
      durationMs: 6000,
    });
  } catch (error) {
    reportFailure(errorMessage(error, "Could not save this topic as a folder."), {
      code: errorCode(error),
    });
  }
}

async function mergeSelectedTopic(source) {
  if (!mergeTarget.value) return;
  try {
    await patchCollection({
      action: "merge_topics",
      sources: [source],
      target: mergeTarget.value,
    });
    selectedTopic.value = mergeTarget.value;
    isolatedTopic.value = mergeTarget.value;
    mergeTarget.value = "";
    notifications.notify({ title: "Topics merged", type: "success", durationMs: 4000 });
  } catch (error) {
    reportFailure(errorMessage(error, "Could not merge topics."), { code: errorCode(error) });
  }
}

async function moveSelected(topic) {
  if (!selectedIds.value.length) return;
  await moveIds(selectedIds.value, topic);
}

async function movePaperTo(topic, paper) {
  if (!topic || !paper) return;
  await moveIds([paper.id], topic);
}

async function moveIds(ids, topic) {
  try {
    await patchCollection({ action: "move_papers", annotation_ids: ids, topic, pin: true });
    selectedIds.value = [];
    notifications.notify({ title: "Papers moved", message: `Pinned to ${topic}.`, type: "success", durationMs: 4000 });
  } catch (error) {
    reportFailure(errorMessage(error, "Could not move papers."), { code: errorCode(error) });
  }
}

async function importCandidate(candidate) {
  if (!candidate?.arxiv_id || importingId.value) return;
  importingId.value = candidate.arxiv_id;
  try {
    const res = await patchCollection({
      action: "import_paper",
      arxiv_id: candidate.arxiv_id,
      title: candidate.title || "",
    });
    notifications.notify({
      title: res.imported?.already_in_library ? "Already in library" : "Paper imported",
      message: res.imported?.title || candidate.title,
      type: "success",
      durationMs: 5000,
    });
    if (res.imported?.document_id && !res.imported.already_in_library) {
      // Stay on the page; the user can open from the card.
    }
  } catch (error) {
    reportFailure(errorMessage(error, "Could not import that paper."), { code: errorCode(error) });
  } finally {
    importingId.value = "";
  }
}

function clearFailureState() {
  requestError.value = "";
  requestErrorCode.value = "";
  stallWarning.value = "";
  stallNoticeShown = false;
}

function reportFailure(message, { code = "", notify = true } = {}) {
  requestError.value = message;
  requestErrorCode.value = code || "";
  stallWarning.value = "";
  if (!notify) return;
  notifications.notify({
    title: "Smart Collection failed",
    message: code ? `${message}\n\nError: ${code}` : message,
    type: "error",
    durationMs: 0,
  });
}

function reportWarnings(warnings) {
  if (!warnings?.length) return;
  notifications.notify({
    title: "Smart Collection finished with warnings",
    message: warnings.join("\n"),
    type: "warning",
    durationMs: 14000,
  });
}

function updateStallWarning(job, unchangedMs) {
  if (!job || !["queued", "running"].includes(job.status)) {
    stallWarning.value = "";
    return;
  }
  if (job.status === "queued" && unchangedMs >= QUEUED_STALL_MS) {
    stallWarning.value =
      "Still queued with no worker pickup. On production this usually means the django-q background worker is not running.";
  } else if (job.status === "running" && unchangedMs >= RUNNING_STALL_MS) {
    const stage = job.stage_label || job.stage || "the current step";
    stallWarning.value = `No progress while ${String(stage).toLowerCase()}. The AI provider may be hanging or the worker may have frozen.`;
  } else {
    stallWarning.value = "";
    return;
  }
  if (!stallNoticeShown) {
    stallNoticeShown = true;
    notifications.notify({
      title: "Smart Collection may be stuck",
      message: stallWarning.value,
      type: "warning",
      durationMs: 12000,
    });
  }
}

async function pollBackend() {
  if (!activeJobId.value) return null;
  try {
    const res = await $fetch(`${apiBaseURL}/smart-collection/jobs/${activeJobId.value}/`);
    store.setJob(res.job);
    return res.job;
  } catch (error) {
    reportFailure(errorMessage(error, "Could not check Smart Collection progress."), {
      code: errorCode(error),
    });
    return null;
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function continuouslyPollBackend() {
  let interval = 1500;
  let lastFingerprint = "";
  let unchangedSince = Date.now();
  stallNoticeShown = false;
  stallWarning.value = "";
  while (pollingActive && activeJobId.value) {
    const job = await pollBackend();
    if (!job) return;
    const fingerprint = `${job.status}:${job.stage}:${job.progress}:${job.processed_items}`;
    if (fingerprint !== lastFingerprint) {
      lastFingerprint = fingerprint;
      unchangedSince = Date.now();
      stallWarning.value = "";
      stallNoticeShown = false;
    } else {
      updateStallWarning(job, Date.now() - unchangedSince);
    }
    if (job.status === "completed") {
      stallWarning.value = "";
      await getData();
      notifications.notify({
        title: "Smart Collection ready",
        message: "Topics, gaps, and influence are ready to use.",
        type: "success",
        durationMs: 6000,
      });
      reportWarnings(job.warnings);
      return;
    }
    if (job.status === "failed") {
      reportFailure(job.error?.message || "Smart Collection generation failed.", {
        code: job.error?.code || "",
      });
      return;
    }
    if (job.status === "cancelled") {
      stallWarning.value = "";
      notifications.notify({
        title: "Smart Collection cancelled",
        message: "Generation was cancelled before it finished.",
        type: "info",
        durationMs: 6000,
      });
      return;
    }
    await sleep(interval);
    interval = Math.min(5000, interval + 500);
  }
}

async function RunSmartCollection() {
  clearFailureState();
  try {
    const res = await $fetch(`${apiBaseURL}/smart-collection/`, { method: "POST" });
    store.setJob(res.job);
    notifications.notify({
      title: res.already_running ? "Smart Collection already running" : "Smart Collection started",
      message: res.already_running
        ? "Resuming progress for the job that is already in progress."
        : "Building embeddings, topics, and knowledge-gap ghosts.",
      type: "info",
      durationMs: 5000,
    });
  } catch (error) {
    if (error?.data?.job) store.setJob(error.data.job);
    reportFailure(errorMessage(error, "Failed to start Smart Collection."), {
      code: errorCode(error),
    });
    return;
  }
  await continuouslyPollBackend();
}

async function getData() {
  try {
    const res = await $fetch(`${apiBaseURL}/smart-collection/`);
    applyCollection(res);
  } catch (error) {
    reportFailure(errorMessage(error, "Failed to fetch Smart Collection data."), {
      code: errorCode(error),
    });
  }
}

async function updateSmartCollection() {
  if (isInitializing.value) return;
  await RunSmartCollection();
}

async function cancelSmartCollection() {
  if (!activeJobId.value) return;
  try {
    const res = await $fetch(`${apiBaseURL}/smart-collection/jobs/${activeJobId.value}/`, {
      method: "DELETE",
    });
    store.setJob(res.job);
  } catch (error) {
    reportFailure(errorMessage(error, "Could not cancel Smart Collection."), {
      code: errorCode(error),
    });
  }
}

async function regenerateRecommendations() {
  if (isRegenerating.value) return;
  isRegenerating.value = true;
  try {
    const res = await $fetch(`${apiBaseURL}/reading-recommendations/`, { method: "POST" });
    readingRecs.value = normalizeRecommendations(res.recommendations);
    if (res.ghosts) ghosts.value = res.ghosts;
    notifications.notify({
      title: "Recommendations updated",
      message: res.auto_imported
        ? `Imported ${res.auto_imported} suggested paper${res.auto_imported === 1 ? "" : "s"}.`
        : "Fresh reading recommendations are ready.",
      type: "success",
      durationMs: 5000,
    });
  } catch (error) {
    reportFailure(errorMessage(error, "Failed to generate recommendations."), {
      code: errorCode(error),
    });
  } finally {
    isRegenerating.value = false;
  }
}

onMounted(async () => {
  pollingActive = true;
  await getData();
  if (jobStatus.value?.status === "failed" && jobStatus.value?.error?.message) {
    reportFailure(jobStatus.value.error.message, {
      code: jobStatus.value.error.code || "",
      notify: false,
    });
  }
  if (activeJobId.value && isInitializing.value) await continuouslyPollBackend();
});

onUnmounted(() => {
  pollingActive = false;
});
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}
.action-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border-radius: 0.5rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  padding: 0.3rem 0.55rem;
  font-size: 10px;
  color: #cbd5e1;
}
.action-chip:disabled {
  opacity: 0.5;
}
.toolbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 0.6rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  padding: 0.35rem 0.7rem;
  font-size: 11px;
  color: #cbd5e1;
}
.zoom-btn {
  display: flex;
  height: 2rem;
  width: 2rem;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.7);
}
.badge-imported {
  border-radius: 999px;
  border: 1px solid rgba(52, 211, 153, 0.3);
  background: rgba(16, 185, 129, 0.12);
  padding: 0.1rem 0.45rem;
  font-size: 10px;
  color: #6ee7b7;
}
.animate-fade-in {
  animation: fadeIn 0.4s ease both;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-gradient {
  background-size: 200% auto;
  animation: gradient 8s ease infinite;
}
@keyframes gradient {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
</style>
