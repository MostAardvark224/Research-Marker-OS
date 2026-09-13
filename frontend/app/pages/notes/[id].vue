<template>
  <main class="flex h-screen flex-col overflow-hidden bg-[#050508] text-white">
    <header class="flex h-16 shrink-0 items-center gap-3 border-b border-white/5 bg-[#07070b] px-4">
      <NuxtLink to="/" class="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-white/5 hover:text-white" title="Back to library"><Icon name="ph:arrow-left" /></NuxtLink>
      <Icon name="ph:notebook" class="text-indigo-400" />
      <input
        v-model="title"
        class="min-w-0 flex-1 bg-transparent text-sm font-semibold text-slate-100 outline-none placeholder:text-slate-700"
        maxlength="255"
        placeholder="Untitled note"
        @blur="flushSave"
      />
      <span class="hidden text-[10px] uppercase tracking-wider sm:block" :class="saveState === 'error' ? 'text-red-400' : 'text-slate-600'">{{ saveLabel }}</span>
      <button class="flex h-9 items-center gap-2 rounded-lg border border-white/10 px-3 text-xs text-slate-400 hover:bg-white/5 hover:text-white" @click="split = !split">
        <Icon :name="split ? 'ph:square-half' : 'ph:columns'" /> {{ split ? "Single pane" : "Side by side" }}
      </button>
    </header>

    <div v-if="loading" class="flex flex-1 items-center justify-center text-sm text-slate-600">Loading note…</div>
    <div v-else-if="error" class="flex flex-1 flex-col items-center justify-center gap-4 text-slate-500"><p>{{ error }}</p><NuxtLink to="/" class="text-indigo-400">Back to library</NuxtLink></div>
    <div v-else class="flex min-h-0 flex-1">
      <nav class="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-white/5 bg-[#07070b] py-3">
        <button v-for="tab in tabs" :key="tab.id" class="relative flex h-10 w-10 items-center justify-center rounded-lg transition" :class="isVisible(tab.id) ? 'bg-indigo-500/15 text-indigo-300' : 'text-slate-600 hover:bg-white/5 hover:text-slate-300'" :title="tab.label" @click="activeTab = tab.id"><Icon :name="tab.icon" class="text-lg" /><span v-if="activeTab === tab.id" class="absolute -left-2 h-5 w-0.5 rounded-full bg-indigo-400"></span></button>
        <div class="mt-auto text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-800 [writing-mode:vertical-rl]">Research Marker</div>
      </nav>

      <section v-show="isVisible('note')" class="min-w-0 flex-1" :class="{ 'border-r border-white/5': split }">
        <NotepadEditor
          v-model="content"
          :papers="papers"
          :download-title="title"
          @save="flushSave"
        />
      </section>

      <section v-show="isVisible('chat')" class="flex min-w-0 flex-1 flex-col bg-[#08080d]">
        <div class="flex h-12 shrink-0 items-center justify-between border-b border-white/5 px-4">
          <div class="flex items-center gap-2"><Icon name="ph:sparkle" class="text-cyan-400" /><span class="text-xs font-semibold">Note assistant</span><span class="text-[10px] text-slate-600">uses this note as context</span></div>
          <div class="flex items-center gap-1">
            <button class="rounded-md p-2 text-slate-600 hover:bg-white/5 hover:text-white" title="Chat history" @click="toggleHistory"><Icon name="ph:clock-counter-clockwise" /></button>
            <button class="rounded-md p-2 text-slate-600 hover:bg-white/5 hover:text-white" title="New chat" @click="newChat"><Icon name="ph:plus" /></button>
          </div>
        </div>

        <div v-if="showHistory" class="border-b border-white/5 bg-black/20 p-3">
          <p v-if="!savedChats.length" class="py-3 text-center text-xs text-slate-600">No chats saved for this note.</p>
          <button v-for="chat in savedChats" :key="chat.id" class="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs text-slate-400 hover:bg-white/5 hover:text-white" @click="loadChat(chat)"><span class="truncate">{{ chat.name }}</span><span class="ml-3 shrink-0 text-[10px] text-slate-700">{{ new Date(chat.updated_at).toLocaleDateString() }}</span></button>
        </div>

        <div ref="chatScroll" class="flex-1 space-y-5 overflow-y-auto px-5 py-6 custom-scrollbar">
          <div v-if="!messages.length" class="flex h-full flex-col items-center justify-center text-center">
            <span class="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-500/20 bg-cyan-500/10 text-cyan-400"><Icon name="ph:chats-circle" class="text-2xl" /></span>
            <h2 class="text-sm font-semibold text-slate-300">Think alongside your note</h2>
            <p class="mt-2 max-w-xs text-xs leading-5 text-slate-600">Ask for an outline, challenge an argument, connect it with your research library, or turn fragments into a draft.</p>
          </div>
          <div v-for="(message, index) in messages" :key="index" class="flex" :class="message.role === 'user' ? 'justify-end' : 'justify-start'">
            <div class="max-w-[86%] rounded-2xl px-4 py-3 text-sm leading-6" :class="message.role === 'user' ? 'rounded-tr-md bg-indigo-600 text-white' : 'chat-prose rounded-tl-md border border-white/8 bg-[#12121a] text-slate-300'">
              <div v-if="message.role === 'user'" class="whitespace-pre-wrap">{{ message.content }}</div><div v-else v-html="renderMarkdown(message.content)"></div>
            </div>
          </div>
          <div v-if="chatLoading" class="text-xs text-slate-600">Assistant is thinking…</div>
        </div>

        <div class="shrink-0 border-t border-white/5 p-4">
          <div class="overflow-hidden rounded-2xl border border-white/10 bg-[#0b0b10] focus-within:border-indigo-500/40">
            <div class="flex gap-2 border-b border-white/5 px-3 py-2">
              <select v-model="selectedAiProvider" class="ai-select min-w-0 flex-1 rounded-md border border-white/10 px-2 py-1 text-[10px]"><option v-for="provider in availableProviders" :key="provider.id" :value="provider.id">{{ provider.label }}</option></select>
              <select v-if="selectedProviderModels.length" v-model="selectedAiModel" class="ai-select min-w-0 flex-1 rounded-md border border-white/10 px-2 py-1 text-[10px]"><option v-for="model in selectedProviderModels" :key="model" :value="model">{{ model }}</option></select>
              <input v-else v-model="selectedAiModel" class="ai-select min-w-0 flex-1 rounded-md border border-white/10 px-2 py-1 text-[10px]" placeholder="Model id" />
            </div>
            <textarea v-model="chatInput" rows="2" class="max-h-36 min-h-16 w-full resize-none bg-transparent px-4 py-3 text-sm text-slate-200 outline-none placeholder:text-slate-700" placeholder="Ask about this note…" @keydown.enter.exact.prevent="sendMessage"></textarea>
            <div class="flex items-center justify-between border-t border-white/5 px-3 py-2">
              <button class="flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px]" :class="ragEnabled ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-white/10 text-slate-500'" @click="ragEnabled = !ragEnabled"><Icon name="ph:database" /> Library RAG {{ ragEnabled ? "on" : "off" }}</button>
              <button class="rounded-lg px-3 py-1.5 text-xs font-semibold" :class="canSend ? 'bg-indigo-500 text-white hover:bg-indigo-400' : 'bg-white/5 text-slate-600'" :disabled="!canSend" @click="sendMessage"><Icon name="ph:paper-plane-tilt" /></button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup>
import { marked } from "marked";
import DOMPurify from "dompurify";
import markedKatex from "marked-katex-extension";

marked.use(markedKatex({ throwOnError: false, output: "html" }));
marked.use({ breaks: true, gfm: true });
const { public: { apiBaseURL } } = useRuntimeConfig();
const route = useRoute();
const noteId = route.params.id;
const title = ref("");
const content = ref("");
const papers = ref([]);
const loading = ref(true);
const error = ref("");
const saveState = ref("saved");
const activeTab = ref("note");
const split = ref(false);
const tabs = [{ id: "note", label: "Note", icon: "ph:notebook" }, { id: "chat", label: "AI chat", icon: "ph:chat-circle-dots" }];
const isVisible = (tab) => split.value || activeTab.value === tab;
let saveTimer = null;
let saveQueue = Promise.resolve();
const saveLabel = computed(() => ({ dirty: "Unsaved", saving: "Saving…", saved: "Saved", error: "Save failed" })[saveState.value]);

const saveNote = () => {
  const body = { title: title.value.trim() || "Untitled note", content: content.value };
  saveState.value = "saving";
  const request = saveQueue.then(() => $fetch(`${apiBaseURL}/notes/${noteId}/`, { method: "PATCH", body }));
  saveQueue = request.then(() => { saveState.value = "saved"; }, () => { saveState.value = "error"; });
  return request;
};
const scheduleSave = () => { saveState.value = "dirty"; clearTimeout(saveTimer); saveTimer = setTimeout(saveNote, 650); };
const flushSave = () => { if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; } return saveNote(); };
watch([title, content], scheduleSave);

const messages = ref([]);
const chatInput = ref("");
const chatId = ref(null);
const chatLoading = ref(false);
const chatScroll = ref(null);
const showHistory = ref(false);
const savedChats = ref([]);
const ragEnabled = ref(false);
const { aiProviders, selectedAiProvider, selectedAiModel, selectedProviderModels, selectedProviderHasModels, initializeAiModels } = useAiModels();
const availableProviders = computed(() => aiProviders.value.filter((provider) => provider.id !== "codex"));
watch([availableProviders, selectedAiProvider], ([providers, selected]) => { if (selected === "codex") selectedAiProvider.value = providers[0]?.id || "gemini"; });
const canSend = computed(() => chatInput.value.trim() && !chatLoading.value && selectedProviderHasModels.value);
const renderMarkdown = (value) => DOMPurify.sanitize(marked.parse(value || ""));
const scrollBottom = async () => { await nextTick(); if (chatScroll.value) chatScroll.value.scrollTop = chatScroll.value.scrollHeight; };
const sendMessage = async () => {
  if (!canSend.value) return;
  const prompt = chatInput.value.trim();
  messages.value.push({ role: "user", content: prompt });
  chatInput.value = "";
  chatLoading.value = true;
  await scrollBottom();
  try {
    await flushSave();
    const response = await $fetch(`${apiBaseURL}/ask-ai/`, { method: "POST", body: { prompt, chat_id: chatId.value, note_id: Number(noteId), rag_enabled: ragEnabled.value, model_provider: selectedAiProvider.value, model: selectedAiModel.value } });
    chatId.value = response.chat_id;
    messages.value.push({ role: "model", content: response.model_response });
  } catch (cause) {
    messages.value.push({ role: "model", content: `Unable to reach the assistant: ${cause?.data?.error || cause.message}` });
  } finally { chatLoading.value = false; await scrollBottom(); }
};
const fetchChats = async () => { savedChats.value = await $fetch(`${apiBaseURL}/chatlogs/?note=${noteId}`); };
const toggleHistory = async () => { showHistory.value = !showHistory.value; if (showHistory.value) await fetchChats(); };
const loadChat = (chat) => { chatId.value = chat.id; messages.value = chat.content || []; showHistory.value = false; scrollBottom(); };
const newChat = () => { chatId.value = null; messages.value = []; showHistory.value = false; };

onMounted(async () => {
  try {
    const [note, documents] = await Promise.all([
      $fetch(`${apiBaseURL}/notes/${noteId}/`),
      $fetch(`${apiBaseURL}/documents/`).catch((cause) => {
        console.error("Could not load papers for note links", cause);
        return [];
      }),
    ]);
    title.value = note.title;
    content.value = note.content;
    papers.value = documents;
    await initializeAiModels();
  } catch (cause) { error.value = cause?.status === 404 ? "This note no longer exists." : "Could not load this note."; }
  finally { loading.value = false; saveState.value = "saved"; }
});
onBeforeUnmount(() => { clearTimeout(saveTimer); if (!loading.value && saveState.value === "dirty") saveNote(); });
useHead({ title: () => `${title.value || "Untitled note"} | Research Marker` });
</script>

<style scoped>
.ai-select { background: #0b0b10; color: #cbd5e1; outline: none; }
.ai-select option { background: #12121a; }
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 999px; }
.chat-prose :deep(p) { margin: .35rem 0; }
.chat-prose :deep(code) { border-radius: .25rem; background: rgba(255,255,255,.06); color: #fbbf24; padding: .1rem .3rem; }
.chat-prose :deep(pre) { margin: .6rem 0; overflow-x: auto; border-radius: .6rem; background: #030306; padding: .75rem; }
</style>
