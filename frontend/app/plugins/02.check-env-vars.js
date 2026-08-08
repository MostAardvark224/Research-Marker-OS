// check whether env vars are set and redirect user to set those env vars
// only runs once on app startup.
// set to run after the api client plugin so that the correct backend url is hit
import { useEnvStateStore } from "~~/stores/useEnvStateStore";
import { useAppReady } from "~/composables/useAppReady";

const MAX_ATTEMPTS = 40;
const RETRY_MS = 250;

export default defineNuxtPlugin(async (nuxtApp) => {
  const {
    public: { apiBaseURL },
  } = useRuntimeConfig();

  const envStateStore = useEnvStateStore();
  const { setSplashProgress } = useAppReady();

  setSplashProgress(90, "Checking configuration…");

  // Retry briefly — Electron used to open the window the instant the URL was
  // printed, sometimes before uvicorn accepted connections.
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    try {
      const res = await $fetch(`${apiBaseURL}/env-vars/`);
      const exists = res.exists; // bool
      console.log(`from plugin: ${exists}`);
      envStateStore.setExists(exists);
      setSplashProgress(93, "Loading workspace…");
      return;
    } catch (error) {
      if (attempt === MAX_ATTEMPTS) {
        console.error("Failed to check env vars:", error);
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, RETRY_MS));
    }
  }
});
