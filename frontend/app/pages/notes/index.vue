<template>
  <main class="min-h-screen bg-[#050508] px-6 py-8 text-white">
    <div class="mx-auto max-w-5xl">
      <header class="mb-10 flex items-center justify-between gap-4">
        <div>
          <NuxtLink to="/" class="mb-4 inline-flex items-center gap-2 text-xs text-slate-500 hover:text-white">
            <Icon name="ph:arrow-left" /> Library
          </NuxtLink>
          <h1 class="text-3xl font-semibold tracking-tight">Standalone notes</h1>
          <p class="mt-2 text-sm text-slate-500">Ideas, synthesis, and working drafts that live beyond a single paper.</p>
        </div>
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-sm font-semibold shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400"
          :disabled="creating"
          @click="createNote"
        >
          <Icon name="ph:plus" /> New note
        </button>
      </header>

      <div class="mb-5 flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.025] px-4">
        <Icon name="ph:magnifying-glass" class="text-slate-600" />
        <input v-model="query" class="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-700" placeholder="Search note titles and content…" />
      </div>

      <div v-if="loading" class="py-24 text-center text-sm text-slate-600">Loading notes…</div>
      <div v-else-if="!filteredNotes.length" class="rounded-2xl border border-dashed border-white/10 py-24 text-center">
        <Icon name="ph:notebook" class="mb-4 text-5xl text-slate-800" />
        <p class="text-slate-400">{{ query ? "No notes match your search." : "No standalone notes yet." }}</p>
        <button v-if="!query" class="mt-4 text-sm text-indigo-400 hover:text-indigo-300" @click="createNote">Create your first note</button>
      </div>
      <div v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <NuxtLink
          v-for="note in filteredNotes"
          :key="note.id"
          :to="`/notes/${note.id}`"
          class="group flex min-h-44 flex-col rounded-2xl border border-white/10 bg-[#0b0b10] p-5 transition hover:-translate-y-0.5 hover:border-indigo-500/40 hover:bg-[#101018]"
        >
          <div class="mb-5 flex items-start justify-between gap-3">
            <span class="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400"><Icon name="ph:notebook" /></span>
            <button type="button" class="rounded-lg p-2 text-slate-700 opacity-0 transition hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100" title="Delete note" @click.prevent.stop="deleteNote(note)"><Icon name="ph:trash" /></button>
          </div>
          <h2 class="line-clamp-2 font-medium text-slate-200">{{ note.title }}</h2>
          <p class="mt-2 line-clamp-3 flex-1 text-xs leading-5 text-slate-600">{{ preview(note.content) }}</p>
          <p class="mt-4 text-[10px] uppercase tracking-wider text-slate-700">Edited {{ formatDate(note.updated_at) }}</p>
        </NuxtLink>
      </div>
    </div>
  </main>
</template>

<script setup>
const { public: { apiBaseURL } } = useRuntimeConfig();
const notes = ref([]);
const query = ref("");
const loading = ref(true);
const creating = ref(false);
const filteredNotes = computed(() => {
  const needle = query.value.trim().toLowerCase();
  if (!needle) return notes.value;
  return notes.value.filter((note) => `${note.title} ${note.content}`.toLowerCase().includes(needle));
});
const preview = (content) => String(content || "").replace(/[#>*_`\[\]-]/g, " ").replace(/\s+/g, " ").trim() || "Empty note";
const formatDate = (value) => new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
const fetchNotes = async () => {
  try { notes.value = await $fetch(`${apiBaseURL}/notes/`); }
  finally { loading.value = false; }
};
const createNote = async () => {
  creating.value = true;
  try {
    const note = await $fetch(`${apiBaseURL}/notes/`, { method: "POST", body: { title: "Untitled note", content: "" } });
    await navigateTo(`/notes/${note.id}`);
  } finally { creating.value = false; }
};
const deleteNote = async (note) => {
  if (!confirm(`Delete “${note.title}”? This cannot be undone.`)) return;
  await $fetch(`${apiBaseURL}/notes/${note.id}/`, { method: "DELETE" });
  notes.value = notes.value.filter((item) => item.id !== note.id);
};
onMounted(fetchNotes);
</script>
