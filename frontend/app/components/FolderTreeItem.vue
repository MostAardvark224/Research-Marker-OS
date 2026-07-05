<template>
  <div class="relative">
    <div
      @click="actions.activateFolder(folder.id)"
      @dragover.prevent
      @dragenter.prevent="actions.setActiveDropFolderId(folder.id)"
      @dragleave="actions.clearActiveDropFolderId(folder.id)"
      @drop="actions.onDropOnFolder($event, folder)"
      :class="[
        'group flex items-center justify-between py-2 rounded-lg cursor-pointer transition-colors',
        state.activeFolderId === folder.id
          ? `${colorScheme.folderActive} ${colorScheme.folderActiveText}`
          : `${colorScheme.sidebarText} ${colorScheme.folderHover} ${colorScheme.sidebarTextHover}`,
        state.activeDropFolderId === folder.id ? 'ring-1 ring-blue-500/50' : '',
      ]"
      :style="{ paddingLeft: `${12 + depth * 12}px`, paddingRight: '12px' }"
    >
      <div class="flex items-center gap-2 overflow-hidden flex-1 min-w-0">
        <Icon
          name="material-symbols:folder-open-rounded"
          :class="[
            'text-lg flex-shrink-0',
            state.activeFolderId === folder.id
              ? colorScheme.folderIconActive
              : `${colorScheme.folderIcon} ${colorScheme.folderIconHover}`,
          ]"
        />

        <template v-if="state.renamingFolderId === folder.id">
          <input
            v-model="state.renamingFolderTitle"
            v-focus
            type="text"
            :class="`${colorScheme.inputBg} border ${colorScheme.inputFocusBorder} rounded px-1 py-0.5 text-sm ${colorScheme.inputText} w-full outline-none`"
            @click.stop
            @keydown.enter="actions.finishRenamingFolder"
            @keydown.esc="actions.cancelRenamingFolder"
            @blur="actions.finishRenamingFolder"
          />
        </template>
        <template v-else>
          <span class="truncate text-sm font-medium select-none">{{
            folder.name
          }}</span>
        </template>
      </div>

      <div class="flex items-center gap-1 shrink-0">
        <span
          :class="`text-xs font-mono ${colorScheme.folderCountBg} px-1.5 py-0.5 rounded ${colorScheme.folderCount}`"
        >
          {{ documentCount }}
        </span>

        <div
          :class="`relative h-6 w-6 flex items-center justify-center rounded ${colorScheme.folderHover} ml-1`"
          @click.stop="actions.toggleFolderMenu(folder.id)"
        >
          <Icon name="material-symbols:more-horiz" class="text-lg" />

          <div
            v-if="state.activeMenuFolderId === folder.id"
            :class="`absolute right-0 top-full mt-1 z-50 w-36 rounded-md border ${colorScheme.containerBorder} ${colorScheme.containerBg} backdrop-blur-md shadow-xl py-1`"
          >
            <button
              @click.stop="actions.startCreatingSubfolder(folder.id)"
              :class="`w-full text-left px-3 py-1.5 text-xs ${colorScheme.sidebarText} ${colorScheme.folderHover} ${colorScheme.folderIconActive} flex items-center gap-2`"
            >
              <Icon name="material-symbols:create-new-folder" />
              New Subfolder
            </button>
            <button
              @click.stop="actions.startRenamingFolder(folder)"
              :class="`w-full text-left px-3 py-1.5 text-xs ${colorScheme.sidebarText} ${colorScheme.folderHover} ${colorScheme.folderIconActive} flex items-center gap-2`"
            >
              <Icon name="material-symbols:edit-outline" />
              Rename
            </button>
            <button
              @click.stop="actions.promptDeleteFolder(folder)"
              :class="`w-full text-left px-3 py-1.5 text-xs ${colorScheme.sidebarText} ${colorScheme.folderHover} ${colorScheme.actionIconDeleteHover} flex items-center gap-2`"
            >
              <Icon name="material-symbols:delete-outline" />
              Delete
            </button>
          </div>
        </div>

        <div
          :class="`h-6 w-6 flex items-center justify-center rounded ${colorScheme.folderHover} transition-colors`"
          @click.stop="actions.toggleFolderExpanded(folder.id)"
        >
          <Icon
            name="material-symbols:keyboard-arrow-down-rounded"
            class="text-lg transition-transform duration-200"
            :class="{
              '-rotate-90': !state.expandedFolderIds.includes(folder.id),
            }"
          />
        </div>
      </div>
    </div>

    <div
      v-if="state.expandedFolderIds.includes(folder.id)"
      :class="`border-l ${colorScheme.sidebarBorder} overflow-hidden`"
      :style="{ marginLeft: `${12 + depth * 12}px` }"
    >
      <div
        v-if="state.creatingSubfolderParentId === folder.id"
        :class="`flex items-center px-2 py-1.5 mx-1 rounded-lg ${colorScheme.folderCountBg} border ${colorScheme.inputBorder} mb-1`"
      >
        <Icon
          name="material-symbols:folder-open-rounded"
          :class="`text-lg ${colorScheme.inputFocusText} mr-2 flex-shrink-0`"
        />
        <input
          v-model="state.newSubfolderName"
          v-focus
          type="text"
          :class="`bg-transparent border-none outline-none text-sm ${colorScheme.inputText} w-full ${colorScheme.inputPlaceholder}`"
          placeholder="Subfolder name..."
          @keydown.enter="actions.finishCreatingSubfolder"
          @keydown.esc="actions.cancelCreatingSubfolder"
          @blur="actions.finishCreatingSubfolder"
        />
      </div>

      <FolderTreeItem
        v-for="subfolder in folder.subfolders || []"
        :key="subfolder.id"
        :folder="subfolder"
        :depth="depth + 1"
      />

      <div
        v-if="
          !(folder.documents || []).length && !(folder.subfolders || []).length
        "
        :class="`px-2 py-1.5 text-xs ${colorScheme.textMuted} italic`"
      >
        Empty folder
      </div>

      <div
        v-for="(doc, docIndex) in folder.documents || []"
        :key="doc.id"
        draggable="true"
        @dragstart="actions.onDragStart($event, doc, folder.id)"
        @dragover.prevent="actions.onDragOverDocument(folder.id, docIndex)"
        @dragleave="actions.onDragLeaveDocument"
        @drop.prevent="actions.onDropOnDocument($event, folder, docIndex)"
        @dblclick="
          actions.navigateToAnnotate(
            doc.id,
            doc.last_page,
            doc.zoom_level ? doc.zoom_level : 100,
          )
        "
        :class="[
          `flex items-center gap-2 px-2 py-1.5 text-xs ${colorScheme.sidebarText} truncate select-none cursor-grab active:cursor-grabbing`,
          state.dragOverDoc?.folderId === folder.id &&
          state.dragOverDoc?.index === docIndex
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
</template>

<script setup>
const props = defineProps({
  folder: { type: Object, required: true },
  depth: { type: Number, default: 0 },
});

const colorScheme = inject("colorScheme");
const state = inject("folderTreeState");
const actions = inject("folderActions");

const vFocus = {
  mounted: (el) => el.focus(),
};

const documentCount = computed(() => {
  const countDocs = (node) => {
    let total = node.documents?.length || 0;
    for (const sub of node.subfolders || []) {
      total += countDocs(sub);
    }
    return total;
  };
  return countDocs(props.folder);
});
</script>
