export default defineNuxtRouteMiddleware((to) => {
  if (
    to.path.includes("C:/") ||
    to.path.includes("Users/") ||
    to.path.includes("app.asar") ||
    to.path.includes(".output/public") ||
    to.path.includes("resources/")
  ) {
    return navigateTo("/");
  }
});
