"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { supabase } from "@/lib/supabase";
import { ROLE_LABELS, canManageTeam, canAssignRole, type UserRole } from "@/lib/roles";

// ─── Types ──────────────────────────────────────────────────────
type ProfileData = {
  id: string;
  email: string;
  subscription_status: string | null;
  created_at: string | null;
};

type AgentRow = {
  id: string;
  user_id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
};

type AgencyData = {
  id: string;
  agency_name: string;
  email: string | null;
  phone: string | null;
  website: string | null;
  address_street: string | null;
  address_city: string | null;
  address_state: string | null;
  address_zip: string | null;
  license_number: string | null;
  tax_id: string | null;
};

// ─── Helpers ────────────────────────────────────────────────────
function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric" }).format(date);
}

function statusBadge(status?: string | null) {
  switch (status) {
    case "active": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
    case "trialing": return "bg-sky-500/20 text-sky-400 border-sky-500/30";
    case "past_due": return "bg-amber-500/20 text-amber-400 border-amber-500/30";
    case "canceled": return "bg-rose-500/20 text-rose-400 border-rose-500/30";
    default: return "bg-slate-500/20 text-slate-400 border-slate-500/30";
  }
}

// ─── Floor 1: Agent Profile ─────────────────────────────────────
function AgentProfile({
  user,
  profile,
  loading,
  authLoading,
  subscriptionStatus,
  error,
  success,
  form,
  setForm,
  handlePasswordChange,
  handleLogout,
}: {
  user: any;
  profile: ProfileData | null;
  loading: boolean;
  authLoading: boolean;
  subscriptionStatus: string;
  error: string | null;
  success: string | null;
  form: { currentPassword: string; newPassword: string; confirmPassword: string };
  setForm: (f: any) => void;
  handlePasswordChange: (e: FormEvent<HTMLFormElement>) => void;
  handleLogout: () => void;
}) {
  return (
    <div className="space-y-8">
      {/* Profile Card */}
      <div className="card bg-[var(--background-secondary)] rounded-[var(--border-radius-large)] shadow-lg border-2 border-[var(--border-color)] p-6">
        <div className="mb-6 flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-primary-hover)] shadow-md">
            <span className="text-xl">📋</span>
          </div>
          <div>
            <h3 className="text-xl font-bold text-[var(--foreground)]">Profile</h3>
            <p className="text-sm text-[var(--foreground-muted)]">Your account details</p>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-[var(--foreground-muted)]">Email</label>
            <input
              type="email"
              readOnly
              value={profile?.email ?? user?.email ?? ""}
              className="w-full rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] font-mono"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-[var(--foreground-muted)]">Member since</label>
            <input
              type="text"
              readOnly
              value={formatDate(profile?.created_at ?? user?.created_at ?? null)}
              className="w-full rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)]"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-[var(--foreground-muted)]">Role</label>
            <div className="flex items-center gap-2 rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3">
              <span>{ROLE_LABELS[user?.role as UserRole]?.icon ?? '👤'}</span>
              <span className="text-sm font-semibold text-[var(--foreground)]">
                {ROLE_LABELS[user?.role as UserRole]?.name ?? 'Agent'}
              </span>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-[var(--foreground-muted)]">Agency</label>
            <div className="flex items-center gap-2 rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3">
              <span>🏢</span>
              <span className="text-sm text-[var(--foreground)]">
                {user?.agency_name ?? 'Solo Agent'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Subscription Card */}
      <div className="card bg-[var(--background-secondary)] rounded-[var(--border-radius-large)] shadow-lg border-2 border-[var(--border-color)] p-6">
        <div className="mb-6 flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 shadow-md">
            <span className="text-xl">💳</span>
          </div>
          <div>
            <h3 className="text-xl font-bold text-[var(--foreground)]">Subscription</h3>
            <p className="text-sm text-[var(--foreground-muted)]">Plan &amp; billing status</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] p-4">
            <p className="text-xs font-semibold uppercase tracking-widest text-[var(--foreground-muted)] mb-2">Status</p>
            <div className="flex items-center gap-3">
              <span className="text-lg font-bold text-[var(--foreground)] capitalize">
                {subscriptionStatus.replace("_", " ")}
              </span>
              <span className={`rounded-full border px-3 py-1 text-xs font-bold ${statusBadge(subscriptionStatus)}`}>
                {subscriptionStatus}
              </span>
            </div>
          </div>
          <div className="rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] p-4">
            <p className="text-xs font-semibold uppercase tracking-widest text-[var(--foreground-muted)] mb-2">Plan</p>
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold text-[var(--foreground)] capitalize">
                {(profile as any)?.subscription_plan?.replace("_", " ") || "Starter"}
              </span>
              <a
                href="/pricing"
                className="text-xs font-semibold text-[var(--accent-primary)] hover:underline"
              >
                Change Plan
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Security Card */}
      <div className="card bg-[var(--background-secondary)] rounded-[var(--border-radius-large)] shadow-lg border-2 border-[var(--border-color)] p-6">
        <div className="mb-6 flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-br from-red-500 to-rose-600 shadow-md">
            <span className="text-xl">🔒</span>
          </div>
          <div>
            <h3 className="text-xl font-bold text-[var(--foreground)]">Security</h3>
            <p className="text-sm text-[var(--foreground-muted)]">Change your password</p>
          </div>
        </div>

        <form className="grid gap-4 md:grid-cols-3" onSubmit={handlePasswordChange}>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-[var(--foreground-muted)]">Current password</label>
            <input
              type="password"
              className="w-full rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
              value={form.currentPassword}
              onChange={(e) => setForm({ ...form, currentPassword: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-[var(--foreground-muted)]">New password</label>
            <input
              type="password"
              className="w-full rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
              value={form.newPassword}
              onChange={(e) => setForm({ ...form, newPassword: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-[var(--foreground-muted)]">Confirm new</label>
            <input
              type="password"
              className="w-full rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
              value={form.confirmPassword}
              onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })}
            />
          </div>

          <div className="md:col-span-3 flex items-center justify-end gap-3 border-t-2 border-[var(--border-color)] pt-4 mt-2">
            <button
              type="submit"
              disabled={loading || authLoading}
              className="inline-flex items-center gap-2 px-6 py-3 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 disabled:opacity-50"
            >
              🔒 {loading ? "Updating..." : "Update Password"}
            </button>
          </div>
        </form>
      </div>

      {/* Logout */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleLogout}
          className="inline-flex items-center gap-2 px-6 py-3 border-2 border-[var(--border-color)] bg-[var(--background-secondary)] text-[var(--foreground)] font-semibold rounded-xl hover:bg-[var(--background)] transition-all duration-300"
        >
          🚪 Sign Out
        </button>
      </div>
    </div>
  );
}

// ─── Floor 2: Team Management ───────────────────────────────────
function TeamManagement({ agencyId, userRole }: { agencyId: string; userRole: UserRole }) {
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [agency, setAgency] = useState<AgencyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newAgent, setNewAgent] = useState({ name: "", email: "", role: "agent" as UserRole });
  const [activeTab, setActiveTab] = useState<"team" | "agency">("team");
  const [agencyForm, setAgencyForm] = useState<Partial<AgencyData>>({});

  // Load team & agency data
  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [teamRes, agencyRes] = await Promise.all([
          fetch(`/api/account/team?agencyId=${agencyId}`),
          fetch(`/api/account/agency?agencyId=${agencyId}`),
        ]);

        if (teamRes.ok) {
          const teamData = await teamRes.json();
          setAgents(teamData.agents ?? []);
        }

        if (agencyRes.ok) {
          const agencyData = await agencyRes.json();
          setAgency(agencyData.agency ?? null);
          setAgencyForm(agencyData.agency ?? {});
        }
      } catch (err: any) {
        setError("Failed to load team data");
      }
      setLoading(false);
    };
    load();
  }, [agencyId]);

  // Auto-clear success
  useEffect(() => {
    if (!success) return;
    const t = setTimeout(() => setSuccess(null), 4000);
    return () => clearTimeout(t);
  }, [success]);

  const handleAddAgent = async (e: FormEvent) => {
    e.preventDefault();
    if (!newAgent.name || !newAgent.email) return;
    setSaving(true);
    setError(null);

    try {
      const res = await fetch("/api/account/team", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agencyId, ...newAgent }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to add agent");
      } else {
        setAgents((prev) => [...prev, data.agent]);
        setNewAgent({ name: "", email: "", role: "agent" });
        setShowAddForm(false);
        setSuccess(`${data.agent.name} added to team`);
      }
    } catch {
      setError("Network error");
    }
    setSaving(false);
  };

  const handleToggleActive = async (agent: AgentRow) => {
    try {
      const res = await fetch("/api/account/team", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agentId: agent.id, is_active: !agent.is_active }),
      });
      if (res.ok) {
        const data = await res.json();
        setAgents((prev) => prev.map((a) => (a.id === agent.id ? { ...a, ...data.agent } : a)));
        setSuccess(`${agent.name} ${agent.is_active ? "deactivated" : "activated"}`);
      }
    } catch {
      setError("Failed to update agent");
    }
  };

  const handleRoleChange = async (agent: AgentRow, newRole: UserRole) => {
    if (!canAssignRole(userRole, newRole)) return;
    try {
      const res = await fetch("/api/account/team", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agentId: agent.id, role: newRole }),
      });
      if (res.ok) {
        const data = await res.json();
        setAgents((prev) => prev.map((a) => (a.id === agent.id ? { ...a, ...data.agent } : a)));
        setSuccess(`${agent.name} role updated to ${ROLE_LABELS[newRole].name}`);
      }
    } catch {
      setError("Failed to update role");
    }
  };

  const handleSaveAgency = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/account/agency", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agencyId, ...agencyForm }),
      });
      if (res.ok) {
        const data = await res.json();
        setAgency(data.agency);
        setSuccess("Agency profile saved");
      } else {
        const data = await res.json();
        setError(data.error || "Failed to save");
      }
    } catch {
      setError("Network error");
    }
    setSaving(false);
  };

  const isManager = canManageTeam(userRole);
  const activeCount = agents.filter((a) => a.is_active).length;

  return (
    <div className="space-y-8">
      {/* Tab Switcher */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab("team")}
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-300 ${
            activeTab === "team"
              ? "bg-[var(--accent-primary)] text-white shadow-lg"
              : "bg-[var(--background-secondary)] text-[var(--foreground-muted)] border-2 border-[var(--border-color)] hover:border-[var(--accent-primary)]"
          }`}
        >
          👥 Team Roster
        </button>
        <button
          onClick={() => setActiveTab("agency")}
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-300 ${
            activeTab === "agency"
              ? "bg-[var(--accent-primary)] text-white shadow-lg"
              : "bg-[var(--background-secondary)] text-[var(--foreground-muted)] border-2 border-[var(--border-color)] hover:border-[var(--accent-primary)]"
          }`}
        >
          🏢 Agency Profile
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="rounded-2xl border-2 border-red-500/30 bg-red-500/10 px-6 py-4 text-sm text-red-400 flex items-center gap-3">
          <span className="text-xl">❌</span> {error}
        </div>
      )}
      {success && (
        <div className="rounded-2xl border-2 border-emerald-500/30 bg-emerald-500/10 px-6 py-4 text-sm text-emerald-400 flex items-center gap-3">
          <span className="text-xl">✅</span> {success}
        </div>
      )}

      {/* ═══ TEAM TAB ═══ */}
      {activeTab === "team" && (
        <div className="space-y-6">
          {/* Team Header */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg">
                <span className="text-2xl text-white">👥</span>
              </div>
              <div>
                <h3 className="text-2xl font-bold text-[var(--foreground)]">Team Roster</h3>
                <p className="text-sm text-[var(--foreground-muted)]">
                  {activeCount} active · {agents.length - activeCount} inactive
                </p>
              </div>
            </div>

            {isManager && (
              <button
                onClick={() => setShowAddForm(!showAddForm)}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300"
              >
                {showAddForm ? "✕ Cancel" : "➕ Add Agent"}
              </button>
            )}
          </div>

          {/* Add Agent Form */}
          {showAddForm && isManager && (
            <form
              onSubmit={handleAddAgent}
              className="card bg-[var(--background-secondary)] rounded-[var(--border-radius-large)] shadow-lg border-2 border-[var(--accent-primary)]/30 p-6"
            >
              <h4 className="text-lg font-bold text-[var(--foreground)] mb-4 flex items-center gap-2">
                <span>➕</span> Add New Team Member
              </h4>
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-[var(--foreground-muted)]">Full Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="Jane Smith"
                    value={newAgent.name}
                    onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                    className="w-full rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-[var(--foreground-muted)]">Email *</label>
                  <input
                    type="email"
                    required
                    placeholder="jane@agency.com"
                    value={newAgent.email}
                    onChange={(e) => setNewAgent({ ...newAgent, email: e.target.value })}
                    className="w-full rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-[var(--foreground-muted)]">Role</label>
                  <select
                    value={newAgent.role}
                    onChange={(e) => setNewAgent({ ...newAgent, role: e.target.value as UserRole })}
                    className="w-full rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                  >
                    {(Object.entries(ROLE_LABELS) as [UserRole, any][])
                      .filter(([role]) => canAssignRole(userRole, role))
                      .map(([role, label]) => (
                        <option key={role} value={role}>
                          {label.icon} {label.name}
                        </option>
                      ))}
                  </select>
                </div>
              </div>
              <div className="flex justify-end mt-4">
                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl shadow-lg transition-all duration-300 disabled:opacity-50"
                >
                  {saving ? "Adding..." : "✅ Add to Team"}
                </button>
              </div>
            </form>
          )}

          {/* Agent Table */}
          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin text-4xl mb-4">⏳</div>
              <p className="text-[var(--foreground-muted)]">Loading team...</p>
            </div>
          ) : agents.length === 0 ? (
            <div className="text-center py-12 card bg-[var(--background-secondary)] rounded-[var(--border-radius-large)] border-2 border-[var(--border-color)]">
              <span className="text-5xl mb-4 block">👥</span>
              <p className="text-lg font-semibold text-[var(--foreground)]">No team members yet</p>
              <p className="text-sm text-[var(--foreground-muted)]">Add your first agent to get started</p>
            </div>
          ) : (
            <div className="card bg-[var(--background-secondary)] rounded-[var(--border-radius-large)] shadow-lg border-2 border-[var(--border-color)] overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b-2 border-[var(--border-color)] bg-[var(--background)]">
                      <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-[var(--foreground-muted)]">Agent</th>
                      <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-[var(--foreground-muted)]">Role</th>
                      <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-[var(--foreground-muted)]">Status</th>
                      <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-[var(--foreground-muted)]">Joined</th>
                      {isManager && (
                        <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-[var(--foreground-muted)]">Actions</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-color)]">
                    {agents.map((agent) => (
                      <tr key={agent.id} className={`hover:bg-[var(--background)] transition-colors ${!agent.is_active ? "opacity-50" : ""}`}>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-primary-hover)] flex items-center justify-center text-white font-bold">
                              {agent.name.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <p className="font-semibold text-[var(--foreground)]">{agent.name}</p>
                              <p className="text-xs text-[var(--foreground-muted)] font-mono">{agent.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          {isManager && agent.role !== "owner" ? (
                            <select
                              value={agent.role}
                              onChange={(e) => handleRoleChange(agent, e.target.value as UserRole)}
                              className="rounded-lg border border-[var(--border-color)] bg-[var(--background)] px-3 py-1.5 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                            >
                              {(Object.entries(ROLE_LABELS) as [UserRole, any][])
                                .filter(([role]) => canAssignRole(userRole, role))
                                .map(([role, label]) => (
                                  <option key={role} value={role}>
                                    {label.icon} {label.name}
                                  </option>
                                ))}
                            </select>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--foreground)]">
                              {ROLE_LABELS[agent.role]?.icon} {ROLE_LABELS[agent.role]?.name}
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${
                            agent.is_active
                              ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                              : "bg-slate-500/20 text-slate-400 border-slate-500/30"
                          }`}>
                            <span className={`h-2 w-2 rounded-full ${agent.is_active ? "bg-emerald-400" : "bg-slate-400"}`} />
                            {agent.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-[var(--foreground-muted)]">
                          {formatDate(agent.created_at)}
                        </td>
                        {isManager && (
                          <td className="px-6 py-4 text-right">
                            {agent.role !== "owner" && (
                              <button
                                onClick={() => handleToggleActive(agent)}
                                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                                  agent.is_active
                                    ? "bg-rose-500/20 text-rose-400 hover:bg-rose-500/30"
                                    : "bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30"
                                }`}
                              >
                                {agent.is_active ? "🚫 Deactivate" : "✅ Activate"}
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ AGENCY TAB ═══ */}
      {activeTab === "agency" && (
        <div className="space-y-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-3 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 shadow-lg">
              <span className="text-2xl text-white">🏢</span>
            </div>
            <div>
              <h3 className="text-2xl font-bold text-[var(--foreground)]">Agency Profile</h3>
              <p className="text-sm text-[var(--foreground-muted)]">Business information &amp; settings</p>
            </div>
          </div>

          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin text-4xl mb-4">⏳</div>
              <p className="text-[var(--foreground-muted)]">Loading agency...</p>
            </div>
          ) : (
            <form onSubmit={handleSaveAgency} className="space-y-6">
              {/* Business Info */}
              <div className="card bg-[var(--background-secondary)] rounded-[var(--border-radius-large)] shadow-lg border-2 border-[var(--border-color)] p-6">
                <h4 className="text-lg font-bold text-[var(--foreground)] mb-4 flex items-center gap-2">
                  <span>📝</span> Business Information
                </h4>
                <div className="grid gap-4 md:grid-cols-2">
                  <InputField label="Agency Name" value={agencyForm.agency_name} onChange={(v) => setAgencyForm({ ...agencyForm, agency_name: v })} disabled={!isManager} />
                  <InputField label="Email" value={agencyForm.email} onChange={(v) => setAgencyForm({ ...agencyForm, email: v })} disabled={!isManager} type="email" />
                  <InputField label="Phone" value={agencyForm.phone} onChange={(v) => setAgencyForm({ ...agencyForm, phone: v })} disabled={!isManager} />
                  <InputField label="Website" value={agencyForm.website} onChange={(v) => setAgencyForm({ ...agencyForm, website: v })} disabled={!isManager} />
                </div>
              </div>

              {/* Address */}
              <div className="card bg-[var(--background-secondary)] rounded-[var(--border-radius-large)] shadow-lg border-2 border-[var(--border-color)] p-6">
                <h4 className="text-lg font-bold text-[var(--foreground)] mb-4 flex items-center gap-2">
                  <span>📍</span> Address
                </h4>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="md:col-span-2">
                    <InputField label="Street" value={agencyForm.address_street} onChange={(v) => setAgencyForm({ ...agencyForm, address_street: v })} disabled={!isManager} />
                  </div>
                  <InputField label="City" value={agencyForm.address_city} onChange={(v) => setAgencyForm({ ...agencyForm, address_city: v })} disabled={!isManager} />
                  <div className="grid grid-cols-2 gap-4">
                    <InputField label="State" value={agencyForm.address_state} onChange={(v) => setAgencyForm({ ...agencyForm, address_state: v })} disabled={!isManager} />
                    <InputField label="ZIP" value={agencyForm.address_zip} onChange={(v) => setAgencyForm({ ...agencyForm, address_zip: v })} disabled={!isManager} />
                  </div>
                </div>
              </div>

              {/* Licensing */}
              <div className="card bg-[var(--background-secondary)] rounded-[var(--border-radius-large)] shadow-lg border-2 border-[var(--border-color)] p-6">
                <h4 className="text-lg font-bold text-[var(--foreground)] mb-4 flex items-center gap-2">
                  <span>🛡️</span> Licensing &amp; Compliance
                </h4>
                <div className="grid gap-4 md:grid-cols-2">
                  <InputField label="License Number" value={agencyForm.license_number} onChange={(v) => setAgencyForm({ ...agencyForm, license_number: v })} disabled={!isManager} />
                  <InputField label="Tax ID / EIN" value={agencyForm.tax_id} onChange={(v) => setAgencyForm({ ...agencyForm, tax_id: v })} disabled={!isManager} />
                </div>
              </div>

              {isManager && (
                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={saving}
                    className="inline-flex items-center gap-2 px-6 py-3 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 disabled:opacity-50"
                  >
                    {saving ? "Saving..." : "💾 Save Agency Profile"}
                  </button>
                </div>
              )}
            </form>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Shared Input Component ─────────────────────────────────────
function InputField({
  label,
  value,
  onChange,
  disabled = false,
  type = "text",
}: {
  label: string;
  value: string | null | undefined;
  onChange: (val: string) => void;
  disabled?: boolean;
  type?: string;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-semibold text-[var(--foreground-muted)]">{label}</label>
      <input
        type={type}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] disabled:opacity-60 disabled:cursor-not-allowed"
      />
    </div>
  );
}

// ─── Main Account Page ──────────────────────────────────────────
export default function AccountPage() {
  const router = useRouter();
  const { user, logout, loading: authLoading, currentFloor, userRole, agencyId } = useAuth();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });

  useEffect(() => {
    if (!user?.id) { setProfile(null); return; }

    const loadProfile = async () => {
      setLoading(true);
      setError(null);
      const { data, error: fetchError } = await supabase
        .from("users")
        .select("id, email, subscription_status, subscription_plan, created_at")
        .eq("id", user.id)
        .maybeSingle();

      if (fetchError) {
        setError("Unable to load account details.");
        setProfile(null);
      } else {
        setProfile(data as ProfileData);
      }
      setLoading(false);
    };
    loadProfile();
  }, [user?.id]);

  // Auto-clear alerts
  useEffect(() => {
    if (!success) return;
    const t = setTimeout(() => setSuccess(null), 4000);
    return () => clearTimeout(t);
  }, [success]);

  const subscriptionStatus = useMemo(
    () => profile?.subscription_status ?? user?.subscription_status ?? "unknown",
    [profile?.subscription_status, user?.subscription_status]
  );

  const handlePasswordChange = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!user?.id) { setError("Please log in."); return; }
    if (!form.currentPassword || !form.newPassword || !form.confirmPassword) { setError("Fill out all password fields."); return; }
    if (form.newPassword !== form.confirmPassword) { setError("Passwords don't match."); return; }

    setLoading(true);
    try {
      const res = await fetch('/api/account/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ currentPassword: form.currentPassword, newPassword: form.newPassword }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Unable to update password.');
      } else {
        setSuccess('Password updated.');
        setForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
      }
    } catch (err) {
      setError('Network error');
    }
    setLoading(false);
  };

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  // Not signed in
  if (!user && !authLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <span className="text-5xl mb-4">🔐</span>
        <h2 className="text-2xl font-bold text-[var(--foreground)] mb-2">Not Signed In</h2>
        <p className="text-[var(--foreground-muted)] mb-6">Log in to manage your account.</p>
        <button
          onClick={() => router.push("/login")}
          className="px-6 py-3 bg-[var(--accent-primary)] text-white font-semibold rounded-xl shadow-lg"
        >
          Go to Login
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8 min-h-screen text-[var(--foreground)] bg-[var(--background)]">
      {/* Page Header */}
      <div className="flex items-center gap-4">
        <div className="p-4 rounded-2xl bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-primary-hover)] shadow-xl">
          <span className="text-4xl">{currentFloor === 2 ? '🏢' : '👤'}</span>
        </div>
        <div>
          <h1 className="text-4xl font-bold text-[var(--foreground)] mb-2">
            {currentFloor === 2 ? '🏢 Agency Management' : '👤 Account Settings'}
          </h1>
          <p className="text-[var(--foreground-muted)] flex items-center gap-2">
            <span className="text-lg">{currentFloor === 2 ? '⚙️' : '🎯'}</span>
            {currentFloor === 2
              ? 'Manage your team, roles, and agency profile'
              : 'Your profile, subscription, and security settings'}
          </p>
        </div>
      </div>

      {/* Global Alerts */}
      {error && (
        <div className="rounded-2xl border-2 border-red-500/30 bg-red-500/10 px-6 py-4 text-sm text-red-400 flex items-center gap-3">
          <span className="text-xl">⚠️</span>
          <div>
            <p className="font-semibold">Error</p>
            <p className="text-xs opacity-80">{error}</p>
          </div>
        </div>
      )}
      {success && (
        <div className="rounded-2xl border-2 border-emerald-500/30 bg-emerald-500/10 px-6 py-4 text-sm text-emerald-400 flex items-center gap-3">
          <span className="text-xl">✅</span> {success}
        </div>
      )}

      {/* Floor-based content */}
      {currentFloor === 2 && agencyId ? (
        <TeamManagement agencyId={agencyId} userRole={userRole} />
      ) : (
        <AgentProfile
          user={user}
          profile={profile}
          loading={loading}
          authLoading={authLoading}
          subscriptionStatus={subscriptionStatus}
          error={error}
          success={success}
          form={form}
          setForm={setForm}
          handlePasswordChange={handlePasswordChange}
          handleLogout={handleLogout}
        />
      )}

      {/* Footer */}
      <footer className="mt-16 border-t-2 border-[var(--border-color)] bg-[var(--background)] py-8 text-center rounded-[var(--border-radius-large)]">
        <div className="container mx-auto max-w-5xl px-4">
          <div className="flex items-center justify-center gap-2 mb-2">
            <span className="text-2xl">🛡️</span>
            <p className="font-bold text-[var(--accent-primary)]">{currentFloor === 2 ? "Agency" : "Agent"} Commission Tracker</p>
          </div>
          <p className="text-xs text-[var(--foreground-muted)]">
            Powered by Metro Point Technology • © 2026 All rights reserved
          </p>
        </div>
      </footer>
    </div>
  );
}
