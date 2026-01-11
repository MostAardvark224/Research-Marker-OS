const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

app.disableHardwareAcceleration();

let mainWindow;
let pythonProcess;
let apiPort = null;

const isDev = process.env.NODE_ENV === "development";

const scriptPath = isDev
  ? path.join(__dirname, "../../backend/dist/api/api")
  : path.join(process.resourcesPath, "backend", "api");

function createPythonProcess() {
  console.log(`Launching Python from: ${scriptPath}`);

  pythonProcess = spawn(scriptPath);

  const handleLog = (data) => {
    const output = data.toString();
    console.log(`[Python]: ${output}`);

    // Uvicorn prints this when it is ready. can use to grab port.
    const match = output.match(/http:\/\/127\.0\.0\.1:(\d+)/);

    if (match) {
      apiPort = match[1]; // SAVE THIS so the Nuxt plugin can fetch it
      console.log(`Python backend ready on port ${apiPort}`);

      // 4. Only open the window if it hasn't opened yet
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
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:3000");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "../.output/public/index.html"));
  }
}

ipcMain.handle("get-api-port", () => {
  return apiPort;
});

app.whenReady().then(createPythonProcess);

app.on("will-quit", () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
