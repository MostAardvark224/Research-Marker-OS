<template>
  <Transition name="modal-fade">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm"
      @click.self="$emit('close')"
    >
      <div
        class="w-full max-w-sm transform overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/90 p-6 text-left shadow-2xl transition-all"
      >
        <div class="flex items-center justify-center mb-5">
          <div
            class="rounded-full bg-red-500/10 p-3 ring-1 ring-red-500/20 shadow-[0_0_15px_-3px_rgba(239,68,68,0.3)]"
          >
            <Icon
              name="material-symbols:delete-outline"
              class="mt-1.5 text-5xl text-red-500"
            />
          </div>
        </div>

        <div class="text-center">
          <h3 class="text-lg font-semibold leading-6 text-slate-100">
            Delete this paper?
          </h3>
          <div class="mt-2">
            <p class="text-sm text-slate-400">
              Are you sure you want to delete
              <span class="text-slate-200 font-medium break-words">
                "{{ paperTitle }}" </span
              >? This action cannot be undone.
            </p>
            <div class="text-sm font-bold mt-3 px-2 text-white">
              This will also delete the physical file on your machine.
            </div>
          </div>
        </div>

        <div class="mt-6 flex gap-3">
          <button
            type="button"
            class="flex-1 rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-2.5 text-sm font-semibold text-slate-300 hover:bg-slate-800 hover:text-white transition-colors focus:outline-none"
            @click="$emit('close')"
          >
            Cancel
          </button>
          <button
            type="button"
            class="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-red-500 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500/40"
            @click="$emit('confirm')"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
defineProps({
  paperTitle: {
    type: String,
    default: "Untitled Paper",
  },
});

defineEmits(["close", "confirm"]);
</script>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
