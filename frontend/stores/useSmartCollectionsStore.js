// saves initializing state whenever user inits a smart collection

export const useSmartCollectionsStore = defineStore(
  "smartCollectionsStore",
  () => {
    const isInitializing = ref(false);
    const taskId = ref(null);

    function setInitializing(value) {
      isInitializing.value = value;
    }

    function setTaskId(value) {
      taskId.value = value;
    }

    return {
      isInitializing,
      taskId,
      setInitializing,
      setTaskId,
    };
  },
  {
    persist: true,
  }
);
