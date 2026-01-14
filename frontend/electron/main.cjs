const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const { autoUpdater } = require("electron-updater");
app.disableHardwareAcceleration();

let mainWindow;
let splashWindow;
let pythonProcess;
let apiPort = null;

const isDev = process.env.NODE_ENV === "development";

const resolvePath = (devPath, prodPath) => {
  if (isDev) {
    return path.join(__dirname, devPath);
  }
  return path.join(app.getAppPath(), prodPath);
};

const scriptPath = isDev
  ? path.join(app.getAppPath(), "../backend/dist/api/api")
  : path.join(process.resourcesPath, "backend", "api");

// creates loading screen before app startup.
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

  // Load html file
  const splashPath = resolvePath(
    "../app/assets/splash.html",
    "app/assets/splash.html"
  );

  console.log("Attempting to load splash from:", splashPath);
  splashWindow.loadFile(splashPath);
}

function createPythonProcess() {
  const userDataPath = app.getPath("userData");

  console.log(`Launching Python from: ${scriptPath}`);
  console.log(`Passing User Data Dir: ${userDataPath}`);

  pythonProcess = spawn(scriptPath, [], {
    env: {
      ...process.env,
      USER_DATA_DIR: userDataPath,
      APP_DEBUG: isDev ? "true" : "false",
    },
  });

  const handleLog = (data) => {
    const output = data.toString();
    console.log(`[Python]: ${output}`);

    // Uvicorn prints this when it is ready. can use to grab port.
    const match = output.match(/http:\/\/127\.0\.0\.1:(\d+)/);

    if (match) {
      apiPort = match[1]; // nuxt plugin will fetch this
      console.log(`Python backend ready on port ${apiPort}`);

      if (!mainWindow) {
        createWindow();
      }
    }
  };

  pythonProcess.stdout.on("data", handleLog);
  pythonProcess.stderr.on("data", handleLog);

  pythonProcess.on("close", (code) => {
    console.log(`Python process exited with code ${code}`);
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
      "app/assets/icons/icon.png"
    ),
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:3000");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(
      path.join(app.getAppPath(), ".output/public/index.html"),
      { hash: "/" }
    );
  }

  // changing from loading to app
  mainWindow.once("ready-to-show", () => {
    splashWindow.destroy();
    mainWindow.show();
    mainWindow.focus();

    if (!isDev) {
      autoUpdater.checkForUpdatesAndNotify();
    }
  });
}

ipcMain.handle("get-api-port", () => {
  return apiPort;
});

app.whenReady().then(() => {
  createSplashWindow();
  createPythonProcess();
});

app.on("will-quit", () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

autoUpdater.on("update-available", () => {
  console.log("Update available.");
  mainWindow.webContents.send("update_available");
});

autoUpdater.on("update-downloaded", () => {
  console.log("Update downloaded");
  mainWindow.webContents.send("update_downloaded");
});
