import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend
} from 'recharts';

const DIRECT_COLOR = '#111111';
const AGENT_COLOR = '#4f46e5';
const FAIL_COLORS = ['#111111', '#4f46e5', '#9ca3af', '#d1d5db'];

// Same shape as the real getPaymentMetrics() mock in metricsService.js
const data = {
  agentic_metrics: {
    total_requests: 142,
    successful_payments_count: 28,
    failed_payments_count: 4,
    total_revenue_inr: 184500,
    success_rate_percentage: 87.5
  },
  comparison: {
    direct_app: { total_orders: 85, paid_orders: 72, failed_orders: 13, revenue_inr: 420000 },
    agentic: { total_orders: 32, paid_orders: 28, failed_orders: 4, revenue_inr: 184500 }
  },
  timeline: [
    { bucket: '09:00', agent_requests: 8, verified_payments: 6 },
    { bucket: '10:00', agent_requests: 14, verified_payments: 11 },
    { bucket: '11:00', agent_requests: 19, verified_payments: 17 },
    { bucket: '12:00', agent_requests: 12, verified_payments: 10 },
    { bucket: '13:00', agent_requests: 17, verified_payments: 14 },
    { bucket: '14:00', agent_requests: 22, verified_payments: 19 },
    { bucket: '15:00', agent_requests: 15, verified_payments: 13 },
    { bucket: '16:00', agent_requests: 9, verified_payments: 7 },
    { bucket: '17:00', agent_requests: 13, verified_payments: 11 },
    { bucket: '18:00', agent_requests: 20, verified_payments: 18 },
    { bucket: '19:00', agent_requests: 16, verified_payments: 14 },
    { bucket: '20:00', agent_requests: 11, verified_payments: 9 }
  ],
  failure_breakdown: [
    { reason: 'Verification Signature Error', count: 1 },
    { reason: 'User Cancelled Widget', count: 1 },
    { reason: 'LLM Timeout', count: 1 },
    { reason: 'Insufficient Stock', count: 1 }
  ],
  recent_orders: [
    { id: 1042, source: 'AGENT', amount: 6499, status: 'PAID', createdAt: new Date(Date.now() - 6 * 60000).toISOString() },
    { id: 1041, source: 'DIRECT_APP', amount: 2199, status: 'PAID', createdAt: new Date(Date.now() - 18 * 60000).toISOString() },
    { id: 1040, source: 'AGENT', amount: 899, status: 'FAILED', createdAt: new Date(Date.now() - 35 * 60000).toISOString() },
    { id: 1039, source: 'DIRECT_APP', amount: 15499, status: 'PAID', createdAt: new Date(Date.now() - 52 * 60000).toISOString() },
    { id: 1038, source: 'AGENT', amount: 3299, status: 'PAID', createdAt: new Date(Date.now() - 71 * 60000).toISOString() },
    { id: 1037, source: 'DIRECT_APP', amount: 4599, status: 'FAILED', createdAt: new Date(Date.now() - 95 * 60000).toISOString() },
    { id: 1036, source: 'AGENT', amount: 1199, status: 'PAID', createdAt: new Date(Date.now() - 120 * 60000).toISOString() },
    { id: 1035, source: 'DIRECT_APP', amount: 8999, status: 'PAID', createdAt: new Date(Date.now() - 140 * 60000).toISOString() },
    { id: 1034, source: 'AGENT', amount: 2599, status: 'PAID', createdAt: new Date(Date.now() - 160 * 60000).toISOString() },
    { id: 1033, source: 'DIRECT_APP', amount: 1099, status: 'PAID', createdAt: new Date(Date.now() - 190 * 60000).toISOString() }
  ]
};

function StatCard({ label, value, sub }) {
  return (
    <div className="border border-black bg-white p-4 grid gap-1">
      <p className="m-0 uppercase tracking-wide text-xs text-neutral-500">{label}</p>
      <p className="m-0 text-2xl font-bold">{value}</p>
      {sub && <p className="m-0 text-sm text-neutral-500">{sub}</p>}
    </div>
  );
}

function ChartPanel({ title, children, wide }) {
  return (
    <div className={`border border-black bg-white p-5 ${wide ? 'col-span-full' : ''}`}>
      <p className="m-0 mb-3 font-bold">{title}</p>
      {children}
    </div>
  );
}

export default function AdminDashboardPreview() {
  const { agentic_metrics: agentic, comparison, timeline, failure_breakdown, recent_orders } = data;

  const ordersComparisonData = [
    { name: 'Direct App', Orders: comparison.direct_app.total_orders },
    { name: 'Agentic AI', Orders: comparison.agentic.total_orders }
  ];

  const revenueComparisonData = [
    { name: 'Direct App', 'Revenue (₹)': comparison.direct_app.revenue_inr },
    { name: 'Agentic AI', 'Revenue (₹)': comparison.agentic.revenue_inr }
  ];

  const agenticShare =
    Math.round((comparison.agentic.revenue_inr / (comparison.direct_app.revenue_inr + comparison.agentic.revenue_inr)) * 1000) / 10;

  return (
    <div className="min-h-screen bg-white text-black font-sans">
      <nav className="max-w-6xl mx-auto flex items-center justify-between gap-4 px-4 py-4 border-b border-black">
        <div className="font-bold uppercase tracking-wide">Ecommerce App</div>
        <div className="flex flex-wrap gap-3 text-sm">
          <span className="border border-black px-3 py-2">Home</span>
          <span className="border border-black px-3 py-2">Add Product</span>
          <span className="border border-black px-3 py-2 bg-black text-white">Dashboard</span>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 py-6 grid gap-5">
        <h1 className="m-0 text-2xl font-bold">Monitoring Dashboard</h1>

        {/* Row 1: KPI cards */}
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          <StatCard label="Total Agent Requests" value={agentic.total_requests} />
          <StatCard
            label="Agentic Payments"
            value={`${agentic.successful_payments_count} Paid`}
            sub={`${agentic.failed_payments_count} Failed · ${agentic.success_rate_percentage}% success`}
          />
          <StatCard label="Agentic Sales Volume" value={`₹${agentic.total_revenue_inr.toLocaleString('en-IN')}`} />
          <StatCard label="Agentic Share of Revenue" value={`${agenticShare}%`} sub="vs. Direct App checkout" />
        </div>

        {/* Row 2: comparison charts */}
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))' }}>
          <ChartPanel title="Orders: Direct App vs Agentic AI">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={ordersComparisonData}>
                <CartesianGrid stroke="#e5e5e5" strokeDasharray="3 3" />
                <XAxis dataKey="name" stroke="#555555" fontSize={12} />
                <YAxis stroke="#555555" fontSize={12} allowDecimals={false} />
                <Tooltip contentStyle={{ border: '1px solid #111111', borderRadius: 0 }} />
                <Bar dataKey="Orders" radius={0}>
                  <Cell fill={DIRECT_COLOR} />
                  <Cell fill={AGENT_COLOR} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartPanel>

          <ChartPanel title="Revenue: Direct App vs Agentic AI">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={revenueComparisonData}>
                <CartesianGrid stroke="#e5e5e5" strokeDasharray="3 3" />
                <XAxis dataKey="name" stroke="#555555" fontSize={12} />
                <YAxis stroke="#555555" fontSize={12} />
                <Tooltip
                  contentStyle={{ border: '1px solid #111111', borderRadius: 0 }}
                  formatter={(value) => `₹${value.toLocaleString('en-IN')}`}
                />
                <Bar dataKey="Revenue (₹)" radius={0}>
                  <Cell fill={DIRECT_COLOR} />
                  <Cell fill={AGENT_COLOR} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartPanel>
        </div>

        {/* Row 2b: time series, full width */}
        <ChartPanel title="Agentic Request & Payment Flow" wide>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={timeline}>
              <CartesianGrid stroke="#e5e5e5" strokeDasharray="3 3" />
              <XAxis dataKey="bucket" stroke="#555555" fontSize={12} />
              <YAxis stroke="#555555" fontSize={12} allowDecimals={false} />
              <Tooltip contentStyle={{ border: '1px solid #111111', borderRadius: 0 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="agent_requests" name="Agent Requests" stroke={DIRECT_COLOR} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="verified_payments" name="Verified Payments" stroke={AGENT_COLOR} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartPanel>

        {/* Row 2c: failure breakdown + note */}
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))' }}>
          <ChartPanel title="Agentic Payment Failure Breakdown">
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={failure_breakdown} dataKey="count" nameKey="reason" outerRadius={95} label>
                  {failure_breakdown.map((entry, index) => (
                    <Cell key={entry.reason} fill={FAIL_COLORS[index % FAIL_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ border: '1px solid #111111', borderRadius: 0 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </ChartPanel>

          <ChartPanel title="Reading this dashboard">
            <p className="text-sm text-neutral-600">
              Direct App figures come from the regular checkout flow. Agentic figures come from orders placed
              through the AI buyer agent, matched via <code className="bg-neutral-100 px-1">order_source</code>.
              Success rate is paid ÷ (paid + failed) agentic orders.
            </p>
          </ChartPanel>
        </div>

        {/* Row 3: recent orders table */}
        <ChartPanel title="Live Activity — Recent Orders" wide>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  {['Order ID', 'Source', 'Amount', 'Status', 'Timestamp'].map((h) => (
                    <th key={h} className="text-left px-3 py-2 border-b border-black uppercase tracking-wide text-xs text-neutral-500">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recent_orders.map((order) => (
                  <tr key={order.id}>
                    <td className="px-3 py-2 border-b border-black whitespace-nowrap">#{order.id}</td>
                    <td className="px-3 py-2 border-b border-black whitespace-nowrap">
                      <span
                        className={`inline-block px-2 py-1 border text-xs ${
                          order.source === 'AGENT' ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-black border-black'
                        }`}
                      >
                        {order.source === 'AGENT' ? 'Agent' : 'Direct'}
                      </span>
                    </td>
                    <td className="px-3 py-2 border-b border-black whitespace-nowrap">₹{order.amount.toLocaleString('en-IN')}</td>
                    <td className="px-3 py-2 border-b border-black whitespace-nowrap">
                      <span
                        className={`inline-block px-2 py-1 border text-xs ${
                          order.status === 'PAID' ? 'bg-black text-white border-black' : 'bg-white text-black border-black'
                        }`}
                      >
                        {order.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 border-b border-black whitespace-nowrap">{new Date(order.createdAt).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartPanel>
      </main>
    </div>
  );
}
