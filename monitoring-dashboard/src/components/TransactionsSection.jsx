import { formatAmount, formatClock, formatDuration, STATUS_BADGE_CLASS } from "../utils/format";

export default function TransactionsSection({ transactions }) {
  if (!transactions) {
    return <div className="panel empty-state">Loading transactions…</div>;
  }

  if (transactions.length === 0) {
    return <div className="panel empty-state">No transactions recorded yet. They'll appear here as checkouts happen.</div>;
  }

  return (
    <div className="panel table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Transaction ID</th>
            <th>Session</th>
            <th>Type</th>
            <th>State</th>
            <th>Amount</th>
            <th>Started</th>
            <th>Completed</th>
            <th>Duration</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((txn) => (
            <tr key={txn.transaction_id}>
              <td>{txn.transaction_id}</td>
              <td>{txn.session_id || "—"}</td>
              <td>{txn.transaction_type}</td>
              <td>{txn.state}</td>
              <td>{formatAmount(txn.amount, txn.currency)}</td>
              <td>{formatClock(txn.started_at)}</td>
              <td>{formatClock(txn.completed_at)}</td>
              <td>{formatDuration(txn.duration_ms)}</td>
              <td>
                <span className={`badge ${STATUS_BADGE_CLASS[txn.status] || "badge-pending"}`}>{txn.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
