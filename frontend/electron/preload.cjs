const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electron", {
  getApiPort: () => ipcRenderer.invoke("get-api-port"),
  onUpdateAvailable: (callback) => ipcRenderer.on("update_available", callback),
  onUpdateDownloaded: (callback) =>
    ipcRenderer.on("update_downloaded", callback),
  restartApp: () => ipcRenderer.send("restart_app"),
});
