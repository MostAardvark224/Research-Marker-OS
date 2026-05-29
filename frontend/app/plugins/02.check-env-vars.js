// check whether env vars are set and redirect user to set those env vars
// only runs once on app startup.
// set to run after the api client plugin so that the correct backend url is hit
import { storeToRefs } from "pinia";
import { useEnvStateStore } from "~~/stores/useEnvStateStore";

export default defineNuxtPlugin(async (nuxtApp) => {
  const {
    public: { apiBaseURL, frontendOrigin },
  } = useRuntimeConfig();

  const envStateStore = useEnvStateStore();

  // checking w/ the backend to see if the user has set any env vars
  try {
    const res = await $fetch(`${apiBaseURL}/env-vars/`);
    const exists = res.exists; // bool
    console.log(`from plugin: ${exists}`);
    const envStateStore = useEnvStateStore();
    envStateStore.setExists(exists);
  } catch (error) {
    console.error("Failed to check env vars:", error);
  }
});
