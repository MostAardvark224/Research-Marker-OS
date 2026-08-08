// Poll startup script worker status once the API is reachable, then show an in-app toast.
import { useNotificationStore } from "~~/stores/useNotificationStore";

const TERMINAL = new Set(["completed", "failed"]);
const MAX_ATTEMPTS = 90;
const POLL_MS = 2000;
const RECENT_MS = 5 * 60 * 1000;

function formatIssueMessage(status) {
  const failures = (status.results || []).filter((item) => !item.ok);
  if (!failures.length) {
    return status.summary || "Startup scripts finished with issues.";
  }
  return failures
    .map((item) => `${item.path}: ${item.message}`)
    .join("\n");
}

function isRecentRun(status) {
  const stamp = status?.started_at || status?.finished_at;
  if (!stamp) return false;
  const parsed = Date.parse(stamp);
  if (Number.isNaN(parsed)) return false;
  return Date.now() - parsed < RECENT_MS;
}

export default defineNuxtPlugin((nuxtApp) => {
  if (!import.meta.client) return;

  const {
    public: { apiBaseURL },
  } = useRuntimeConfig();
  const notifications = useNotificationStore();

  let attempts = 0;
  let seenRunId = null;
  let timer = null;

  async function pollOnce() {
    attempts += 1;
    try {
      const status = await $fetch(`${apiBaseURL}/startup-scripts/status/`);
      const runStatus = status?.status || "idle";

      if (runStatus === "idle") {
        return true;
      }

      if (runStatus === "queued" || runStatus === "running") {
        return attempts >= MAX_ATTEMPTS;
      }

      if (!TERMINAL.has(runStatus)) {
        return attempts >= MAX_ATTEMPTS;
      }

      if (!status.run_id || !(status.results || []).length) {
        return true;
      }
      if (status.run_id === seenRunId) {
        return true;
      }
      // Ignore leftover results from a previous app session.
      if (!isRecentRun(status)) {
        return true;
      }

      seenRunId = status.run_id;

      if (runStatus === "completed") {
        notifications.notify({
          title: "Startup scripts finished",
          message: status.summary || "All startup scripts completed successfully.",
          type: "success",
          durationMs: 9000,
        });
      } else {
        notifications.notify({
          title: "Startup scripts had issues",
          message: formatIssueMessage(status),
          type: "error",
          durationMs: 14000,
        });
      }
      return true;
    } catch {
      return attempts >= MAX_ATTEMPTS;
    }
  }

  async function startPolling() {
    const done = await pollOnce();
    if (done) return;
    timer = setInterval(async () => {
      const finished = await pollOnce();
      if (finished && timer) {
        clearInterval(timer);
        timer = null;
      }
    }, POLL_MS);
  }

  nuxtApp.hook("app:mounted", () => {
    startPolling();
  });
});
