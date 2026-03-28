"use client";

import { useEffect, useState } from "react";

type Metrics = {
  policy_retention_rate: number | null;
  commission_recovery_rate: number | null;
  avg_days_to_payment: number | null;
  discrepancy_rate: number | null;
  book_growth_rate: number | null;
  total_policies: number;
  total_premium: number;
  total_expected_commission: number;
  total_received_commission: number;
  total_outstanding: number;
};

type CarrierScore = {
  carrier_name: string;
  accuracy_score: number | null;
  timeliness_score: number | null;
  dispute_rate: number | null;
  overall_score: number | null;
  statement_count: number;
  total_commission: number;
};

type Alert = {
  id: string;
  alert_type: string;
  title: string;
  body: string | null;
  severity: string;
  is_read: boolean;
  created_at: string;
};

function formatCurrency(v: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v);
}

function formatPct(v: number | null) {
  if (v === null || v === undefined) return "—";
  return `${v.toFixed(1)}%`;
}

function severityColor(s: string) {
  switch (s) {
    case "critical": return "border-l-red-500 bg-red-500/5";
    case "warning": return "border-l-amber-500 bg-amber-500/5";
    default: return "border-l-sky-500 bg-sky-500/5";
  }
}

function scoreColor(score: number | null) {
  if (score === null) return "text-[var(--foreground-muted)]";
  if (score >= 90) return "text-emerald-500";
  if (score >= 70) return "text-amber-500";
  return "text-red-500";
}

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [carriers, setCarriers] = useState<CarrierScore[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/metrics")
      .then((r) => r.json())
      .then((data) => {
        setMetrics(data.metrics);
        setCarriers(data.carriers || []);
        setAlerts(data.alerts || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <div className="p-4 rounded-2xl bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-primary-hover)] shadow-lg">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
          </div>
          <div>
            <h2 className="text-3xl font-bold text-[var(--foreground)]">Performance Metrics</h2>
            <p className="text-[var(--foreground-muted)]">Loading...</p>
          </div>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 animate-pulse">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-28 rounded-xl bg-[var(--background-secondary)]" />
          ))}
        </div>
      </div>
    );
  }

  const m = metrics;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="p-4 rounded-2xl bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-primary-hover)] shadow-lg">
          <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
        </div>
        <div>
          <h2 className="text-3xl font-bold text-[var(--foreground)]">Performance Metrics</h2>
          <p className="text-[var(--foreground-muted)]">Real-time business intelligence from your commission data</p>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <MetricTile label="Policy Retention" value={formatPct(m?.policy_retention_rate ?? null)} sublabel="Renewed vs expired (12mo)" color={m?.policy_retention_rate && m.policy_retention_rate >= 85 ? "success" : "warning"} />
        <MetricTile label="Commission Recovery" value={formatPct(m?.commission_recovery_rate ?? null)} sublabel="Received vs expected" color={m?.commission_recovery_rate && m.commission_recovery_rate >= 95 ? "success" : "warning"} />
        <MetricTile label="Avg Days to Payment" value={m?.avg_days_to_payment !== null ? `${m?.avg_days_to_payment}d` : "—"} sublabel="Statement to payment" color="info" />
        <MetricTile label="Discrepancy Rate" value={formatPct(m?.discrepancy_rate ?? null)} sublabel="Statements with errors" color={m?.discrepancy_rate && m.discrepancy_rate <= 5 ? "success" : "error"} />
        <MetricTile label="Book Growth" value={formatPct(m?.book_growth_rate ?? null)} sublabel="Net new policies (90d)" color={m?.book_growth_rate && m.book_growth_rate > 0 ? "success" : "error"} />
        <MetricTile label="Outstanding" value={formatCurrency(m?.total_outstanding ?? 0)} sublabel="Unpaid commissions" color="gold" />
      </div>

      {/* Summary Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card-elevated rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-[var(--foreground)]">{m?.total_policies ?? 0}</p>
          <p className="text-xs text-[var(--foreground-muted)]">Total Policies</p>
        </div>
        <div className="card-elevated rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-[var(--foreground)]">{formatCurrency(m?.total_premium ?? 0)}</p>
          <p className="text-xs text-[var(--foreground-muted)]">Total Premium</p>
        </div>
        <div className="card-elevated rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-emerald-500">{formatCurrency(m?.total_received_commission ?? 0)}</p>
          <p className="text-xs text-[var(--foreground-muted)]">Received</p>
        </div>
        <div className="card-elevated rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-amber-500">{formatCurrency(m?.total_expected_commission ?? 0)}</p>
          <p className="text-xs text-[var(--foreground-muted)]">Expected</p>
        </div>
      </div>

      {/* Carrier Performance Table */}
      {carriers.length > 0 && (
        <div className="card">
          <div className="mb-4 flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-[var(--gold-primary)] to-amber-600 shadow-md">
              <span className="text-xl text-white">&#9733;</span>
            </div>
            <div>
              <h3 className="text-xl font-bold text-[var(--foreground)]">Carrier Performance</h3>
              <p className="text-sm text-[var(--foreground-muted)]">Ranked by overall reliability score</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border-color)]">
                  <th className="text-left py-3 px-2 font-semibold text-[var(--foreground-muted)]">Carrier</th>
                  <th className="text-center py-3 px-2 font-semibold text-[var(--foreground-muted)]">Overall</th>
                  <th className="text-center py-3 px-2 font-semibold text-[var(--foreground-muted)]">Accuracy</th>
                  <th className="text-center py-3 px-2 font-semibold text-[var(--foreground-muted)]">Timeliness</th>
                  <th className="text-center py-3 px-2 font-semibold text-[var(--foreground-muted)]">Disputes</th>
                  <th className="text-center py-3 px-2 font-semibold text-[var(--foreground-muted)]">Statements</th>
                  <th className="text-right py-3 px-2 font-semibold text-[var(--foreground-muted)]">Commission</th>
                </tr>
              </thead>
              <tbody>
                {carriers.map((c) => (
                  <tr key={c.carrier_name} className="border-b border-[var(--border-color)] hover:bg-[var(--background-secondary)]">
                    <td className="py-3 px-2 font-medium text-[var(--foreground)]">{c.carrier_name}</td>
                    <td className={`py-3 px-2 text-center font-bold ${scoreColor(c.overall_score)}`}>{formatPct(c.overall_score)}</td>
                    <td className={`py-3 px-2 text-center ${scoreColor(c.accuracy_score)}`}>{formatPct(c.accuracy_score)}</td>
                    <td className={`py-3 px-2 text-center ${scoreColor(c.timeliness_score)}`}>{formatPct(c.timeliness_score)}</td>
                    <td className="py-3 px-2 text-center text-[var(--foreground-muted)]">{formatPct(c.dispute_rate)}</td>
                    <td className="py-3 px-2 text-center text-[var(--foreground-muted)]">{c.statement_count}</td>
                    <td className="py-3 px-2 text-right text-[var(--foreground)]">{formatCurrency(c.total_commission)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="card">
          <div className="mb-4 flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-red-500 to-rose-600 shadow-md">
              <span className="text-xl text-white">&#9888;</span>
            </div>
            <div>
              <h3 className="text-xl font-bold text-[var(--foreground)]">Alerts</h3>
              <p className="text-sm text-[var(--foreground-muted)]">Proactive notifications from your AI agent</p>
            </div>
          </div>
          <div className="space-y-3">
            {alerts.map((a) => (
              <div key={a.id} className={`border-l-4 rounded-r-lg p-4 ${severityColor(a.severity)} ${a.is_read ? "opacity-60" : ""}`}>
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-[var(--foreground)]">{a.title}</p>
                  <span className="text-xs text-[var(--foreground-muted)]">
                    {new Date(a.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  </span>
                </div>
                {a.body && <p className="text-sm text-[var(--foreground-muted)] mt-1">{a.body}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!m?.total_policies && carriers.length === 0 && (
        <div className="card text-center py-12">
          <p className="text-4xl mb-4">&#128202;</p>
          <h3 className="text-xl font-bold text-[var(--foreground)] mb-2">No Metrics Yet</h3>
          <p className="text-[var(--foreground-muted)]">
            Metrics will appear here after you upload and reconcile your first commission statement.
            Head to the Reconciliation page to get started.
          </p>
        </div>
      )}
    </div>
  );
}

function MetricTile({ label, value, sublabel, color }: { label: string; value: string; sublabel: string; color: string }) {
  const colorMap: Record<string, string> = {
    success: "border-emerald-500/30 bg-emerald-500/5",
    warning: "border-amber-500/30 bg-amber-500/5",
    error: "border-red-500/30 bg-red-500/5",
    info: "border-sky-500/30 bg-sky-500/5",
    gold: "border-amber-400/30 bg-amber-400/5",
  };

  return (
    <div className={`rounded-xl border-2 p-4 ${colorMap[color] || colorMap.info}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)] mb-1">{label}</p>
      <p className="text-2xl font-bold text-[var(--foreground)]">{value}</p>
      <p className="text-xs text-[var(--foreground-muted)] mt-1">{sublabel}</p>
    </div>
  );
}
