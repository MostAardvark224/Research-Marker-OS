<template>
  <div
    class="min-h-screen bg-[#020204] text-white selection:bg-indigo-500/30 font-sans flex flex-col relative overflow-hidden"
  >
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div
        class="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[size:40px_40px] bg-[position:center_bottom] [mask-image:radial-gradient(ellipse_100%_50%_at_50%_10%,#000_70%,transparent_110%)]"
      ></div>
      <div
        class="absolute top-0 left-0 w-[1000px] h-[500px] bg-indigo-600/10 blur-[120px] rounded-full opacity-50"
      ></div>
    </div>

    <nav
      class="flex-none flex items-center justify-between max-w-7xl mx-auto px-6 py-6 z-50 w-full"
    >
      <div class="flex items-center gap-2">
        <div
          class="w-6 h-6 bg-gradient-to-tr from-white to-slate-500 transform rotate-45 rounded-sm"
        ></div>
        <div class="flex flex-col leading-none">
          <span class="font-bold text-lg tracking-tight">Research Marker</span>
          <span
            class="text-[10px] uppercase tracking-wider text-slate-500 font-medium mt-0.5"
          >
            by Amay Babel
          </span>
        </div>
      </div>

      <div
        class="hidden md:flex items-center gap-8 text-sm font-medium text-slate-400"
      >
        <NuxtLink
          to="https://github.com/MostAardvark224/Research-Marker-OS.git"
          class="hover:text-white transition-colors"
          >GitHub</NuxtLink
        >
        <!-- <a
          href="#features"
          class="hover:text-white transition-colors cursor-pointer"
          >Features</a
        >
        <a
          href="#about"
          class="hover:text-white transition-colors cursor-pointer"
          >About</a
        > -->
        <NuxtLink
          to="/dashboard"
          class="bg-white text-black px-5 py-2 rounded font-semibold hover:bg-slate-200 transition-colors"
        >
          Get started
        </NuxtLink>
      </div>
    </nav>

    <main
      class="flex-1 flex items-center justify-center relative z-10 w-full max-w-7xl mx-auto px-6 py-12 lg:py-0"
    >
      <div
        class="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-12 items-center w-full"
      >
        <div class="max-w-2xl mx-auto lg:mx-0 text-center lg:text-left">
          <h1
            class="text-4xl md:text-5xl lg:text-6xl font-semibold tracking-tight leading-[1.1] mb-6"
          >
            Your Intelligent <br class="hidden lg:block" />
            <span
              class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-400 animate-gradient"
            >
              Knowledge Base
            </span>
          </h1>

          <p
            class="text-[16px] text-slate-400 leading-relaxed mb-8 max-w-lg mx-auto lg:mx-0"
          >
            Streamline your research workflow. Keep your papers and annotations
            fully private with a local-only workspace designed for serious
            research and deeper comprehension.
          </p>

          <div class="flex flex-col items-center lg:items-start gap-6 w-full">
            <div class="flex flex-wrap justify-center lg:justify-start gap-4">
              <NuxtLink
                to="/dashboard"
                class="rounded text-black font-semibold flex items-center justify-center transition-colors"
              >
                <GetStartedButton />
              </NuxtLink>

              <!-- <a
                href="#features"
                class="h-12 px-8 rounded border border-white/10 text-slate-300 font-medium hover:bg-white/5 hover:text-white transition-colors flex items-center gap-2 cursor-pointer"
              >
                <Icon name="uil:book-open" />
                <span>Explore Features</span>
              </a> -->
            </div>

            <NuxtLink
              to=""
              target="_blank"
              class="group flex items-center gap-3 text-sm text-slate-400 hover:text-white transition-colors"
            >
              <NuxtLink
                to="https://github.com/MostAardvark224/Research-Marker-OS.git"
                class="flex items-center gap-2 px-3 py-1.5 rounded-full border border-slate-800 bg-slate-900/50 group-hover:border-slate-700 transition-colors"
              >
                <Icon name="uil:github" class="text-lg" />
                <span class="font-medium">Star on GitHub</span>
              </NuxtLink>
              <span
                class="text-xs text-slate-600 group-hover:text-slate-500 transition-colors"
              >
                Open Source
              </span>
            </NuxtLink>
          </div>
        </div>

        <div
          class="flex flex-col gap-4 relative w-full max-w-md mx-auto lg:max-w-none"
        >
          <div
            class="group relative rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] p-5 transition-all duration-300 hover:-translate-y-1"
          >
            <div class="flex items-start gap-4">
              <div
                class="p-3 rounded-lg bg-indigo-500/10 text-indigo-400 group-hover:text-indigo-300 transition-colors shrink-0"
              >
                <Icon
                  name="material-symbols:psychology-alt-outline"
                  class="text-2xl"
                />
              </div>
              <div>
                <h3 class="font-medium text-white text-lg mb-1">
                  Semantic Linking
                </h3>
                <p class="text-sm text-slate-500 leading-relaxed">
                  Connect ideas automatically. My engine finds relationships
                  between your papers as you read.
                </p>
              </div>
            </div>
          </div>

          <div
            class="group relative rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] p-5 transition-all duration-300 hover:-translate-y-1"
          >
            <div class="flex items-start gap-4">
              <div
                class="p-3 rounded-lg bg-purple-500/10 text-purple-400 group-hover:text-purple-300 transition-colors shrink-0"
              >
                <Icon
                  name="material-symbols:verified-user-outline"
                  class="text-2xl"
                />
              </div>
              <div>
                <h3 class="font-medium text-white text-lg mb-1">
                  Local-First Security
                </h3>
                <p class="text-sm text-slate-500 leading-relaxed">
                  Your data lives on your device. Zero cloud dependency ensures
                  absolute privacy.
                </p>
              </div>
            </div>
          </div>

          <div
            class="group relative rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] p-5 transition-all duration-300 hover:-translate-y-1"
          >
            <div class="flex items-start gap-4">
              <div
                class="p-3 rounded-lg bg-pink-500/10 text-pink-400 group-hover:text-pink-300 transition-colors shrink-0"
              >
                <Icon name="material-symbols:format-shapes" class="text-2xl" />
              </div>
              <div>
                <h3 class="font-medium text-white text-lg mb-1">
                  Notetaking Your Way
                </h3>
                <p class="text-sm text-slate-500 leading-relaxed">
                  Fork the repository and adapt the interface to match your
                  specific research methodology.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <footer class="flex-none py-6 text-center z-10">
      <p class="text-slate-600 text-sm">
        © {{ new Date().getFullYear() }} Research Marker. Open Source Software.
      </p>
    </footer>
  </div>
</template>

<style scoped>
@keyframes spin-slow {
  from {
    transform: translate(-50%, -50%) rotate(0deg);
  }
  to {
    transform: translate(-50%, -50%) rotate(360deg);
  }
}

.animate-spin-slow {
  animation: spin-slow 8s linear infinite;
}

@keyframes gradient {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

.animate-gradient {
  background-size: 200% auto;
  animation: gradient 5s ease infinite;
}
</style>

<script setup>
const smoothScroll = (id) => {
  const element = document.getElementById(id);
  if (element) {
    element.scrollIntoView({ behavior: "smooth" });
  }
};
</script>
