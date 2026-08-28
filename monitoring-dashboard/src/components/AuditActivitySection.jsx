import { formatClock } from "../utils/format";

export default function AuditActivitySection({ events }) {
  if (!events) {
    return <div className="panel empty-state">Loading audit activity…</div>;
  }

  if (events.length === 0) {
    return <div className="panel empty-state">No audit activity recorded yet.</div>;
  }

  return (
    <div className="panel table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Event</th>
            <th>Transaction</th>
            <th>Service</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event, index) => (
            <tr key={`${event.timestamp}-${index}`}>
              <td>{formatClock(event.timestamp)}</td>
              <td>{event.event_type.replace(/_/g, " ")}</td>
              <td>{event.transaction_id || "—"}</td>
              <td>{event.service.replace(/_/g, " ")}</td>
              <td>{event.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
