import assert from "node:assert/strict";
import test from "node:test";

import {
  UPDATE_PROMPT_DISABLED_STORAGE_KEY,
  disableUpdatePrompt,
  isUpdatePromptDisabled,
} from "./updatePromptPreference.js";

test("update prompt is enabled by default", () => {
  const storage = {
    getItem() {
      return null;
    },
  };

  assert.equal(isUpdatePromptDisabled(storage), false);
});

test("update prompt can be permanently disabled", () => {
  const values = new Map();
  const storage = {
    getItem(key) {
      return values.get(key) ?? null;
    },
    setItem(key, value) {
      values.set(key, value);
    },
  };

  disableUpdatePrompt(storage);

  assert.equal(values.get(UPDATE_PROMPT_DISABLED_STORAGE_KEY), "1");
  assert.equal(isUpdatePromptDisabled(storage), true);
});

test("unavailable storage does not break the update prompt", () => {
  const storage = {
    getItem() {
      throw new Error("Storage unavailable");
    },
    setItem() {
      throw new Error("Storage unavailable");
    },
  };

  assert.equal(isUpdatePromptDisabled(storage), false);
  assert.doesNotThrow(() => disableUpdatePrompt(storage));
});
