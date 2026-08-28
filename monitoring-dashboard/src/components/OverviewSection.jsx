import { formatDuration } from "../utils/format";

function Card({ label, value, accent }) {
  return (
    <div className="panel stat-card">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${accent ? "stat-accent" : ""}`}>{value}</div>
    </div>
  );
}

export default function OverviewSection({ overview }) {
  if (!overview) {
    return <div className="panel empty-state">Loading system overview…</div>;
  }

  return (
    <div className="grid grid-cards">
      <Card label="System Status" value={overview.system_status} accent />
      <Card label="Total Transactions" value={overview.total_transactions} />
      <Card label="Successful" value={overview.successful_transactions} />
      <Card label="Failed" value={overview.failed_transactions} />
      <Card label="Pending" value={overview.pending_transactions} />
      <Card label="Active" value={overview.active_transactions} />
      <Card label="Success Rate" value={`${overview.success_rate}%`} />
      <Card label="Avg Duration" value={formatDuration(overview.avg_transaction_duration_ms)} />
    </div>
  );
}
