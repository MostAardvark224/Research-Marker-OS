import { joinURL } from "ufo";

export default defineEventHandler(async (event) => {
  // get url from runtimeconfig
  const proxyURL = useRuntimeConfig().urlToProxy;
  // check the path
  const target = joinURL(proxyURL, event.path);

  return proxyRequest(event, target);
});
