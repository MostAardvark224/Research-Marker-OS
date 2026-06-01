const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getApiPort: () => ipcRenderer.invoke("get-api-port"),
  getAppVersion: () => ipcRenderer.invoke("updater:get-version"),
  getUpdateStatus: () => ipcRenderer.invoke("updater:get-status"),
  checkForUpdates: () => ipcRenderer.invoke("updater:check"),
  installUpdate: () => ipcRenderer.invoke("updater:install"),
  restartApp: () => ipcRenderer.send("restart_app"),
  onUpdateStatus: (callback) => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on("updater:status-changed", listener);
    return () => ipcRenderer.removeListener("updater:status-changed", listener);
  },
});
