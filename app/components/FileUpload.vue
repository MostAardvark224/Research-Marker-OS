<script setup>
import { ref, computed } from "vue";

const emit = defineEmits(["files-selected"]);

const fileInput = ref(null);
const selectedFiles = ref([]);

// Trigger the hidden input
const triggerFileDialog = () => {
  // We use optional chaining because fileInput might not be bound immediately
  fileInput.value?.click();
};

const handleFileChange = (event) => {
  const target = event.target;
  if (target.files && target.files.length > 0) {
    const filesArray = Array.from(target.files);
    const validPdfs = filesArray.filter(
      (file) => file.type === "application/pdf"
    );

    if (validPdfs.length < filesArray.length) {
      alert("Only PDF files are allowed.");
    }

    if (validPdfs.length > 0) {
      selectedFiles.value = validPdfs;
      emit("files-selected", validPdfs);
    }
  }
};

const clearFile = (event) => {
  if (event) event.stopPropagation();

  selectedFiles.value = [];
  if (fileInput.value) fileInput.value.value = "";
  emit("files-selected", []);
};

const displayText = computed(() => {
  const count = selectedFiles.value.length;
  if (count === 0) return "No files selected";
  if (count === 1) return selectedFiles.value[0].name;
  return `${count} files selected`;
});
</script>

<template>
  <div class="container">
    <!-- HEADER -->
    <div class="header" @click="triggerFileDialog">
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <g id="SVGRepo_bgCarrier" stroke-width="0"></g>
        <g
          id="SVGRepo_tracerCarrier"
          stroke-linecap="round"
          stroke-linejoin="round"
        ></g>
        <g id="SVGRepo_iconCarrier">
          <path
            d="M7 10V9C7 6.23858 9.23858 4 12 4C14.7614 4 17 6.23858 17 9V10C19.2091 10 21 11.7909 21 14C21 15.4806 20.1956 16.8084 19 17.5M7 10C4.79086 10 3 11.7909 3 14C3 15.4806 3.8044 16.8084 5 17.5M7 10C7.43285 10 7.84965 10.0688 8.24006 10.1959M12 12V21M12 12L15 15M12 12L9 15"
            stroke="#000000"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          ></path>
        </g>
      </svg>
      <p>Browse PDF(s) to upload!</p>
    </div>

    <!-- FOOTER -->
    <div class="footer" @click="triggerFileDialog">
      <svg
        fill="#000000"
        viewBox="0 0 32 32"
        xmlns="http://www.w3.org/2000/svg"
      >
        <g id="SVGRepo_bgCarrier" stroke-width="0"></g>
        <g
          id="SVGRepo_tracerCarrier"
          stroke-linecap="round"
          stroke-linejoin="round"
        ></g>
        <g id="SVGRepo_iconCarrier">
          <path d="M15.331 6H8.5v20h15V14.154h-8.169z"></path>
          <path d="M18.153 6h-.009v5.342H23.5v-.002z"></path>
        </g>
      </svg>

      <p>{{ displayText }}</p>

      <svg
        @click="clearFile"
        class="delete-icon"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <g id="SVGRepo_bgCarrier" stroke-width="0"></g>
        <g
          id="SVGRepo_tracerCarrier"
          stroke-linecap="round"
          stroke-linejoin="round"
        ></g>
        <g id="SVGRepo_iconCarrier">
          <path
            d="M5.16565 10.1534C5.07629 8.99181 5.99473 8 7.15975 8H16.8402C18.0053 8 18.9237 8.9918 18.8344 10.1534L18.142 19.1534C18.0619 20.1954 17.193 21 16.1479 21H7.85206C6.80699 21 5.93811 20.1954 5.85795 19.1534L5.16565 10.1534Z"
            stroke="#000000"
            stroke-width="2"
          ></path>
          <path
            d="M19.5 5H4.5"
            stroke="#000000"
            stroke-width="2"
            stroke-linecap="round"
          ></path>
          <path
            d="M10 3C10 2.44772 10.4477 2 11 2H13C13.5523 2 14 2.44772 14 3V5H10V3Z"
            stroke="#000000"
            stroke-width="2"
          ></path>
        </g>
      </svg>
    </div>

    <!-- CRITICAL FIX: ClientOnly wrapper prevents hydration errors -->
    <ClientOnly>
      <input
        id="file"
        type="file"
        accept="application/pdf"
        multiple
        ref="fileInput"
        @change="handleFileChange"
        style="display: none"
      />
    </ClientOnly>
  </div>
</template>

<style scoped>
/* Your existing CSS (unchanged) */
.container {
  height: 300px;
  width: 300px;
  border-radius: 10px;
  box-shadow: 4px 4px 30px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 10px;
  gap: 5px;
  background-color: rgba(0, 110, 255, 0.041);
}

.header {
  flex: 1;
  width: 100%;
  border: 2px dashed royalblue;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  cursor: pointer;
  transition: background-color 0.2s;
}

.header:hover {
  background-color: rgba(65, 105, 225, 0.1);
}

.header svg {
  height: 100px;
}

.header p {
  text-align: center;
  color: black;
}

.footer {
  background-color: rgba(0, 110, 255, 0.075);
  width: 100%;
  height: 40px;
  padding: 8px;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  color: black;
  border: none;
}

.footer svg {
  height: 130%;
  fill: royalblue;
  background-color: rgba(70, 66, 66, 0.103);
  border-radius: 50%;
  padding: 2px;
  box-shadow: 0 2px 30px rgba(0, 0, 0, 0.205);
}

.delete-icon {
  cursor: pointer;
}

.delete-icon:hover {
  background-color: rgba(255, 0, 0, 0.1);
  fill: red;
}

.footer p {
  flex: 1;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 0 5px;
}
</style>
