export function useAiModels() {
  const {
    public: { apiBaseURL },
  } = useRuntimeConfig();

  const aiProviders = ref([]);
  const aiModels = ref({});
  const selectedAiProvider = ref("gemini");
  const aiModelsLoading = ref(false);
  const aiModelsError = ref(null);

  const defaultModelByProvider = computed(() =>
    Object.fromEntries(
      aiProviders.value.map((provider) => [
        provider.id,
        provider.default_chat_model || provider.models?.[0] || "",
      ])
    )
  );

  const selectedProvider = computed(() =>
    aiProviders.value.find((provider) => provider.id === selectedAiProvider.value)
  );

  const selectedProviderModels = computed(() => selectedProvider.value?.models || []);

  const selectedAiModel = computed({
    get: () => aiModels.value[selectedAiProvider.value] || "",
    set: (value) => {
      aiModels.value[selectedAiProvider.value] = value;
    },
  });

  const selectedProviderAllowsCustomModel = computed(
    () => selectedProvider.value?.id === "custom" || !selectedProviderModels.value.length
  );

  const selectedProviderModelHint = computed(() => {
    const provider = selectedProvider.value;
    if (!provider) return null;

    if (provider.id === "codex") {
      if (provider.ready) return null;
      return (
        provider.status?.message ||
        "Connect your ChatGPT account in Settings → Models before using Codex."
      );
    }

    if (provider.id === "custom") {
      if (!provider.has_api_key) {
        return "Add your Custom Server base URL in Settings → General.";
      }
      if (!selectedAiModel.value?.trim()) {
        return "Enter the model id your local server expects (e.g. llama3.2).";
      }
      return null;
    }

    if (!provider.models?.length) {
      if (!provider.has_api_key) {
        return `Add your ${provider.label} API key in Settings → General to select a model.`;
      }
      return provider.error || `No models available for ${provider.label}.`;
    }

    return null;
  });

  const selectedProviderHasModels = computed(() => {
    if (selectedProvider.value?.id === "codex") {
      if (!selectedProvider.value.ready) return false;
      if (selectedProviderModels.value.length > 0) {
        return Boolean(selectedAiModel.value?.trim());
      }
      return true;
    }
    if (!selectedProvider.value?.has_api_key) return false;
    if (selectedProviderModels.value.length > 0) {
      return Boolean(selectedAiModel.value?.trim());
    }
    // Custom / local servers often need a manually typed model id.
    return (
      selectedProvider.value?.id === "custom" &&
      Boolean(selectedAiModel.value?.trim())
    );
  });

  function applyProviderCatalog(providers = []) {
    aiProviders.value = providers;

    const nextModels = { ...aiModels.value };
    for (const provider of providers) {
      const current = nextModels[provider.id];
      if (current) continue;
      nextModels[provider.id] =
        provider.default_chat_model || provider.models?.[0] || "";
    }
    aiModels.value = nextModels;

    if (!providers.some((provider) => provider.id === selectedAiProvider.value)) {
      selectedAiProvider.value = providers[0]?.id || "gemini";
    }
  }

  function applySavedPreferences(aiPrefs = {}) {
    if (aiPrefs.default_provider) {
      selectedAiProvider.value = aiPrefs.default_provider;
    }

    if (aiPrefs.models && typeof aiPrefs.models === "object") {
      aiModels.value = {
        ...aiModels.value,
        ...aiPrefs.models,
      };
    }
  }

  async function fetchAiModels({ refresh = false } = {}) {
    aiModelsLoading.value = true;
    aiModelsError.value = null;

    try {
      const res = await $fetch(`${apiBaseURL}/ai-models/`, {
        query: refresh ? { refresh: "true" } : undefined,
      });
      applyProviderCatalog(res.providers || []);
    } catch (error) {
      aiModelsError.value = error?.message || "Failed to load AI models";
      console.error("Failed to fetch AI models:", error);
    } finally {
      aiModelsLoading.value = false;
    }
  }

  async function loadAiPreferences() {
    try {
      const res = await $fetch(`${apiBaseURL}/user-preferences/`);
      applySavedPreferences(res.user_preferences?.ai || {});
    } catch (error) {
      console.error("Failed to load AI preferences:", error);
    }
  }

  async function initializeAiModels({ refresh = false } = {}) {
    await fetchAiModels({ refresh });
    await loadAiPreferences();
  }

  return {
    aiProviders,
    aiModels,
    selectedAiProvider,
    selectedAiModel,
    selectedProvider,
    selectedProviderModels,
    selectedProviderAllowsCustomModel,
    selectedProviderModelHint,
    selectedProviderHasModels,
    defaultModelByProvider,
    aiModelsLoading,
    aiModelsError,
    fetchAiModels,
    loadAiPreferences,
    initializeAiModels,
    applySavedPreferences,
  };
}
