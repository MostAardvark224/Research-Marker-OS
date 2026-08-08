<template>
  <div
    class="pointer-events-none fixed bottom-4 right-4 z-[200] flex w-full max-w-sm flex-col gap-2 px-4 sm:px-0"
    aria-live="polite"
  >
    <TransitionGroup name="toast">
      <div
        v-for="item in notifications"
        :key="item.id"
        class="pointer-events-auto rounded-xl border px-4 py-3 shadow-xl backdrop-blur-md"
        :class="toastClass(item.type)"
      >
        <div class="flex items-start gap-3">
          <Icon :name="toastIcon(item.type)" class="mt-0.5 text-lg flex-shrink-0" />
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-white">{{ item.title }}</p>
            <p
              v-if="item.message"
              class="mt-1 text-xs leading-relaxed text-slate-300 whitespace-pre-wrap break-words"
            >
              {{ item.message }}
            </p>
          </div>
          <button
            type="button"
            class="rounded-md p-1 text-slate-400 hover:bg-white/10 hover:text-white transition-colors"
            aria-label="Dismiss notification"
            @click="dismiss(item.id)"
          >
            <Icon name="material-symbols:close" class="text-base" />
          </button>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { storeToRefs } from "pinia";
import { useNotificationStore } from "~~/stores/useNotificationStore";

const store = useNotificationStore();
const { notifications } = storeToRefs(store);
const { dismiss } = store;

function toastClass(type) {
  switch (type) {
    case "success":
      return "border-emerald-500/30 bg-[#0a1210]/95";
    case "error":
      return "border-red-500/30 bg-[#140a0c]/95";
    case "warning":
      return "border-amber-500/30 bg-[#14100a]/95";
    default:
      return "border-indigo-500/30 bg-[#0a0a12]/95";
  }
}

function toastIcon(type) {
  switch (type) {
    case "success":
      return "material-symbols:check-circle-outline";
    case "error":
      return "material-symbols:error-outline";
    case "warning":
      return "material-symbols:warning-outline";
    default:
      return "material-symbols:info-outline";
  }
}
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.22s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
