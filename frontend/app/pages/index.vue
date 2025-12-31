<template>
  <div
    class="min-h-screen bg-[#020204] text-white selection:bg-indigo-500/30 font-sans overflow-x-hidden"
  >
    <nav
      class="flex items-center justify-between max-w-7xl mx-auto px-6 py-6 z-50 relative"
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
        <NuxtLink to="" class="hover:text-white transition-colors"
          >GitHub</NuxtLink
        >
        <a
          href="#features"
          @click.prevent="smoothScroll('features')"
          class="hover:text-white transition-colors"
          >Features</a
        >
        <a
          href="#about"
          @click.prevent="smoothScroll('about')"
          class="hover:text-white transition-colors"
          >About</a
        >
        <NuxtLink
          to="/dashboard"
          class="bg-white text-black px-5 py-2 rounded font-semibold hover:bg-slate-200 transition-colors"
        >
          Get started
        </NuxtLink>
      </div>
    </nav>

    <section
      class="relative pt-10 pb-20 lg:pt-20 lg:pb-32 max-w-7xl mx-auto px-6"
    >
      <div class="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          class="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[size:40px_40px] bg-[position:center_bottom] [mask-image:radial-gradient(ellipse_100%_50%_at_50%_10%,#000_70%,transparent_110%)]"
        ></div>
        <div
          class="absolute top-0 left-0 w-[1000px] h-[500px] bg-indigo-600/10 blur-[120px] rounded-full opacity-50"
        ></div>
      </div>

      <div
        class="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-12 items-center"
      >
        <div class="max-w-2xl">
          <h1
            class="text-4xl md:text-6xl font-semibold tracking-tight leading-[1.1] mb-6"
          >
            Your Intelligent <br />
            <span
              class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-400 animate-gradient"
            >
              Knowledge Base
            </span>
          </h1>

          <p class="text-[16px] text-slate-400 leading-relaxed mb-8 max-w-lg">
            Streamline your research workflow. Keep your papers and annotations
            fully private with a local-only workspace designed for serious
            research and deeper comprehension of complex material.
          </p>

          <div class="flex flex-col items-start gap-6">
            <div class="flex flex-wrap gap-4">
              <NuxtLink
                to="/dashboard"
                class="rounded text-black font-semibold flex items-center justify-center transition-colors"
              >
                <GetStartedButton />
              </NuxtLink>

              <a
                href="#features"
                @click.prevent="smoothScroll('features')"
                class="h-12 px-8 rounded border border-white/10 text-slate-300 font-medium hover:bg-white/5 hover:text-white transition-colors flex items-center gap-2 cursor-pointer"
              >
                <Icon name="uil:book-open" />
                <span>Explore Features</span>
              </a>
            </div>

            <NuxtLink
              to=""
              target="_blank"
              class="group flex items-center gap-3 text-sm text-slate-400 hover:text-white transition-colors"
            >
              <div
                class="flex items-center gap-2 px-3 py-1.5 rounded-full border border-slate-800 bg-slate-900/50 group-hover:border-slate-700 transition-colors"
              >
                <Icon name="uil:github" class="text-lg" />
                <span class="font-medium">Star on GitHub</span>
              </div>
              <span
                class="text-xs text-slate-600 group-hover:text-slate-500 transition-colors"
              >
                Open Source
              </span>
            </NuxtLink>
          </div>
        </div>

        <div class="flex flex-col gap-4 relative">
          <div
            class="group relative rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] p-6 transition-all duration-300 hover:-translate-y-1"
          >
            <div class="flex items-start gap-4">
              <div
                class="p-3 rounded-lg bg-indigo-500/10 text-indigo-400 group-hover:text-indigo-300 transition-colors"
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
                  between your papers as you read, creating a web of knowledge.
                </p>
              </div>
            </div>
          </div>

          <div
            class="group relative rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] p-6 transition-all duration-300 hover:-translate-y-1"
          >
            <div class="flex items-start gap-4">
              <div
                class="p-3 rounded-lg bg-purple-500/10 text-purple-400 group-hover:text-purple-300 transition-colors"
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
                  absolute privacy for sensitive research material.
                </p>
              </div>
            </div>
          </div>

          <div
            class="group relative rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] p-6 transition-all duration-300 hover:-translate-y-1"
          >
            <div class="flex items-start gap-4">
              <div
                class="p-3 rounded-lg bg-pink-500/10 text-pink-400 group-hover:text-pink-300 transition-colors"
              >
                <Icon name="material-symbols:format-shapes" class="text-2xl" />
              </div>
              <div>
                <h3 class="font-medium text-white text-lg mb-1">
                  Notetaking Your Way
                </h3>
                <p class="text-sm text-slate-500 leading-relaxed">
                  Customizable workflows. Fork the repository and adapt the
                  interface to match your specific research methodology.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section id="about" class="py-24 border-t border-white/5 bg-black/20">
      <div class="max-w-4xl mx-auto px-6 text-center">
        <span
          class="text-indigo-400 font-medium text-sm tracking-wider uppercase mb-3 block"
          >About Project</span
        >
        <h2 class="text-3xl md:text-4xl font-semibold mb-6">
          Why Research Marker?
        </h2>
        <div
          class="p-12 rounded-2xl border border-dashed border-slate-800 bg-slate-900/30"
        >
          <p class="text-slate-500 italic">About</p>
        </div>
      </div>
    </section>

    <section id="features" class="py-24 border-t border-white/5">
      <div class="max-w-7xl mx-auto px-6">
        <div class="text-center mb-16">
          <span
            class="text-purple-400 font-medium text-sm tracking-wider uppercase mb-3 block"
            >Capabilities</span
          >
          <h2 class="text-3xl md:text-4xl font-semibold">
            Deep Dive into Features
          </h2>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <div
            class="h-64 rounded-xl border border-dashed border-slate-800 bg-slate-900/20 flex items-center justify-center"
          >
            <span class="text-slate-600">Feature 1</span>
          </div>
          <div
            class="h-64 rounded-xl border border-dashed border-slate-800 bg-slate-900/20 flex items-center justify-center"
          >
            <span class="text-slate-600">Feature 2</span>
          </div>
          <div
            class="h-64 rounded-xl border border-dashed border-slate-800 bg-slate-900/20 flex items-center justify-center"
          >
            <span class="text-slate-600">Feature 3</span>
          </div>
        </div>
      </div>
    </section>

    <footer class="py-8 border-t border-white/5 text-center">
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
