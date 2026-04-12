/**
 * Backend origin for REST and WebSocket.
 * - Production build: set REACT_APP_BACKEND_URL (e.g. in .env.production or CI).
 * - Development: defaults to http://localhost:8000 when unset.
 */
function resolveBackendUrl() {
  const raw = process.env.REACT_APP_BACKEND_URL;
  if (raw != null && String(raw).trim() !== "") {
    return String(raw).replace(/\/$/, "");
  }
  if (process.env.NODE_ENV === "development") {
    return "http://localhost:8000";
  }
  console.error(
    "[api] REACT_APP_BACKEND_URL is not set. Configure it before building for production."
  );
  return "";
}

export const BACKEND_URL = resolveBackendUrl();
export const API_BASE = BACKEND_URL ? `${BACKEND_URL}/api` : "";

/** True when a backend origin is resolved (production must set REACT_APP_BACKEND_URL). */
export function isApiConfigured() {
  return Boolean(BACKEND_URL);
}
