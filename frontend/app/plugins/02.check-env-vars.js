// check whether env vars are set and redirect user to set those env vars
// only runs once on app startup.
// set to run after the api client plugin so that the correct backend url is hit

export default defineNuxtPlugin(async (nuxtApp) => {
  const {
    public: { apiBaseURL },
  } = useRuntimeConfig();

  // checking w/ the backend to see if the user has set any env vars
  const res = await $fetch(`${apiBaseURL}/env-vars/`);

  const exists = res.exists; // bool

  // redirecting to env var setting page if they havent set anything
  const route = useRoute();
  if (!exists && route.path !== "/env-vars") {
    return navigateTo("/env-vars");
  }
});
