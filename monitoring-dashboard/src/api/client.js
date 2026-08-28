import { API_BASE_URL } from "./config";

/** Thrown for any non-2xx response or network failure, so callers can
 * distinguish "backend unreachable" from "no data yet" (empty arrays are a
 * normal, valid response - see components' empty states). */
export class MonitoringApiError extends Error {
  constructor(message, cause) {
    super(message);
    this.name = "MonitoringApiError";
    this.cause = cause;
  }
}

async function get(path, params = {}) {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) url.searchParams.set(key, value);
  });

  let response;
  try {
    response = await fetch(url.toString(), { headers: { Accept: "application/json" } });
  } catch (err) {
    throw new MonitoringApiError(`Could not reach monitoring API at ${API_BASE_URL}`, err);
  }
  if (!response.ok) {
    throw new MonitoringApiError(`Monitoring API returned ${response.status} for ${path}`);
  }
  return response.json();
}

// One function per backend endpoint (see merchant-agent-core/monitoring/routes.py).
// Never reshapes the response beyond JSON parsing - components read the
// backend's own field names directly, so the backend stays the single
// source of truth for monitoring business logic.
export const monitoringApi = {
  getHealth: () => get("/monitoring/health"),
  getMetrics: () => get("/monitoring/metrics"),
  getTransactions: (limit = 100) => get("/monitoring/transactions", { limit }),
  getFailures: (limit = 50) => get("/monitoring/failures", { limit }),
  getAuditEvents: (limit = 100) => get("/monitoring/audit-events", { limit }),
  getAlerts: () => get("/monitoring/alerts"),
};
