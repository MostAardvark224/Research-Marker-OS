// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  modules: ["@nuxtjs/tailwindcss", "@nuxt/icon"],
  ssr: false,
  runtimeConfig: {
    public: {
      firebaseMeasurementId: "",
    },
  },
  icon: {
    provider: "none",
    fallbackToApi: false,
    serverBundle: false,
    clientBundle: {
      scan: true,
      sizeLimitKb: 256,
    },
  },
  app: {
    head: {
      link: [{ rel: "icon", type: "image/svg+xml", href: "/logo.svg" }],
    },
  },
});
