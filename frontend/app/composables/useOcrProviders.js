export function useOcrProviders() {
  const {
    public: { apiBaseURL },
  } = useRuntimeConfig();

  const ocrProviders = ref([]);
  const ocrProvidersLoading = ref(false);
  const ocrProvidersError = ref("");

  const localProviders = computed(() =>
    ocrProviders.value.filter((provider) => provider.kind === "local")
  );

  const byokProviders = computed(() =>
    ocrProviders.value.filter((provider) => provider.kind === "byok")
  );

  async function fetchOcrProviders() {
    ocrProvidersLoading.value = true;
    ocrProvidersError.value = "";

    try {
      const res = await $fetch(`${apiBaseURL}/ocr-providers/`);
      ocrProviders.value = res.providers || [];
    } catch (error) {
      console.error("Failed to load OCR providers:", error);
      ocrProvidersError.value = "Could not load OCR providers.";
      ocrProviders.value = [
        {
          id: "paddleocr",
          label: "PaddleOCR Local",
          kind: "local",
          description: "Bundled PaddleOCR ONNX models. Runs fully on-device.",
          has_api_key: true,
        },
      ];
    } finally {
      ocrProvidersLoading.value = false;
    }
  }

  function getProviderById(providerId) {
    return ocrProviders.value.find((provider) => provider.id === providerId);
  }

  function isProviderAvailable(providerId) {
    const provider = getProviderById(providerId);
    if (!provider) return false;
    if (provider.kind === "local") return true;
    return Boolean(provider.has_api_key);
  }

  return {
    ocrProviders,
    ocrProvidersLoading,
    ocrProvidersError,
    localProviders,
    byokProviders,
    fetchOcrProviders,
    getProviderById,
    isProviderAvailable,
  };
}
