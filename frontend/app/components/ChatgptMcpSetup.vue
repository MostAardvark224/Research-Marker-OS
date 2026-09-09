<script setup>
const props = defineProps({
  setup: { type: Object, default: null },
  busy: Boolean,
  error: { type: String, default: "" },
});
defineEmits(["refresh"]);
const server = computed(() => props.setup?.chatgpt_desktop_config?.mcp_servers?.["research-marker"]);
const copied = ref("");
const copyError = ref("");
let copiedTimer;
async function copy(value, key) {
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    copyError.value = "";
    copied.value = key;
    clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => { copied.value = ""; }, 2000);
  } catch {
    copyError.value = "Could not copy. Select and copy the text below.";
  }
}
onBeforeUnmount(() => clearTimeout(copiedTimer));
</script>

<template>
  <div class="space-y-3 rounded-xl border border-white/10 bg-white/[0.02] p-4">
    <div class="flex items-start justify-between gap-3">
      <div>
        <h4 class="text-sm font-medium text-white">ChatGPT Desktop / Codex</h4>
        <p class="mt-1 text-xs leading-relaxed text-slate-400">
          Let ChatGPT and Codex read the open paper, selected text, and page images. One local MCP setup works in both.
        </p>
      </div>
      <span class="shrink-0 text-[11px]" :class="setup?.ready ? 'text-emerald-400' : 'text-amber-400'">
        {{ setup?.ready ? "Backend ready" : "Waiting for backend" }}
      </span>
    </div>

    <ol class="list-decimal space-y-2 pl-5 text-xs leading-relaxed text-slate-400">
      <li>Keep Research Marker running and open a PDF.</li>
      <li>In ChatGPT Desktop, open <strong class="text-slate-200">Settings → MCP servers → Add server</strong>.</li>
      <li>Choose <strong class="text-slate-200">STDIO</strong>, name it <code>research-marker</code>, and enter the command, arguments, and environment variables below.</li>
      <li>Save, select <strong class="text-slate-200">Restart</strong>, then type <code>/mcp</code> in a chat to check the connection.</li>
    </ol>

    <p class="rounded-lg bg-indigo-500/10 px-3 py-2 text-xs text-indigo-200">
      Try: “Use Research Marker to explain the diagram on @page.”
    </p>
    <p v-if="error || copyError" class="text-xs text-red-300">{{ copyError || error }}</p>

    <div v-if="server" class="space-y-2 text-xs">
      <div class="flex items-center justify-between text-slate-400">
        <span>Command</span>
        <button type="button" class="text-indigo-300 hover:text-indigo-200" @click="copy(server.command, 'command')">
          {{ copied === 'command' ? "Copied" : "Copy command" }}
        </button>
      </div>
      <pre class="overflow-auto whitespace-pre-wrap break-all rounded-lg bg-black/30 px-3 py-2 text-[11px] text-slate-300">{{ server.command }}</pre>
      <details class="rounded-lg border border-white/10 px-3 py-2">
        <summary class="cursor-pointer text-slate-400">Arguments and environment variables</summary>
        <p class="mt-2 text-[11px] text-slate-500">Add each argument as a separate entry, in this order.</p>
        <ol v-if="server.args.length" class="mt-1 list-decimal space-y-1 pl-5">
          <li v-for="(argument, index) in server.args" :key="index" class="break-all font-mono text-[11px] text-slate-300">{{ argument }}</li>
        </ol>
        <p v-else class="mt-1 text-slate-400">No arguments needed.</p>
        <dl class="mt-3 space-y-2">
          <div v-for="(value, name) in server.env" :key="name">
            <dt class="break-all font-mono text-[10px] text-slate-500">{{ name }}</dt>
            <dd class="break-all font-mono text-[11px] text-slate-300">{{ value }}</dd>
          </div>
        </dl>
      </details>
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        type="button" :disabled="busy || !setup?.chatgpt_desktop_config_toml"
        class="rounded-lg border border-indigo-500/30 bg-indigo-500/20 px-3 py-1.5 text-xs text-indigo-200 disabled:opacity-50"
        @click="copy(setup.chatgpt_desktop_config_toml, 'config')"
      >{{ copied === 'config' ? "Copied" : "Copy ChatGPT / Codex config" }}</button>
      <button type="button" :disabled="busy" class="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 disabled:opacity-50" @click="$emit('refresh')">
        Refresh status
      </button>
    </div>
    <details class="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-400">
      <summary class="cursor-pointer">Use config.toml instead</summary>
      <p class="mt-2 leading-relaxed">
        Add this block to <code>~/.codex/config.toml</code> (or <code>%USERPROFILE%\.codex\config.toml</code> on Windows).
        Replace an existing <code>research-marker</code> block if present; keep your other settings.
        Restart the MCP server in ChatGPT after saving. This configuration is also shared with Codex CLI on the same host.
      </p>
      <pre class="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all font-mono text-[10px] text-slate-300">{{ setup?.chatgpt_desktop_config_toml || "Loading…" }}</pre>
    </details>
    <details class="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-400">
      <summary class="cursor-pointer">Connect from Codex</summary>
      <p class="mt-2 leading-relaxed">
        Save the same config block in <code>~/.codex/config.toml</code>, then start a new Codex session.
        Run <code>codex mcp list</code> or type <code>/mcp</code> inside Codex to check the connection.
        Restart the Codex IDE extension if you use it. Keep Research Marker open on the same host.
      </p>
    </details>
    <p class="text-[11px] leading-relaxed text-slate-500">
      Requires ChatGPT Desktop with local MCP server settings on this computer. The web app does not read this local configuration.
      Requested paper text and images are sent to ChatGPT when it calls these tools. The bridge runs locally.
    </p>
    <a href="https://learn.chatgpt.com/docs/extend/mcp" target="_blank" rel="noopener noreferrer" class="inline-block text-[11px] text-indigo-300 hover:underline">
      OpenAI connection guide ↗
    </a>
  </div>
</template>
