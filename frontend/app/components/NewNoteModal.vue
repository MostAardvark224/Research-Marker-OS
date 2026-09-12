<template>
  <div
    class="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
  >
    <div
      class="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
      @click="$emit('close')"
    ></div>

    <div
      class="relative w-full max-w-2xl bg-[#020204] border border-white/10 rounded-xl shadow-2xl overflow-hidden"
    >
      <header
        class="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#020204]"
      >
        <div>
          <h2 class="font-semibold text-lg tracking-tight text-white">
            {{ mode === "create" ? "New note" : "Import Markdown notes" }}
          </h2>
          <p class="text-xs text-slate-500 mt-0.5">
            {{ mode === "create"
              ? "Create a Markdown note and file it alongside your papers."
              : "Add .md files from uploads or paths on this machine." }}
          </p>
        </div>
        <button
          @click="$emit('close')"
          class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
        >
          <Icon name="material-symbols:close" class="text-xl" />
        </button>
      </header>

      <main class="p-4 space-y-4 max-h-[75vh] overflow-y-auto">
        <div class="grid grid-cols-2 gap-1 rounded-lg bg-white/[0.04] p-1">
          <button
            type="button"
            class="rounded-md px-3 py-2 text-sm font-medium transition-colors"
            :class="mode === 'create' ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white'"
            @click="mode = 'create'"
          >
            Create empty
          </button>
          <button
            type="button"
            class="rounded-md px-3 py-2 text-sm font-medium transition-colors"
            :class="mode === 'import' ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white'"
            @click="mode = 'import'"
          >
            Import .md
          </button>
        </div>

        <div v-if="mode === 'create'" class="space-y-2">
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
            {{ mode === "import" && createNewFolder ? "Parent folder" : "Folder" }}
          </label>
          <select
            id="newNoteFolder"
            v-model="selectedFolderId"
            class="w-full rounded-lg border border-white/10 bg-[#020204] px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
          >
            <option value="">
              {{ mode === "import" && createNewFolder ? "Top level" : "Unassigned" }}
            </option>
            <option
              v-for="folder in flattenedFolders"
              :key="folder.id"
              :value="folder.id"
            >
              {{ folder.label }}
            </option>
          </select>
          <label
            v-if="mode === 'import'"
            class="flex cursor-pointer items-start gap-3 rounded-lg border border-white/10 bg-white/[0.025] px-3 py-3"
          >
            <input
              v-model="createNewFolder"
              type="checkbox"
              class="mt-0.5 h-4 w-4 rounded border-white/20 bg-black/30 text-indigo-500 focus:ring-indigo-500/50"
            />
            <span>
              <span class="block text-sm font-medium text-slate-200">Create a new folder for this import</span>
              <span class="mt-0.5 block text-xs leading-relaxed text-slate-500">
                The folder and notes are created together only after every Markdown file passes validation.
              </span>
            </span>
          </label>
          <div v-if="mode === 'import' && createNewFolder" class="space-y-2 pt-1">
            <label for="newImportFolderName" class="text-xs font-medium text-slate-400">
              New folder name
            </label>
            <input
              id="newImportFolderName"
              v-model="newFolderName"
              type="text"
              maxlength="255"
              placeholder="Imported notes"
              class="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            />
          </div>
        </div>

        <div v-if="mode === 'import'" class="space-y-4">
          <div class="space-y-2">
            <label class="text-xs font-medium text-slate-400">Upload Markdown files</label>
            <button
              type="button"
              class="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-indigo-400/40 bg-indigo-500/[0.06] px-4 py-4 text-sm text-indigo-200 transition hover:bg-indigo-500/10"
              @click="fileInput?.click()"
            >
              <Icon name="ph:upload-simple" class="text-lg" />
              {{ selectedFilesLabel }}
            </button>
            <input
              ref="fileInput"
              class="hidden"
              type="file"
              accept=".md,text/markdown"
              multiple
              @change="selectFiles"
            />
          </div>

          <div class="space-y-2">
            <label for="markdownFilePaths" class="text-xs font-medium text-slate-400">
              Absolute paths to .md files
            </label>
            <textarea
              id="markdownFilePaths"
              v-model="filePathsText"
              rows="3"
              placeholder="One absolute file path per line"
              class="w-full resize-y rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-mono text-xs text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            ></textarea>
          </div>

          <div class="space-y-2">
            <label for="markdownDirectoryPaths" class="text-xs font-medium text-slate-400">
              Absolute paths to directories
            </label>
            <textarea
              id="markdownDirectoryPaths"
              v-model="directoryPathsText"
              rows="3"
              placeholder="One absolute directory path per line"
              class="w-full resize-y rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-mono text-xs text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            ></textarea>
            <p class="text-xs leading-relaxed text-slate-500">
              Every .md file in these directories and their subdirectories will be imported into
              {{ createNewFolder ? "the new folder" : "the folder selected above" }}.
            </p>
          </div>
        </div>

        <button
          @click="mode === 'create' ? createNote() : importNotes()"
          :disabled="isWorking"
          class="w-full flex items-center justify-center gap-2 px-5 py-2 rounded-lg text-sm font-medium bg-white text-black hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
        >
          <Icon
            v-if="isWorking"
            name="eos-icons:loading"
            class="text-lg animate-spin"
          />
          <Icon v-else :name="mode === 'create' ? 'ph:note-pencil' : 'ph:files'" class="text-lg" />
          <span v-if="mode === 'create'">{{ isWorking ? "Creating…" : "Create Note" }}</span>
          <span v-else>{{ isWorking ? "Importing…" : "Import Notes" }}</span>
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

const emit = defineEmits(["close", "created", "imported"]);

const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const title = ref("");
const mode = ref("create");
const selectedFolderId = ref(
  props.defaultFolderId === null || props.defaultFolderId === undefined
    ? ""
    : props.defaultFolderId,
);
const isCreating = ref(false);
const isImporting = ref(false);
const titleInput = ref(null);
const fileInput = ref(null);
const selectedFiles = ref([]);
const filePathsText = ref("");
const directoryPathsText = ref("");
const createNewFolder = ref(false);
const newFolderName = ref("");

const isWorking = computed(() => isCreating.value || isImporting.value);
const selectedFilesLabel = computed(() => {
  if (!selectedFiles.value.length) return "Choose one or more .md files";
  if (selectedFiles.value.length === 1) return selectedFiles.value[0].name;
  return `${selectedFiles.value.length} Markdown files selected`;
});

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

function nonEmptyLines(value) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function selectFiles(event) {
  const files = Array.from(event.target.files || []);
  const markdownFiles = files.filter((file) => file.name.toLowerCase().endsWith(".md"));
  if (markdownFiles.length !== files.length) {
    alert("Only .md files can be imported.");
  }
  selectedFiles.value = markdownFiles;
}

async function importNotes() {
  if (isWorking.value) return;

  const paths = nonEmptyLines(filePathsText.value);
  const directories = nonEmptyLines(directoryPathsText.value);
  if (!selectedFiles.value.length && !paths.length && !directories.length) {
    alert("Choose a Markdown file or enter at least one file or directory path.");
    return;
  }
  if (createNewFolder.value && !newFolderName.value.trim()) {
    alert("Enter a name for the new folder.");
    return;
  }

  isImporting.value = true;
  const formData = new FormData();
  selectedFiles.value.forEach((file) => formData.append("files", file));
  paths.forEach((path) => formData.append("paths", path));
  directories.forEach((path) => formData.append("directories", path));
  if (createNewFolder.value) {
    formData.append("new_folder_name", newFolderName.value.trim());
    if (selectedFolderId.value !== "") {
      formData.append("new_folder_parent", selectedFolderId.value);
    }
  } else if (selectedFolderId.value !== "") {
    formData.append("folder", selectedFolderId.value);
  }

  try {
    const result = await $fetch(`${apiBaseURL}/notes/import/`, {
      method: "POST",
      body: formData,
    });
    emit("imported", result);
    emit("close");
  } catch (error) {
    console.error("Error importing notes:", error);
    alert(error?.data?.error || "Could not import Markdown notes.");
  } finally {
    isImporting.value = false;
  }
}
</script>
