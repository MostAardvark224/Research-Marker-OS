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
          </div>

          <div class="mb-4 relative group">
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
              placeholder="Search concepts, highlight text, or tags... (hint: use the @ symbol to narrow your search)"
              class="w-full bg-white/[0.03] border border-white/10 rounded-2xl py-5 pl-12 pr-6 text-lg text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500/50 focus:bg-white/[0.05] focus:ring-1 focus:ring-indigo-500/50 transition-all shadow-lg shadow-black/50"
            />
          </div>

          <div class="flex justify-center items-center gap-5 mb-10">
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
                @click="focusAIChat"
                class="text-[11px] font-semibold uppercase tracking-widest text-slate-300 group-hover:text-cyan-400 transition-colors"
                >Ask AI</span
              >
            </button>
          </div>

          <div class="mb-12">
            <div class="flex items-center justify-between mb-6">
              <h2
                class="text-lg font-medium text-white flex items-center gap-2"
              >
                <Icon name="uil:pen" class="text-indigo-400" />
                Recent Annotations
              </h2>
              <!-- <button
                class="text-xs text-slate-500 hover:text-white transition-colors"
              >
                View All
              </button> -->
            </div>

            <div
              class="flex gap-4 overflow-x-auto pb-4 custom-scrollbar mask-right"
            >
              <div
                class="min-w-[280px] h-48 rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] p-5 flex flex-col justify-between transition-all cursor-pointer group"
              >
                <div>
                  <div class="flex items-center gap-2 mb-3">
                    <span class="w-2 h-2 rounded-full bg-yellow-400"></span>
                    <span
                      class="text-xs text-slate-500 uppercase tracking-wider"
                      >Highlight</span
                    >
                  </div>
                  <p
                    class="text-sm text-slate-300 line-clamp-3 leading-relaxed font-serif italic"
                  >
                    "xyz text from highlight..."
                  </p>
                </div>
                <div
                  class="flex items-center gap-2 text-xs text-slate-500 group-hover:text-indigo-300 transition-colors"
                >
                  <Icon name="uil:file-alt" />
                  <span>xyz paper name</span>
                </div>
              </div>

              <div
                class="min-w-[280px] h-48 rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] p-5 flex flex-col justify-between transition-all cursor-pointer group"
              >
                <div>
                  <div class="flex items-center gap-2 mb-3">
                    <span class="w-2 h-2 rounded-full bg-pink-400"></span>
                    <span
                      class="text-xs text-slate-500 uppercase tracking-wider"
                      >Sticky Note</span
                    >
                  </div>
                  <p
                    class="text-sm text-slate-300 line-clamp-3 leading-relaxed"
                  >
                    xyz sticky note
                  </p>
                </div>
                <div
                  class="flex items-center gap-2 text-xs text-slate-500 group-hover:text-pink-300 transition-colors"
                >
                  <Icon name="uil:file-alt" />
                  <span>xyz paper title</span>
                </div>
              </div>

              <div
                class="min-w-[280px] h-48 rounded-xl border border-dashed border-white/10 bg-transparent flex flex-col items-center justify-center gap-3 text-slate-600"
              >
                <Icon name="uil:plus" class="text-2xl" />
                <span class="text-sm">New Annotation</span>
              </div>
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between mb-6">
              <h2
                class="text-lg font-medium text-white flex items-center gap-2"
              >
                <Icon name="uil:layer-group" class="text-purple-400" />
                Smart Collections
              </h2>
            </div>
            <div class="flex gap-4 overflow-x-auto pb-4 custom-scrollbar">
              <div
                class="min-w-[200px] h-32 rounded-xl bg-gradient-to-br from-indigo-500/10 to-transparent border border-indigo-500/20 p-4 flex flex-col justify-end hover:border-indigo-500/40 transition-colors cursor-pointer"
              >
                <h3 class="font-medium text-indigo-100">xyz</h3>
                <span class="text-xs text-indigo-400/70">xyz Papers</span>
              </div>
              <div
                class="min-w-[200px] h-32 rounded-xl bg-gradient-to-br from-purple-500/10 to-transparent border border-purple-500/20 p-4 flex flex-col justify-end hover:border-purple-500/40 transition-colors cursor-pointer"
              >
                <h3 class="font-medium text-purple-100">xyz</h3>
                <span class="text-xs text-purple-400/70">xyz Papers</span>
              </div>
              <div
                class="min-w-[200px] h-32 rounded-xl bg-gradient-to-br from-slate-800/30 to-transparent border border-white/10 p-4 flex flex-col justify-end hover:bg-slate-800/50 transition-colors cursor-pointer"
              >
                <h3 class="font-medium text-slate-300">xyz</h3>
                <span class="text-xs text-slate-500">xyz Papers</span>
              </div>
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
                Hello! I have indexed <strong>x papers</strong> and
                <strong>y annotations</strong>. I can help you summarize
                documents, find connections between concepts, or draft outlines.
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
  animation: gradient 5s ease infinite;
}

.mask-right {
  mask-image: linear-gradient(to right, black 85%, transparent 100%);
  -webkit-mask-image: linear-gradient(to right, black 85%, transparent 100%);
}
</style>
