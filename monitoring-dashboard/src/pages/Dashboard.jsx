import { useState } from "react";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";
import OverviewSection from "../components/OverviewSection";
import ServiceHealthSection from "../components/ServiceHealthSection";
import TransactionsSection from "../components/TransactionsSection";
import PaymentsSection from "../components/PaymentsSection";
import FailuresSection from "../components/FailuresSection";
import AuditActivitySection from "../components/AuditActivitySection";
import PerformanceSection from "../components/PerformanceSection";
import AlertsSection from "../components/AlertsSection";
import { useMonitoringData } from "../hooks/useMonitoringData";

const SECTION_TITLES = {
  overview: "System Overview",
  services: "Service Health",
  transactions: "Transaction Monitoring",
  payments: "Payment Monitoring",
  failures: "Failure Monitoring",
  audit: "Audit Activity",
  performance: "Performance",
  alerts: "Alerts",
};

export default function Dashboard() {
  const [active, setActive] = useState("overview");
  const data = useMonitoringData();

  const overallStatus = data.health?.overall_status;
  const activeAlertCount = data.alerts.filter((a) => a.status === "ACTIVE").length;

  return (
    <div className="app-shell">
      <Sidebar active={active} onNavigate={setActive} />
      <TopBar overallStatus={overallStatus} connected={data.connected} lastUpdate={data.lastUpdate} />
      <main className="main">
        {data.error && (
          <div className="banner-error">
            {data.error} — showing the most recent data available. The dashboard will keep retrying automatically.
          </div>
        )}

        <div className="section">
          <div className="section-header">
            <span className="section-title">{SECTION_TITLES[active]}</span>
            {active === "alerts" && activeAlertCount > 0 && (
              <span className="section-sub">{activeAlertCount} active</span>
            )}
          </div>

          {active === "overview" && <OverviewSection overview={data.metrics?.overview} />}
          {active === "services" && <ServiceHealthSection health={data.health} />}
          {active === "transactions" && <TransactionsSection transactions={data.transactions} />}
          {active === "payments" && <PaymentsSection payments={data.metrics?.payments} />}
          {active === "failures" && <FailuresSection failures={data.failures} />}
          {active === "audit" && <AuditActivitySection events={data.auditEvents} />}
          {active === "performance" && <PerformanceSection performance={data.metrics?.performance} />}
          {active === "alerts" && <AlertsSection alerts={data.alerts} />}
        </div>
      </main>
    </div>
  );
}
