import tailwindcss from "@tailwindcss/vite";
const isDev = process.env.NODE_ENV === "development";

// https://nuxt.com/docs/api/configuration/nuxt-config
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
      frontendOrigin: process.env.FRONTEND_ORIGIN,
    },
  },

  css: ["~/assets/main.css"],

  router: {
    options: {
      hashMode: true,
    },
  },

  app: {
    baseURL: "./",
    head: {
      title:
        "Research Marker | Research Paper Annotator | Understand Scientific Papers!",

      htmlAttrs: {
        lang: "en",
      },
    },
  },

  vite: {
    plugins: [tailwindcss()],
  },
});
