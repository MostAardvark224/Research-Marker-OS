<script setup>
const props = defineProps({
  downloadLink: {
    type: String,
    required: true,
  },
  os: {
    type: String,
    required: true,
    validator: (value) => ["windows", "mac", "linux"].includes(value),
  },
});

const osConfig = computed(() => {
  const config = {
    windows: {
      label: "Windows",
      icon: "mdi:microsoft-windows",
      hoverClass:
        "group-hover:text-[#00a2ed] group-hover:border-[#00a2ed]/30 group-hover:bg-[#00a2ed]/10",
      glow: "group-hover:shadow-[0_0_20px_-5px_rgba(0,162,237,0.3)]",
    },
    mac: {
      label: "macOS",
      icon: "mdi:apple",
      hoverClass:
        "group-hover:text-white group-hover:border-white/30 group-hover:bg-white/10",
      glow: "group-hover:shadow-[0_0_20px_-5px_rgba(255,255,255,0.2)]",
    },
    linux: {
      label: "Linux",
      icon: "mdi:linux",
      hoverClass:
        "group-hover:text-[#E34F26] group-hover:border-[#E34F26]/30 group-hover:bg-[#E34F26]/10",
      glow: "group-hover:shadow-[0_0_20px_-5px_rgba(227,79,38,0.3)]",
    },
  };
  return config[props.os];
});
</script>

<template>
  <a
    :href="downloadLink"
    target="_blank"
    class="group relative flex items-center gap-3 px-5 py-3 rounded-xl border border-white/10 bg-white/[0.03] backdrop-blur-sm transition-all duration-300 ease-out hover:-translate-y-1"
    :class="[osConfig.hoverClass, osConfig.glow]"
  >
    <div
      class="flex items-center justify-center transition-colors duration-300 text-slate-400 group-hover:text-current"
    >
      <Icon :name="osConfig.icon" size="24" />
    </div>

    <div class="flex flex-col">
      <span
        class="text-xs font-medium text-slate-500 uppercase tracking-wider group-hover:text-current/70 transition-colors"
      >
        Download for
      </span>
      <span
        class="text-sm font-semibold text-slate-200 group-hover:text-current transition-colors"
      >
        {{ osConfig.label }}
      </span>
    </div>

    <Icon
      name="heroicons:arrow-down-tray"
      class="ml-2 w-4 h-4 text-slate-600 group-hover:text-current opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300"
    />
  </a>
</template>
