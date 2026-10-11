// Finds the route for a request. A key is "METHOD /path", and a path part in braces ("/customers/{customerNumber}")
// matches any one part and returns it in `params`.
export function match(routes, method, path) {
  const parts = path.split("/");
  for (const [key, route] of Object.entries(routes)) {
    const [m, template] = key.split(" ");
    const want = template.split("/");
    if (m !== method || want.length !== parts.length) continue;
    const params = {};
    if (want.every((w, i) => (w.startsWith("{") ? ((params[w.slice(1, -1)] = decodeURIComponent(parts[i])), true) : w === parts[i])))
      return { route, params };
  }
  return null;
}
