/**
 * Coordinates Electron splash teardown with real UI readiness.
 * Pages call signalAppReady() after their first critical data load.
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
