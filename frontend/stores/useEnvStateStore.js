export const useEnvStateStore = defineStore("envStateStore", () => {
  const exists = ref(true);

  function setExists(val) {
    exists.value = val;
  }

  return {
    exists,
    setExists,
  };
});
