// Fallback: if a page never signals ready (unexpected route / crash), still dismiss splash.
import { useAppReady } from "~/composables/useAppReady";

const FALLBACK_MS = 20000;

export default defineNuxtPlugin((nuxtApp) => {
  if (!import.meta.client || !window.electronAPI?.notifyAppReady) {
    return;
  }

  const { signalAppReady } = useAppReady();

  nuxtApp.hook("app:mounted", () => {
    window.setTimeout(() => {
      signalAppReady("Ready");
    }, FALLBACK_MS);
  });
});
