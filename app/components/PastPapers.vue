<template>
  <div></div>
</template>

<script setup>
const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const paperList = ref([]);

async function fetchPastPapers() {
  try {
    const res = await $fetch(`${apiBaseURL}/documents/`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
  } catch (error) {
    console.error("Error fetching past papers:", error);
  }
}

onMounted(() => {
  fetchPastPapers();
});

function refreshPastPapers() {
  fetchPastPapers();
}
</script>
