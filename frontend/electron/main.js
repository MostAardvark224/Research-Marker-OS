const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let mainWindow;
let pythonProcess;
let apiPort = null;

// 1. Determine the path to the Python executable
const isDev = process.env.NODE_ENV === "development";

// In Dev: Look for the binary in your local backend-dist folder
// In Prod: Look inside the installed app's resources folder
const scriptPath = isDev
  ? path.join(__dirname, "../backend-dist/api") // Adjust 'api' to 'api.exe' on Windows if not handled automatically
  : path.join(process.resourcesPath, "backend", "api");

function createPythonProcess() {
  console.log(`Launching Python from: ${scriptPath}`);

  // Spawn the process
  pythonProcess = spawn(scriptPath);

  pythonProcess.stdout.on("data", (data) => {
    const output = data.toString();
    console.log(`[Python]: ${output}`);

    // HANDSHAKE: Listen for the port
    if (output.includes("API_PORT:") && !mainWindow) {
      const match = output.match(/API_PORT:(\d+)/);
      if (match) {
        apiPort = match[1];
        console.log(`Python started on port ${apiPort}. Launching UI...`);
        createWindow();
      }
    }
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`[Python Error]: ${data}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // In Dev: Load the Nuxt dev server URL
  // In Prod: Load the generated index.html
  if (isDev) {
    mainWindow.loadURL("http://localhost:3000");
    mainWindow.webContents.openDevTools(); // Optional: Open DevTools
  } else {
    mainWindow.loadFile(path.join(__dirname, "../.output/public/index.html"));
  }
}

// IPC handler for the frontend to ask for the port
ipcMain.handle("get-api-port", () => {
  return apiPort;
});

app.whenReady().then(createPythonProcess);

// Clean exit: Kill Python when Electron quits
app.on("will-quit", () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
