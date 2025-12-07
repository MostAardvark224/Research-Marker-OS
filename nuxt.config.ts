import tailwindcss from "@tailwindcss/vite";

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  modules: ["@nuxt/hints", "@nuxt/image", "@nuxt/ui", "@nuxt/icon"],
  ssr: true,

  runtimeConfig: {
    urlToProxy: process.env.URL_TO_PROXY,
    public: {
      apiBaseURL: "/api",
      frontendOrigin: process.env.FRONTEND_ORIGIN,
    },
  },

  css: ["~/assets/main.css"],

  app: {
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