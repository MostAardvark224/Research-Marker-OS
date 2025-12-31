// saves initializing state whenever user inits a smart collection

export const useSmartCollectionsStore = defineStore(
  "smartCollectionsStore",
  () => {
    const isInitializing = ref(false);

    function setInitializing(value) {
      isInitializing.value = value;
    }

    return {
      isInitializing,
      setInitializing,
    };
  },
  {
    persist: true,
  }
);
