// Start a fresh Codex runtime on app launch when Codex powers chat by default.
import { useAppReady } from "~/composables/useAppReady";

export default defineNuxtPlugin(async () => {
  const {
    public: { apiBaseURL },
  } = useRuntimeConfig();
  const { setSplashProgress } = useAppReady();

  try {
    const preferences = await $fetch(`${apiBaseURL}/user-preferences/`);
    const defaultProvider = preferences?.user_preferences?.ai?.default_provider;

    if (defaultProvider !== "codex") return;

    setSplashProgress(94, "Starting Codex…");
    await $fetch(`${apiBaseURL}/codex/status/`, {
      method: "POST",
      body: { action: "restart" },
    });
  } catch (error) {
    // Codex status and recovery remain available in Settings; a provider
    // startup failure should not prevent the rest of the app from opening.
    console.error("Failed to restart Codex on app startup:", error);
  }
});
