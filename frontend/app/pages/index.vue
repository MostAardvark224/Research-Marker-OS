<template>
  <main
    :class="`w-screen h-screen overflow-hidden flex flex-col ${colorScheme.containerBg} ${colorScheme.textPrimary}`"
    @click="closeMenus"
  >
    <div
      v-if="isUploading"
      class="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm cursor-wait"
      @click.stop
    >
      <Icon
        name="material-symbols:progress-activity"
        class="text-6xl text-blue-500 animate-spin mb-4"
      />
      <h3 class="text-xl font-semibold text-white">
        Uploading & Processing...
      </h3>
      <p class="text-slate-400 mt-2 text-sm">
        Please do not close this window. This may take a couple minutes
        depending on the size of your file
      </p>
    </div>

    <div class="flex-1 flex flex-col w-full h-full overflow-hidden">
      <div
        :class="`flex-1 flex flex-col overflow-hidden ${colorScheme.containerBorder} ${colorScheme.containerBg}`"
      >
        <header
          :class="`flex shrink-0 items-center justify-between px-4 md:px-5 py-3 border-b ${colorScheme.headerBorder} ${colorScheme.headerBg}`"
        >
          <div class="flex items-center gap-2">
            <span
              :class="`inline-flex h-2.5 w-2.5 rounded-full ${colorScheme.dotRed}`"
            ></span>
            <span
              :class="`inline-flex h-2.5 w-2.5 rounded-full ${colorScheme.dotAmber}`"
            ></span>
            <span
              :class="`inline-flex h-2.5 w-2.5 rounded-full ${colorScheme.dotGreen}`"
            ></span>

            <h2
              :class="`ml-3 text-sm md:text-base font-semibold tracking-wide ${colorScheme.headerText}`"
            >
              Research Marker
            </h2>

            <Icon
              @click="showSettings = true"
              name="material-symbols:settings"
              :class="`ml-3 text-2xl ${colorScheme.headerText} cursor-pointer hover:text-blue-400 transition-colors`"
            />
            <NuxtLink
              to="https://github.com/MostAardvark224/Research-Marker-OS"
              target="_blank"
              class="flex items-center"
            >
              <Icon
                name="uil:github"
                :class="`ml-3 text-2xl ${colorScheme.headerText} hover:text-gray-400 transition-colors`"
              />
            </NuxtLink>

            <div class="flex items-center gap-2">
              <button
                type="button"
                @click="showUpload = true"
                :class="[
                  'group flex items-center gap-2 rounded-lg transition-all duration-200 ml-2',
                  'p-2 sm:px-3 sm:py-2',
                  colorScheme.btnPrimary,
                  colorScheme.btnPrimaryHover,
                ]"
                aria-label="Upload Papers"
              >
                <Icon
                  name="material-symbols:upload-sharp"
                  :class="[
                    'text-2xl flex-shrink-0',
                    colorScheme.btnPrimaryText,
                  ]"
                />
                <span
                  :class="[
                    'hidden md:inline text-xs font-semibold leading-none',
                    colorScheme.btnPrimaryText,
                  ]"
                >
                  Upload Papers
                </span>
              </button>

              <NuxtLink
                to="/knowledge-base"
                :class="[
                  'group flex items-center gap-2 rounded-lg transition-all duration-200',
                  'p-2 sm:px-3 sm:py-2',
                  colorScheme.btnSecondary,
                  colorScheme.btnSecondaryHover,
                ]"
                aria-label="Knowledge Index"
              >
                <Icon
                  name="material-symbols:book-ribbon-outline"
                  :class="[
                    'text-2xl flex-shrink-0',
                    colorScheme.btnPrimaryText,
                  ]"
                />
                <span
                  :class="[
                    'hidden md:inline text-xs font-semibold leading-none',
                    colorScheme.btnPrimaryText,
                  ]"
                >
                  Knowledge Index
                </span>
              </NuxtLink>

              <button
                type="button"
                @click="showScholarInbox = true"
                :class="[
                  'group flex items-center gap-2 rounded-lg transition-all duration-200 mr-2',
                  'p-2 sm:px-3 sm:py-2',
                  colorScheme.btnTertiary,
                  colorScheme.btnTertiaryHover,
                ]"
                aria-label="Upload Papers"
              >
                <Icon
                  name="material-symbols:school"
                  :class="[
                    'text-2xl flex-shrink-0',
                    colorScheme.btnPrimaryText,
                  ]"
                />
                <span
                  :class="[
                    'hidden md:inline text-xs font-semibold leading-none',
                    colorScheme.btnPrimaryText,
                  ]"
                >
                  Scholar Inbox
                </span>
              </button>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search title…"
              :class="`hidden sm:block ${colorScheme.inputBg} border ${colorScheme.inputBorder} rounded-lg px-2.5 py-1.5 text-xs ${colorScheme.inputText} ${colorScheme.inputPlaceholder} focus:outline-none focus:ring-1 ${colorScheme.inputFocusRing} ${colorScheme.inputFocusBorder}`"
            />
            <select
              v-model="sortBy"
              :class="`${colorScheme.inputBg} border ${colorScheme.inputBorder} rounded-lg px-1 py-1.5 text-xs ${colorScheme.inputText} focus:outline-none focus:ring-1 ${colorScheme.inputFocusRing} ${colorScheme.inputFocusBorder}`"
            >
              <option value="custom">Custom order</option>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="title">Title A–Z</option>
            </select>
          </div>
        </header>

        <div class="flex flex-1 min-h-0">
          <aside
            :class="`w-56 sm:w-60 md:w-64 border-r ${colorScheme.sidebarBorder} ${colorScheme.sidebarBg} p-3 md:p-4 flex flex-col`"
          >
            <div class="flex items-center justify-between mb-3">
              <h3
                :class="`text-sm font-semibold uppercase tracking-wide ${colorScheme.sidebarText}`"
              >
                Folders
              </h3>
              <Icon
                name="material-symbols:create-new-folder"
                :class="`text-xl ${colorScheme.sidebarText} ${colorScheme.sidebarTextHover} cursor-pointer transition-colors`"
                @click.stop="startCreatingFolder"
                title="New Folder"
              />
            </div>

            <div class="flex-1 overflow-y-auto space-y-0.5">
              <div
                v-if="isCreatingFolder"
                :class="`flex items-center px-3 py-1.5 rounded-lg ${colorScheme.folderCountBg} border ${colorScheme.inputBorder} mb-1`"
              >
                <Icon
                  name="material-symbols:folder-open-rounded"
                  :class="`text-lg ${colorScheme.inputFocusText} mr-2 flex-shrink-0`"
                />
                <input
                  v-model="newFolderName"
                  v-focus
                  type="text"
                  :class="`bg-transparent border-none outline-none text-sm ${colorScheme.inputText} w-full ${colorScheme.inputPlaceholder}`"
                  placeholder="Folder name..."
                  @keydown.enter="finishCreatingFolder"
                  @keydown.esc="cancelCreatingFolder"
                  @blur="finishCreatingFolder"
                />
              </div>

              <FolderTreeItem
                v-for="folder in folderList"
                :key="folder.id"
                :folder="folder"
                :depth="0"
              />

              <div class="relative mt-1">
                <div
                  @click="activateFolder(null)"
                  @dragover.prevent
                  @dragenter.prevent="activeDropFolderId = null"
                  @dragleave="activeDropFolderId = null"
                  @drop="onDrop($event, unassignedFolder)"
                  :class="[
                    'group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors',
                    activeFolderId === null
                      ? `${colorScheme.folderActive} ${colorScheme.folderActiveText}`
                      : `${colorScheme.sidebarText} ${colorScheme.folderHover} ${colorScheme.sidebarTextHover}`,
                    activeDropFolderId === null && draggedDocSourceFolderId !== null
                      ? 'ring-1 ring-blue-500/50'
                      : '',
                  ]"
                >
                  <div class="flex items-center gap-2 overflow-hidden flex-1">
                    <Icon
                      name="material-symbols:folder-off-outline"
                      :class="[
                        'text-lg flex-shrink-0',
                        activeFolderId === null
                          ? colorScheme.folderIconActive
                          : `${colorScheme.folderIcon} ${colorScheme.folderIconHover}`,
                      ]"
                    />
                    <span class="truncate text-sm font-medium select-none">
                      Unassigned
                    </span>
                  </div>

                  <div class="flex items-center gap-1">
                    <span
                      :class="`text-xs font-mono ${colorScheme.folderCountBg} px-1.5 py-0.5 rounded ${colorScheme.folderCount}`"
                    >
                      {{ unassignedDocs.length }}
                    </span>
                    <div
                      :class="`h-6 w-6 flex items-center justify-center rounded ${colorScheme.folderHover} transition-colors`"
                      @click.stop="toggleFolderExpanded(null)"
                    >
                      <Icon
                        name="material-symbols:keyboard-arrow-down-rounded"
                        class="text-lg transition-transform duration-200"
                        :class="{
                          '-rotate-90': !expandedFolderIds.includes(null),
                        }"
                      />
                    </div>
                  </div>
                </div>

                <div
                  v-if="expandedFolderIds.includes(null)"
                  :class="`ml-3 pl-3 border-l ${colorScheme.sidebarBorder} overflow-hidden`"
                >
                  <div
                    v-if="unassignedDocs.length === 0"
                    :class="`px-2 py-1.5 text-xs ${colorScheme.textMuted} italic`"
                  >
                    Empty folder
                  </div>
                  <div
                    v-for="(doc, docIndex) in unassignedDocs"
                    :key="doc.id"
                    draggable="true"
                    @dragstart="onDragStart($event, doc, null)"
                    @dragover.prevent="onDragOverDocument(null, docIndex)"
                    @dragleave="onDragLeaveDocument"
                    @drop.prevent="onDropOnDocument($event, unassignedFolder, docIndex)"
                    @dblclick="
                      navigateToAnnotate(
                        doc.id,
                        doc.last_page,
                        doc.zoom_level ? doc.zoom_level : 100,
                      )
                    "
                    :class="[
                      `flex items-center gap-2 px-2 py-1.5 text-xs ${colorScheme.sidebarText} truncate select-none cursor-grab active:cursor-grabbing`,
                      dragOverDoc?.folderId === null && dragOverDoc?.index === docIndex
                        ? 'bg-blue-500/10 ring-1 ring-blue-500/30 rounded'
                        : colorScheme.sidebarTextHover,
                    ]"
                  >
                    <Icon
                      name="material-symbols:drag-indicator"
                      class="text-sm flex-shrink-0 opacity-40"
                    />
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
              :class="`flex-1 flex flex-col items-center justify-center text-center border border-dashed ${colorScheme.emptyBorder} rounded-2xl ${colorScheme.emptyBg} px-4`"
            >
              <p
                :class="`text-base md:text-lg ${colorScheme.emptyText} font-medium`"
              >
                No past papers found.
              </p>
              <p :class="`mt-2 text-sm ${colorScheme.emptySubtext} max-w-md`">
                Upload a paper or select a different folder.
              </p>
            </div>

            <div v-else class="flex-1 flex flex-col gap-3 min-h-0">
              <div class="flex items-center justify-between text-xs">
                <p :class="`${colorScheme.textSecondary}`">
                  Showing
                  <span :class="`font-semibold ${colorScheme.textPrimary}`">
                    {{ filteredPapers.length }}
                  </span>
                  paper<span v-if="filteredPapers.length !== 1">s</span>
                </p>
              </div>

              <div
                :class="`flex-1 overflow-y-auto overflow-x-auto rounded-xl border ${colorScheme.tableBorder} ${colorScheme.tableBg}`"
              >
                <table class="min-w-full table-auto border-collapse text-sm">
                  <thead class="sticky top-0 z-10">
                    <tr
                      :class="`${colorScheme.tableHeaderBg} text-[0.7rem] md:text-xs uppercase tracking-wide ${colorScheme.tableHeaderText} border-b ${colorScheme.tableHeaderBorder}`"
                    >
                      <th
                        scope="col"
                        class="px-4 py-3 text-left w-14 font-semibold"
                      ></th>
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
                        class="px-4 py-3 text-left font-semibold min-w-[10rem]"
                      >
                        Searchable
                      </th>
                      <th
                        scope="col"
                        class="px-4 py-3 text-center font-semibold w-24"
                      >
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody class="cursor-pointer">
                    <tr
                      v-for="(paper, index) in filteredPapers"
                      :key="paper.id"
                      draggable="sortBy === 'custom' && !searchQuery.trim()"
                      @dragstart="onTableDragStart($event, paper, index)"
                      @dragover.prevent="onTableDragOver(index)"
                      @drop.prevent="onTableDrop($event, index)"
                      @dblclick="
                        navigateToAnnotate(
                          paper.id,
                          paper.last_page,
                          paper.zoom_level ? paper.zoom_level : 100,
                        )
                      "
                      :class="[
                        `border-b ${colorScheme.tableRowBorder} ${colorScheme.tableRowHover} transition-colors cursor-grab active:cursor-grabbing`,
                        index % 2 === 0
                          ? `${colorScheme.tableRowEven}`
                          : `${colorScheme.tableRowOdd}`,
                        tableDragOverIndex === index ? 'ring-1 ring-inset ring-blue-500/40' : '',
                      ]"
                    >
                      <td
                        :class="`px-3 py-3 text-sm ${colorScheme.tableCellText} align-middle`"
                      >
                        <span
                          :class="`inline-flex h-7 w-7 items-center justify-center rounded-full ${colorScheme.tableCellNumber} border ${colorScheme.tableCellNumberBorder} font-mono text-xs`"
                        >
                          {{ index + 1 }}
                        </span>
                      </td>

                      <td class="px-4 py-3 align-middle max-w-xs md:max-w-sm">
                        <div class="flex flex-col gap-0.5">
                          <input
                            v-if="paperToRename?.id === paper.id"
                            v-model="newPaperTitle"
                            type="text"
                            v-focus
                            @keydown.enter="confirmRename"
                            @keydown.esc="cancelRename"
                            :class="`${colorScheme.inputBg} border ${colorScheme.inputBorder} rounded-lg px-2.5 py-1.5 text-sm ${colorScheme.inputText} ${colorScheme.inputPlaceholder} focus:outline-none focus:ring-1 ${colorScheme.inputFocusRing} ${colorScheme.inputFocusBorder} w-full`"
                          />
                          <p
                            v-else
                            :class="`font-medium ${colorScheme.tableTitleText} truncate cursor-text`"
                            :title="paper.title"
                          >
                            {{ paper.title }}
                          </p>
                        </div>
                      </td>

                      <td
                        :class="`px-4 py-3 text-xs md:text-sm ${colorScheme.tableDate} align-middle whitespace-nowrap`"
                      >
                        {{ formatDate(paper.uploaded_at) }}
                      </td>

                      <td class="px-[40px] py-3 align-middle text-left">
                        <div
                          v-if="paper.searchable"
                          :class="`inline-flex h-7 w-7 items-center justify-center rounded-full ${colorScheme.tableCellNumber} border ${colorScheme.tableCellNumberBorder} font-mono text-xs`"
                        >
                          <Icon
                            name="material-symbols:check-small"
                            class="text-lg text-green-500"
                          />
                        </div>
                        <div
                          v-else
                          :class="`inline-flex h-7 w-7 items-center justify-center rounded-full ${colorScheme.tableCellNumber} border ${colorScheme.tableCellNumberBorder} font-mono text-xs`"
                        >
                          <Icon
                            name="material-symbols:close-small-outline"
                            class="text-lg text-red-500"
                          />
                        </div>
                      </td>

                      <td
                        class="px-4 py-3 text-center align-middle whitespace-nowrap"
                      >
                        <div class="flex items-center justify-center gap-1">
                          <template v-if="paperToRename?.id === paper.id">
                            <button
                              :class="`group inline-flex h-8 w-8 items-center justify-center rounded-lg ${colorScheme.actionBtnConfirmHover} transition-all duration-200`"
                              title="Confirm Rename"
                              @click="confirmRename"
                            >
                              <Icon
                                name="material-symbols:check-small"
                                :class="`text-2xl ${colorScheme.actionIconDefault} ${colorScheme.actionIconConfirmHover} transition-colors`"
                              />
                            </button>
                            <button
                              :class="`group inline-flex h-8 w-8 items-center justify-center rounded-lg ${colorScheme.actionBtnDeleteHover} transition-all duration-200`"
                              title="Cancel Rename"
                              @click="cancelRename"
                            >
                              <Icon
                                name="material-symbols:close-small-outline"
                                :class="`text-2xl ${colorScheme.actionIconDefault} ${colorScheme.actionIconDeleteHover} transition-colors`"
                              />
                            </button>
                          </template>
                          <template v-else>
                            <button
                              :class="`group inline-flex h-8 w-8 items-center justify-center rounded-lg ${colorScheme.actionBtnEditHover} transition-all duration-200`"
                              title="Rename Paper"
                              @click="initializeRename(paper)"
                            >
                              <Icon
                                name="material-symbols:edit-outline"
                                :class="`text-lg ${colorScheme.actionIconDefault} ${colorScheme.actionIconEditHover} transition-colors`"
                              />
                            </button>
                            <button
                              :class="`group inline-flex h-8 w-8 items-center justify-center rounded-lg ${colorScheme.actionBtnDeleteHover} transition-all duration-200`"
                              title="Delete Paper"
                              @click="
                                paperToDelete = paper;
                                showDeleteModal = true;
                              "
                            >
                              <Icon
                                name="material-symbols:delete-outline"
                                :class="`text-lg ${colorScheme.actionIconDefault} ${colorScheme.actionIconDeleteHover} transition-colors`"
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
    </div>

    <ScholarInboxModal
      v-if="showScholarInbox"
      @close="showScholarInbox = false"
    />

    <SettingsModal v-if="showSettings" @close="showSettings = false" />

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

// Colors
const colorScheme = ref({
  bgGradientFrom: "from-slate-950",
  bgGradientVia: "via-slate-925",
  bgGradientTo: "to-black",

  containerBorder: "border-slate-800",
  containerBg: "bg-slate-950",

  headerBorder: "border-slate-800",
  headerBg: "bg-slate-900/90",
  headerText: "text-slate-100",

  dotRed: "bg-red-500",
  dotAmber: "bg-amber-500",
  dotGreen: "bg-emerald-500",

  btnPrimary: "bg-blue-600",
  btnPrimaryHover: "hover:bg-blue-700",
  btnPrimaryText: "text-white",

  btnSecondary: "bg-emerald-600",
  btnSecondaryHover: "hover:bg-green-700",

  btnTertiary: "bg-black",
  btnTertiaryHover: "hover:bg-gray-800",

  inputBg: "bg-slate-900",
  inputBorder: "border-slate-700",
  inputText: "text-slate-200",
  inputPlaceholder: "placeholder:text-slate-600",
  inputFocusRing: "focus:ring-blue-500/50",
  inputFocusBorder: "focus:border-blue-500/50",
  inputFocusText: "text-blue-500",

  sidebarBorder: "border-slate-800",
  sidebarBg: "bg-slate-950",
  sidebarText: "text-slate-400",
  sidebarTextHover: "hover:text-slate-100",

  folderActive: "bg-slate-800",
  folderActiveText: "text-blue-100",
  folderIcon: "text-slate-600",
  folderIconHover: "group-hover:text-slate-400",
  folderIconActive: "text-blue-400",
  folderHover: "hover:bg-slate-900",
  folderCount: "text-slate-500",
  folderCountBg: "bg-slate-900",

  tableBorder: "border-slate-800",
  tableBg: "bg-slate-950",
  tableHeaderBg: "bg-slate-900",
  tableHeaderText: "text-slate-400",
  tableHeaderBorder: "border-slate-800",
  tableRowBorder: "border-slate-800/50",
  tableRowHover: "hover:bg-slate-900",
  tableRowEven: "bg-slate-950",
  tableRowOdd: "bg-slate-900/50",
  tableCellText: "text-slate-300",
  tableCellNumber: "bg-slate-800",
  tableCellNumberBorder: "border-slate-700",
  tableTitleText: "text-slate-100",
  tableDate: "text-slate-400",

  actionIconDefault: "text-slate-500",
  actionBtnEditHover: "hover:bg-blue-500/10",
  actionIconEditHover: "group-hover:text-blue-400",
  actionBtnDeleteHover: "hover:bg-red-500/10",
  actionIconDeleteHover: "group-hover:text-red-400",
  actionBtnConfirmHover: "hover:bg-emerald-500/10",
  actionIconConfirmHover: "group-hover:text-emerald-400",

  emptyBorder: "border-slate-800",
  emptyBg: "bg-slate-900/20",
  emptyText: "text-slate-200",
  emptySubtext: "text-slate-500",

  textPrimary: "text-slate-100",
  textSecondary: "text-slate-400",
  textMuted: "text-slate-600",
});

const vFocus = {
  mounted: (el) => el.focus(),
};

// State vars
const isUploading = ref(false);
const showUpload = ref(false);
const showScholarInbox = ref(false);
const showSettings = ref(false);

const filesToUpload = ref([]);
const folderList = ref([]);
const unassignedDocs = ref([]);
const activeFolderId = ref(null);

const uploadSkipOcr = ref(false);
const uploadOcrProvider = ref("paddleocr");

const searchQuery = ref("");
const sortBy = ref("custom");

const showDeleteModal = ref(false);
const paperToDelete = ref(null);

const paperToRename = ref(null);
const newPaperTitle = ref("");

const isCreatingFolder = ref(false);
const newFolderName = ref("");
const creatingSubfolderParentId = ref(null);
const newSubfolderName = ref("");

const renamingFolderId = ref(null);
const renamingFolderTitle = ref("");

const activeMenuFolderId = ref(null);
const expandedFolderIds = ref([]);

const showDeleteFolderModal = ref(false);
const folderToDelete = ref(null);

const activeDropFolderId = ref(null);
const draggedDocSourceFolderId = ref(null);
const dragOverDoc = ref(null);
const tableDragOverIndex = ref(null);
const tableDragSourceIndex = ref(null);

const unassignedFolder = computed(() => ({
  id: null,
  name: "Unassigned",
  documents: unassignedDocs.value,
}));

function findFolderById(folders, folderId) {
  for (const folder of folders) {
    if (folder.id === folderId) return folder;
    if (folder.subfolders?.length) {
      const match = findFolderById(folder.subfolders, folderId);
      if (match) return match;
    }
  }
  return null;
}

function findFolderPath(folders, folderId, path = []) {
  for (const folder of folders) {
    const nextPath = [...path, folder.id];
    if (folder.id === folderId) return nextPath;
    if (folder.subfolders?.length) {
      const match = findFolderPath(folder.subfolders, folderId, nextPath);
      if (match) return match;
    }
  }
  return null;
}

function expandFolderAncestors(folderId) {
  if (folderId === null) return;
  const path = findFolderPath(folderList.value, folderId) || [];
  for (const id of path) {
    if (!expandedFolderIds.value.includes(id)) {
      expandedFolderIds.value.push(id);
    }
  }
}

// Funcs

// Dragging Docs

function onDragStart(event, doc, sourceFolderId) {
  draggedDocSourceFolderId.value = sourceFolderId;
  event.dataTransfer.dropEffect = "move";
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData(
    "application/json",
    JSON.stringify({ ...doc, _sourceFolderId: sourceFolderId }),
  );
}

function onDragOverDocument(folderId, docIndex) {
  dragOverDoc.value = { folderId, index: docIndex };
}

function onDragLeaveDocument() {
  dragOverDoc.value = null;
}

async function reorderDocuments(folderId, documentIds) {
  await $fetch(`${apiBaseURL}/documents/reorder/`, {
    method: "POST",
    body: {
      folder_id: folderId,
      document_ids: documentIds,
    },
  });
  await fetchPastPapers();
}

async function onDropOnDocument(event, folder, targetIndex) {
  dragOverDoc.value = null;
  activeDropFolderId.value = null;

  const data = event.dataTransfer.getData("application/json");
  if (!data) return;

  const doc = JSON.parse(data);
  const sourceFolderId =
    doc._sourceFolderId !== undefined
      ? doc._sourceFolderId
      : draggedDocSourceFolderId.value;
  const targetFolderId = folder.id;

  if (sourceFolderId === targetFolderId) {
    const docs = [...(folder.documents || [])];
    const fromIndex = docs.findIndex((item) => item.id === doc.id);
    if (fromIndex === -1) return;

    const [movedDoc] = docs.splice(fromIndex, 1);
    const insertIndex = fromIndex < targetIndex ? targetIndex - 1 : targetIndex;
    docs.splice(insertIndex, 0, movedDoc);

    await reorderDocuments(targetFolderId, docs.map((item) => item.id));
    return;
  }

  await updateDocumentFolder(doc, targetFolderId);
  draggedDocSourceFolderId.value = null;
}

async function onDrop(event, targetFolder) {
  activeDropFolderId.value = null;
  dragOverDoc.value = null;

  const data = event.dataTransfer.getData("application/json");
  if (!data) return;

  const doc = JSON.parse(data);
  const sourceFolderId =
    doc._sourceFolderId !== undefined
      ? doc._sourceFolderId
      : draggedDocSourceFolderId.value;

  const isAlreadyInFolder = (targetFolder.documents || []).some(
    (item) => item.id === doc.id,
  );

  if (!isAlreadyInFolder || sourceFolderId !== targetFolder.id) {
    await updateDocumentFolder(doc, targetFolder.id);
  }

  activeFolderId.value = targetFolder.id;
  draggedDocSourceFolderId.value = null;
}

function onTableDragStart(event, paper, index) {
  if (sortBy.value !== "custom") return;
  tableDragSourceIndex.value = index;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", String(paper.id));
}

function onTableDragOver(index) {
  if (sortBy.value !== "custom") return;
  tableDragOverIndex.value = index;
}

async function onTableDrop(event, targetIndex) {
  if (sortBy.value !== "custom") return;

  const sourceIndex = tableDragSourceIndex.value;
  tableDragOverIndex.value = null;
  tableDragSourceIndex.value = null;

  if (sourceIndex === null || sourceIndex === targetIndex) return;

  const docs = [...currentDocuments.value].sort(
    (a, b) =>
      (a.sort_order ?? 0) - (b.sort_order ?? 0) || (a.id ?? 0) - (b.id ?? 0),
  );
  const [movedDoc] = docs.splice(sourceIndex, 1);
  const insertIndex = sourceIndex < targetIndex ? targetIndex - 1 : targetIndex;
  docs.splice(insertIndex, 0, movedDoc);

  await reorderDocuments(activeFolderId.value, docs.map((item) => item.id));
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

      // Retrieve the last active folder from local storage
      const storedFolder = localStorage.getItem("researchMarker_lastFolder");

      if (storedFolder === "unassigned" || !storedFolder) {
        activeFolderId.value = null;
      } else {
        const existingFolder = findFolderById(
          folderList.value,
          Number(storedFolder),
        );
        activeFolderId.value = existingFolder ? existingFolder.id : null;
        if (existingFolder) {
          expandFolderAncestors(existingFolder.id);
        }
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
async function onModalFileSelection(files, skipOcr, ocrProvider = "paddleocr") {
  filesToUpload.value = files;
  uploadSkipOcr.value = skipOcr;
  uploadOcrProvider.value = ocrProvider;

  if (files && files.length > 0) {
    showUpload.value = false;
    await sendDocuments();
  }
}

// Handles sending selected documents to the backend
async function sendDocuments() {
  if (filesToUpload.value.length === 0) {
    alert("Please select files first!");
    return;
  }

  isUploading.value = true;

  const formData = new FormData();
  filesToUpload.value.forEach((file) => {
    formData.append("file", file);
  });

  if (activeFolderId.value !== null) {
    formData.append("folder_id", activeFolderId.value);
  }

  formData.append("skip_ocr", uploadSkipOcr.value);
  formData.append("ocr_provider", uploadOcrProvider.value);

  try {
    const res = await $fetch(`${apiBaseURL}/documents/`, {
      method: "POST",
      body: formData,
    });
    await fetchPastPapers();
    filesToUpload.value = [];
    uploadSkipOcr.value = false;
    uploadOcrProvider.value = "paddleocr";
  } catch (error) {
    console.error("Error uploading files:", error);
    alert("Upload Failed");
  } finally {
    isUploading.value = false;
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

// Opening dropdown when folder is activated
function activateFolder(folderId) {
  activeFolderId.value = folderId;

  if (folderId !== null && !expandedFolderIds.value.includes(folderId)) {
    toggleFolderExpanded(folderId);
  }

  expandFolderAncestors(folderId);

  localStorage.setItem(
    "researchMarker_lastFolder",
    folderId === null ? "unassigned" : folderId,
  );
}

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
      body: { name: name, parent: null },
    });
    await fetchPastPapers();
  } catch (error) {
    if (error.response && error.response.status === 400) {
      alert("You can't have two folders of the same name at this level.");
    } else {
      console.error("Error creating folder:", error);
      alert("Folder Creation Failed.");
    }
  } finally {
    cancelCreatingFolder();
  }
}

function startCreatingSubfolder(parentId) {
  closeMenus();
  creatingSubfolderParentId.value = parentId;
  newSubfolderName.value = "";
  if (!expandedFolderIds.value.includes(parentId)) {
    expandedFolderIds.value.push(parentId);
  }
}

function cancelCreatingSubfolder() {
  creatingSubfolderParentId.value = null;
  newSubfolderName.value = "";
}

async function finishCreatingSubfolder() {
  if (creatingSubfolderParentId.value === null) return;

  const name = newSubfolderName.value.trim();
  const parentId = creatingSubfolderParentId.value;

  if (name === "") {
    cancelCreatingSubfolder();
    return;
  }

  try {
    await $fetch(`${apiBaseURL}/folders/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: { name, parent: parentId },
    });
    await fetchPastPapers();
    expandFolderAncestors(parentId);
  } catch (error) {
    if (error.response && error.response.status === 400) {
      alert("You can't have two folders of the same name at this level.");
    } else {
      console.error("Error creating subfolder:", error);
      alert("Subfolder Creation Failed.");
    }
  } finally {
    cancelCreatingSubfolder();
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
      alert("You can't have two folders of the same name at this level.");
    } else {
      console.error("Error renaming folder:", error);
      alert("Folder Rename Failed.");
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
      (id) => id !== folderId,
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
    subfolders: [],
  });
  return folders;
});

// Docs for current folder
const currentDocuments = computed(() => {
  if (activeFolderId.value === null) {
    return unassignedDocs.value;
  }
  const folder = findFolderById(folderList.value, activeFolderId.value);
  return folder ? folder.documents : [];
});

// Cgecks if there are any papers to show
const hasPapers = computed(() => {
  return currentDocuments.value.length > 0;
});

// Filters and sorts papers based on user input
const filteredPapers = computed(() => {
  let list = [...currentDocuments.value];

  if (sortBy.value === "custom") {
    list.sort(
      (a, b) =>
        (a.sort_order ?? 0) - (b.sort_order ?? 0) || (a.id ?? 0) - (b.id ?? 0),
    );
  } else if (sortBy.value === "newest") {
    list.sort((a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at));
  } else if (sortBy.value === "oldest") {
    list.sort((a, b) => new Date(a.uploaded_at) - new Date(b.uploaded_at));
  } else if (sortBy.value === "title") {
    list.sort((a, b) =>
      (a.title || "").localeCompare(b.title || "", undefined, {
        sensitivity: "base",
      }),
    );
  }

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase();
    list = list.filter((paper) =>
      (paper.title || "").toLowerCase().includes(q),
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

// Annotate Page Navigation
// ADD PAGE NUM LOGIC HERE, IT SHOULD BE A QUERY PARAM
function navigateToAnnotate(paperId, lastPage, zoom) {
  navigateTo({
    path: `/annotate/${paperId}`,
    query: {
      page: lastPage,
      zoom: zoom,
    },
  });
}

const folderTreeState = reactive({
  activeFolderId,
  expandedFolderIds,
  renamingFolderId,
  renamingFolderTitle,
  activeMenuFolderId,
  activeDropFolderId,
  creatingSubfolderParentId,
  newSubfolderName,
  dragOverDoc,
});

provide("colorScheme", colorScheme);
provide("folderTreeState", folderTreeState);
provide("folderActions", {
  activateFolder,
  toggleFolderExpanded,
  toggleFolderMenu,
  startRenamingFolder,
  finishRenamingFolder,
  cancelRenamingFolder,
  startCreatingSubfolder,
  finishCreatingSubfolder,
  cancelCreatingSubfolder,
  promptDeleteFolder,
  onDragStart,
  onDragOverDocument,
  onDragLeaveDocument,
  onDropOnDocument,
  onDropOnFolder: onDrop,
  setActiveDropFolderId: (folderId) => {
    activeDropFolderId.value = folderId;
  },
  clearActiveDropFolderId: () => {
    activeDropFolderId.value = null;
  },
  navigateToAnnotate,
});
</script>
