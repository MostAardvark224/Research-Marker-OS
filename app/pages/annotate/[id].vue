<script setup>
const isSidebarOpen = ref(true);
const currentPage = ref(1);
const totalPages = ref(null);
const zoomLevel = ref(100);
const isAnnotationsHidden = ref(false);
const isColorPickerOpen = ref(false);
const selectedColor = ref("#ef4444");

const colors = [
  "#ef4444", // Red
  "#f59e0b", // Amber
  "#10b981", // Emerald
  "#3b82f6", // Blue
  "#8b5cf6", // Violet
  "#ec4899", // Pink
];

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value;
};

const selectColor = (color) => {
  selectedColor.value = color;
  isColorPickerOpen.value = false;
};

const zoomIn = () => {
  if (zoomLevel.value < 200) zoomLevel.value += 10;
};
const zoomOut = () => {
  if (zoomLevel.value > 50) zoomLevel.value -= 10;
};
</script>

<template>
  <div
    class="flex h-screen w-full flex-col overflow-hidden bg-slate-950 text-slate-300 font-sans selection:bg-indigo-500/30"
  >
    <header
      class="relative flex h-16 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900 px-4 shadow-sm z-20"
    >
      <div class="flex items-center gap-4">
        <button class="icon-btn" title="Search Document">
          <Icon name="ph:magnifying-glass" class="h-5 w-5" />
        </button>

        <div class="h-5 w-px bg-slate-700/50"></div>

        <div class="flex items-center gap-2">
          <button
            class="icon-btn"
            :disabled="currentPage <= 1"
            @click="currentPage--"
          >
            <Icon name="ph:caret-left" class="h-4 w-4" />
          </button>

          <div
            class="flex items-center bg-slate-800 rounded border border-slate-700 overflow-hidden"
          >
            <input
              type="number"
              v-model="currentPage"
              class="w-10 bg-transparent py-1 text-center text-sm font-medium text-slate-200 outline-none focus:bg-slate-700 transition-colors [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            />
            <span
              class="border-l border-slate-700 bg-slate-800 px-2 text-xs text-slate-500 select-none"
            >
              / {{ totalPages }}
            </span>
          </div>

          <button
            class="icon-btn"
            :disabled="currentPage >= totalPages"
            @click="currentPage++"
          >
            <Icon name="ph:caret-right" class="h-4 w-4" />
          </button>
        </div>
      </div>

      <div
        class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden md:flex"
      >
        <div
          class="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/50 p-1 shadow-sm"
        >
          <button class="tool-btn" title="Undo">
            <Icon name="ph:arrow-u-up-left" class="h-5 w-5" />
          </button>
          <button class="tool-btn" title="Redo">
            <Icon name="ph:arrow-u-up-right" class="h-5 w-5" />
          </button>

          <div class="mx-1 h-5 w-px bg-slate-600/50"></div>

          <button class="tool-btn active-tool" title="Select Cursor">
            <Icon name="ph:cursor" class="h-5 w-5" />
          </button>

          <button class="tool-btn" title="Highlight Text">
            <Icon name="ph:highlighter" class="h-5 w-5" />
          </button>
          <button class="tool-btn" title="Draw">
            <Icon name="ph:pencil-simple" class="h-5 w-5" />
          </button>
          <button class="tool-btn" title="Sticky Note">
            <Icon name="ph:note" class="h-5 w-5" />
          </button>

          <div class="relative mx-0.5">
            <button
              class="tool-btn flex items-center justify-center"
              title="Color Palette"
              @click="isColorPickerOpen = !isColorPickerOpen"
            >
              <div
                class="h-4 w-4 rounded-full border border-slate-500"
                :style="{ backgroundColor: selectedColor }"
              ></div>
            </button>
            <div
              v-if="isColorPickerOpen"
              class="absolute top-full left-1/2 mt-2 -translate-x-1/2 flex flex-col gap-2 rounded-lg border border-slate-700 bg-slate-800 p-2 shadow-xl"
            >
              <button
                v-for="color in colors"
                :key="color"
                class="h-6 w-6 rounded-full border border-transparent hover:scale-110 transition-transform"
                :class="{
                  'ring-2 ring-indigo-400 ring-offset-2 ring-offset-slate-800':
                    selectedColor === color,
                }"
                :style="{ backgroundColor: color }"
                @click="selectColor(color)"
              ></button>
            </div>
          </div>

          <div class="mx-1 h-5 w-px bg-slate-600/50"></div>

          <button
            class="tool-btn"
            :class="{ 'text-indigo-400': isAnnotationsHidden }"
            @click="isAnnotationsHidden = !isAnnotationsHidden"
            title="Toggle Annotations"
          >
            <Icon
              :name="isAnnotationsHidden ? 'ph:eye-slash' : 'ph:eye'"
              class="h-5 w-5"
            />
          </button>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <div
          class="flex items-center rounded-md border border-slate-700 bg-slate-800"
        >
          <button
            class="p-1.5 hover:bg-slate-700 hover:text-white transition-colors"
            @click="zoomOut"
          >
            <Icon name="ph:minus" class="h-3.5 w-3.5" />
          </button>
          <span
            class="w-12 text-center text-xs font-medium text-slate-300 select-none"
            >{{ zoomLevel }}%</span
          >
          <button
            class="p-1.5 hover:bg-slate-700 hover:text-white transition-colors"
            @click="zoomIn"
          >
            <Icon name="ph:plus" class="h-3.5 w-3.5" />
          </button>
        </div>

        <div class="h-5 w-px bg-slate-700/50"></div>

        <button
          @click="toggleSidebar"
          class="icon-btn active:bg-indigo-500/20"
          :class="{ 'bg-slate-800 text-indigo-400': isSidebarOpen }"
          title="Toggle Sidebar"
        >
          <Icon name="ph:sidebar-simple" class="h-5 w-5" />
        </button>
      </div>
    </header>

    <div class="flex flex-1 overflow-hidden relative">
      <main
        class="flex-1 overflow-auto bg-slate-950 p-8 flex justify-center items-start custom-scrollbar"
      >
        <div
          class="relative w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-sm shadow-2xl min-h-[800px] flex flex-col items-center justify-center text-slate-600 transition-all duration-200 ease-out"
          :style="{
            transform: `scale(${zoomLevel / 100})`,
            transformOrigin: 'top center',
          }"
        >
          <div class="text-center space-y-4">
            <div class="p-6 bg-slate-800/50 rounded-full inline-block">
              <Icon name="ph:file-pdf-light" class="h-16 w-16 opacity-50" />
            </div>
            <h3 class="text-lg font-medium text-slate-400">
              PDF Viewer Implementation
            </h3>
            <p class="text-sm max-w-xs mx-auto text-slate-500">
              The PDF canvas or IFrame will be mounted here.
            </p>
          </div>

          <div
            class="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/20 to-transparent pointer-events-none"
          ></div>
        </div>
      </main>

      <aside
        class="border-l border-slate-800 bg-slate-900 transition-all duration-300 ease-[cubic-bezier(0.25,0.8,0.25,1)] flex flex-col"
        :class="[
          isSidebarOpen
            ? 'w-80 translate-x-0'
            : 'w-0 translate-x-full border-none opacity-0',
        ]"
      >
        <div
          class="h-12 border-b border-slate-800 flex items-center px-2"
          v-if="isSidebarOpen"
        >
          <div
            class="flex-1 text-center py-2 text-sm font-medium text-slate-200 border-b-2 border-indigo-500"
          >
            Notes
          </div>
          <div
            class="flex-1 text-center py-2 text-sm font-medium text-slate-500 hover:text-slate-300 cursor-pointer"
          >
            Info
          </div>
        </div>

        <div
          class="flex-1 p-6 flex flex-col items-center justify-center text-slate-600"
          v-if="isSidebarOpen"
        >
          <span class="text-sm italic opacity-50">No content available</span>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.icon-btn {
  border-radius: 0.25rem;
  padding: 0.5rem;
  color: #94a3b8;
  transition: all 150ms ease-in-out;
}

.icon-btn:hover {
  background-color: #1e293b;
  color: #f8fafc;
}

.icon-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.tool-btn {
  border-radius: 0.25rem;
  padding: 0.375rem;
  color: #94a3b8;
  transition: all 150ms ease-in-out;
  margin-left: 0.125rem;
  margin-right: 0.125rem;
}

.tool-btn:hover {
  background-color: #334155;
  color: #f8fafc;
}

.active-tool {
  background-color: rgba(99, 102, 241, 0.1);
  color: #818cf8;
}

.active-tool:hover {
  background-color: rgba(99, 102, 241, 0.2);
  color: #c7d2fe;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 14px;
  height: 14px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: #0f172a;
  border-left: 1px solid #1e293b;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #334155;
  border: 3px solid #0f172a;
  border-radius: 8px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #475569;
}
</style>
