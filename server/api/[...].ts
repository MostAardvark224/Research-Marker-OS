import { joinURL } from "ufo";
const { urlToProxy } = useRuntimeConfig();

export default defineEventHandler(async (event) => {
  // get url from runtimeconfig
  const target = joinURL(urlToProxy, event.path);

  return proxyRequest(event, target);
});
