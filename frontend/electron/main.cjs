const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

app.disableHardwareAcceleration();

let mainWindow;
let splashWindow;
let pythonProcess;
let apiPort = null;

const isDev = process.env.NODE_ENV === "development";

const scriptPath = isDev
  ? path.join(__dirname, "../../backend/dist/api/api")
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
  const splashPath = isDev
    ? path.join(__dirname, "../app/assets/splash.html")
    : path.join(app.getAppPath(), ".output/public/splash.html");

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
      preload: path.join(__dirname, "preload.cjs"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(__dirname, "../app/assets/icons/icon.png"),
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:3000");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "../.output/public/index.html"));
  }

  // changing from loading to app
  mainWindow.once("ready-to-show", () => {
    splashWindow.destroy();
    mainWindow.show();
    mainWindow.focus();
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
