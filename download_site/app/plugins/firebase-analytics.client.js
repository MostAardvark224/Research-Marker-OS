export default defineNuxtPlugin((nuxtApp) => {
  const configuredMeasurementId =
    useRuntimeConfig().public.firebaseMeasurementId?.trim();
  const pendingEvents = [];
  let analyticsReady = false;

  const trackEvent = (name, parameters = {}) => {
    if (!analyticsReady) {
      pendingEvents.push([name, parameters]);
      return;
    }

    window.gtag("event", name, parameters);
  };

  const initializeAnalytics = (measurementId) => {
    if (!/^G-[A-Z0-9]+$/i.test(measurementId)) {
      console.warn(
        "Firebase Analytics is disabled because its measurement ID is invalid.",
      );
      return;
    }

    window.dataLayer = window.dataLayer || [];
    window.gtag =
      window.gtag ||
      function () {
        window.dataLayer.push(arguments);
      };

    const script = document.createElement("script");
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    document.head.appendChild(script);

    window.gtag("js", new Date());
    window.gtag("config", measurementId, { send_page_view: false });
    analyticsReady = true;

    pendingEvents.splice(0).forEach(([name, parameters]) => {
      trackEvent(name, parameters);
    });

    let lastPage;
    const trackPageView = () => {
      const page = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      if (page === lastPage) return;

      lastPage = page;
      window.gtag("event", "page_view", {
        page_location: window.location.href,
        page_path: page,
        page_title: document.title,
      });
    };

    trackPageView();
    nuxtApp.hook("page:finish", trackPageView);
  };

  if (configuredMeasurementId) {
    initializeAnalytics(configuredMeasurementId);
  } else {
    // Firebase Hosting exposes the linked web app's public SDK configuration at
    // this reserved URL, so hosted builds need no committed Firebase credentials.
    fetch("/__/firebase/init.json")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Firebase auto-config was unavailable");
        }
        return response.json();
      })
      .then((firebaseConfig) => {
        if (firebaseConfig.measurementId) {
          initializeAnalytics(firebaseConfig.measurementId.trim());
        }
      })
      .catch(() => {
        // This is expected for local development and non-Firebase preview hosts.
      });
  }

  return {
    provide: {
      analytics: { trackEvent },
    },
  };
});
