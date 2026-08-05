export const useSmartCollectionsStore = defineStore(
  "smartCollectionsStore",
  () => {
    const activeJobId = ref(null);
    const jobStatus = ref(null);
    const isInitializing = computed(() =>
      ["queued", "running"].includes(jobStatus.value?.status),
    );

    function setJob(job) {
      jobStatus.value = job || null;
      activeJobId.value = job?.id || null;
    }

    function clearJob() {
      activeJobId.value = null;
      jobStatus.value = null;
    }

    return {
      isInitializing,
      activeJobId,
      jobStatus,
      setJob,
      clearJob,
    };
  },
  {
    persist: true,
  }
);
