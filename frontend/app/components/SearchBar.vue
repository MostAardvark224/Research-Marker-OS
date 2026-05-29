<script setup>
const searchQuery = defineModel("searchQuery", {
  type: String,
  default: "",
});
</script>

<template>
  <label class="search-label">
    <input
      v-model="searchQuery"
      type="text"
      name="text"
      class="input"
      placeholder="Search..."
    />
    <kbd class="slash-icon">/</kbd>
    <svg
      class="search-icon"
      xmlns="http://www.w3.org/2000/svg"
      version="1.1"
      xmlns:xlink="http://www.w3.org/1999/xlink"
      width="512"
      height="512"
      x="0"
      y="0"
      viewBox="0 0 56.966 56.966"
      style="enable-background: new 0 0 512 512"
      xml:space="preserve"
    >
      <g>
        <path
          d="M55.146 51.887 41.588 37.786A22.926 22.926 0 0 0 46.984 23c0-12.682-10.318-23-23-23s-23 10.318-23 23 10.318 23 23 23c4.761 0 9.298-1.436 13.177-4.162l13.661 14.208c.571.593 1.339.92 2.162.92.779 0 1.518-.297 2.079-.837a3.004 3.004 0 0 0 .083-4.242zM23.984 6c9.374 0 17 7.626 17 17s-7.626 17-17 17-17-7.626-17-17 7.626-17 17-17z"
          fill="currentColor"
          data-original="#000000"
          class=""
        ></path>
      </g>
    </svg>
  </label>
</template>

<style scoped>
.search-label {
  display: flex;
  align-items: center;
  box-sizing: border-box;
  position: relative;
  /* Slate-800 */
  border: 1px solid #1e293b;
  border-radius: 8px;
  overflow: hidden;
  /* Slate-900/50 */
  background: #0f172a;
  padding: 8px 10px;
  cursor: text;
  transition: all 150ms ease-in-out;
  min-width: 200px;
}

.search-label:focus-within {
  background: #020617;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
}

.search-label input {
  outline: none;
  width: 100%;
  border: none;
  background: none;
  color: #e2e8f0;
  font-size: 0.875rem;
  font-weight: 500;
}

.search-label input::placeholder {
  color: #64748b;
}

.search-label input:focus + .slash-icon,
.search-label input:valid + .slash-icon {
  display: none;
}

.search-label input:valid ~ .search-icon {
  display: block;
}

.search-label input:valid {
  width: calc(100% - 22px);
  transform: translateX(20px);
}

.search-label svg {
  position: absolute;
  /* Slate-400 */
  color: #94a3b8;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
}

.slash-icon {
  position: absolute;
  right: 8px;
  border: 1px solid #1e293b;
  background: linear-gradient(-225deg, #1e293b, #334155);
  border-radius: 4px;
  text-align: center;
  box-shadow: inset 0 -2px 0 0 #0f172a, inset 0 0 1px 1px #1e293b,
    0 1px 2px 1px rgba(0, 0, 0, 0.4);
  cursor: pointer;
  font-size: 0.75rem;
  width: 20px;
  height: 20px;
  line-height: 18px;
  color: #94a3b8;
  font-family: monospace;
}

.slash-icon:active {
  box-shadow: inset 0 1px 0 0 #0f172a, inset 0 0 1px 1px #1e293b,
    0 1px 2px 0 rgba(0, 0, 0, 0.4);
  color: transparent;
}

.search-icon {
  display: none;
  width: 14px;
  height: auto;
}
</style>
