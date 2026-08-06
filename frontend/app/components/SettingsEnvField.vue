<template>
  <div class="p-4 rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
    <div class="space-y-3">
      <div>
        <label class="block text-sm font-medium text-white mb-1 tracking-wide">
          {{ label }}
        </label>
        <p
          v-if="fieldKey !== label"
          class="font-mono text-[10px] text-slate-600 mb-1"
        >
          {{ fieldKey }}
        </p>
        <p
          v-if="description"
          class="text-xs text-slate-500 leading-relaxed"
        >
          {{ description }}
        </p>
      </div>

      <div class="relative">
        <input
          v-model="localValue"
          :type="type"
          :placeholder="placeholder"
          class="w-full bg-[#0A0A0C] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-700 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 focus:bg-white/[0.03] outline-none transition-colors font-mono"
          spellcheck="false"
        />

        <div
          class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
        >
          <div
            v-if="localValue"
            class="w-1.5 h-1.5 rounded-full bg-emerald-500"
          ></div>
          <div
            v-else
            class="w-1.5 h-1.5 rounded-full bg-slate-700"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  fieldKey: { type: String, required: true },
  label: { type: String, required: true },
  description: { type: String, default: "" },
  placeholder: { type: String, default: "" },
  type: { type: String, default: "text" },
  modelValue: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

const localValue = ref(props.modelValue ?? "");

watch(
  () => props.modelValue,
  (value) => {
    if (value !== localValue.value) {
      localValue.value = value ?? "";
    }
  },
);

watch(localValue, (value) => {
  if (value !== props.modelValue) {
    emit("update:modelValue", value);
  }
});
</script>
