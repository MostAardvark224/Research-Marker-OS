const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getApiPort: () => ipcRenderer.invoke("get-api-port"),
  openCodexAuthUrl: (url) => ipcRenderer.invoke("codex:open-auth-url", url),
  openProjectPage: () => ipcRenderer.invoke("app:open-project-page"),
  getAppVersion: () => ipcRenderer.invoke("updater:get-version"),
  getUpdateStatus: () => ipcRenderer.invoke("updater:get-status"),
  checkForUpdates: () => ipcRenderer.invoke("updater:check"),
  installUpdate: () => ipcRenderer.invoke("updater:install"),
  restartApp: () => ipcRenderer.send("restart_app"),
  setSplashProgress: (percent, message) =>
    ipcRenderer.send("splash:progress", { percent, message }),
  notifyAppReady: () => ipcRenderer.send("app:ready"),
  popOutSidebar: (documentId) =>
    ipcRenderer.invoke("sidebar:pop-out", { documentId }),
  focusSidebarPopout: () => ipcRenderer.invoke("sidebar:focus-popout"),
  closeSidebarPopout: () => ipcRenderer.invoke("sidebar:close-popout"),
  revealSidebarAnnotation: (payload) =>
    ipcRenderer.send("sidebar:reveal-annotation", payload),
  onSidebarPopoutClosed: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("sidebar:popout-closed", listener);
    return () => ipcRenderer.removeListener("sidebar:popout-closed", listener);
  },
  onRevealSidebarAnnotation: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("sidebar:reveal-annotation", listener);
    return () =>
      ipcRenderer.removeListener("sidebar:reveal-annotation", listener);
  },
  onUpdateStatus: (callback) => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on("updater:status-changed", listener);
    return () => ipcRenderer.removeListener("updater:status-changed", listener);
  },
});
