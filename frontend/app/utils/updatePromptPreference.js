export const UPDATE_PROMPT_DISABLED_STORAGE_KEY =
  "researchMarker_disableUpdateReadyPrompt";

export function isUpdatePromptDisabled(storage) {
  try {
    return storage?.getItem(UPDATE_PROMPT_DISABLED_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function disableUpdatePrompt(storage) {
  try {
    storage?.setItem(UPDATE_PROMPT_DISABLED_STORAGE_KEY, "1");
  } catch {
    // The prompt remains dismissed for this session even if storage is unavailable.
  }
}
