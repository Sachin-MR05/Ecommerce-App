import { useEffect, useRef, useState, useCallback } from "react";
import { WS_URL } from "../api/config";

const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_DELAY_MS = 15000;

/**
 * Connects to /monitoring/ws and calls `onEvent({event, data})` for every
 * message. Reconnects automatically (with backoff) on drop - the dashboard
 * must never depend on a browser refresh (see project brief, section 9).
 * Returns the live connection status for the top bar's LIVE/DISCONNECTED
 * indicator.
 */
export function useMonitoringSocket(onEvent) {
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const attemptRef = useRef(0);
  const closedByUsRef = useRef(false);

  useEffect(() => {
    let socket;
    let reconnectTimer;

    const connect = () => {
      socket = new WebSocket(WS_URL);

      socket.onopen = () => {
        attemptRef.current = 0;
        setConnected(true);
      };

      socket.onmessage = (message) => {
        try {
          const parsed = JSON.parse(message.data);
          if (parsed?.event === "ping") return; // keepalive only
          onEventRef.current?.(parsed);
        } catch {
          // Ignore a malformed frame rather than crashing the live view.
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (closedByUsRef.current) return;
        const delay = Math.min(RECONNECT_DELAY_MS * 2 ** attemptRef.current, MAX_RECONNECT_DELAY_MS);
        attemptRef.current += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connect();

    return () => {
      closedByUsRef.current = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return { connected };
}
