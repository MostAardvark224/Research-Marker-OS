const test = require("node:test");
const assert = require("node:assert/strict");

const {
  installSessionGuards,
  installWindowGuards,
  isLoopbackUrl,
  isSameDocumentNavigation,
} = require("./security.cjs");

test("only loopback network URLs are accepted", () => {
  assert.equal(isLoopbackUrl("http://127.0.0.1:4321/api/documents/"), true);
  assert.equal(isLoopbackUrl("ws://localhost:3000/_nuxt/"), true);
  assert.equal(isLoopbackUrl("https://example.com/payload"), false);
  assert.equal(isLoopbackUrl("file:///tmp/paper.pdf"), false);
  assert.equal(isLoopbackUrl("not a url"), false);
});

test("navigation is limited to hash changes on the loaded application document", () => {
  const trusted = "file:///opt/research-marker/index.html#/";
  assert.equal(
    isSameDocumentNavigation(
      "file:///opt/research-marker/index.html#/annotate/42",
      trusted,
    ),
    true,
  );
  assert.equal(
    isSameDocumentNavigation("https://example.com/", trusted),
    false,
  );
  assert.equal(
    isSameDocumentNavigation("file:///tmp/other.html", trusted),
    false,
  );
});

test("session guards deny permissions and non-loopback requests", () => {
  let checkPermission;
  let requestPermission;
  let beforeRequest;
  const session = {
    setPermissionCheckHandler(handler) {
      checkPermission = handler;
    },
    setPermissionRequestHandler(handler) {
      requestPermission = handler;
    },
    webRequest: {
      onBeforeRequest(_filter, handler) {
        beforeRequest = handler;
      },
    },
  };

  installSessionGuards(session);
  assert.equal(checkPermission(), false);

  requestPermission(null, "media", (allowed) => {
    assert.equal(allowed, false);
  });
  beforeRequest({ url: "https://attacker.example/file" }, (result) => {
    assert.deepEqual(result, { cancel: true });
  });
  beforeRequest({ url: "http://127.0.0.1:8000/api/" }, (result) => {
    assert.deepEqual(result, { cancel: false });
  });
});

test("window guards deny popups and unexpected navigation", () => {
  let openHandler;
  const listeners = new Map();
  const browserWindow = {
    webContents: {
      setWindowOpenHandler(handler) {
        openHandler = handler;
      },
      on(event, handler) {
        listeners.set(event, handler);
      },
    },
  };

  installWindowGuards(browserWindow, "file:///app/index.html");
  assert.deepEqual(openHandler(), { action: "deny" });

  let prevented = false;
  listeners.get("will-navigate")(
    { preventDefault: () => (prevented = true) },
    "https://attacker.example/",
  );
  assert.equal(prevented, true);
});
