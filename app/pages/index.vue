<template>
  <div class="text-center pt-10 text-[40px]">Welcome To Research Marker!</div>

  <div class="pt-5 items-center text-center flex flex-col">
    <FileUpload />
  </div>

  <div class="pt-5 items-center text-center flex flex-col">
    <ContinueButton @continue="sendDocuments()" class="flex items-center" />
  </div>
</template>

<script setup>
const {
  public: { apiBaseURL },
} = useRuntimeConfig();

const filesToUpload = ref([]);

const updateFiles = (files) => {
  filesToUpload.value = files;
};

async function sendDocuments() {
  if (filesToUpload.value.length === 0) {
    alert("Please select files first!");
    return;
  }

  const formData = new FormData();

  filesToUpload.value.forEach((file) => {
    formData.append("file", file);
  });

  try {
    const res = await $fetch(`${apiBaseURL}/upload-documents/`, {
      method: "POST",
      body: formData,
    });

    alert("Upload Successful!");
    console.log(res);
  } catch (error) {
    console.error("Error uploading files:", error);
    alert("Upload Failed");
  }
}
</script>
