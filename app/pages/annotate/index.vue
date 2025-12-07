<template>
  <main
    class="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100 flex flex-col items-center"
    @click="closeMenus"
  >
    <div class="pt-6 pb-10 flex flex-col items-center gap-6 w-full">
      <section class="w-[98vw] h-[95vh]">
        <div
          class="h-full rounded-2xl border border-slate-800/80 bg-slate-900/70 shadow-2xl backdrop-blur-xl overflow-hidden flex flex-col"
        >
          <header
            class="flex items-center justify-between px-4 md:px-5 py-3 border-b border-slate-800/80 bg-slate-950/70"
          >
            <div class="flex items-center gap-2">
              <span
                class="inline-flex h-2.5 w-2.5 rounded-full bg-red-500/80"
              ></span>
              <span
                class="inline-flex h-2.5 w-2.5 rounded-full bg-amber-400/80"
              ></span>
              <span
                class="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500/80"
              ></span>

              <h2
                class="ml-3 text-sm md:text-base font-semibold tracking-wide text-slate-100"
              >
                Research Marker
              </h2>

              <Icon name="material-symbols:settings" class="ml-3 text-2xl" />
              <Icon name="uil:github" class="ml-3 text-2xl" />

              <div
                @click="showUpload = true"
                class="ml-3 inline-flex items-center gap-1.5 cursor-pointer rounded-lg bg-blue-600/90 hover:bg-blue-600/100 px-3 py-1.5 transition-colors"
              >
                <Icon name="material-symbols:upload-sharp" class="text-2xl" />
                <span class="text-xs font-semibold text-white leading-none">
                  Upload Papers
                </span>
              </div>
            </div>

            <div class="flex items-center gap-2">
              <input
                v-model="searchQuery"
                type="text"
                placeholder="Search title…"
                class="hidden sm:block bg-slate-900/80 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-400/70 focus:border-slate-400/70"
              />
              <select
                v-model="sortBy"
                class="bg-slate-900/80 border border-slate-700/80 rounded-lg px-1 py-1.5 pr-1 mr-1 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-slate-400/70 focus:border-slate-400/70"
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="title">Title A–Z</option>
              </select>
            </div>
          </header>

          <div class="flex flex-1 min-h-0">
            <aside
              class="w-56 sm:w-60 md:w-64 border-r border-slate-800/80 bg-slate-950/40 p-3 md:p-4 flex flex-col"
            >
              <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-semibold uppercase tracking-wide">
                  Folders
                </h3>
                <Icon
                  name="material-symbols:create-new-folder"
                  class="text-xl text-white hover:text-blue-400 cursor-pointer transition-colors"
                  @click.stop="startCreatingFolder"
                  title="New Folder"
                />
              </div>

              <div class="flex-1 overflow-y-auto space-y-0.5">
                <div
                  v-if="isCreatingFolder"
                  class="flex items-center px-3 py-1.5 rounded-lg bg-slate-800/50 border border-blue-500/50 mb-1"
                >
                  <Icon
                    name="material-symbols:folder-open-rounded"
                    class="text-lg text-blue-400 mr-2 flex-shrink-0"
                  />
                  <input
                    v-model="newFolderName"
                    v-focus
                    type="text"
                    class="bg-transparent border-none outline-none text-sm text-white w-full placeholder-slate-500"
                    placeholder="Folder name..."
                    @keydown.enter="finishCreatingFolder"
                    @keydown.esc="cancelCreatingFolder"
                    @blur="finishCreatingFolder"
                  />
                </div>

                <div
                  v-for="folder in allFolders"
                  :key="folder.id || 'unassigned'"
                  class="relative"
                >
                  <div
                    @click="activeFolderId = folder.id"
                    @dragover.prevent
                    @dragenter.prevent="activeDropFolderId = folder.id"
                    @dragleave="activeDropFolderId = null"
                    @drop="onDrop($event, folder)"
                    class="group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors"
                    :class="[
                      activeFolderId === folder.id
                        ? 'bg-blue-600/20 text-blue-100'
                        : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200',
                    ]"
                  >
                    <div class="flex items-center gap-2 overflow-hidden flex-1">
                      <Icon
                        :name="
                          folder.id === null
                            ? 'material-symbols:folder-off-outline'
                            : 'material-symbols:folder-open-rounded'
                        "
                        class="text-lg flex-shrink-0"
                        :class="
                          activeFolderId === folder.id
                            ? 'text-blue-400'
                            : 'text-slate-500 group-hover:text-slate-300'
                        "
                      />

                      <template
                        v-if="
                          folder.id !== null && renamingFolderId === folder.id
                        "
                      >
                        <input
                          v-model="renamingFolderTitle"
                          v-focus
                          type="text"
                          class="bg-slate-950 border border-blue-500/50 rounded px-1 py-0.5 text-sm text-white w-full outline-none"
                          @click.stop
                          @keydown.enter="finishRenamingFolder"
                          @keydown.esc="cancelRenamingFolder"
                          @blur="finishRenamingFolder"
                        />
                      </template>
                      <template v-else>
                        <span class="truncate text-sm font-medium select-none">
                          {{ folder.name }}
                        </span>
                      </template>
                    </div>

                    <div class="flex items-center gap-1">
                      <span
                        class="text-xs font-mono bg-slate-900/50 px-1.5 py-0.5 rounded text-slate-500"
                      >
                        {{ folder.documents.length }}
                      </span>

                      <template v-if="folder.id !== null">
                        <div
                          class="relative h-6 w-6 flex items-center justify-center rounded hover:bg-slate-700/50 ml-1"
                          @click.stop="toggleFolderMenu(folder.id)"
                        >
                          <Icon
                            name="material-symbols:more-horiz"
                            class="text-lg"
                          />

                          <div
                            v-if="activeMenuFolderId === folder.id"
                            class="absolute right-0 top-full mt-1 z-50 w-32 rounded-md border border-slate-700 bg-slate-900 shadow-xl py-1"
                          >
                            <button
                              @click.stop="startRenamingFolder(folder)"
                              class="w-full text-left px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 hover:text-blue-400 flex items-center gap-2"
                            >
                              <Icon name="material-symbols:edit-outline" />
                              Rename
                            </button>
                            <button
                              @click.stop="promptDeleteFolder(folder)"
                              class="w-full text-left px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 hover:text-red-400 flex items-center gap-2"
                            >
                              <Icon name="material-symbols:delete-outline" />
                              Delete
                            </button>
                          </div>
                        </div>
                      </template>
                      <div
                        class="h-6 w-6 flex items-center justify-center rounded hover:bg-slate-700/50 transition-colors"
                        @click.stop="toggleFolderExpanded(folder.id)"
                      >
                        <Icon
                          name="material-symbols:keyboard-arrow-down-rounded"
                          class="text-lg transition-transform duration-200"
                          :class="{
                            '-rotate-90': !expandedFolderIds.includes(
                              folder.id
                            ),
                          }"
                        />
                      </div>
                    </div>
                  </div>

                  <div
                    v-if="expandedFolderIds.includes(folder.id)"
                    class="ml-3 pl-3 border-l border-slate-800/50 overflow-hidden"
                  >
                    <div
                      v-if="folder.documents.length === 0"
                      class="px-2 py-1.5 text-xs text-slate-600 italic"
                    >
                      Empty folder
                    </div>
                    <div
                      v-else
                      v-for="doc in folder.documents"
                      draggable="true"
                      @dragstart="onDragStart($event, doc)"
                      :key="doc.id"
                      class="cursor-grab active:cursor-grabbing flex items-center gap-2 px-2 py-1.5 text-xs text-slate-400 truncate hover:text-slate-200 select-none"
                    >
                      <Icon
                        name="material-symbols:description-outline"
                        class="text-sm flex-shrink-0"
                      />
                      <span class="truncate">{{ doc.title }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </aside>

            <div class="flex-1 p-3 md:p-4 flex flex-col min-h-0">
              <div
                v-if="!hasPapers"
                class="flex-1 flex flex-col items-center justify-center text-center border border-dashed border-slate-800/80 rounded-2xl bg-slate-950/40 px-4"
              >
                <p class="text-base md:text-lg text-slate-100 font-medium">
                  No past papers found.
                </p>
                <p class="mt-2 text-sm text-slate-400 max-w-md">
                  Upload a paper or select a different folder.
                </p>
              </div>

              <div v-else class="flex-1 flex flex-col gap-3 min-h-0">
                <div class="flex items-center justify-between text-xs">
                  <p class="text-slate-300">
                    Showing
                    <span class="font-semibold text-slate-100">
                      {{ filteredPapers.length }}
                    </span>
                    paper<span v-if="filteredPapers.length !== 1">s</span>
                  </p>
                </div>

                <div
                  class="flex-1 overflow-auto rounded-xl border border-slate-800/90 bg-slate-950/60"
                >
                  <table class="min-w-full table-auto border-collapse text-sm">
                    <thead class="sticky top-0 z-10">
                      <tr
                        class="bg-slate-900/95 text-[0.7rem] md:text-xs uppercase tracking-wide text-slate-300 border-b border-slate-800"
                      >
                        <th
                          scope="col"
                          class="px-4 py-3 text-left w-14 font-semibold"
                        >
                          #
                        </th>
                        <th
                          scope="col"
                          class="px-4 py-3 text-left font-semibold min-w-[10rem]"
                        >
                          Title
                        </th>
                        <th
                          scope="col"
                          class="px-4 py-3 text-left font-semibold min-w-[10rem]"
                        >
                          Uploaded At
                        </th>
                        <th
                          scope="col"
                          class="px-4 py-3 text-center font-semibold w-24"
                        >
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(paper, index) in filteredPapers"
                        :key="paper.id"
                        :class="[
                          'border-b border-slate-800/80 hover:bg-slate-800/70 transition-colors',
                          index % 2 === 0
                            ? 'bg-slate-900/70'
                            : 'bg-slate-900/50',
                        ]"
                      >
                        <td
                          class="px-4 py-3 text-sm text-slate-300 align-middle"
                        >
                          <span
                            class="inline-flex h-7 w-7 items-center justify-center rounded-full bg-slate-950/80 border border-slate-700 font-mono text-xs"
                          >
                            {{ index + 1 }}
                          </span>
                        </td>

                        <td class="px-4 py-3 align-middle">
                          <div
                            class="flex flex-col gap-0.5 max-w-xs md:max-w-md"
                          >
                            <input
                              v-if="paperToRename?.id === paper.id"
                              v-model="newPaperTitle"
                              type="text"
                              v-focus
                              @keydown.enter="confirmRename"
                              @keydown.esc="cancelRename"
                              class="bg-slate-900/80 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-400/70 focus:border-blue-400/70 w-full"
                            />
                            <p
                              v-else
                              class="font-medium text-slate-50 truncate cursor-text"
                              :title="paper.title"
                            >
                              {{ paper.title }}
                            </p>
                          </div>
                        </td>

                        <td
                          class="px-4 py-3 text-xs md:text-sm text-slate-200 align-middle whitespace-nowrap"
                        >
                          {{ formatDate(paper.uploaded_at) }}
                        </td>

                        <td
                          class="px-4 py-3 text-center align-middle whitespace-nowrap"
                        >
                          <div class="flex items-center justify-center gap-1">
                            <template v-if="paperToRename?.id === paper.id">
                              <button
                                class="group inline-flex h-8 w-8 items-center justify-center rounded-lg hover:bg-emerald-500/20 transition-all duration-200"
                                title="Confirm Rename"
                                @click="confirmRename"
                              >
                                <Icon
                                  name="material-symbols:check-small"
                                  class="text-2xl text-slate-400 group-hover:text-emerald-400 transition-colors"
                                />
                              </button>
                              <button
                                class="group inline-flex h-8 w-8 items-center justify-center rounded-lg hover:bg-red-500/20 transition-all duration-200"
                                title="Cancel Rename"
                                @click="cancelRename"
                              >
                                <Icon
                                  name="material-symbols:close-small-outline"
                                  class="text-2xl text-slate-400 group-hover:text-red-400 transition-colors"
                                />
                              </button>
                            </template>
                            <template v-else>
                              <button
                                class="group inline-flex h-8 w-8 items-center justify-center rounded-lg hover:bg-blue-500/20 transition-all duration-200"
                                title="Rename Paper"
                                @click="initializeRename(paper)"
                              >
                                <Icon
                                  name="material-symbols:edit-outline"
                                  class="text-lg text-slate-400 group-hover:text-blue-400 transition-colors"
                                />
                              </button>
                              <button
                                class="group inline-flex h-8 w-8 items-center justify-center rounded-lg hover:bg-red-500/20 transition-all duration-200"
                                title="Delete Paper"
                                @click="
                                  paperToDelete = paper;
                                  showDeleteModal = true;
                                "
                              >
                                <Icon
                                  name="material-symbols:delete-outline"
                                  class="text-lg text-slate-400 group-hover:text-red-400 transition-colors"
                                />
                              </button>
                            </template>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <FileUploadModal
      v-if="showUpload"
      @close="showUpload = false"
      @files-selected="onModalFileSelection"
    />

    <DeletePaperModal
      v-if="showDeleteModal"
      :paper-title="paperToDelete?.title"
      @close="showDeleteModal = false"
      @confirm="deletePaper"
    />

    <DeleteFolderModal
      v-if="showDeleteFolderModal"
      :folder-name="folderToDelete?.name"
      @close="showDeleteFolderModal = false"
      @confirm="confirmDeleteFolder"
    />
  </main>
</template>

<script setup>
const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const vFocus = {
  mounted: (el) => el.focus(),
};

// State vars
const showUpload = ref(false);

const filesToUpload = ref([]);
const folderList = ref([]);
const unassignedDocs = ref([]);
const activeFolderId = ref(null);

const searchQuery = ref("");
const sortBy = ref("newest");

const showDeleteModal = ref(false);
const paperToDelete = ref(null);

const paperToRename = ref(null);
const newPaperTitle = ref("");

const isCreatingFolder = ref(false);
const newFolderName = ref("");

const renamingFolderId = ref(null);
const renamingFolderTitle = ref("");

const activeMenuFolderId = ref(null);
const expandedFolderIds = ref([]);

const showDeleteFolderModal = ref(false);
const folderToDelete = ref(null);

const activeDropFolderId = ref(null);

// Funcs

// Dragging Docs

function onDragStart(event, doc) {
  event.dataTransfer.dropEffect = "move";
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("application/json", JSON.stringify(doc));
}

async function onDrop(event, targetFolder) {
  activeDropFolderId.value = null;

  const data = event.dataTransfer.getData("application/json");
  if (!data) return;

  const doc = JSON.parse(data);

  const isAlreadyInFolder = targetFolder.documents.some((d) => d.id === doc.id);

  if (!isAlreadyInFolder) {
    await updateDocumentFolder(doc, targetFolder.id);
  }

  activeFolderId.value = targetFolder.id;
}

// Main func that fetches all of user data, includes folders and documents
async function fetchPastPapers() {
  try {
    const res = await $fetch(`${apiBaseURL}/complete-fetch/`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (res && typeof res === "object") {
      folderList.value = Array.isArray(res.folders) ? res.folders : [];
      unassignedDocs.value = Array.isArray(res.Unassigned)
        ? res.Unassigned
        : [];

      if (activeFolderId.value === null && unassignedDocs.value.length > 0) {
        activeFolderId.value = null;
      } else if (
        activeFolderId.value !== null &&
        !folderList.value.some((f) => f.id === activeFolderId.value)
      ) {
        activeFolderId.value = null;
      }
    }
  } catch (error) {
    console.error("Error fetching past papers:", error);
    alert("Paper Fetch Failed.");
  }
}

onMounted(() => {
  fetchPastPapers();
});

// DOCUMENT HANDLING FUNCS

// Handles file selection from the upload modal
async function onModalFileSelection(files) {
  filesToUpload.value = files;

  if (files && files.length > 0) {
    await sendDocuments();
    showUpload.value = false;
  }
}

// Handles sending selected documents to the backend
async function sendDocuments() {
  if (filesToUpload.value.length === 0) {
    alert("Please select files first!");
    return;
  }

  const formData = new FormData();
  filesToUpload.value.forEach((file) => {
    formData.append("file", file);
  });

  if (activeFolderId.value !== null) {
    formData.append("folder_id", activeFolderId.value);
  }

  try {
    const res = await $fetch(`${apiBaseURL}/documents/`, {
      method: "POST",
      body: formData,
    });
    await fetchPastPapers();
    filesToUpload.value = [];
  } catch (error) {
    console.error("Error uploading files:", error);
    alert("Upload Failed");
  }
}

// Handles deleting a paper
async function deletePaper() {
  const id = paperToDelete.value?.id;
  try {
    await $fetch(`${apiBaseURL}/documents/${id}/`, {
      method: "DELETE",
    });
    showDeleteModal.value = false;
    paperToDelete.value = null;
    await fetchPastPapers();
  } catch (error) {
    console.error("Error deleting paper:", error);
    alert("Delete Failed.");
    showDeleteModal.value = false;
    paperToDelete.value = null;
  }
}

// Handles initializing rename state
function initializeRename(paper) {
  paperToRename.value = paper;
  newPaperTitle.value = paper.title || "";
}

function cancelRename() {
  paperToRename.value = null;
  newPaperTitle.value = "";
}

async function confirmRename() {
  if (!paperToRename.value || newPaperTitle.value.trim() === "") {
    cancelRename();
    return;
  }

  const id = paperToRename.value.id;

  try {
    await $fetch(`${apiBaseURL}/documents/${id}/`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: { title: newPaperTitle.value.trim() },
    });

    await fetchPastPapers();
    cancelRename();
  } catch (error) {
    console.error("Error renaming paper:", error);
    alert("Rename Failed.");
    cancelRename();
  }
}

// Update the folder for a document
async function updateDocumentFolder(paper, newFolderId) {
  const paperId = paper.id;

  try {
    await $fetch(`${apiBaseURL}/documents/${paperId}/`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: { folder: newFolderId },
    });

    await fetchPastPapers();
  } catch (error) {
    console.error("Error updating document folder:", error);
    alert("Update Failed.");
  }
}

// FOLDER HANDLING FUNCS

// Create a new folder
function startCreatingFolder() {
  isCreatingFolder.value = true;
  newFolderName.value = "";
}

function cancelCreatingFolder() {
  isCreatingFolder.value = false;
  newFolderName.value = "";
}

async function finishCreatingFolder() {
  if (!isCreatingFolder.value) return;

  const name = newFolderName.value.trim();
  if (name === "") {
    cancelCreatingFolder();
    return;
  }

  try {
    await $fetch(`${apiBaseURL}/folders/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: { name: name },
    });
    await fetchPastPapers();
  } catch (error) {
    if (error.response && error.response.status === 400) {
      alert("You can't have two folders of the same name.");
    } else {
      console.error("Error creating folder:", error);
      alert("Folder Creation Failed.");
    }
  } finally {
    cancelCreatingFolder();
  }
}

// Rename an existing folder
function startRenamingFolder(folder) {
  closeMenus();
  renamingFolderId.value = folder.id;
  renamingFolderTitle.value = folder.name;
}

function cancelRenamingFolder() {
  renamingFolderId.value = null;
  renamingFolderTitle.value = "";
}

async function finishRenamingFolder() {
  if (renamingFolderId.value === null) return;

  const name = renamingFolderTitle.value.trim();
  const id = renamingFolderId.value;

  if (name === "") {
    cancelRenamingFolder();
    return;
  }

  try {
    await $fetch(`${apiBaseURL}/folders/${id}/`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: { name: name },
    });
    await fetchPastPapers();
  } catch (error) {
    if (error.response && error.response.status === 400) {
      alert("You can't have two folders of the same name.");
    } else {
      console.error("Error creating folder:", error);
      alert("Folder Creation Failed.");
    }
  } finally {
    cancelRenamingFolder();
  }
}

// Delete a folder
function promptDeleteFolder(folder) {
  closeMenus();
  folderToDelete.value = folder;
  showDeleteFolderModal.value = true;
}

async function confirmDeleteFolder() {
  if (!folderToDelete.value) return;
  const id = folderToDelete.value.id;

  try {
    await $fetch(`${apiBaseURL}/folders/${id}/`, {
      method: "DELETE",
    });

    if (activeFolderId.value === id) {
      activeFolderId.value = null;
    }
    await fetchPastPapers();
  } catch (error) {
    console.error("Error deleting folder:", error);
    alert("Folder Deletion Failed.");
  } finally {
    showDeleteFolderModal.value = false;
    folderToDelete.value = null;
  }
}

function toggleFolderMenu(folderId) {
  if (activeMenuFolderId.value === folderId) {
    activeMenuFolderId.value = null;
  } else {
    activeMenuFolderId.value = folderId;
  }
}

function closeMenus() {
  activeMenuFolderId.value = null;
}

function toggleFolderExpanded(folderId) {
  if (expandedFolderIds.value.includes(folderId)) {
    expandedFolderIds.value = expandedFolderIds.value.filter(
      (id) => id !== folderId
    );
  } else {
    expandedFolderIds.value.push(folderId);
  }
}

// Computed properties

// Combines folders with unassigned documents into a single list
const allFolders = computed(() => {
  const folders = [...folderList.value];
  folders.push({
    id: null,
    name: "Unassigned",
    documents: unassignedDocs.value,
  });
  return folders;
});

// Docs for current folder
const currentDocuments = computed(() => {
  if (activeFolderId.value === null) {
    return unassignedDocs.value;
  }
  const folder = folderList.value.find((f) => f.id === activeFolderId.value);
  return folder ? folder.documents : [];
});

// Cgecks if there are any papers to show
const hasPapers = computed(() => {
  return currentDocuments.value.length > 0;
});

// Filters and sorts papers based on user input
const filteredPapers = computed(() => {
  let list = [...currentDocuments.value];

  if (sortBy.value === "newest") {
    list.sort((a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at));
  } else if (sortBy.value === "oldest") {
    list.sort((a, b) => new Date(a.uploaded_at) - new Date(b.uploaded_at));
  } else if (sortBy.value === "title") {
    list.sort((a, b) =>
      (a.title || "").localeCompare(b.title || "", undefined, {
        sensitivity: "base",
      })
    );
  }

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase();
    list = list.filter((paper) =>
      (paper.title || "").toLowerCase().includes(q)
    );
  }

  return list;
});

function formatDate(isoString) {
  if (!isoString) return "—";

  const date = new Date(isoString);

  if (isNaN(date.getTime())) return isoString;

  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    timeZone: "UTC",
  });
}
</script>
