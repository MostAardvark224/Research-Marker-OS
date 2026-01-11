import { storeToRefs } from "pinia";
import { useEnvStateStore } from "~~/stores/useEnvStateStore";

export default defineNuxtRouteMiddleware(async (to, from) => {
  if (to.path === "/env-vars") return;

  const {
    public: { apiBaseURL },
  } = useRuntimeConfig();

  const envStateStore = useEnvStateStore();

  const { exists } = storeToRefs(envStateStore);

  if (!exists.value) {
    console.log("Middleware directing to /env-vars");
    return navigateTo("/env-vars");
  }
});
