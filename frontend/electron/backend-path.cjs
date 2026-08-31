const path = require("path");

function resolveBackendPath({
  isDev,
  appPath,
  resourcesPath,
  platform = process.platform,
}) {
  const executableName = platform === "win32" ? "api.exe" : "api";

  return isDev
    ? path.join(appPath, "../backend/dist/api", executableName)
    : path.join(resourcesPath, "backend", executableName);
}

module.exports = { resolveBackendPath };
