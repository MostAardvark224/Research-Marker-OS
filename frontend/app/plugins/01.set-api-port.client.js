// dynamically setting port for backend
import { useAppReady } from "~/composables/useAppReady";

export default defineNuxtPlugin(async (nuxtApp) => {
  const config = useRuntimeConfig();
  const { setSplashProgress } = useAppReady();

  console.log("Attempting to get API port from Electron");

  if (window.electronAPI) {
    console.log("Initializing Electron API connection...");
    setSplashProgress(82, "Connecting to backend…");

    const waitForPort = async () => {
      let port = await window.electronAPI.getApiPort();

      while (!port) {
        console.log("Waiting for Python backend...");
        await new Promise((resolve) => setTimeout(resolve, 500));
        port = await window.electronAPI.getApiPort();
      }
      return port;
    };

    const port = await waitForPort();

    config.public.apiBaseURL = `http://127.0.0.1:${port}/api`;

    console.log(`Config updated: API is at ${config.public.apiBaseURL}`);
    setSplashProgress(86, "Backend connected…");
  } else {
    console.log("Not an electron window");
  }
});
