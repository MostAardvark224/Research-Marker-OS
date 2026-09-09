const { existsSync } = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const backendDirectory = __dirname;
const virtualEnvironmentPython = path.join(
  backendDirectory,
  "venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);

const candidates = [
  process.env.PYTHON,
  existsSync(virtualEnvironmentPython) ? virtualEnvironmentPython : null,
  process.platform === "win32" ? "python" : "python3",
  process.platform === "win32" ? "py" : "python",
].filter(Boolean);

let python;
for (const candidate of candidates) {
  const result = spawnSync(candidate, ["-c", "import PyInstaller"], {
    stdio: "ignore",
  });
  if (result.status === 0) {
    python = candidate;
    break;
  }
}

if (!python) {
  console.error(
    "Unable to build the backend: no Python interpreter with PyInstaller was found. " +
      "Install backend/requirements.txt in backend/venv or set PYTHON to the correct interpreter.",
  );
  process.exit(1);
}

console.log(`Building packaged backend with ${python}...`);
const result = spawnSync(
  python,
  ["-m", "PyInstaller", "api.spec", "--noconfirm", "--clean"],
  {
    cwd: backendDirectory,
    stdio: "inherit",
  },
);

if (result.error) {
  console.error(`Unable to start the backend build: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
