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
          <span
            class="text-[10px] uppercase tracking-wider text-slate-500 font-medium mt-0.5"
          >
            by Amay Babel
          </span>
        </div>
        <NuxtLink
          to="/"
          class="flex h-10 items-center justify-start gap-3 overflow-hidden whitespace-nowrap rounded-lg px-3 text-white/40 transition-all hover:bg-white/5 hover:text-white"
        >
          <Icon name="uil:arrow-left" class="text-xl shrink-0" />
          <span class="text-xs font-semibold uppercase tracking-widest">
            Back to Index
          </span>
        </NuxtLink>
      </div>
    </nav>

    <div class="flex flex-1 overflow-hidden h-[calc(100vh-65px)]">
      <main
        class="p-8 lg:p-12 overflow-y-auto relative border-r border-white/5 custom-scrollbar"
        :style="{ width: `${100 - sidebarWidth}%` }"
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

      <div
        @mousedown.prevent="startDrag"
        class="w-1 h-full cursor-col-resize z-50 flex flex-col justify-center items-center group relative -ml-[2px]"
      >
        <div
          class="absolute inset-y-0 w-[1px] bg-indigo-500/0 group-hover:bg-indigo-500/50 transition-colors duration-300"
        ></div>

        <div
          class="relative w-5 h-10 bg-[#050508] border border-white/10 rounded-full flex items-center justify-center shadow-[0_0_10px_rgba(0,0,0,0.8)] group-hover:border-indigo-500/50 group-hover:scale-110 group-active:scale-95 transition-all duration-200"
        >
          <Icon
            name="uil:angle-left"
            class="text-slate-500 group-hover:text-indigo-400 transition-colors text-lg mr-[1px]"
          />
        </div>
      </div>
      <aside
        class="bg-[#050508] fixed right-0 top-[65px] bottom-0 flex flex-col border-l border-white/5 overflow-hidden z-30"
        :style="{ width: `${sidebarWidth}%` }"
      >
        <div
          class="p-6 border-b border-white/5 flex items-center justify-between bg-[#050508]/90 backdrop-blur z-10"
        >
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
              <Icon name="material-symbols:smart-toy-outline" class="text-xl" />
            </div>
            <div>
              <h2 class="text-sm font-semibold text-white">
                Research Assistant
              </h2>
              <div class="flex items-center gap-1.5 mt-0.5">
                <span
                  class="w-1.5 h-1.5 rounded-full"
                  :class="
                    isAiLoading
                      ? 'bg-amber-400 animate-pulse'
                      : 'bg-emerald-500'
                  "
                ></span>
                <span
                  class="text-[10px] text-slate-500 uppercase tracking-wider font-medium"
                >
                  {{ isAiLoading ? "Thinking..." : "Online" }}
                </span>
              </div>
            </div>
          </div>

          <button
            @click="
              showHistory = !showHistory;
              if (showHistory) fetchSavedChats();
            "
            class="p-2 rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors relative"
            title="Chat History"
          >
            <Icon
              :name="showHistory ? 'uil:times' : 'uil:history'"
              class="text-xl"
            />
          </button>
        </div>

        <div class="flex-1 relative overflow-hidden flex flex-col">
          <div
            ref="chatContainerRef"
            class="flex-1 overflow-y-auto p-6 pb-32 space-y-6 custom-scrollbar flex flex-col"
          >
            <div v-if="chatHistory.length === 0" class="space-y-6">
              <div class="flex gap-4">
                <div
                  class="w-8 h-8 rounded bg-indigo-500/20 flex items-center justify-center shrink-0"
                >
                  <Icon name="uil:robot" class="text-indigo-400" />
                </div>
                <div class="space-y-2">
                  <div class="text-xs text-slate-500">Research Assistant</div>
                  <div
                    class="p-4 rounded-xl rounded-tl-none bg-white/[0.03] border border-white/5 text-sm xl:text-[16px] text-slate-300 leading-relaxed"
                  >
                    Hello! I have indexed
                    <strong>{{ countAnnotations }} papers</strong>. I can help
                    you summarize documents, find connections between concepts,
                    or draft outlines.
                  </div>
                </div>
              </div>
              <div
                class="flex-1 flex flex-col items-center justify-center text-center opacity-30 pointer-events-none select-none pt-20"
              >
                <Icon
                  name="uil:comment-alt-lines"
                  class="text-4xl text-slate-700 mb-2"
                />
                <p class="text-sm text-slate-600">Ask a question to begin</p>
              </div>
            </div>

            <div
              v-for="(msg, index) in chatHistory"
              :key="index"
              class="flex gap-4"
            >
              <div
                v-if="msg.role === 'user'"
                class="w-8 h-8 shrink-0 flex items-center justify-center"
              >
                <div
                  class="w-6 h-6 rounded-full bg-slate-700 border border-white/10 flex items-center justify-center"
                >
                  <Icon name="uil:user" class="text-slate-300 text-xs" />
                </div>
              </div>

              <div
                v-else
                class="w-8 h-8 rounded bg-indigo-500/20 flex items-center justify-center shrink-0"
              >
                <Icon name="uil:robot" class="text-indigo-400" />
              </div>

              <div class="space-y-1 max-w-[85%]">
                <div class="text-xs xl:text-[16px] text-slate-500 capitalize">
                  {{ msg.role === "model" ? "Assistant" : "You" }}
                </div>
                <div
                  class="p-4 rounded-xl text-sm xl:text-[16px] leading-relaxed overflow-x-auto"
                  :class="
                    msg.role === 'user'
                      ? 'bg-indigo-500/10 border border-indigo-500/20 text-indigo-100 rounded-tr-none'
                      : 'bg-white/[0.03] border border-white/5 text-slate-300 rounded-tl-none prose prose-invert prose-sm'
                  "
                  v-html="
                    msg.role === 'model' ? msg.displayContent : msg.content
                  "
                ></div>
              </div>
            </div>

            <div v-if="isAiLoading" class="flex gap-4">
              <div
                class="w-8 h-8 rounded bg-indigo-500/20 flex items-center justify-center shrink-0"
              >
                <Icon name="uil:robot" class="text-indigo-400" />
              </div>
              <div
                class="p-4 rounded-xl rounded-tl-none bg-white/[0.03] border border-white/5"
              >
                <div class="flex gap-1">
                  <span
                    class="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce"
                  ></span>
                  <span
                    class="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce delay-100"
                  ></span>
                  <span
                    class="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce delay-200"
                  ></span>
                </div>
              </div>
            </div>
          </div>

          <div
            v-if="showHistory"
            class="absolute inset-0 bg-[#050508] z-40 flex flex-col animate-fade-in"
          >
            <div class="p-4 border-b border-white/5">
              <button
                @click="startNewChat"
                class="w-full py-3 rounded-xl border border-dashed border-white/20 text-slate-400 hover:text-white hover:border-indigo-500/50 hover:bg-indigo-500/10 transition-all flex items-center justify-center gap-2 text-sm font-medium"
              >
                <Icon name="uil:plus" />
                Start New Chat
              </button>
            </div>

            <div class="flex-1 overflow-y-auto p-2 custom-scrollbar">
              <div v-if="savedChats.length === 0" class="text-center py-10">
                <p class="text-slate-500 text-sm">No saved chats found.</p>
              </div>

              <div
                v-for="chat in savedChats"
                :key="chat.id"
                @click="loadChat(chat.id)"
                class="group p-3 rounded-xl hover:bg-white/5 cursor-pointer transition-colors border border-transparent hover:border-white/5 flex justify-between items-center mb-1"
                :class="{
                  'bg-white/5 border-white/10': chat.id === currentChatId,
                }"
              >
                <div class="flex-1 min-w-0 pr-3">
                  <h4
                    class="text-sm text-slate-300 truncate group-hover:text-white transition-colors"
                  >
                    {{ chat.name }}
                  </h4>
                  <p class="text-[10px] text-slate-600 truncate mt-0.5">
                    {{ new Date(chat.updated_at).toLocaleDateString() }}
                  </p>
                </div>

                <button
                  @click="deleteChat(chat.id, $event)"
                  class="p-1.5 rounded text-slate-600 hover:text-red-400 hover:bg-red-400/10 opacity-0 group-hover:opacity-100 transition-all"
                  title="Delete Chat"
                >
                  <Icon name="uil:trash-alt" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <div
          class="absolute bottom-0 left-0 w-full p-6 border-t border-white/5 bg-[#050508] z-20"
        >
          <div class="relative">
            <div
              v-if="showChatSuggestions"
              class="absolute bottom-full mb-2 w-full bg-[#15151A] border border-white/10 rounded-xl overflow-hidden shadow-2xl z-50 max-h-48 overflow-y-auto custom-scrollbar"
            >
              <div
                v-for="(suggestion, index) in filteredChatSuggestions"
                :key="suggestion.id"
                class="px-4 py-3 cursor-pointer hover:bg-white/5 flex items-center gap-3 transition-colors border-b border-white/5 last:border-0"
                :class="{ 'bg-white/10': activeChatSuggestionIndex === index }"
                @click="selectChatSuggestion(suggestion)"
              >
                <div
                  class="w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold"
                  :class="
                    suggestion.type === 'cmd'
                      ? 'bg-purple-500/20 text-purple-400'
                      : 'bg-indigo-500/20 text-indigo-400'
                  "
                >
                  {{ suggestion.type === "cmd" ? "/" : "@" }}
                </div>
                <span class="text-sm text-slate-200 truncate">{{
                  suggestion.label
                }}</span>
              </div>
            </div>

            <textarea
              ref="chatInputRef"
              v-model="chatInput"
              @input="handleChatInput"
              @keydown.down.prevent="navigateChatSuggestions(1)"
              @keydown.up.prevent="navigateChatSuggestions(-1)"
              @keydown.enter.prevent="
                showChatSuggestions
                  ? selectChatSuggestion(
                      filteredChatSuggestions[activeChatSuggestionIndex]
                    )
                  : sendChatMessage()
              "
              rows="1"
              placeholder="Ask a question..."
              class="w-full bg-slate-900/50 border border-white/10 rounded-xl py-1 xl:py-4 pl-4 pr-46 text-[14px] xl:text-[17px] text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500/40 focus:bg-slate-900 resize-none overflow-y-auto transition-all shadow-inner custom-scrollbar"
              style="min-height: 56px; max-height: 150px"
            ></textarea>

            <div
              class="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-4 backdrop-blur-md rounded-lg pl-2 py-1"
            >
              <div
                class="flex items-center gap-2 border-r border-white/10 pr-4 mb-2 transition-opacity duration-300"
                :class="{ 'opacity-50 cursor-not-allowed': hasContextTag }"
              >
                <div
                  class="flex items-center gap-2"
                  :class="
                    hasContextTag ? 'pointer-events-none' : 'cursor-pointer'
                  "
                  @click="!hasContextTag && (isRagEnabled = !isRagEnabled)"
                >
                  <span
                    class="text-[10px] font-bold uppercase tracking-wider transition-colors"
                    :class="
                      hasContextTag
                        ? 'text-slate-600'
                        : isRagEnabled
                        ? 'text-emerald-400'
                        : 'text-slate-600'
                    "
                    >RAG</span
                  >

                  <div
                    class="w-8 h-4 rounded-full relative transition-colors duration-200"
                    :class="
                      hasContextTag
                        ? 'bg-slate-900 border border-white/5'
                        : isRagEnabled
                        ? 'bg-emerald-500/20 border border-emerald-500/50'
                        : 'bg-slate-800 border border-white/5'
                    "
                  >
                    <div
                      class="absolute top-0.5 left-0.5 w-2.5 h-2.5 rounded-full bg-current transition-all duration-200 shadow-sm"
                      :class="
                        hasContextTag
                          ? 'translate-x-0 bg-slate-600'
                          : isRagEnabled
                          ? 'translate-x-4 bg-emerald-400'
                          : 'translate-x-0 bg-slate-500'
                      "
                    ></div>
                  </div>
                </div>

                <div class="relative group">
                  <Icon
                    name="uil:question-circle"
                    class="text-slate-600 hover:text-slate-400 text-lg cursor-help transition-colors mt-1.5"
                  />
                  <div
                    class="absolute bottom-full right-[-50px] mb-4 w-64 p-3 bg-[#15151A] border border-white/10 rounded-xl shadow-2xl text-xs text-slate-400 leading-relaxed opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50"
                  >
                    <div class="font-bold text-slate-200 mb-1">
                      Retrieval Augmented Generation
                    </div>
                    <p v-if="hasContextTag" class="text-amber-400 font-medium">
                      <Icon name="uil:padlock" class="mr-1 inline-block" />
                      RAG is disabled because you are using specific context
                      tags (@).
                    </p>
                    <p v-else>
                      Scans your library for context before answering.
                    </p>
                  </div>
                </div>
              </div>

              <button
                @click="sendChatMessage"
                :disabled="isAiLoading || !chatInput"
                class="p-1.5 mb-1.5 rounded transition-all duration-200 flex items-center justify-center"
                :class="
                  chatInput
                    ? 'bg-indigo-500 text-white hover:bg-indigo-400 shadow-lg shadow-indigo-500/20'
                    : 'bg-indigo-500/10 text-indigo-400/50 cursor-not-allowed'
                "
              >
                <Icon name="uil:message" class="text-lg" />
              </button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
const {
  public: { frontendOrigin, apiBaseURL },
} = useRuntimeConfig();
import { marked } from "marked";
import DOMPurify from "dompurify";
import markedKatex from "marked-katex-extension";
import "katex/dist/katex.min.css";

// settings for rendering AI chat
marked.use(
  markedKatex({
    throwOnError: false,
    output: "html",
  })
);

marked.use({ breaks: true, gfm: true });

// sidebar dragging to change width
const sidebarWidth = ref(30);
const isDragging = ref(false);

const startDrag = () => {
  isDragging.value = true;
  document.addEventListener("mousemove", onDrag);
  document.addEventListener("mouseup", stopDrag);
  document.body.style.userSelect = "none";
};

const onDrag = (e) => {
  if (!isDragging.value) return;

  const containerWidth = window.innerWidth;
  const newWidth = ((containerWidth - e.clientX) / containerWidth) * 100;

  if (newWidth >= 30 && newWidth <= 40) {
    sidebarWidth.value = newWidth;
  } else if (newWidth < 30) {
    sidebarWidth.value = 30;
  } else if (newWidth > 40) {
    sidebarWidth.value = 40;
  }
};

const stopDrag = () => {
  isDragging.value = false;
  document.removeEventListener("mousemove", onDrag);
  document.removeEventListener("mouseup", stopDrag);
  document.body.style.userSelect = "";
};

// Since these files are getting rlly big, going to start using "HEADER" as a way to locate functionality.
// Two headers as of time of writing
// HEADER: SEARCH
// HEADER: AI
// just control-f to find those sections

// HEADER: SEARCH

const userNotes = ref([]);
// fetching user notes
async function fetchNotes() {
  try {
    const res = await $fetch(`${apiBaseURL}/search-notes/`, {
      method: "GET",
    });
    userNotes.value = res;
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
const hasAnnotations = computed(() => userNotes.value.length > 0);

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
    const dateStr = doc.annotations?.updated_at;
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
        paper_id: doc.doc_id,
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
            paper_id: doc.doc_id,
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
            paper_id: doc.doc_id,
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
          paper_id: doc.doc_id,
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

// when result card clicked, send to url
function sendToPaper(result) {
  // default frontend origin is localhost:3000, if this isn't working check ur env vars
  const doc_id = result.paper_id;
  const url = `${frontendOrigin}/annotate/${doc_id}`;
  window.open(url, "_blank"); // opens in a new window
}

// HEADER: AI

/* @ functionality
- @paper:<paperTitle> match with paper title and upload that pdf as model context
- @recent: context for the past week (limit somehow)
- @collections (COME BACK TO THIS)
More notes can be found in backend api/views.py
*/

const chatHistory = ref([]);
const chatInput = ref("");
const currentChatId = ref(null);
const isAiLoading = ref(false);
const chatContainerRef = ref(null); // auto-scrolling
const chatInputRef = ref(null); // Ref for the textarea
const isRagEnabled = ref(false);

const showHistory = ref(false);
const savedChats = ref([]);
const isDeleting = ref(false);

// CHATS
// logic having to do w/ loading and deleting previous chats

// fetching all chats
async function fetchSavedChats() {
  try {
    const res = await $fetch(`${apiBaseURL}/chatlogs/`, {
      method: "GET",
    });
    savedChats.value = res.sort((a, b) => b.id - a.id); // sort by newest
    // console.log(savedChats.value);
  } catch (error) {
    console.error("Error fetching chats:", error);
  }
}

// load a specific chat
async function loadChat(chatId) {
  try {
    isAiLoading.value = true;
    const res = await $fetch(`${apiBaseURL}/chatlogs/${chatId}/`, {
      method: "GET",
    });

    currentChatId.value = res.id;
    // console.log(currentChatId.value);

    chatHistory.value = (res.content || []).map((msg) => ({
      role: msg.role,
      content: msg.content,
      displayContent:
        msg.role === "model" ? parseMarkdown(msg.content) : msg.content, // only parsing md for model just to optimize
    }));

    showHistory.value = false;
    await scrollToBottom();
  } catch (error) {
    console.error("Error loading chat:", error);
  } finally {
    isAiLoading.value = false;
  }
}

// delete a chat
async function deleteChat(chatId, event) {
  if (event) event.stopPropagation();

  if (!confirm("Are you sure you want to delete this chat log?")) return;

  try {
    isDeleting.value = true;
    await $fetch(`${apiBaseURL}/chatlogs/${chatId}/`, {
      method: "DELETE",
    });

    savedChats.value = savedChats.value.filter((c) => c.id !== chatId);

    if (currentChatId.value === chatId) {
      currentChatId.value = null;
      chatHistory.value = [];
    }
  } catch (error) {
    console.error("Error deleting chat:", error);
  } finally {
    isDeleting.value = false;
  }
}

// start a new chat
function startNewChat() {
  currentChatId.value = null;
  chatHistory.value = [];
  showHistory.value = false;
  if (chatInputRef.value) chatInputRef.value.focus(); // focuses input
}

// autocomplete logic
const showChatSuggestions = ref(false);
const activeChatSuggestionIndex = ref(0);

// combine papers and special commands for suggestions
const chatSuggestions = computed(() => {
  const papers = userNotes.value.map((n) => ({
    type: "paper",
    label: n.title,
    id: n.doc_id,
  }));
  const commands = [{ type: "cmd", label: "recent", id: "recent" }];
  return [...commands, ...papers];
});

const filteredChatSuggestions = computed(() => {
  const match = chatInput.value.match(/@([\w\s]*)$/);
  if (!match) return [];
  const query = match[1].toLowerCase();

  return chatSuggestions.value
    .filter((item) => item.label.toLowerCase().includes(query))
    .slice(0, 5); // Limit to 5 suggestions
});

const handleChatInput = (e) => {
  autoResizeInput();

  // Check for @
  const match = chatInput.value.match(/@([\w\s]*)$/);
  showChatSuggestions.value =
    !!match && filteredChatSuggestions.value.length > 0;
  if (showChatSuggestions.value) activeChatSuggestionIndex.value = 0;
};

const navigateChatSuggestions = (direction) => {
  if (!showChatSuggestions.value) return;
  const len = filteredChatSuggestions.value.length;
  activeChatSuggestionIndex.value =
    (activeChatSuggestionIndex.value + direction + len) % len;
};

const selectChatSuggestion = (suggestion) => {
  const regex = /@([\w\s]*)$/;
  // wrap paper titles in quotes to make parsing easier
  const replacement =
    suggestion.type === "paper"
      ? `@paper:"${suggestion.label}" `
      : `@${suggestion.label} `;

  chatInput.value = chatInput.value.replace(regex, replacement);
  showChatSuggestions.value = false;
  if (chatInputRef.value) chatInputRef.value.focus();
};

// api logic

// no rag if @xyz exists in prompt
const hasContextTag = computed(() => {
  return /(@recent|@paper:"[^"]+")/.test(chatInput.value);
});

watch(hasContextTag, (newVal) => {
  if (newVal) {
    isRagEnabled.value = false;
  }
});

// auto-scroll to bottom
const scrollToBottom = async () => {
  await nextTick();
  if (chatContainerRef.value) {
    chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight;
  }
};

// parse the raw input string to find context flags
const parseContextFromInput = (text) => {
  let paperIds = [];
  let atRecent = false;
  let cleanPrompt = text;

  if (text.includes("@recent")) {
    atRecent = true;
    cleanPrompt = cleanPrompt.replace("@recent", "");
  }

  const paperMatches = [...text.matchAll(/@paper:"([^"]+)"/g)];

  paperMatches.forEach((match) => {
    const title = match[1];
    const foundNote = userNotes.value.find((n) => n.title === title);
    if (foundNote) {
      paperIds.push(foundNote.doc_id);
    }
    cleanPrompt = cleanPrompt.replace(match[0], ""); // removes @xyz from prompt
  });

  return {
    prompt: cleanPrompt.trim(),
    paper_ids: paperIds,
    at_recent: atRecent,
  };
};

const parseMarkdown = (rawText) => {
  if (!rawText) return "";

  // parse the md and katex
  const html = marked.parse(rawText);

  // allows katex specific tags & classes
  return DOMPurify.sanitize(html, {
    ADD_TAGS: [
      "math",
      "annotation",
      "semantics",
      "mtext",
      "mn",
      "mo",
      "mi",
      "jsp",
      "span",
    ],
    ADD_ATTR: ["class", "style"],
  });
};

async function sendChatMessage() {
  if (!chatInput.value.trim() || isAiLoading.value) return;

  const rawInput = chatInput.value;
  const contextData = parseContextFromInput(rawInput);

  chatHistory.value.push({
    role: "user",
    content: rawInput, // raw input so user sees tags
    displayContent: rawInput,
  });

  chatInput.value = "";
  isAiLoading.value = true;
  await scrollToBottom();

  try {
    // send to backend
    const payload = {
      prompt: contextData.prompt,
      chat_id: currentChatId.value,
      paper_ids: contextData.paper_ids,
      at_recent: contextData.at_recent,
      rag_enabled: isRagEnabled.value,
    };

    const res = await $fetch(`${apiBaseURL}/ask-ai/`, {
      method: "POST",
      body: payload,
    });

    // handle response
    if (res.model_response) {
      chatHistory.value.push({
        role: "model",
        content: res.model_response,
        displayContent: parseMarkdown(res.model_response),
      });

      // update session id if new chat
      if (res.chat_id) currentChatId.value = res.chat_id;
    }
  } catch (error) {
    // error handling
    console.error("AI Chat Error:", error);
    chatHistory.value.push({
      role: "model",
      content: "Error: Unable to connect to Research Assistant.",
      displayContent: `<span class="text-red-400">Error: Unable to connect to Research Assistant. (${error.message})</span>`,
    });
  } finally {
    isAiLoading.value = false;
    await scrollToBottom();
  }
}

const focusAIChat = () => {
  if (chatInputRef.value) {
    chatInputRef.value.focus();
  }
};

// deals w/ chatbox input
const autoResizeInput = () => {
  const el = chatInputRef.value;
  if (!el) return;

  el.style.height = "auto";

  const newHeight = Math.min(el.scrollHeight, 150);
  el.style.height = `${newHeight}px`;
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

/* Force katex to use the current text color */
:deep(.katex) {
  color: inherit !important;
  font-size: 1.1em;
}

:deep(.katex-display) {
  margin: 1em 0;
  overflow-x: auto;
  overflow-y: hidden;
}
</style>
