const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { resolveBackendPath } = require("./backend-path.cjs");

test("packaged backend path uses api.exe on Windows", () => {
  assert.equal(
    resolveBackendPath({
      isDev: false,
      appPath: "/unused",
      resourcesPath: "/app/resources",
      platform: "win32",
    }),
    path.join("/app/resources", "backend", "api.exe"),
  );
});

for (const platform of ["darwin", "linux"]) {
  test(`packaged backend path uses api on ${platform}`, () => {
    assert.equal(
      resolveBackendPath({
        isDev: false,
        appPath: "/unused",
        resourcesPath: "/app/resources",
        platform,
      }),
      path.join("/app/resources", "backend", "api"),
    );
  });
}

test("development backend path uses the platform executable name", () => {
  assert.equal(
    resolveBackendPath({
      isDev: true,
      appPath: "/repo/frontend",
      resourcesPath: "/unused",
      platform: "win32",
    }),
    path.join("/repo/frontend", "../backend/dist/api", "api.exe"),
  );
  assert.equal(
    resolveBackendPath({
      isDev: true,
      appPath: "/repo/frontend",
      resourcesPath: "/unused",
      platform: "linux",
    }),
    path.join("/repo/frontend", "../backend/dist/api", "api"),
  );
});
