<template>
  <label
    :title="title"
    :class="[
      'group/app-check inline-flex flex-shrink-0 items-center justify-center rounded-md',
      disabled ? 'cursor-wait opacity-60' : 'cursor-pointer',
    ]"
    @click.stop
    @dblclick.stop
    @dragstart.stop.prevent
  >
    <input
      ref="input"
      type="checkbox"
      :checked="checked"
      :disabled="disabled"
      :aria-label="label"
      class="peer sr-only"
      @change="$emit('change', $event)"
    />
    <span
      aria-hidden="true"
      :class="[
        'inline-flex items-center justify-center rounded-[5px] border border-slate-500/80 bg-slate-800/80 text-transparent shadow-sm transition-all duration-150',
        'group-hover/app-check:border-blue-400 group-hover/app-check:bg-slate-700',
        'peer-checked:border-blue-500 peer-checked:bg-blue-500 peer-checked:text-white peer-checked:shadow-blue-500/25',
        'peer-indeterminate:border-blue-500 peer-indeterminate:bg-blue-500 peer-indeterminate:shadow-blue-500/25',
        'peer-focus-visible:ring-2 peer-focus-visible:ring-blue-400/60 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-slate-900',
        size === 'small' ? 'h-3.5 w-3.5' : 'h-4 w-4',
      ]"
    >
      <svg
        v-if="!indeterminate"
        viewBox="0 0 16 16"
        fill="none"
        class="h-3 w-3"
        stroke="currentColor"
        stroke-width="2.25"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="m3.25 8.25 3 3 6.5-6.5" />
      </svg>
      <svg
        v-else
        viewBox="0 0 16 16"
        fill="none"
        class="h-3 w-3 text-white"
        stroke="currentColor"
        stroke-width="2.25"
        stroke-linecap="round"
      >
        <path d="M4 8h8" />
      </svg>
    </span>
  </label>
</template>

<script setup>
const props = defineProps({
  checked: { type: Boolean, default: false },
  indeterminate: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  label: { type: String, required: true },
  title: { type: String, required: true },
  size: {
    type: String,
    default: "default",
    validator: (value) => ["default", "small"].includes(value),
  },
});

defineEmits(["change"]);

const input = ref(null);

watchEffect(() => {
  if (input.value) input.value.indeterminate = props.indeterminate;
});
</script>
