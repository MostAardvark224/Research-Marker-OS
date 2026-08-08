/**
 * Coordinates Electron splash teardown with first UI paint.
 * Do not wait on library/API data here — that made boot feel much slower.
 */
let hasSignaled = false;

export function useAppReady() {
  function setSplashProgress(percent, message) {
    if (!import.meta.client || !window.electronAPI?.setSplashProgress) {
      return;
    }
    window.electronAPI.setSplashProgress(percent, message);
  }

  function signalAppReady(message = "Ready") {
    if (!import.meta.client || hasSignaled) {
      return;
    }
    hasSignaled = true;
    setSplashProgress(100, message);
    window.electronAPI?.notifyAppReady?.();
  }

  return {
    setSplashProgress,
    signalAppReady,
  };
}
