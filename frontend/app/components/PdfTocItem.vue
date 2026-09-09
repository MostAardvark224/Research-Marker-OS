<script setup>
defineOptions({ name: "PdfTocItem" });

const props = defineProps({
  item: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  expandedIds: { type: Set, required: true },
  activeItemId: { type: String, default: null },
  activePathIds: { type: Set, required: true },
  editable: { type: Boolean, default: false },
  index: { type: Number, default: 0 },
  siblingCount: { type: Number, default: 1 },
  maxPage: { type: Number, default: 0 },
});

const emit = defineEmits(["toggle", "navigate", "edit-action"]);
const hasChildren = computed(() => Boolean(props.item.children?.length));
const isExpanded = computed(() => props.expandedIds.has(props.item.id));
</script>

<template>
  <li>
    <div
      class="group flex min-h-8 items-start gap-0.5 rounded-md transition-colors"
      :class="
        item.id === activeItemId
          ? 'bg-indigo-500/15 text-indigo-200'
          : activePathIds.has(item.id)
            ? 'text-slate-200'
            : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200'
      "
      :style="{ paddingLeft: `${depth * 12 + 2}px` }"
    >
      <button
        v-if="hasChildren"
        type="button"
        class="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded text-slate-500 hover:bg-slate-700 hover:text-slate-200"
        :aria-label="`${isExpanded ? 'Collapse' : 'Expand'} ${item.title}`"
        :aria-expanded="isExpanded"
        @click.stop="emit('toggle', item.id)"
      >
        <Icon
          name="ph:caret-right-bold"
          class="h-3 w-3 transition-transform"
          :class="{ 'rotate-90': isExpanded }"
        />
      </button>
      <span v-else class="w-6 shrink-0"></span>

      <div
        v-if="editable"
        class="flex min-w-0 flex-1 items-center gap-1 py-1 pr-1"
      >
        <input
          :value="item.title"
          class="min-w-0 flex-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200 outline-none focus:border-indigo-500"
          aria-label="Section title"
          @input="emit('edit-action', { type: 'update', id: item.id, field: 'title', value: $event.target.value })"
        />
        <input
          :value="item.page"
          type="number"
          min="1"
          :max="maxPage || undefined"
          class="w-14 rounded border border-slate-700 bg-slate-950 px-1 py-1 text-center font-mono text-[10px] text-slate-200 outline-none focus:border-indigo-500"
          aria-label="PDF page"
          @input="emit('edit-action', { type: 'update', id: item.id, field: 'page', value: $event.target.value })"
        />
        <button
          type="button"
          class="rounded p-1 text-slate-500 hover:bg-slate-700 hover:text-slate-200"
          title="Add subchapter"
          @click="emit('edit-action', { type: 'add-child', id: item.id })"
        >
          <Icon name="ph:plus" class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="rounded p-1 text-slate-500 hover:bg-slate-700 hover:text-slate-200 disabled:opacity-25"
          title="Move up"
          :disabled="index === 0"
          @click="emit('edit-action', { type: 'move', id: item.id, direction: -1 })"
        >
          <Icon name="ph:arrow-up" class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="rounded p-1 text-slate-500 hover:bg-slate-700 hover:text-slate-200 disabled:opacity-25"
          title="Move down"
          :disabled="index >= siblingCount - 1"
          @click="emit('edit-action', { type: 'move', id: item.id, direction: 1 })"
        >
          <Icon name="ph:arrow-down" class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="rounded p-1 text-slate-500 hover:bg-red-500/10 hover:text-red-300"
          title="Delete section"
          @click="emit('edit-action', { type: 'delete', id: item.id })"
        >
          <Icon name="ph:trash" class="h-3.5 w-3.5" />
        </button>
      </div>

      <button
        v-else
        type="button"
        class="flex min-w-0 flex-1 items-start justify-between gap-2 py-1.5 pr-2 text-left disabled:cursor-default disabled:opacity-60"
        :disabled="!Number.isInteger(item.page)"
        :title="Number.isInteger(item.page) ? `${item.title} — PDF page ${item.page}` : item.title"
        @click="emit('navigate', item.page)"
      >
        <span class="min-w-0 break-words text-xs leading-5">{{ item.title }}</span>
        <span
          v-if="Number.isInteger(item.page)"
          class="mt-0.5 shrink-0 rounded bg-slate-950/70 px-1.5 py-0.5 font-mono text-[9px] text-slate-500 group-hover:text-slate-300"
        >
          {{ item.page }}
        </span>
      </button>
    </div>

    <ul v-if="hasChildren" v-show="isExpanded">
      <PdfTocItem
        v-for="(child, childIndex) in item.children"
        :key="child.id"
        :item="child"
        :depth="depth + 1"
        :index="childIndex"
        :sibling-count="item.children.length"
        :expanded-ids="expandedIds"
        :active-item-id="activeItemId"
        :active-path-ids="activePathIds"
        :editable="editable"
        :max-page="maxPage"
        @toggle="emit('toggle', $event)"
        @navigate="emit('navigate', $event)"
        @edit-action="emit('edit-action', $event)"
      />
    </ul>
  </li>
</template>
