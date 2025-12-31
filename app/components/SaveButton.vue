<style scoped>
.button {
  background: var(--color-back);
  border-radius: 0.5em;
  box-shadow: inset 0px -6px 18px -6px rgba(3, 15, 20, 0),
    inset rgba(54, 69, 75, 1) -1px -1px 6px 0px,
    inset 12px 0px 12px -6px rgba(3, 15, 20, 0),
    inset -12px 0px 12px -6px rgba(3, 15, 20, 0),
    rgba(54, 69, 75, 1) -1px -1px 6px 0px;
  border: solid 2px #030f14;
  cursor: pointer;
  font-size: 18px;
  padding: 0.7em 1.7em;
  outline: none;
  transition: all 0.3s;
  user-select: none;
}

.button:hover {
  box-shadow: inset 0px -6px 18px -6px rgba(3, 15, 20, 1),
    inset 0px 6px 18px -6px rgba(3, 15, 20, 1),
    inset 12px 0px 12px -6px rgba(3, 15, 20, 0),
    inset -12px 0px 12px -6px rgba(3, 15, 20, 0),
    -1px -1px 6px 0px rgba(54, 69, 75, 1);
}

.button:active {
  box-shadow: inset 0px -12px 12px -6px rgba(3, 15, 20, 1),
    inset 0px 12px 12px -6px rgba(3, 15, 20, 1),
    inset 12px 0px 12px -6px rgba(3, 15, 20, 1),
    inset -12px 0px 12px -6px rgba(3, 15, 20, 1),
    -1px -1px 6px 0px rgba(54, 69, 75, 1);
}

.text {
  color: #d0a756;
  font-weight: 700;
  margin: auto;
  transition: all 0.3s;
  width: fit-content;
}

.button:hover .text {
  transform: scale(0.9);
}

.button:active .text {
  transform: scale(0.8);
}
</style>

<template>
  <button class="button">
    <div @click="emits('save')" class="text">Save</div>
  </button>
</template>

<script setup>
const emits = defineEmits(["save"]);
</script>
