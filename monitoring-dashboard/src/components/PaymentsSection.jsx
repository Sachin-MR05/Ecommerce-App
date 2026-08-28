import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { formatDuration } from "../utils/format";

function Stat({ label, value }) {
  return (
    <div className="panel stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value small">{value}</div>
    </div>
  );
}

export default function PaymentsSection({ payments }) {
  if (!payments) {
    return <div className="panel empty-state">Loading payment metrics…</div>;
  }

  const chartData = payments.timeline.map((bucket) => ({
    time: new Date(bucket.bucket_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    Successful: bucket.successful,
    Failed: bucket.failed,
    "Timed out": bucket.timed_out,
  }));

  return (
    <>
      <div className="grid grid-cards" style={{ marginBottom: 14 }}>
        <Stat label="Payment Attempts" value={payments.payment_attempts} />
        <Stat label="Successful" value={payments.successful_payments} />
        <Stat label="Failed" value={payments.failed_payments} />
        <Stat label="Timeouts" value={payments.payment_timeouts} />
        <Stat label="Success Rate" value={`${payments.payment_success_rate}%`} />
        <Stat label="Avg Latency" value={formatDuration(payments.avg_payment_latency_ms)} />
      </div>
      <div className="panel chart-panel">
        <div className="chart-title">Payment success / failure over time</div>
        {chartData.length === 0 ? (
          <div className="empty-state">No payment activity yet.</div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData}>
              <CartesianGrid stroke="#1f2732" strokeDasharray="3 3" />
              <XAxis dataKey="time" stroke="#576374" fontSize={11} />
              <YAxis stroke="#576374" fontSize={11} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "#161c24", border: "1px solid #1f2732", fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="Successful" stroke="#34d399" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="Failed" stroke="#f87171" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="Timed out" stroke="#fbbf24" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </>
  );
}
