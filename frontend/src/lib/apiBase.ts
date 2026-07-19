export function getApiOrigin() {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured !== undefined) return configured.replace(/\/$/, "");
  return process.env.NODE_ENV === "development" ? "http://localhost:8000" : "";
}

export function apiPath(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiOrigin()}${normalizedPath}`;
}
