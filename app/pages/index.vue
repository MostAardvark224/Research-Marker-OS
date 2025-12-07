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
        <span class="font-bold text-lg tracking-tight">Research Marker</span>
      </div>
      <div
        class="hidden md:flex items-center gap-8 text-sm font-medium text-slate-400"
      >
        <a href="#" class="hover:text-white transition-colors">GitHub</a>
        <a href="#" class="hover:text-white transition-colors">Features</a>
        <NuxtLink
          to="/dashboard"
          class="bg-white text-black px-5 py-2 rounded font-semibold hover:bg-slate-200 transition-colors"
        >
          Get started
        </NuxtLink>
      </div>
    </nav>

    <section class="relative pb-32 max-w-7xl mx-auto px-6">
      <div class="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          class="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[size:40px_40px] bg-[position:center_bottom] [mask-image:radial-gradient(ellipse_100%_50%_at_50%_10%,#000_70%,transparent_110%)]"
        ></div>

        <div
          class="absolute top-0 left-0 w-[1000px] h-[500px] bg-indigo-600/10 blur-[120px] rounded-full opacity-50"
        ></div>
      </div>

      <div
        class="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-4 items-center"
      >
        <div class="max-w-2xl">
          <h1
            class="text-4xl md:text-6xl font-semibold tracking-tight leading-[1.1] mb-4"
          >
            Your Intelligent <br />
            <span
              class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-400 animate-gradient"
            >
              Knowledge Base
            </span>
          </h1>

          <p class="text-[16px] text-slate-400 leading-relaxed mb-6 max-w-lg">
            Streamline your research workflow. Keep your papers and annotations
            fully private with a local-only workspace designed for serious
            research and deeper comprehension of complex material.
          </p>

          <div class="flex flex-wrap gap-4">
            <NuxtLink
              to="/dashboard"
              class="h-12 px-8 rounded bg-white text-black font-semibold flex items-center justify-center hover:bg-slate-200 transition-colors"
            >
              Get started
            </NuxtLink>
            <button
              class="h-12 px-8 rounded border border-white/10 text-slate-300 font-medium hover:bg-white/5 hover:text-white transition-colors flex items-center gap-2"
            >
              <Icon name="uil:book-open" />
              <span>Explore Features</span>
            </button>
          </div>
        </div>

        <div
          class="relative h-[500px] w-full flex flex-col gap-6 justify-center"
        >
          <div class="grid grid-cols-2 gap-6 h-1/2">
            <div
              class="relative rounded-xl border border-white/10 bg-white/[0.02] p-6 overflow-hidden group flex items-center justify-center"
            >
              <span class="text-slate-600 text-sm">placeholder</span>
            </div>

            <div
              class="relative rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden flex items-center justify-center"
            >
              <span class="text-slate-600 text-sm">placeholder</span>
            </div>
          </div>

          <div
            class="h-1/2 w-full relative rounded-xl border border-white/10 bg-white/[0.02] p-8 flex items-center justify-center overflow-hidden"
          >
            <span class="text-slate-600 text-sm">placeholder</span>
          </div>
        </div>
      </div>

      <div class="mt-32 grid grid-cols-1 md:grid-cols-3 gap-8 pt-8">
        <div class="group cursor-default">
          <div class="flex items-center gap-3 mb-3 text-indigo-400">
            <Icon
              name="material-symbols:psychology-alt-outline"
              class="text-xl"
            />
            <h3 class="font-medium text-white">Semantic Linking</h3>
          </div>
          <p
            class="text-sm text-slate-500 leading-relaxed group-hover:text-slate-400 transition-colors"
          >
            Connect ideas automatically. Our engine finds relationships between
            your papers as you read.
          </p>
        </div>

        <div class="group cursor-default">
          <div class="flex items-center gap-3 mb-3 text-purple-400">
            <Icon
              name="material-symbols:verified-user-outline"
              class="text-xl"
            />
            <h3 class="font-medium text-white">Local-First Security</h3>
          </div>
          <p
            class="text-sm text-slate-500 leading-relaxed group-hover:text-slate-400 transition-colors"
          >
            Your data is stored only on your device. Zero cloud dependency,
            giving you full privacy.
          </p>
        </div>

        <div class="group cursor-default">
          <div class="flex items-center gap-3 mb-3 text-pink-400">
            <Icon name="material-symbols:format-shapes" class="text-xl" />
            <h3 class="font-medium text-white">Notetaking Your Way</h3>
          </div>
          <p
            class="text-sm text-slate-500 leading-relaxed group-hover:text-slate-400 transition-colors"
          >
            Fork my repository and customize the app to fit your unique
            workflow.
          </p>
        </div>
      </div>
    </section>
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

<script setup></script>
