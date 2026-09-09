<script setup>
const props = defineProps({
  modelValue: { type: String, default: "" },
  options: { type: Array, default: () => [] },
  defaultEffort: { type: String, default: "" },
  disabled: Boolean,
});
const emit = defineEmits(["update:modelValue"]);
const label = (effort) => ({
  none: "None", minimal: "Minimal", low: "Low", medium: "Medium",
  high: "High", xhigh: "Extra high", max: "Max", ultra: "Ultra",
}[effort] || effort);
const description = computed(() =>
  props.options.find((option) => option.effort === (props.modelValue || props.defaultEffort))?.description
  || "Higher effort gives Codex more time to reason and may take longer.",
);
</script>

<template>
  <label class="flex flex-wrap items-center gap-2 text-xs text-slate-400" :title="description">
    <span>Reasoning</span>
    <select
      :value="modelValue"
      :disabled="disabled || !options.length"
      aria-label="Codex reasoning effort"
      class="min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-indigo-400 disabled:opacity-50"
      @change="emit('update:modelValue', $event.target.value)"
    >
      <option value="">{{ defaultEffort ? `Default (${label(defaultEffort)})` : "Model default" }}</option>
      <option v-for="option in options" :key="option.effort" :value="option.effort">
        {{ label(option.effort) }}
      </option>
    </select>
    <span class="w-full text-[10px] leading-relaxed text-slate-500">{{ description }}</span>
  </label>
</template>
