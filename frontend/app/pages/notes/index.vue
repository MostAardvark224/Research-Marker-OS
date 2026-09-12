<template>
  <!-- Only rendered if the router-level redirect below is ever bypassed. -->
  <main class="flex h-screen items-center justify-center bg-[#050508] text-sm text-slate-500">
    <NuxtLink to="/" class="text-indigo-400">Go to your library</NuxtLink>
  </main>
</template>

<script setup>
// Standalone notes are first-class citizens of the main library now: they live
// in folders next to papers on `/`, are created through the New Note modal,
// and are searchable from the knowledge index. This route stays only so old
// links and bookmarks land somewhere sensible.
definePageMeta({ redirect: "/" });
</script>
