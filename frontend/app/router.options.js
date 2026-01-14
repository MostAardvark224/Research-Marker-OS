import { createWebHashHistory, createWebHistory } from "vue-router";

export default {
  history: (base) => {
    return process.env.NODE_ENV === "development"
      ? createWebHistory(base)
      : createWebHashHistory(base);
  },
};
