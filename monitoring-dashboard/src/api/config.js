// Single source of truth for the monitoring API location. Every other
// file imports from here instead of reading import.meta.env directly, so
// the backend URL is never hardcoded/duplicated elsewhere in this app.
const RAW_BASE_URL = import.meta.env.VITE_MONITORING_API_URL || "http://localhost:8000";

// Strip a trailing slash so callers can always do `${API_BASE_URL}/path`.
export const API_BASE_URL = RAW_BASE_URL.replace(/\/+$/, "");

export const WS_URL = `${API_BASE_URL.replace(/^http/, "ws")}/monitoring/ws`;
