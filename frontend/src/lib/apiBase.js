/**
 * Backend origin for REST and WebSocket. Prefer REACT_APP_BACKEND_URL in .env.
 * In development, defaults to http://localhost:8000 when unset (avoids "undefined/api").
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
