const NAV_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "services", label: "Service Health" },
  { id: "transactions", label: "Transactions" },
  { id: "payments", label: "Payments" },
  { id: "failures", label: "Failures" },
  { id: "audit", label: "Audit Activity" },
  { id: "performance", label: "Performance" },
  { id: "alerts", label: "Alerts" },
];

export default function Sidebar({ active, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="mark" />
        <div className="sidebar-brand-text">
          <strong>Merchant Agent</strong>
          <span>Monitoring</span>
        </div>
      </div>
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          className={`nav-item ${active === item.id ? "active" : ""}`}
          onClick={() => onNavigate(item.id)}
        >
          <span className="dot" />
          {item.label}
        </button>
      ))}
    </aside>
  );
}
