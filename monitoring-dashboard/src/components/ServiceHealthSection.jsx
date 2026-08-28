import { timeAgo } from "../utils/format";

const STATUS_CLASS = {
  UP: "status-up",
  DEGRADED: "status-degraded",
  DOWN: "status-down",
  UNKNOWN: "status-unknown",
};

const SERVICE_LABELS = {
  agent_gateway: "Agent Gateway",
  merchant_agent: "Merchant Agent",
  transaction_orchestrator: "Transaction / Payment Orchestrator",
  payment_service: "Payment Service",
  failure_handling: "Failure Handling Service",
  audit_service: "Audit Service",
  monitoring_service: "Monitoring Service",
  database: "Database",
};

export default function ServiceHealthSection({ health }) {
  if (!health) {
    return <div className="panel empty-state">Loading service health…</div>;
  }

  return (
    <div className="panel service-list">
      {health.services.map((service) => (
        <div className="service-row" key={service.service}>
          <span className="service-name">{SERVICE_LABELS[service.service] || service.service}</span>
          <span className={`system-pill ${STATUS_CLASS[service.status] || "status-unknown"}`} style={{ width: "fit-content" }}>
            <span className="status-dot" />
            {service.status}
          </span>
          <span className="service-meta">
            {service.latency_ms !== null && service.latency_ms !== undefined
              ? `${Math.round(service.latency_ms)}ms`
              : "—"}
          </span>
          <span className="service-meta">heartbeat {timeAgo(service.last_heartbeat)}</span>
        </div>
      ))}
    </div>
  );
}
