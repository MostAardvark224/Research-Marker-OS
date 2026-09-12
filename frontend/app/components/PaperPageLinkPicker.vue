<template>
  <div class="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-5 backdrop-blur-sm" @mousedown.self="$emit('close')">
    <form class="w-full max-w-md rounded-2xl border border-white/10 bg-[#0d0d14] p-5 shadow-2xl" @submit.prevent="insertLink">
      <div class="mb-5 flex items-start justify-between">
        <div>
          <h2 class="text-sm font-semibold text-white">Link to a paper page</h2>
          <p class="mt-1 text-xs text-slate-500">Saved in Markdown as [Paper title][page].</p>
        </div>
        <button type="button" class="rounded-md p-1 text-slate-600 hover:bg-white/5 hover:text-white" @click="$emit('close')"><Icon name="ph:x" /></button>
      </div>
      <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500">Paper</label>
      <input v-model="paperTitle" list="paper-link-titles" autofocus class="mt-2 h-11 w-full rounded-xl border border-white/10 bg-black/25 px-3 text-sm text-slate-200 outline-none focus:border-indigo-500/50" placeholder="Start typing a paper title…" @input="validationError = ''" />
      <datalist id="paper-link-titles"><option v-for="paper in availablePapers" :key="paper.id" :value="paper.title" /></datalist>

      <label class="mt-4 block text-[10px] font-semibold uppercase tracking-wider text-slate-500">Page</label>
      <select v-if="selectedPaper?.page_count" v-model.number="page" class="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0b0b10] px-3 text-sm text-slate-200 outline-none focus:border-indigo-500/50">
        <option v-for="number in Number(selectedPaper.page_count)" :key="number" :value="number">Page {{ number }}</option>
      </select>
      <input v-else v-model.number="page" type="number" min="1" step="1" class="mt-2 h-11 w-full rounded-xl border border-white/10 bg-black/25 px-3 text-sm text-slate-200 outline-none focus:border-indigo-500/50" />
      <div class="mt-4 rounded-lg border border-white/5 bg-black/20 px-3 py-2 font-mono text-xs text-cyan-300">
        [{{ selectedPaper?.title || "paper" }}][{{ selectedPaper ? page : "page" }}]
      </div>
      <p v-if="validationError" class="mt-3 text-xs text-red-400">{{ validationError }}</p>
      <div class="mt-5 flex justify-end gap-2">
        <button type="button" class="rounded-lg px-3 py-2 text-xs text-slate-500 hover:bg-white/5 hover:text-white" @click="$emit('close')">Cancel</button>
        <button type="submit" class="rounded-lg bg-indigo-500 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-400">Insert link</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { findPaperByTitle, validatePaperPageLink } from "../utils/paperPageLinks.js";

const props = defineProps({ papers: { type: Array, default: () => [] }, excludePaperId: { type: [String, Number], default: null }, initialTitle: { type: String, default: "" } });
const emit = defineEmits(["insert", "close"]);
const paperTitle = ref(props.initialTitle);
const page = ref(1);
const validationError = ref("");
const availablePapers = computed(() => props.papers.filter((paper) => String(paper.id) !== String(props.excludePaperId ?? "")));
const selectedPaper = computed(() => findPaperByTitle(availablePapers.value, paperTitle.value));
watch(selectedPaper, () => { page.value = 1; });
const insertLink = () => {
  const result = validatePaperPageLink(availablePapers.value, paperTitle.value, page.value);
  if (!result.valid) { validationError.value = result.error; return; }
  emit("insert", { paper: result.paper, page: result.page });
};
</script>
