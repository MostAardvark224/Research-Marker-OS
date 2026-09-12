<template>
  <div
    class="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
  >
    <div
      class="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
      @click="$emit('close')"
    ></div>

    <div
      class="relative w-full max-w-md bg-[#020204] border border-white/10 rounded-xl shadow-2xl overflow-hidden"
    >
      <header
        class="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#020204]"
      >
        <div>
          <h2 class="font-semibold text-lg tracking-tight text-white">
            New note
          </h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Create a markdown note and file it alongside your papers.
          </p>
        </div>
        <button
          @click="$emit('close')"
          class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
        >
          <Icon name="material-symbols:close" class="text-xl" />
        </button>
      </header>

      <main class="p-4 space-y-4">
        <div class="space-y-2">
          <label for="newNoteTitle" class="text-xs font-medium text-slate-400">
            Title
          </label>
          <input
            id="newNoteTitle"
            ref="titleInput"
            v-model="title"
            type="text"
            placeholder="Untitled note"
            class="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            @keydown.enter.prevent="createNote"
          />
        </div>

        <div class="space-y-2">
          <label for="newNoteFolder" class="text-xs font-medium text-slate-400">
            Folder
          </label>
          <select
            id="newNoteFolder"
            v-model="selectedFolderId"
            class="w-full rounded-lg border border-white/10 bg-[#020204] px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
          >
            <option value="">Unassigned</option>
            <option
              v-for="folder in flattenedFolders"
              :key="folder.id"
              :value="folder.id"
            >
              {{ folder.label }}
            </option>
          </select>
        </div>

        <button
          @click="createNote"
          :disabled="isCreating"
          class="w-full flex items-center justify-center gap-2 px-5 py-2 rounded-lg text-sm font-medium bg-white text-black hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
        >
          <Icon
            v-if="isCreating"
            name="eos-icons:loading"
            class="text-lg animate-spin"
          />
          <Icon v-else name="ph:note-pencil" class="text-lg" />
          <span>{{ isCreating ? "Creating…" : "Create Note" }}</span>
        </button>
      </main>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  folders: {
    type: Array,
    default: () => [],
  },
  // Preselects a folder so "New note here" inside a folder files the note
  // there without the user picking it again.
  defaultFolderId: {
    type: [String, Number],
    default: null,
  },
});

const emit = defineEmits(["close", "created"]);

const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const title = ref("");
const selectedFolderId = ref(
  props.defaultFolderId === null || props.defaultFolderId === undefined
    ? ""
    : props.defaultFolderId,
);
const isCreating = ref(false);
const titleInput = ref(null);

const flattenedFolders = computed(() => {
  const result = [];

  function walk(folderList, depth = 0) {
    for (const folder of folderList) {
      result.push({
        id: folder.id,
        label: `${"— ".repeat(depth)}${folder.name}`,
      });
      if (folder.subfolders?.length) {
        walk(folder.subfolders, depth + 1);
      }
    }
  }

  walk(props.folders);
  return result;
});

onMounted(() => {
  titleInput.value?.focus();
});

async function createNote() {
  if (isCreating.value) return;
  isCreating.value = true;

  try {
    const note = await $fetch(`${apiBaseURL}/notes/`, {
      method: "POST",
      body: {
        title: title.value.trim() || "Untitled note",
        content: "",
        folder: selectedFolderId.value === "" ? null : selectedFolderId.value,
      },
    });

    emit("created", note);
    emit("close");
  } catch (error) {
    console.error("Error creating note:", error);
    alert(error?.data?.error || "Could not create note.");
  } finally {
    isCreating.value = false;
  }
}
</script>
