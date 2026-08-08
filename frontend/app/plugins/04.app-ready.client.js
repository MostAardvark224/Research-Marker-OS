// Dismiss Electron splash once the Vue shell has painted (not after data loads).
import { useAppReady } from "~/composables/useAppReady";

const FALLBACK_MS = 12000;

export default defineNuxtPlugin((nuxtApp) => {
  if (!import.meta.client || !window.electronAPI?.notifyAppReady) {
    return;
  }

  const { setSplashProgress, signalAppReady } = useAppReady();

  nuxtApp.hook("app:mounted", () => {
    setSplashProgress(96, "Opening workspace…");
    // Two frames: layout committed, then paint — avoids revealing a blank frame.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        signalAppReady("Ready");
      });
    });

    window.setTimeout(() => {
      signalAppReady("Ready");
    }, FALLBACK_MS);
  });
});
