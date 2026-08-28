import { formatClock } from "../utils/format";

export default function AlertsSection({ alerts }) {
  if (!alerts) {
    return <div className="panel empty-state">Loading alerts…</div>;
  }

  const active = alerts.filter((a) => a.status === "ACTIVE");
  const resolved = alerts.filter((a) => a.status === "RESOLVED");

  return (
    <>
      <div className="panel" style={{ marginBottom: 14 }}>
        {active.length === 0 ? (
          <div className="empty-state">No active alerts. Everything looks healthy.</div>
        ) : (
          active.map((alert) => <AlertRow key={alert.alert_id} alert={alert} />)
        )}
      </div>
      {resolved.length > 0 && (
        <div>
          <div className="section-sub" style={{ marginBottom: 8 }}>
            Recently resolved
          </div>
          <div className="panel">
            {resolved.slice(0, 10).map((alert) => (
              <AlertRow key={alert.alert_id} alert={alert} muted />
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function AlertRow({ alert, muted }) {
  return (
    <div className="alert-row" style={{ opacity: muted ? 0.55 : 1 }}>
      <span className={`alert-icon ${alert.severity}`} />
      <div>
        <div className="alert-title">{alert.title}</div>
        <div className="alert-desc">{alert.description}</div>
        <div className="alert-meta">
          {alert.affected_service.replace(/_/g, " ")} · {alert.status} · {formatClock(alert.timestamp)}
        </div>
      </div>
    </div>
  );
}
