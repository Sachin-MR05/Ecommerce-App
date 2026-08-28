import { useCallback, useEffect, useRef, useState } from "react";
import { monitoringApi, MonitoringApiError } from "../api/client";
import { useMonitoringSocket } from "./useMonitoringSocket";

const FALLBACK_POLL_MS = 20000; // safety net in case a WS event is missed - not the primary update path

/**
 * Loads every monitoring resource once on mount (REST), then keeps them
 * fresh by reacting to /monitoring/ws events - never by requiring a page
 * refresh. Each WS event only triggers a refetch of the specific
 * resource(s) it affects, debounced per-resource so a burst of events
 * (e.g. several transactions completing at once) collapses into one
 * network call instead of one per event.
 */
export function useMonitoringData() {
  const [state, setState] = useState({
    health: null,
    metrics: null,
    transactions: [],
    failures: null,
    auditEvents: [],
    alerts: [],
    error: null,
    lastUpdate: null,
  });

  const debounceTimers = useRef({});

  const load = useCallback(async (keys) => {
    const tasks = {
      health: () => monitoringApi.getHealth(),
      metrics: () => monitoringApi.getMetrics(),
      transactions: () => monitoringApi.getTransactions(100),
      failures: () => monitoringApi.getFailures(50),
      auditEvents: () => monitoringApi.getAuditEvents(100),
      alerts: () => monitoringApi.getAlerts(),
    };
    const targets = keys || Object.keys(tasks);

    const results = await Promise.allSettled(targets.map((key) => tasks[key]()));

    setState((prev) => {
      const next = { ...prev, lastUpdate: new Date().toISOString() };
      let hadError = false;
      results.forEach((result, index) => {
        const key = targets[index];
        if (result.status === "fulfilled") {
          const value = result.value;
          if (key === "transactions") next.transactions = value.transactions;
          else if (key === "auditEvents") next.auditEvents = value.events;
          else if (key === "alerts") next.alerts = value.alerts;
          else next[key] = value;
        } else {
          hadError = true;
        }
      });
      next.error = hadError
        ? (results.find((r) => r.status === "rejected")?.reason instanceof MonitoringApiError
            ? results.find((r) => r.status === "rejected").reason.message
            : "Could not reach the monitoring API.")
        : null;
      return next;
    });
  }, []);

  const scheduleRefetch = useCallback(
    (keys) => {
      keys.forEach((key) => {
        clearTimeout(debounceTimers.current[key]);
        debounceTimers.current[key] = setTimeout(() => load([key]), 250);
      });
    },
    [load]
  );

  useEffect(() => {
    load();
    const interval = setInterval(() => load(), FALLBACK_POLL_MS);
    return () => clearInterval(interval);
  }, [load]);

  const handleSocketEvent = useCallback(
    ({ event }) => {
      switch (event) {
        case "transaction.updated":
          scheduleRefetch(["transactions", "metrics"]);
          break;
        case "failure.created":
          scheduleRefetch(["failures", "auditEvents"]);
          break;
        case "audit.event":
          scheduleRefetch(["auditEvents"]);
          break;
        case "service.health_changed":
          scheduleRefetch(["health"]);
          break;
        case "alert.created":
        case "alert.resolved":
          scheduleRefetch(["alerts"]);
          break;
        case "metrics.updated":
          scheduleRefetch(["metrics"]);
          break;
        default:
          break;
      }
    },
    [scheduleRefetch]
  );

  const { connected } = useMonitoringSocket(handleSocketEvent);

  return { ...state, connected };
}
