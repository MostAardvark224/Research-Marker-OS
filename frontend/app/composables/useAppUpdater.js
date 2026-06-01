const defaultUpdateState = () => ({
  status: "idle",
  currentVersion: null,
  availableVersion: null,
  progress: null,
  error: null,
});

export function useAppUpdater() {
  const isDesktopApp = import.meta.client && typeof window.electronAPI !== "undefined";

  const updateState = ref(defaultUpdateState());
  const isChecking = computed(() => updateState.value.status === "checking");
  const isDownloading = computed(() => updateState.value.status === "downloading");
  const isReadyToInstall = computed(() => updateState.value.status === "downloaded");
  const isUpToDate = computed(() => updateState.value.status === "up-to-date");
  const hasUpdateError = computed(() => updateState.value.status === "error");

  let unsubscribe = null;

  async function refreshUpdateStatus() {
    if (!isDesktopApp) {
      return;
    }

    try {
      const status = await window.electronAPI.getUpdateStatus();
      updateState.value = { ...updateState.value, ...status };
    } catch (error) {
      console.error("Failed to fetch update status:", error);
    }
  }

  async function loadAppVersion() {
    if (!isDesktopApp) {
      return;
    }

    try {
      const version = await window.electronAPI.getAppVersion();
      updateState.value.currentVersion = version;
    } catch (error) {
      console.error("Failed to fetch app version:", error);
    }
  }

  async function checkForUpdates() {
    if (!isDesktopApp) {
      updateState.value = {
        ...updateState.value,
        status: "unavailable",
        error: "Updates are only available in the desktop app.",
      };
      return updateState.value;
    }

    try {
      const status = await window.electronAPI.checkForUpdates();
      updateState.value = { ...updateState.value, ...status };
      return updateState.value;
    } catch (error) {
      updateState.value = {
        ...updateState.value,
        status: "error",
        error: error?.message || "Failed to check for updates.",
      };
      return updateState.value;
    }
  }

  async function installUpdate() {
    if (!isDesktopApp || !isReadyToInstall.value) {
      return { ok: false };
    }

    return window.electronAPI.installUpdate();
  }

  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) {
      return "";
    }

    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    let unitIndex = 0;

    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex += 1;
    }

    return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
  }

  const statusMessage = computed(() => {
    const state = updateState.value;

    switch (state.status) {
      case "checking":
        return "Checking for updates…";
      case "available":
        return `Version ${state.availableVersion} is available. Downloading…`;
      case "downloading": {
        const percent = Math.round(state.progress?.percent || 0);
        const transferred = formatBytes(state.progress?.transferred);
        const total = formatBytes(state.progress?.total);
        if (transferred && total) {
          return `Downloading update… ${percent}% (${transferred} / ${total})`;
        }
        return `Downloading update… ${percent}%`;
      }
      case "downloaded":
        return `Version ${state.availableVersion} is ready to install.`;
      case "up-to-date":
        return `You're on the latest version (${state.currentVersion || "unknown"}).`;
      case "error":
        return state.error || "Something went wrong while checking for updates.";
      case "unavailable":
        return state.error || "Updates are not available in this environment.";
      default:
        return "Check for updates to get the latest version of Research Marker.";
    }
  });

  const downloadProgress = computed(() =>
    Math.min(100, Math.max(0, Math.round(updateState.value.progress?.percent || 0))),
  );

  function initializeUpdater() {
    if (!import.meta.client || !isDesktopApp) {
      return;
    }

    loadAppVersion();
    refreshUpdateStatus();

    unsubscribe = window.electronAPI.onUpdateStatus((status) => {
      updateState.value = { ...updateState.value, ...status };
    });
  }

  function teardownUpdater() {
    if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
  }

  return {
    isDesktopApp,
    updateState,
    isChecking,
    isDownloading,
    isReadyToInstall,
    isUpToDate,
    hasUpdateError,
    statusMessage,
    downloadProgress,
    checkForUpdates,
    installUpdate,
    refreshUpdateStatus,
    loadAppVersion,
    initializeUpdater,
    teardownUpdater,
  };
}
