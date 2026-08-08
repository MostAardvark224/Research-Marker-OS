export const useNotificationStore = defineStore("notificationStore", () => {
  const notifications = ref([]);
  let nextId = 1;

  function notify({
    title,
    message = "",
    type = "info",
    durationMs = 8000,
  } = {}) {
    const id = nextId++;
    const entry = {
      id,
      title: title || "Notification",
      message: message || "",
      type: ["success", "error", "info", "warning"].includes(type)
        ? type
        : "info",
    };
    notifications.value = [...notifications.value, entry];

    if (durationMs > 0) {
      setTimeout(() => dismiss(id), durationMs);
    }
    return id;
  }

  function dismiss(id) {
    notifications.value = notifications.value.filter((item) => item.id !== id);
  }

  function clear() {
    notifications.value = [];
  }

  return {
    notifications,
    notify,
    dismiss,
    clear,
  };
});
