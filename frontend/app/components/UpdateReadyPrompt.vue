<template>
  <Teleport to="body">
    <Transition name="update-prompt">
      <div
        v-if="shouldShow"
        class="fixed inset-0 z-[250] flex items-center justify-center p-4 sm:p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="update-ready-title"
        aria-describedby="update-ready-description"
      >
        <button
          type="button"
          class="absolute inset-0 cursor-default bg-black/75"
          aria-label="Install update later"
          @click="dismissForNow"
        ></button>

        <div
          class="relative w-full max-w-md overflow-hidden rounded-2xl border border-white/10 bg-[#07070a] shadow-2xl shadow-black/50"
        >
          <div class="border-b border-white/5 px-6 py-5">
            <div class="flex items-start gap-4">
              <div
                class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl border border-indigo-500/25 bg-indigo-500/10 text-indigo-300"
              >
                <Icon name="uil:sync" class="text-2xl" />
              </div>
              <div class="min-w-0 flex-1">
                <p class="mb-1 text-[10px] font-bold uppercase tracking-[0.18em] text-indigo-400">
                  Update downloaded
                </p>
                <h2 id="update-ready-title" class="text-xl font-semibold text-white">
                  Restart to update Research Marker
                </h2>
              </div>
              <button
                type="button"
                class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-white/10 hover:text-white"
                aria-label="Install update later"
                @click="dismissForNow"
              >
                <Icon name="material-symbols:close" class="text-xl" />
              </button>
            </div>
          </div>

          <div class="space-y-4 px-6 py-5">
            <p id="update-ready-description" class="text-sm leading-relaxed text-slate-300">
              Version {{ availableVersion }} is ready. Research Marker will close, install the
              update, and reopen.
            </p>
            <div class="flex gap-3 rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-3">
              <Icon
                name="material-symbols:info-outline"
                class="mt-0.5 flex-shrink-0 text-lg text-indigo-400"
              />
              <p class="text-xs leading-relaxed text-indigo-200/80">
                You can install this update anytime from
                <strong class="font-semibold text-indigo-100">Settings → Updates</strong>.
              </p>
            </div>
            <p v-if="installError" class="text-xs leading-relaxed text-red-300" role="alert">
              {{ installError }}
            </p>
          </div>

          <div
            class="flex flex-col-reverse gap-3 border-t border-white/5 bg-white/[0.02] px-6 py-4 sm:flex-row sm:items-center"
          >
            <button
              type="button"
              class="px-1 py-2 text-left text-xs font-medium text-slate-500 transition-colors hover:text-slate-300 sm:mr-auto"
              @click="neverShowAgain"
            >
              Don’t show again
            </button>
            <button
              type="button"
              class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
              @click="dismissForNow"
            >
              Later
            </button>
            <button
              type="button"
              :disabled="isInstalling"
              class="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
              @click="installAndRestart"
            >
              {{ isInstalling ? "Restarting…" : "Install & Restart" }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import {
  disableUpdatePrompt,
  isUpdatePromptDisabled,
} from "~/utils/updatePromptPreference";

const {
  isDesktopApp,
  updateState,
  isReadyToInstall,
  installUpdate,
  initializeUpdater,
  teardownUpdater,
} = useAppUpdater();

const promptsDisabled = ref(false);
const dismissedVersion = ref(null);
const isInstalling = ref(false);
const installError = ref("");

const availableVersion = computed(
  () => updateState.value.availableVersion || "the latest version",
);

const shouldShow = computed(
  () =>
    isDesktopApp &&
    isReadyToInstall.value &&
    !promptsDisabled.value &&
    dismissedVersion.value !== updateState.value.availableVersion,
);

function dismissForNow() {
  dismissedVersion.value = updateState.value.availableVersion;
  installError.value = "";
}

function neverShowAgain() {
  promptsDisabled.value = true;
  disableUpdatePrompt(window.localStorage);
  installError.value = "";
}

async function installAndRestart() {
  isInstalling.value = true;
  installError.value = "";

  try {
    const result = await installUpdate();
    if (!result?.ok) {
      installError.value =
        result?.reason ||
        "The update could not be started. Try again in Settings.";
      isInstalling.value = false;
    }
  } catch (error) {
    installError.value =
      error?.message ||
      "The update could not be started. Try again in Settings.";
    isInstalling.value = false;
  }
}

onMounted(() => {
  promptsDisabled.value = isUpdatePromptDisabled(window.localStorage);
  initializeUpdater();
});

onUnmounted(() => {
  teardownUpdater();
});
</script>

<style scoped>
.update-prompt-enter-active,
.update-prompt-leave-active {
  transition: opacity 0.18s ease;
}

.update-prompt-enter-active > div,
.update-prompt-leave-active > div {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.update-prompt-enter-from,
.update-prompt-leave-to,
.update-prompt-enter-from > div,
.update-prompt-leave-to > div {
  opacity: 0;
}

.update-prompt-enter-from > div,
.update-prompt-leave-to > div {
  transform: translateY(8px) scale(0.98);
}
</style>
