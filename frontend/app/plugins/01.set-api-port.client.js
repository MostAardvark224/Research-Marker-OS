// dynamically setting port for backend
export default defineNuxtPlugin(async (nuxtApp) => {
  const config = useRuntimeConfig();

  if (window.electronAPI) {
    console.log("Initializing Electron API connection...");

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
  }
});
