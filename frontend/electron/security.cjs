const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]"]);

const guardedSessions = new WeakSet();

function parseUrl(rawUrl) {
  try {
    return new URL(rawUrl);
  } catch {
    return null;
  }
}

function isLoopbackUrl(rawUrl) {
  const parsed = parseUrl(rawUrl);
  return (
    parsed !== null &&
    (parsed.protocol === "http:" ||
      parsed.protocol === "https:" ||
      parsed.protocol === "ws:" ||
      parsed.protocol === "wss:") &&
    LOOPBACK_HOSTS.has(parsed.hostname)
  );
}

function isSameDocumentNavigation(rawUrl, trustedDocumentUrl) {
  const candidate = parseUrl(rawUrl);
  const trusted = parseUrl(trustedDocumentUrl);
  if (!candidate || !trusted) {
    return false;
  }

  candidate.hash = "";
  trusted.hash = "";
  return candidate.href === trusted.href;
}

/**
 * Keep the renderer a passive local UI. PDF data is supplied as bytes, so it
 * never needs permission prompts, arbitrary navigation, popups, or Internet
 * requests. The loopback API is its only network dependency.
 */
function installSessionGuards(session, { isDev = false } = {}) {
  if (guardedSessions.has(session)) {
    return;
  }
  guardedSessions.add(session);

  session.setPermissionCheckHandler(() => false);
  session.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false);
  });

  if (!isDev) {
    session.webRequest.onBeforeRequest(
      { urls: ["http://*/*", "https://*/*", "ws://*/*", "wss://*/*"] },
      (details, callback) => callback({ cancel: !isLoopbackUrl(details.url) }),
    );
  }
}

function installWindowGuards(browserWindow, trustedDocumentUrl) {
  browserWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));

  const preventUnexpectedNavigation = (event, url) => {
    if (!isSameDocumentNavigation(url, trustedDocumentUrl)) {
      event.preventDefault();
    }
  };

  browserWindow.webContents.on("will-navigate", preventUnexpectedNavigation);
  browserWindow.webContents.on("will-redirect", preventUnexpectedNavigation);
}

module.exports = {
  installSessionGuards,
  installWindowGuards,
  isLoopbackUrl,
  isSameDocumentNavigation,
};
