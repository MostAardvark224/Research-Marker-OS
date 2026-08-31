const http = require("http");

const ANSI_ESCAPE_PATTERN = /\x1b\[[0-?]*[ -/]*[@-~]/g;

function createLineParser(onLine) {
  let buffer = "";

  return {
    push(chunk) {
      buffer += chunk.toString();
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || "";
      for (const line of lines) {
        onLine(line);
      }
    },
    flush() {
      if (buffer) {
        onLine(buffer);
        buffer = "";
      }
    },
  };
}

function parseBackendAnnouncement(rawLine) {
  const line = String(rawLine).replace(ANSI_ESCAPE_PATTERN, "").trim();
  let match = line.match(
    /^(?:RESEARCH_MARKER_BACKEND_READY=)?http:\/\/127\.0\.0\.1:(\d+)\/?$/,
  );
  if (match) {
    return { port: match[1], source: "backend ready announcement" };
  }

  match = line.match(
    /Uvicorn running on http:\/\/127\.0\.0\.1:(\d+)(?:\s|\/|$)/i,
  );
  if (match) {
    return { port: match[1], source: "Uvicorn startup log" };
  }

  return null;
}

function probeBackend(port, { timeoutMs = 1500, httpGet = http.get } = {}) {
  return new Promise((resolve, reject) => {
    const request = httpGet(
      {
        hostname: "127.0.0.1",
        port: Number(port),
        path: "/api/health/",
        timeout: timeoutMs,
        headers: { Accept: "application/json" },
      },
      (response) => {
        response.resume();
        response.once("end", () => {
          // A 404 still proves that the expected HTTP server is accepting
          // requests, which keeps this compatible with older dev backends.
          if (response.statusCode >= 200 && response.statusCode < 500) {
            resolve({ statusCode: response.statusCode });
            return;
          }
          reject(
            new Error(`health check returned HTTP ${response.statusCode}`),
          );
        });
      },
    );

    request.once("timeout", () => {
      request.destroy(new Error(`health check timed out after ${timeoutMs}ms`));
    });
    request.once("error", reject);
  });
}

module.exports = {
  createLineParser,
  parseBackendAnnouncement,
  probeBackend,
};
