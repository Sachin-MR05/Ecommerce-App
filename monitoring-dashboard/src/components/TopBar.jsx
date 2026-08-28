import { formatClock } from "../utils/format";

const STATUS_CLASS = {
  UP: "status-up",
  DEGRADED: "status-degraded",
  DOWN: "status-down",
  UNKNOWN: "status-unknown",
};

export default function TopBar({ overallStatus, connected, lastUpdate }) {
  const statusClass = STATUS_CLASS[overallStatus] || "status-unknown";

  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className={`system-pill ${statusClass}`}>
          <span className="status-dot" />
          {overallStatus || "Unknown"}
        </span>
      </div>
      <div className="topbar-right">
        <span className="last-update">Updated {formatClock(lastUpdate)}</span>
        <span className={`live-indicator ${connected ? "live" : "disconnected"}`}>
          <span className="live-dot" />
          {connected ? "LIVE" : "DISCONNECTED"}
        </span>
      </div>
    </header>
  );
}
