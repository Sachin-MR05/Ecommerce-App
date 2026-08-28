import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { formatDuration } from "../utils/format";

function Stat({ label, value }) {
  return (
    <div className="panel stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value small">{value}</div>
    </div>
  );
}

export default function PerformanceSection({ performance }) {
  if (!performance) {
    return <div className="panel empty-state">Loading performance metrics…</div>;
  }

  const chartData = performance.latency_timeline.map((bucket) => ({
    time: new Date(bucket.bucket_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    "API latency (ms)": bucket.api_latency_ms,
    Requests: bucket.request_count,
  }));

  return (
    <>
      <div className="grid grid-cards" style={{ marginBottom: 14 }}>
        <Stat label="API Latency" value={formatDuration(performance.api_latency_ms)} />
        <Stat label="Transaction Latency" value={formatDuration(performance.transaction_latency_ms)} />
        <Stat label="Payment Latency" value={formatDuration(performance.payment_latency_ms)} />
        <Stat label="Database Latency" value={formatDuration(performance.database_latency_ms)} />
        <Stat label="LLM Latency" value={formatDuration(performance.llm_latency_ms)} />
        <Stat label="Request Rate" value={`${performance.request_rate_per_min}/min`} />
      </div>
      <div className="grid grid-2">
        <div className="panel chart-panel">
          <div className="chart-title">API latency over time</div>
          {chartData.length === 0 ? (
            <div className="empty-state">Not enough traffic yet to chart latency.</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="#1f2732" strokeDasharray="3 3" />
                <XAxis dataKey="time" stroke="#576374" fontSize={11} />
                <YAxis stroke="#576374" fontSize={11} />
                <Tooltip contentStyle={{ background: "#161c24", border: "1px solid #1f2732", fontSize: 12 }} />
                <Line type="monotone" dataKey="API latency (ms)" stroke="#f5a623" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="panel chart-panel">
          <div className="chart-title">Throughput (requests / minute bucket)</div>
          {chartData.length === 0 ? (
            <div className="empty-state">Not enough traffic yet to chart throughput.</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="#1f2732" strokeDasharray="3 3" />
                <XAxis dataKey="time" stroke="#576374" fontSize={11} />
                <YAxis stroke="#576374" fontSize={11} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#161c24", border: "1px solid #1f2732", fontSize: 12 }} />
                <Line type="monotone" dataKey="Requests" stroke="#60a5fa" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </>
  );
}
