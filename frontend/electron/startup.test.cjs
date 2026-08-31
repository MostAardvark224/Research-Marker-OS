const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const { PassThrough } = require("node:stream");
const test = require("node:test");

const {
  createLineParser,
  parseBackendAnnouncement,
  probeBackend,
} = require("./startup.cjs");

test("line parser reconstructs a ready URL split across Windows chunks", () => {
  const lines = [];
  const parser = createLineParser((line) => lines.push(line));

  parser.push(Buffer.from("Migrations applied successfully.\r\nhttp://127.0."));
  parser.push(Buffer.from("0.1:53745\r"));
  parser.push(Buffer.from("\n"));

  assert.deepEqual(lines, [
    "Migrations applied successfully.",
    "http://127.0.0.1:53745",
  ]);
  assert.deepEqual(parseBackendAnnouncement(lines[1]), {
    port: "53745",
    source: "backend ready announcement",
  });
});

test("announcement parser accepts the structured marker and Uvicorn fallback", () => {
  assert.deepEqual(
    parseBackendAnnouncement(
      "RESEARCH_MARKER_BACKEND_READY=http://127.0.0.1:49152",
    ),
    { port: "49152", source: "backend ready announcement" },
  );
  assert.deepEqual(
    parseBackendAnnouncement(
      "\u001b[32mINFO\u001b[0m: Uvicorn running on http://127.0.0.1:49153 (Press CTRL+C to quit)",
    ),
    { port: "49153", source: "Uvicorn startup log" },
  );
});

test("health probe waits for an HTTP response", async () => {
  const httpGet = (options, onResponse) => {
    assert.equal(options.hostname, "127.0.0.1");
    assert.equal(options.port, 53745);
    assert.equal(options.path, "/api/health/");

    const request = new EventEmitter();
    request.destroy = (error) => request.emit("error", error);
    process.nextTick(() => {
      const response = new PassThrough();
      response.statusCode = 200;
      onResponse(response);
      response.end('{"status":"ok"}');
    });
    return request;
  };

  assert.deepEqual(await probeBackend(53745, { httpGet }), {
    statusCode: 200,
  });
});
