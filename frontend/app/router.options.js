import { createWebHashHistory, createWebHistory } from "vue-router";

export default {
  history: (base) => {
    console.log("CreateHistory called. ENV:", process.env.NODE_ENV);

    return process.env.NODE_ENV === "development"
      ? createWebHistory(base)
      : createWebHashHistory();
  },
};
