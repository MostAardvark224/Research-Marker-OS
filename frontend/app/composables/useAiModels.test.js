import assert from "node:assert/strict";
import test from "node:test";
import { ref, computed } from "vue";
import { useAiModels } from "./useAiModels.js";

Object.assign(globalThis, {
  ref, computed,
  useRuntimeConfig: () => ({ public: { apiBaseURL: "http://localhost/api" } }),
});

test("saved reasoning survives settings changes before the catalog is loaded", () => {
  const state = useAiModels();
  state.applySavedPreferences({ models: { codex: "astra" }, codex_reasoning_effort: "high" });
  assert.equal(state.codexReasoningEffort.value, "high");
});

test("reasoning choices follow the selected model and safely fall back to its default", async () => {
  globalThis.$fetch = async () => ({ providers: [{
    id: "codex", models: ["astra", "luna"], default_chat_model: "astra",
    model_details: [
      { id: "astra", default_reasoning_effort: "low", supported_reasoning_efforts: [{ effort: "low" }, { effort: "ultra" }] },
      { id: "luna", default_reasoning_effort: "medium", supported_reasoning_efforts: [{ effort: "medium" }] },
    ],
  }] });
  const state = useAiModels();
  await state.fetchAiModels();
  state.applySavedPreferences({ default_provider: "codex", codex_reasoning_effort: "ultra" });
  assert.equal(state.codexReasoningEffort.value, "ultra");
  state.selectedAiModel.value = "luna";
  assert.equal(state.codexReasoningEffort.value, "");
  assert.equal(state.codexDefaultReasoningEffort.value, "medium");
  assert.deepEqual(state.codexReasoningOptions.value, [{ effort: "medium" }]);
  state.selectedAiModel.value = "astra";
  assert.equal(state.codexReasoningEffort.value, "ultra");
  state.codexReasoningEffort.value = "";
  assert.equal(state.codexReasoningEffort.value, "");
});
