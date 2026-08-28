import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { formatClock } from "../utils/format";

function Stat({ label, value }) {
  return (
    <div className="panel stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value small">{value}</div>
    </div>
  );
}

const RECOVERY_BADGE = {
  RECOVERED: "badge-success",
  UNRECOVERABLE: "badge-failed",
  RECOVERY_PENDING: "badge-processing",
  UNKNOWN: "badge-pending",
};

export default function FailuresSection({ failures }) {
  if (!failures) {
    return <div className="panel empty-state">Loading failure data…</div>;
  }

  const { summary, recent_failures: recent } = failures;
  const trendData = summary.trend.map((bucket) => ({
    time: new Date(bucket.bucket_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    Failures: bucket.count,
  }));

  return (
    <>
      <div className="grid grid-cards" style={{ marginBottom: 14 }}>
        <Stat label="Total Failures" value={summary.total_failures} />
        <Stat label="Retry Count" value={summary.retry_count} />
        <Stat label="Retry Success Rate" value={summary.retry_success_rate !== null ? `${summary.retry_success_rate}%` : "—"} />
        <Stat label="Unrecoverable" value={summary.unrecoverable_failures} />
      </div>

      <div className="grid grid-2" style={{ marginBottom: 14 }}>
        <div className="panel chart-panel">
          <div className="chart-title">Failure trend</div>
          {trendData.length === 0 ? (
            <div className="empty-state">No failures recorded yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={trendData}>
                <CartesianGrid stroke="#1f2732" strokeDasharray="3 3" />
                <XAxis dataKey="time" stroke="#576374" fontSize={11} />
                <YAxis stroke="#576374" fontSize={11} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#161c24", border: "1px solid #1f2732", fontSize: 12 }} />
                <Bar dataKey="Failures" fill="#f87171" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="panel chart-panel">
          <div className="chart-title">Failures by service</div>
          {Object.keys(summary.failures_by_service).length === 0 ? (
            <div className="empty-state">No failures recorded yet.</div>
          ) : (
            <div style={{ padding: "4px 0" }}>
              {Object.entries(summary.failures_by_service).map(([service, count]) => (
                <div key={service} className="service-row" style={{ gridTemplateColumns: "1fr auto" }}>
                  <span className="service-name">{service.replace(/_/g, " ")}</span>
                  <span className="mono">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="panel table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Failure ID</th>
              <th>Transaction</th>
              <th>Service</th>
              <th>Error Type</th>
              <th>Message</th>
              <th>Retries</th>
              <th>Recovery</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {recent.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-state">
                  No failures recorded yet.
                </td>
              </tr>
            ) : (
              recent.map((failure) => (
                <tr key={failure.failure_id}>
                  <td>{failure.failure_id}</td>
                  <td>{failure.transaction_id || "—"}</td>
                  <td>{failure.service.replace(/_/g, " ")}</td>
                  <td>{failure.error_type}</td>
                  <td style={{ whiteSpace: "normal", maxWidth: 260 }}>{failure.error_message || "—"}</td>
                  <td>{failure.retry_count}</td>
                  <td>
                    <span className={`badge ${RECOVERY_BADGE[failure.recovery_status] || "badge-pending"}`}>
                      {failure.recovery_status.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td>{formatClock(failure.timestamp)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
