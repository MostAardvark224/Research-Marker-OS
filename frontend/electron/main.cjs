const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const { autoUpdater } = require("electron-updater");
const log = require("electron-log");

autoUpdater.logger = log;
autoUpdater.autoDownload = true;
autoUpdater.autoInstallOnAppQuit = false;

app.disableHardwareAcceleration();

let mainWindow;
let splashWindow;
let pythonProcess;
let apiPort = null;
let isAppReady = false;
let updateCheckTimer = null;

const isDev = process.env.NODE_ENV === "development";
const useExternalBackend =
  isDev && process.env.ELECTRON_EXTERNAL_BACKEND === "1";
const devApiPort = process.env.DEV_API_PORT || "8000";
const UPDATE_CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000;

let updateState = {
  status: "idle",
  currentVersion: app.getVersion(),
  availableVersion: null,
  progress: null,
  error: null,
};

const resolvePath = (devPath, prodPath) => {
  if (isDev) {
    return path.join(__dirname, devPath);
  }
  return path.join(app.getAppPath(), prodPath);
};

const scriptPath = isDev
  ? path.join(app.getAppPath(), "../backend/dist/api/api")
  : path.join(process.resourcesPath, "backend", "api");

function broadcastUpdateStatus() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("updater:status-changed", { ...updateState });
  }
}

function setUpdateStatus(partial) {
  updateState = { ...updateState, ...partial };
  broadcastUpdateStatus();
}

function killPythonProcess() {
  if (pythonProcess) {
    log.info("Stopping Python backend before update");
    pythonProcess.kill();
    pythonProcess = null;
  }
}

function installDownloadedUpdate() {
  killPythonProcess();
  autoUpdater.quitAndInstall(true, true);
}

function setupAutoUpdater() {
  autoUpdater.on("checking-for-update", () => {
    setUpdateStatus({
      status: "checking",
      error: null,
      progress: null,
    });
  });

  autoUpdater.on("update-available", (info) => {
    log.info("Update available:", info.version);
    setUpdateStatus({
      status: "available",
      availableVersion: info.version,
      error: null,
    });
  });

  autoUpdater.on("update-not-available", (info) => {
    log.info("No update available. Current:", info.version);
    setUpdateStatus({
      status: "up-to-date",
      availableVersion: null,
      progress: null,
      error: null,
    });
  });

  autoUpdater.on("download-progress", (progress) => {
    setUpdateStatus({
      status: "downloading",
      progress: {
        percent: progress.percent,
        transferred: progress.transferred,
        total: progress.total,
        bytesPerSecond: progress.bytesPerSecond,
      },
    });
  });

  autoUpdater.on("update-downloaded", (info) => {
    log.info("Update downloaded:", info.version);
    setUpdateStatus({
      status: "downloaded",
      availableVersion: info.version,
      progress: null,
      error: null,
    });

    if (!isAppReady) {
      installDownloadedUpdate();
    }
  });

  autoUpdater.on("error", (err) => {
    log.error("Auto-updater error:", err);
    if (updateState.status === "downloaded") {
      return;
    }
    setUpdateStatus({
      status: "error",
      error: err?.message || String(err),
      progress: null,
    });
  });
}

async function runUpdateCheck() {
  if (isDev) {
    setUpdateStatus({
      status: "unavailable",
      error: "Updates are disabled in development mode.",
      progress: null,
    });
    return updateState;
  }

  try {
    await autoUpdater.checkForUpdates();
  } catch (err) {
    log.error("Update check failed:", err);
    setUpdateStatus({
      status: "error",
      error: err?.message || String(err),
      progress: null,
    });
  }

  return updateState;
}

function scheduleUpdateChecks() {
  if (isDev || updateCheckTimer) {
    return;
  }

  updateCheckTimer = setInterval(() => {
    autoUpdater.checkForUpdates().catch((err) => {
      log.error("Periodic update check failed:", err);
    });
  }, UPDATE_CHECK_INTERVAL_MS);
}

function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 300,
    transparent: false,
    frame: true,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: false,
    },
  });

  const splashPath = resolvePath(
    "../app/assets/splash.html",
    "app/assets/splash.html",
  );

  log.info("Attempting to load splash from:", splashPath);
  splashWindow.loadFile(splashPath);
}

function createPythonProcess() {
  const userDataPath = app.getPath("userData");

  log.info(`Launching Python from: ${scriptPath}`);
  log.info(`Passing User Data Dir: ${userDataPath}`);

  pythonProcess = spawn(scriptPath, [], {
    env: {
      ...process.env,
      USER_DATA_DIR: userDataPath,
      APP_DEBUG: isDev ? "true" : "false",
    },
  });

  const handleLog = (data) => {
    const output = data.toString();
    log.info(`[Python]: ${output}`);

    const match = output.match(/http:\/\/127\.0\.0\.1:(\d+)/);

    if (match) {
      apiPort = match[1];
      log.info(`Python backend ready on port ${apiPort}`);

      if (!mainWindow) {
        createWindow();
        isAppReady = true;
      }
    }
  };

  pythonProcess.stdout.on("data", handleLog);
  pythonProcess.stderr.on("data", handleLog);

  pythonProcess.on("close", (code) => {
    log.info(`Python process exited with code ${code}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false,
    frame: true,
    webPreferences: {
      preload: resolvePath("preload.cjs", "electron/preload.cjs"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: resolvePath(
      "../app/assets/icons/icon.png",
      "app/assets/icons/icon.png",
    ),
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:3000");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(
      path.join(app.getAppPath(), ".output/public/index.html"),
      { hash: "/" },
    );
  }

  mainWindow.once("ready-to-show", () => {
    splashWindow.destroy();
    mainWindow.show();
    mainWindow.focus();
    broadcastUpdateStatus();
  });
}

ipcMain.handle("get-api-port", () => {
  return apiPort;
});

ipcMain.handle("updater:get-status", () => {
  return { ...updateState };
});

ipcMain.handle("updater:get-version", () => {
  return app.getVersion();
});

ipcMain.handle("updater:check", async () => {
  return runUpdateCheck();
});

ipcMain.handle("updater:install", () => {
  if (updateState.status !== "downloaded") {
    return { ok: false, reason: "No downloaded update is ready to install." };
  }
  installDownloadedUpdate();
  return { ok: true };
});

ipcMain.on("restart_app", () => {
  installDownloadedUpdate();
});

app.whenReady().then(() => {
  setupAutoUpdater();
  createSplashWindow();

  if (useExternalBackend) {
    apiPort = devApiPort;
    log.info(`Using external backend at http://127.0.0.1:${apiPort}/api`);
    createWindow();
    isAppReady = true;
  } else {
    createPythonProcess();
  }

  if (isDev) {
    setUpdateStatus({
      status: "unavailable",
      error: "Updates are disabled in development mode.",
    });
  } else {
    runUpdateCheck();
    scheduleUpdateChecks();
  }
});

app.on("will-quit", () => {
  if (updateCheckTimer) {
    clearInterval(updateCheckTimer);
    updateCheckTimer = null;
  }
  killPythonProcess();
});
