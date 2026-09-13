import { useNotificationStore } from "~~/stores/useNotificationStore";

export default defineNuxtPlugin((nuxtApp) => {
  if (!import.meta.client) return;
  if (new URLSearchParams(window.location.search).get("sidebarPopout") === "1") return;

  const {
    public: { apiBaseURL },
  } = useRuntimeConfig();
  const notifications = useNotificationStore();

  nuxtApp.hook("app:mounted", async () => {
    try {
      const preferences = await $fetch(`${apiBaseURL}/user-preferences/`);
      const general = preferences?.user_preferences?.general || {};
      if (
        !general.note_sync_on_startup ||
        !Array.isArray(general.note_sync_directories) ||
        !general.note_sync_directories.length
      ) {
        return;
      }

      const result = await $fetch(`${apiBaseURL}/note-sync/refresh/`, {
        method: "POST",
      });
      window.dispatchEvent(
        new CustomEvent("research-marker:notes-refreshed", { detail: result }),
      );
      const imported = result?.counts?.imported || 0;
      const conflicts = result?.counts?.conflict || 0;
      if (imported || conflicts) {
        notifications.notify({
          title: conflicts ? "Note sync needs attention" : "Markdown notes refreshed",
          message: conflicts
            ? `${imported} imported; ${conflicts} conflict(s) need review in their PDF viewer.`
            : `${imported} paper note(s) imported from Markdown.`,
          type: conflicts ? "warning" : "success",
          durationMs: 10000,
        });
      }
    } catch (error) {
      notifications.notify({
        title: "Markdown note refresh failed",
        message: error?.data?.message || error?.message || "Could not scan note folders.",
        type: "error",
        durationMs: 10000,
      });
    }
  });
});
