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
        <div class="flex items-center gap-4"></div>
      </div>
    </nav>

    <div class="flex flex-1 overflow-hidden h-[calc(100vh-65px)]">
      <main
        class="w-[70%] p-8 lg:p-12 overflow-y-auto relative border-r border-white/5 custom-scrollbar"
      >
        <div
          class="absolute top-0 left-0 w-[600px] h-[300px] bg-indigo-600/10 blur-[120px] rounded-full opacity-40 pointer-events-none"
        ></div>

        <div class="max-w-5xl mx-auto relative z-10">
          <div class="mb-10">
            <h1 class="text-4xl font-semibold tracking-tight mb-2">
              Your
              <span
                class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-400 animate-gradient"
                >Knowledge Index</span
              >
            </h1>
            <p class="text-slate-400">
              Manage your papers, annotations, and generated insights.
            </p>
            <p class="pt-2 text-xs text-slate-500">
              See docs on GitHub for a full feature overview & advanced
              searching techniques.
            </p>
          </div>

          <div class="mb-4 relative group z-50">
            <div
              class="absolute inset-y-0 left-4 flex items-center pointer-events-none"
            >
              <Icon
                name="uil:search"
                class="text-slate-500 text-xl group-focus-within:text-indigo-400 transition-colors"
              />
            </div>
            <input
              type="text"
              v-model="searchQuery"
              @input="handleInput"
              @keydown.down.prevent="navigateSuggestions(1)"
              @keydown.up.prevent="navigateSuggestions(-1)"
              @keydown.enter.prevent="selectSuggestion"
              placeholder="Search concepts, highlight text, or tags... (hint: use the @ symbol to narrow your search)"
              class="w-full bg-white/[0.03] border border-white/10 rounded-2xl py-5 pl-12 pr-6 text-lg text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500/50 focus:bg-white/[0.05] focus:ring-1 focus:ring-indigo-500/50 transition-all shadow-lg shadow-black/50"
            />

            <div
              v-if="showSuggestions"
              class="absolute top-full mt-2 w-full bg-[#15151A] border border-white/10 rounded-xl overflow-hidden shadow-2xl z-50"
            >
              <div
                v-for="(suggestion, index) in filteredSuggestions"
                :key="suggestion"
                class="px-4 py-3 cursor-pointer hover:bg-white/5 flex items-center gap-3 transition-colors"
                :class="{ 'bg-white/10': activeSuggestionIndex === index }"
                @click="applyFilter(suggestion)"
              >
                <div
                  class="w-6 h-6 rounded bg-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold"
                >
                  @
                </div>
                <span class="text-sm text-slate-200">{{ suggestion }}</span>
              </div>
            </div>
          </div>

          <div
            v-if="errorMsg"
            class="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2"
          >
            <Icon name="uil:exclamation-circle" />
            {{ errorMsg }}
          </div>

          <div
            v-if="!searchActive"
            class="flex justify-center items-center gap-5 mb-16"
          >
            <NuxtLink
              to="/knowledge-base/smart-collections"
              class="group flex flex-col items-center gap-2"
            >
              <div
                class="w-12 h-12 rounded-xl border border-purple-500/20 bg-purple-500/5 hover:bg-purple-500/20 hover:border-purple-500/50 hover:scale-105 active:scale-95 flex items-center justify-center transition-all duration-300 shadow-[0_0_15px_-3px_rgba(168,85,247,0.15)] group-hover:shadow-[0_0_20px_-3px_rgba(168,85,247,0.3)]"
              >
                <Icon
                  name="uil:layer-group"
                  class="text-xl text-purple-400 group-hover:text-purple-200 transition-colors"
                />
              </div>
              <span
                class="text-[11px] font-semibold uppercase tracking-widest text-slate-300 group-hover:text-purple-400 transition-colors"
                >Collections</span
              >
            </NuxtLink>

            <button
              @click="focusAIChat"
              class="group flex flex-col items-center gap-2"
            >
              <div
                class="w-12 h-12 rounded-xl border border-cyan-500/20 bg-cyan-500/5 hover:bg-cyan-500/20 hover:border-cyan-500/50 hover:scale-105 active:scale-95 flex items-center justify-center transition-all duration-300 shadow-[0_0_15px_-3px_rgba(34,211,238,0.15)] group-hover:shadow-[0_0_20px_-3px_rgba(34,211,238,0.3)] relative overflow-hidden"
              >
                <div
                  class="absolute inset-0 bg-gradient-to-tr from-transparent via-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"
                ></div>
                <Icon
                  name="heroicons:sparkles-20-solid"
                  class="text-xl text-cyan-400 group-hover:text-cyan-200 transition-colors"
                />
              </div>
              <span
                class="text-[11px] font-semibold uppercase tracking-widest text-slate-300 group-hover:text-cyan-400 transition-colors"
                >Ask AI</span
              >
            </button>
          </div>

          <div v-if="hasAnnotations && !searchActive" class="space-y-12">
            <div class="relative w-full overflow-hidden mask-sides">
              <div class="flex gap-6 w-max animate-scroll-left">
                <div
                  v-for="(doc, index) in topRowDocs"
                  :key="`${doc.title}-1-${index}`"
                  class="w-[320px] h-44 rounded-2xl border border-white/10 bg-[#0A0A0C]/80 backdrop-blur-sm hover:bg-[#15151A] hover:border-indigo-500/30 p-5 flex flex-col justify-between transition-all group cursor-pointer shadow-lg shadow-black/20"
                >
                  <div>
                    <div class="flex justify-between items-start mb-3">
                      <div class="flex items-center gap-2">
                        <span
                          class="w-1.5 h-1.5 rounded-full bg-indigo-400"
                        ></span>
                        <span
                          class="text-[10px] uppercase tracking-wider text-slate-500 font-bold"
                          >Top Source</span
                        >
                      </div>
                      <span
                        class="text-[10px] bg-white/5 px-2 py-0.5 rounded text-indigo-300"
                        >{{ doc.count }} Notes</span
                      >
                    </div>
                    <h3
                      class="text-sm font-medium text-slate-200 line-clamp-2 leading-snug group-hover:text-indigo-200 transition-colors"
                    >
                      {{ doc.title }}
                    </h3>
                  </div>
                  <div class="relative">
                    <p class="text-[16px] text-slate-500 italic line-clamp-2">
                      "{{ doc.content }}"
                    </p>
                    <div class="absolute bottom-0 right-0">
                      <Icon
                        name="uil:arrow-right"
                        class="text-slate-600 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="relative w-full overflow-hidden mask-sides">
              <div class="flex gap-6 w-max animate-scroll-right hover:pause">
                <div
                  v-for="(doc, index) in bottomRowDocs"
                  :key="`${doc.title}-2-${index}`"
                  class="w-[320px] h-44 rounded-2xl border border-white/10 bg-[#0A0A0C]/80 backdrop-blur-sm hover:bg-[#15151A] hover:border-purple-500/30 p-5 flex flex-col justify-between transition-all group cursor-pointer shadow-lg shadow-black/20"
                >
                  <div>
                    <div class="flex justify-between items-start mb-3">
                      <div class="flex items-center gap-2">
                        <span
                          class="w-1.5 h-1.5 rounded-full bg-purple-400"
                        ></span>
                        <span
                          class="text-[10px] uppercase tracking-wider text-slate-500 font-bold"
                          >Heavy Read</span
                        >
                      </div>
                      <span
                        class="text-[10px] bg-white/5 px-2 py-0.5 rounded text-purple-300"
                        >{{ doc.count }} Notes</span
                      >
                    </div>
                    <h3
                      class="text-sm font-medium text-slate-200 line-clamp-2 leading-snug group-hover:text-purple-200 transition-colors"
                    >
                      {{ doc.title }}
                    </h3>
                  </div>
                  <div class="relative">
                    <p class="text-[16px] text-slate-500 italic line-clamp-2">
                      "{{ doc.content }}"
                    </p>
                    <div class="absolute bottom-0 right-0">
                      <Icon
                        name="uil:arrow-right"
                        class="text-slate-600 group-hover:text-purple-400 group-hover:translate-x-1 transition-all"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div
            v-else-if="!hasAnnotations && !searchActive"
            class="flex flex-col items-center justify-center py-20 opacity-50"
          >
            <Icon
              name="uil:files-landscapes-alt"
              class="text-6xl text-slate-700 mb-4"
            />
            <h3 class="text-lg font-medium text-slate-500">
              No annotations found
            </h3>
            <p class="text-sm text-slate-600">
              Start highlighting your papers to see them here.
            </p>
          </div>

          <div v-else class="space-y-4">
            <div
              v-if="searchResults.length === 0"
              class="text-center py-12 text-slate-500"
            >
              No results found matching your query.
            </div>

            <div
              v-for="(result, index) in searchResults"
              :key="index"
              @click="sendToPaper(result)"
              class="p-5 rounded-2xl border border-white/10 bg-[#0A0A0C]/80 backdrop-blur-sm hover:bg-[#15151A] hover:border-indigo-500/30 transition-all group"
            >
              <div class="flex justify-between items-start mb-2">
                <div class="flex items-center gap-2">
                  <span
                    class="px-2 py-0.5 rounded bg-white/5 text-[10px] font-bold uppercase tracking-wider"
                    :class="result.typeColor"
                  >
                    {{ result.matchType }}
                  </span>
                  <span
                    v-if="result.isRecent"
                    class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase tracking-wider"
                  >
                    Recent
                  </span>
                </div>
                <span class="text-xs text-slate-600">{{ result.date }}</span>
              </div>

              <h3 class="text-sm font-medium text-indigo-200 mb-2">
                {{ result.title }}
              </h3>

              <p
                class="text-sm text-slate-400 leading-relaxed"
                v-html="highlightMatch(result.content)"
              ></p>
            </div>
          </div>
        </div>
      </main>

      <aside class="w-[30%] bg-[#050508] relative flex flex-col">
        <div
          class="p-6 border-b border-white/5 flex items-center gap-3 bg-[#050508]/90 backdrop-blur z-10"
        >
          <div class="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
            <Icon name="material-symbols:smart-toy-outline" class="text-xl" />
          </div>
          <div>
            <h2 class="text-sm font-semibold text-white">Research Assistant</h2>
            <div class="flex items-center gap-1.5 mt-0.5">
              <span
                class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"
              ></span>
              <span
                class="text-[10px] text-slate-500 uppercase tracking-wider font-medium"
                >Online</span
              >
            </div>
          </div>
        </div>

        <div
          class="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar flex flex-col"
        >
          <div class="flex gap-4">
            <div
              class="w-8 h-8 rounded bg-indigo-500/20 flex items-center justify-center shrink-0"
            >
              <Icon name="uil:robot" class="text-indigo-400" />
            </div>
            <div class="space-y-2">
              <div class="text-xs text-slate-500">Research Assistant</div>
              <div
                class="p-4 rounded-xl rounded-tl-none bg-white/[0.03] border border-white/5 text-sm text-slate-300 leading-relaxed"
              >
                Hello! I have indexed
                <strong>{{ countAnnotations }} papers</strong>. I can help you
                summarize documents, find connections between concepts, or draft
                outlines.
              </div>
            </div>
          </div>

          <div
            class="flex-1 flex flex-col items-center justify-center text-center opacity-30 pointer-events-none select-none"
          >
            <Icon
              name="uil:comment-alt-lines"
              class="text-4xl text-slate-700 mb-2"
            />
            <p class="text-sm text-slate-600">Ask a question to begin</p>
          </div>
        </div>

        <div class="p-6 border-t border-white/5 bg-[#050508]">
          <div class="relative">
            <textarea
              ref="chatInputRef"
              rows="1"
              placeholder="Use '@' to reference paper titles"
              class="w-full bg-slate-900/50 border border-white/10 rounded-xl py-4 pl-4 pr-12 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500/40 focus:bg-slate-900 resize-none overflow-hidden transition-all"
            ></textarea>
            <button
              class="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500 hover:text-white transition-colors"
            >
              <Icon name="uil:message" class="text-lg" />
            </button>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
const userNotes = ref([]);
// fetching user notes
async function fetchNotes() {
  try {
    const res = await $fetch("/api/search-notes", {
      method: "GET",
    });
    userNotes.value = res;
    console.log(userNotes.value);
  } catch (error) {
    console.error(`error fetching notes ${error}`);
  }
}

onMounted(() => {
  fetchNotes();
});

/* Setting up display for carousel animation
Picks even amount of sticky notes or highlights to display in template cards
Need 12 cards to fill scroll without artificial inflation, so will look for as many as possible before we reach that point.
returns a list of dicts where in the template you can just do v-for and display everything. Make sure to run thru prepareInfiniteList so that it's carousel ready.

each card needs a
1. count (idx)
2. paper title
3. annotation to display
*/

const carouselCards = computed(() => {
  const lastPicked = ref("highlight");

  if (!userNotes.value || Object.keys(userNotes.value).length === 0) {
    console.log("Data is empty or not loaded yet");
    return [];
  }

  let allCards = [];

  Object.entries(userNotes.value).forEach(([idx, obj]) => {
    let content = "";

    if (
      lastPicked.value == "highlight" &&
      obj.annotations.sticky_note_data.length != 0
    ) {
      // need to get a sticky note
      content = obj.annotations.sticky_note_data[0].content;
      lastPicked.value = "sticky";
    } else if (
      lastPicked.value == "sticky" &&
      obj.annotations.highlight_data.length != 0
    ) {
      // get highlight
      content = obj.annotations.highlight_data[0].text;
      lastPicked.value = "highlight";
    } else {
      // default to whatever the paper has
      if (obj.annotations.highlight_data.length != 0) {
        content = obj.annotations.highlight_data[0].text;
        lastPicked.value = "highlight";
      } else if (obj.annotations.sticky_note_data.length != 0) {
        content = obj.annotations.sticky_note_data[0].content;
        lastPicked.value = "sticky";
      }
    }

    let cardObj = {
      count: idx,
      title: obj.title,
      content: content,
    };

    if (content && content.trim() !== "") {
      allCards.push(cardObj);
    }
  });

  // Limit to 50 cards as to not cause perf issues
  if (allCards.length > 50) {
    allCards = allCards.slice(0, 50);
  }

  return allCards;
});

// Function copies items until there's enough to fit in the infinite scroll (12 * 2)
// doubles at the end so that the snap back isn't noticeable to the user when the animation ends
const prepareInfiniteList = (items) => {
  if (!items || items.length === 0) return [];

  let baseList = [...items];
  while (baseList.length < 12) {
    baseList = [...baseList, ...items];
  }

  return [...baseList, ...baseList];
};

const topRowDocs = computed(() => {
  let arr1 = carouselCards.value.slice(0, carouselCards.value.length / 2);
  return prepareInfiniteList(arr1);
});

const bottomRowDocs = computed(() => {
  let arr2 = carouselCards.value.slice(
    carouselCards.value.length / 2,
    carouselCards.value.length
  );
  return prepareInfiniteList(arr2);
});

const countAnnotations = computed(() => userNotes.value.length);

/* Search functionality
- When user starts typing, animation goes away and search results show up
- Highlight in green if the user selects/types a match
- @paper: Searches in papers  
- @highlight: Searches in highlight text
- @sticky: Searches in sticky note content
- @recent: Searches within the past week
- @collections (COME BACK TO THIS)

*note to self -> make sure search is implemented robustly and @recent works with other filters.
- No mixing and matching filters with anything besides <x> and @recent
- Don't allow user to set @paper and @highlight for ex (make a warning somewhere)
- Recent is defined as within the past week

will also implement cool ui stuff for UX with the @
- Whenever a search result is clicked, open that paper in a new tab

For template:
On the search card will highlight the similarity with the search query

*/

const searchQuery = ref("");
const searchActive = computed(() => searchQuery.value.length > 0);
const errorMsg = ref("");

// Auto-complete logic
const showSuggestions = ref(false);
const validFilters = ["paper", "highlight", "sticky", "notepad", "recent"];
const activeSuggestionIndex = ref(0);

const filteredSuggestions = computed(() => {
  const match = searchQuery.value.match(/@(\w*)$/); // regex finds out if query contains @
  if (!match) return [];
  const query = match[1].toLowerCase(); // gets the string user types after @
  return validFilters.filter((f) => f.startsWith(query)); //find valid filters from list
});

// checks on each input on whether @ suggestions sshould be active
const handleInput = (e) => {
  errorMsg.value = "";
  const match = searchQuery.value.match(/@(\w*)$/);
  showSuggestions.value = !!match && filteredSuggestions.value.length > 0;
  if (showSuggestions.value) activeSuggestionIndex.value = 0;
};

// completes @<filter> whenever you hit enter on a filter suggestion
const applyFilter = (filter) => {
  const regex = /@(\w*)$/;
  searchQuery.value = searchQuery.value.replace(regex, `@${filter} `);
  showSuggestions.value = false;
  if (chatInputRef.value) chatInputRef.value.focus();
};

// up and down on @ suggestions
const navigateSuggestions = (direction) => {
  if (!showSuggestions.value) return;
  const len = filteredSuggestions.value.length;
  activeSuggestionIndex.value =
    (activeSuggestionIndex.value + direction + len) % len;
};

const selectSuggestion = () => {
  if (showSuggestions.value) {
    applyFilter(filteredSuggestions.value[activeSuggestionIndex.value]);
  }
};

// final func to get search results
function getSearchResults(
  query,
  at_paper,
  at_highlight,
  at_notepad,
  at_sticky,
  at_recent
) {
  // handling @ filters
  let possibleVals = userNotes.value;

  const oneWeekAgo = new Date();
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);

  if (at_recent) {
    possibleVals = possibleVals.filter((obj) => {
      const dateStr = obj.annotations?.updated_at;
      if (!dateStr) return false;
      const lastUpdate = new Date(dateStr);
      return lastUpdate >= oneWeekAgo;
    });
  }

  // makes sure that user can't select two of the following tags in same query
  const trueCount = at_paper + at_highlight + at_sticky + at_notepad;
  if (trueCount >= 2) {
    errorMsg.value = "You can only use 1 filter + @recent at a time.";
    return [];
  }

  let flattenedResults = [];

  possibleVals.forEach((doc) => {
    // check if document is within recent window (a week) for tagging
    const dateStr = doc.updated_at || doc.annotations?.updated_at;
    const isRecent = dateStr ? new Date(dateStr) >= oneWeekAgo : false;
    const displayDate = dateStr ? new Date(dateStr).toLocaleDateString() : "";

    const cleanQuery = query.toLowerCase();

    // check which filters are active. If none, check all fields.

    // @paper
    if (at_paper && doc.title.toLowerCase().includes(cleanQuery)) {
      flattenedResults.push({
        title: doc.title,
        content: doc.title, // bc the match is the title
        matchType: "Paper Match",
        typeColor: "text-indigo-400",
        isRecent,
        date: displayDate,
      });
    }

    const anns = doc.annotations || {};

    // @highlights
    if (at_highlight || trueCount === 0) {
      (anns.highlight_data || []).forEach((h) => {
        if (h.text.toLowerCase().includes(cleanQuery)) {
          flattenedResults.push({
            title: doc.title,
            content: h.text,
            matchType: "Highlight",
            typeColor: "text-emerald-400",
            isRecent,
            date: displayDate,
          });
        }
      });
    }

    // @sticky
    if (at_sticky || trueCount === 0) {
      (anns.sticky_note_data || []).forEach((s) => {
        if (s.content.toLowerCase().includes(cleanQuery)) {
          flattenedResults.push({
            title: doc.title,
            content: s.content,
            matchType: "Sticky Note",
            typeColor: "text-purple-400",
            isRecent,
            date: displayDate,
          });
        }
      });
    }

    // @notepad
    if (at_notepad || trueCount === 0) {
      if (
        anns.notepad &&
        typeof anns.notepad === "string" &&
        anns.notepad.toLowerCase().includes(cleanQuery)
      ) {
        flattenedResults.push({
          title: doc.title,
          content: anns.notepad,
          matchType: "Notepad",
          typeColor: "text-amber-400",
          isRecent,
          date: displayDate,
        });
      }
    }
  });

  return flattenedResults.slice(0, 100);
}

const searchResults = computed(() => {
  if (!searchQuery.value) return [];

  const q = searchQuery.value;
  const at_paper = q.includes("@paper");
  const at_highlight = q.includes("@highlight");
  const at_notepad = q.includes("@notepad");
  const at_sticky = q.includes("@sticky");
  const at_recent = q.includes("@recent");

  // Remove tags before query gets searched
  const cleanQuery = q
    .replace(/@(paper|highlight|notepad|sticky|recent)\s?/g, "")
    .trim();

  if (!cleanQuery && (at_paper || at_highlight || at_notepad || at_sticky))
    return [];

  return getSearchResults(
    cleanQuery,
    at_paper,
    at_highlight,
    at_notepad,
    at_sticky,
    at_recent
  );
});

// highlights matching text on template
const highlightMatch = (text) => {
  if (!searchQuery.value) return text;
  const cleanTerm = searchQuery.value.replace(/@\w+\s?/g, "").trim();
  if (!cleanTerm) return text;

  const regex = new RegExp(`(${cleanTerm})`, "gi");
  return text.replace(
    regex,
    '<span class="text-green-400 font-bold bg-green-400/10 rounded px-1">$1</span>'
  );
};

// Ai chat

/* @ functionality
- @paper:<paperTitle> match with paper title and upload that pdf as model context
- @recent: context for the past week (limit somehow)
- @collections (COME BACK TO THIS)

*/
const paperSuggestions = computed(() => {
  return userNotes.value.map((doc) => ({
    label: doc.title,
    id: doc.id,
  }));
});

const hasAnnotations = computed(() => userNotes.value.length > 0);
const chatInputRef = ref(null);

const focusAIChat = () => {
  if (chatInputRef.value) {
    chatInputRef.value.focus();
  }
};
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
  animation: gradient 10s ease infinite;
}

@keyframes scrollLeft {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
}

@keyframes scrollRight {
  0% {
    transform: translateX(-50%);
  }
  100% {
    transform: translateX(0);
  }
}

.animate-scroll-left {
  animation: scrollLeft 60s linear infinite;
}

.animate-scroll-right {
  animation: scrollRight 60s linear infinite;
}

.mask-sides {
  mask-image: linear-gradient(
    to right,
    transparent,
    black 10%,
    black 90%,
    transparent
  );
  -webkit-mask-image: linear-gradient(
    to right,
    transparent,
    black 10%,
    black 90%,
    transparent
  );
}
</style>
