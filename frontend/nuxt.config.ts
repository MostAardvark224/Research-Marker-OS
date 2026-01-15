import tailwindcss from "@tailwindcss/vite";
const isDev = process.env.NODE_ENV === "development";
import fs from "node:fs";
import path from "node:path";

export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  modules: [
    "@nuxt/hints",
    "@nuxt/image",
    "@nuxt/ui",
    "@nuxt/icon",
    "@pinia/nuxt",
  ],
  ssr: false,

  runtimeConfig: {
    urlToProxy: process.env.URL_TO_PROXY,
    public: {
      apiBaseURL: isDev ? "/api" : "http://127.0.0.1:8000",
      frontendOrigin: process.env.FRONTEND_ORIGIN
        ? process.env.FRONTEND_ORIGIN
        : "http://localhost:3000",
    },
  },

  css: ["~/assets/main.css"],

  vite: {
    build: {
      assetsDir: "assets",
    },
    plugins: [tailwindcss()],
  },

  router: {
    options: {
      hashMode: true,
    },
  },

  app: {
    baseURL: "./",
    buildAssetsDir: "_nuxt",
    head: {
      title:
        "Research Marker | Research Paper Annotator | Understand Scientific Papers!",

      htmlAttrs: {
        lang: "en",
      },
    },
  },

  $development: {
    devtools: { enabled: true },
  },

  $production: {
    devtools: { enabled: false },
  },

  experimental: {
    appManifest: false,
    payloadExtraction: false,
  },

  // have to implement this hook to fix relative paths for electron
  // Nuxt doesn't allow relative paths, but electron needs them, so i have to change them after generation
  // There's a github issue open since mid 2024 but its still unanswered.
  hooks: {
    close: async () => {
      const indexHtmlPath = path.resolve(
        process.cwd(),
        ".output/public/index.html"
      );

      if (fs.existsSync(indexHtmlPath)) {
        console.log("Electron Fix: Patching index.html paths...");
        let content = fs.readFileSync(indexHtmlPath, "utf-8");

        // fixing for css and js files
        content = content.replace(/href="\/_nuxt\//g, 'href="./_nuxt/');
        content = content.replace(/src="\/_nuxt\//g, 'src="./_nuxt/');

        content = content.replace(/href="\//g, 'href="./');
        content = content.replace(/src="\//g, 'src="./');

        fs.writeFileSync(indexHtmlPath, content);
        console.log("Electron Fix: Paths converted to relative ./");
      } else {
        console.log("Electron Fix: Could not find index.html to patch.");
      }
    },
  },
});
