<template>
  <div
    class="notification-viewport pointer-events-none fixed inset-y-4 right-4 z-[200] w-[calc(100vw-2rem)] max-w-sm overflow-y-auto"
    aria-live="polite"
  >
    <TransitionGroup
      name="toast"
      tag="div"
      class="flex min-h-full flex-col justify-end gap-2"
    >
      <div
        v-for="item in notifications"
        :key="item.id"
        class="notification-toast pointer-events-auto shrink-0 overflow-hidden rounded-xl border px-4 py-3 shadow-xl backdrop-blur-md"
        :class="toastClass(item.type)"
      >
        <div class="flex items-start gap-3">
          <Icon :name="toastIcon(item.type)" class="mt-0.5 text-lg flex-shrink-0" />
          <div class="min-w-0 flex-1">
            <p class="break-words text-sm font-medium text-white [overflow-wrap:anywhere]">
              {{ item.title }}
            </p>
            <p
              v-if="item.message"
              class="notification-message mt-1 overflow-y-auto whitespace-pre-wrap break-words pr-1 text-xs leading-relaxed text-slate-300 [overflow-wrap:anywhere]"
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
.notification-viewport {
  max-height: calc(100dvh - 2rem);
  overscroll-behavior: contain;
  scrollbar-width: thin;
}

.notification-toast {
  max-height: calc(100dvh - 2rem);
}

.notification-message {
  /* Leave room for the toast padding, title, and dismiss button. */
  max-height: calc(100dvh - 7rem);
  overscroll-behavior: contain;
  scrollbar-width: thin;
}

.notification-viewport::-webkit-scrollbar,
.notification-message::-webkit-scrollbar {
  width: 4px;
}

.notification-viewport::-webkit-scrollbar-thumb,
.notification-message::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgb(148 163 184 / 0.35);
}

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
