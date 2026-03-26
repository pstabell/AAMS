"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { formatCurrency } from "@/lib/calculations";
import { supabase } from "@/lib/supabase";

type StatementRow = {
  id: string;
  customer: string;
  policy_number: string;
  carrier: string;
  premium: number;
  commission: number;
  effective_date: string;
  matched: boolean;
  matchedPolicyId?: string;
};

type MatchCandidate = {
  id: string;
  customer: string;
  policy_number: string;
  carrier: string;
  premium_sold: number;
  agency_estimated_comm: number;
  effective_date: string;
  score: number;
};

export default function ReconciliationPage() {
  const { user } = useAuth();

  // State
  const [uploadedRows, setUploadedRows] = useState<StatementRow[]>([]);
  const [selectedRow, setSelectedRow] = useState<StatementRow | null>(null);
  const [matchCandidates, setMatchCandidates] = useState<MatchCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Stats
  const totalRows = uploadedRows.length;
  const matchedRows = uploadedRows.filter((r) => r.matched).length;
  const unmatchedRows = totalRows - matchedRows;
  const totalCommission = uploadedRows.reduce((sum, r) => sum + r.commission, 0);

  // Helper to parse a File directly (used by input change and drop)
  const parseAndLoadFile = useCallback(async (file: File) => {
    if (!file) return;
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      const text = await file.text();
      const lines = text.split(/\r?\n/).filter((line) => line.trim());
      if (lines.length < 2) {
        setError("File must have a header row and at least one data row.");
        setLoading(false);
        return;
      }
      const header = parseCSVLine(lines[0]).map((h) => h.toLowerCase().trim());
      const customerIdx = findColumnIndex(header, [
        "customer",
        "insured",
        "name",
        "policyholder",
      ]);
      const policyIdx = findColumnIndex(header, [
        "policy",
        "policy_number",
        "policy number",
        "policy#",
        "policy_no",
      ]);
      const carrierIdx = findColumnIndex(header, ["carrier", "company", "insurer"]);
      const premiumIdx = findColumnIndex(header, ["premium", "premium_sold", "amount"]);
      const commissionIdx = findColumnIndex(header, [
        "commission",
        "comm",
        "agency_commission",
        "agency commission",
      ]);
      const dateIdx = findColumnIndex(header, [
        "effective",
        "effective_date",
        "eff_date",
        "date",
      ]);
      if (customerIdx === -1 && policyIdx === -1) {
        setError("Could not find customer or policy number column. Please check your file format.");
        setLoading(false);
        return;
      }
      const rows: StatementRow[] = [];
      for (let i = 1; i < lines.length; i++) {
        const values = parseCSVLine(lines[i]);
        if (values.length === 0) continue;
        rows.push({
          id: `row-${i}`,
          customer: customerIdx >= 0 ? values[customerIdx] ?? "" : "",
          policy_number: policyIdx >= 0 ? values[policyIdx] ?? "" : "",
          carrier: carrierIdx >= 0 ? values[carrierIdx] ?? "" : "",
          premium: premiumIdx >= 0 ? parseNumber(values[premiumIdx]) : 0,
          commission: commissionIdx >= 0 ? parseNumber(values[commissionIdx]) : 0,
          effective_date: dateIdx >= 0 ? values[dateIdx] ?? "" : "",
          matched: false,
        });
      }
      setUploadedRows(rows);
      setSuccess(`Loaded ${rows.length} transactions from file.`);
    } catch (err) {
      setError("Failed to parse file. Please check the format.");
    }
    setLoading(false);
  }, []);

  // Drag handlers
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };
  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };
  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      await parseAndLoadFile(files[0]);
    }
  };

  // Parse CSV file (file input change)
  const handleFileUpload = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      await parseAndLoadFile(file);
      // Reset input
      event.target.value = "";
    },
    [parseAndLoadFile]
  );

  // Find matching policies for a statement row
  const findMatches = useCallback(
    async (row: StatementRow) => {
      if (!user?.email) return;

      setSelectedRow(row);
      setMatchCandidates([]);

      // Search for potential matches (use legacy DB column names)
      let query = supabase
        .from("policies")
        .select("*")
        .eq("user_email", user.email)
        .limit(20);

      // Try to match by policy number first
      if (row.policy_number) {
        query = query.ilike("Policy Number", `%${row.policy_number}%`);
      } else if (row.customer) {
        query = query.ilike("Customer", `%${row.customer}%`);
      }

      const { data, error } = await query;

      if (error || !data) {
        setMatchCandidates([]);
        return;
      }

      // Score candidates (map legacy column names)
      const scored: MatchCandidate[] = data.map((policy: any) => {
        let score = 0;
        const policyNumber = policy["Policy Number"] || policy.policy_number || "";
        const customer = policy["Customer"] || policy.customer || "";
        const carrier = policy["Carrier Name"] || policy.carrier || "";
        const agencyComm = Number(policy["Agency Estimated Comm/Revenue (CRM)"] || policy.agency_estimated_comm || 0);

        // Policy number match (highest weight)
        if (
          row.policy_number &&
          policyNumber.toLowerCase().includes(row.policy_number.toLowerCase())
        ) {
          score += 50;
        }

        // Customer name match
        if (
          row.customer &&
          customer.toLowerCase().includes(row.customer.toLowerCase())
        ) {
          score += 30;
        }

        // Carrier match
        if (
          row.carrier &&
          carrier.toLowerCase().includes(row.carrier.toLowerCase())
        ) {
          score += 10;
        }

        // Commission amount within 10%
        const commDiff = Math.abs(agencyComm - row.commission);
        if (row.commission > 0 && commDiff / row.commission < 0.1) {
          score += 10;
        }

        return {
          id: policy._id || policy.id,
          customer,
          policy_number: policyNumber,
          carrier,
          premium_sold: Number(policy["Premium Sold"] || policy.premium_sold || 0),
          agency_estimated_comm: agencyComm,
          effective_date: policy["Effective Date"] || policy.effective_date || "",
          score,
        };
      });

      // Sort by score descending
      scored.sort((a, b) => b.score - a.score);
      setMatchCandidates(scored);
    },
    [user?.email]
  );

  // Confirm a match
  const confirmMatch = useCallback(
    async (policyId: string) => {
      if (!selectedRow || !user) return;

      // Persist match to backend
      try {
        const resp = await fetch('/api/reconciliation/matches', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            statementRowId: selectedRow.id,
            policyId,
            userId: user.id,
            matchedAt: new Date().toISOString(),
          }),
        });

        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          setError(err?.error || 'Failed to save match');
          return;
        }

        // Update local state
        setUploadedRows((prev) =>
          prev.map((row) =>
            row.id === selectedRow.id
              ? { ...row, matched: true, matchedPolicyId: policyId }
              : row
          )
        );

        setSelectedRow(null);
        setMatchCandidates([]);
        setSuccess('Match confirmed!');
      } catch (e: any) {
        setError(e?.message || 'Failed to save match');
      }
    },
    [selectedRow, user]
  );

  // Clear all uploaded data
  const clearData = () => {
    setUploadedRows([]);
    setSelectedRow(null);
    setMatchCandidates([]);
    setError(null);
    setSuccess(null);
  };

  // On upload or user change, fetch any previously persisted matches for these statement rows
  useEffect(() => {
    const fetchMatches = async () => {
      if (!user || uploadedRows.length === 0) return;

      const ids = uploadedRows.map((r) => r.id);
      const { data, error } = await supabase
        .from('reconciliation_matches')
        .select('*')
        .in('statement_row_id', ids)
        .eq('user_id', user.id);

      if (error || !data) return;

      const matchedMap = new Map<string, any>();
      data.forEach((m: any) => matchedMap.set(m.statement_row_id, m));

      setUploadedRows((prev) =>
        prev.map((r) =>
          matchedMap.has(r.id)
            ? { ...r, matched: true, matchedPolicyId: matchedMap.get(r.id).policy_id }
            : r
        )
      );
    };

    fetchMatches();
  }, [uploadedRows.length, user]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4 mb-2">
        <div className="p-4 rounded-2xl bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-primary-hover)] shadow-lg">
          <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" /></svg>
        </div>
        <div>
          <h2 className="text-3xl font-bold text-[var(--foreground)] mb-1">Reconciliation</h2>
          <p className="text-[var(--foreground-muted)]">
            Upload commission statements and match transactions
          </p>
        </div>
      </div>

      {/* Upload Section */}
      <div className="card">
        <div className="mb-6 flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-br from-[var(--accent-secondary)] to-[var(--accent-secondary-hover)] shadow-md">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
          </div>
          <h3 className="text-xl font-bold text-[var(--foreground)]">Upload Statement</h3>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <label
            className={`btn-primary cursor-pointer flex items-center gap-2 ${isDragging ? 'ring-2 ring-[var(--accent-primary)] ring-offset-2' : ''}`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            Choose CSV File
            <input
              type="file"
              accept=".csv,.txt"
              className="hidden"
              onChange={handleFileUpload}
              disabled={loading}
            />
          </label>
          {uploadedRows.length > 0 && (
            <button
              type="button"
              onClick={clearData}
              className="rounded-xl border-2 border-[var(--border-color)] bg-[var(--background)] px-4 py-3 text-sm font-bold text-[var(--foreground)] shadow-lg hover:bg-[var(--background-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:ring-opacity-50 transition-all flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              Clear Data
            </button>
          )}
          {loading && (
            <span className="text-sm text-[var(--foreground-muted)] flex items-center gap-2">
              <span className="animate-pulse">...</span>
              Processing...
            </span>
          )}
        </div>
        <p className="mt-4 text-sm text-[var(--foreground-muted)]">
          Supported columns: customer/insured, policy number, carrier, premium, commission, effective date
        </p>
      </div>

      {/* Messages */}
      {error && (
        <div className="rounded-2xl border-2 border-[var(--error-red)] bg-gradient-to-br from-[var(--background)] to-[var(--background-secondary)] px-6 py-4 text-sm text-[var(--error-red)] shadow-lg flex items-center gap-3">
          <svg className="w-6 h-6 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          <div>
            <p className="font-semibold">Upload Error</p>
            <p className="text-xs opacity-80">{error}</p>
          </div>
        </div>
      )}
      {success && (
        <div className="rounded-2xl border-2 border-[var(--success-green)] bg-gradient-to-br from-[var(--background)] to-[var(--background-secondary)] px-6 py-4 text-sm text-[var(--success-green)] shadow-lg flex items-center gap-3">
          <svg className="w-6 h-6 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          <div>
            <p className="font-semibold">Success</p>
            <p className="text-xs opacity-80">{success}</p>
          </div>
        </div>
      )}

      {/* Summary Stats */}
      {uploadedRows.length > 0 && (
        <div className="grid gap-6 sm:grid-cols-4">
          <div className="card group cursor-pointer hover:scale-105">
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-primary-hover)] shadow-md text-white font-bold text-lg">#</div>
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-[0.3em] text-[var(--accent-primary)] mb-1">Total Rows</p>
                <p className="text-2xl font-bold text-[var(--foreground)] group-hover:text-[var(--accent-primary)] transition-colors">{totalRows}</p>
              </div>
            </div>
            <div className="mt-3 h-2 bg-[var(--border-color)] rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-[var(--accent-primary)] to-[var(--accent-primary-hover)] rounded-full transition-all duration-1000 ease-out" style={{ width: '100%' }}></div>
            </div>
          </div>
          <div className="card group cursor-pointer hover:scale-105">
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-[var(--success-green)] to-green-600 shadow-md">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
              </div>
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-[0.3em] text-[var(--accent-primary)] mb-1">Matched</p>
                <p className="text-2xl font-bold text-[var(--success-green)] group-hover:text-green-600 transition-colors">{matchedRows}</p>
              </div>
            </div>
            <div className="mt-3 h-2 bg-[var(--border-color)] rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-[var(--success-green)] to-green-600 rounded-full transition-all duration-1000 ease-out" style={{ width: totalRows > 0 ? `${(matchedRows / totalRows) * 100}%` : '0%' }}></div>
            </div>
          </div>
          <div className="card group cursor-pointer hover:scale-105">
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-[var(--highlight-amber)] to-orange-500 shadow-md">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              </div>
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-[0.3em] text-[var(--accent-primary)] mb-1">Unmatched</p>
                <p className="text-2xl font-bold text-[var(--highlight-amber)] group-hover:text-orange-500 transition-colors">{unmatchedRows}</p>
              </div>
            </div>
            <div className="mt-3 h-2 bg-[var(--border-color)] rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-[var(--highlight-amber)] to-orange-500 rounded-full transition-all duration-1000 ease-out" style={{ width: totalRows > 0 ? `${(unmatchedRows / totalRows) * 100}%` : '0%' }}></div>
            </div>
          </div>
          <div className="card group cursor-pointer hover:scale-105">
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-[var(--accent-secondary)] to-[var(--accent-secondary-hover)] shadow-md text-white font-bold text-lg">$</div>
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-[0.3em] text-[var(--accent-primary)] mb-1">Total Commission</p>
                <p className="text-2xl font-bold text-[var(--foreground)] group-hover:text-[var(--accent-primary)] transition-colors">{formatCurrency(totalCommission)}</p>
              </div>
            </div>
            <div className="mt-3 h-2 bg-[var(--border-color)] rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-[var(--accent-secondary)] to-[var(--accent-secondary-hover)] rounded-full transition-all duration-1000 ease-out" style={{ width: '100%' }}></div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Grid */}
      {uploadedRows.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Statement Transactions */}
          <div className="card">
            <div className="mb-6 flex items-center gap-3">
              <div className="p-2 rounded-xl bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-primary-hover)] shadow-md">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
              </div>
              <h3 className="text-xl font-bold text-[var(--foreground)]">Statement Transactions</h3>
            </div>
            <div className="max-h-[500px] overflow-auto">
              <table className="table-warm w-full text-sm">
                <thead>
                  <tr>
                    <th className="text-left">Status</th>
                    <th className="text-left">Customer</th>
                    <th className="text-left">Policy #</th>
                    <th className="text-right">Commission</th>
                    <th className="text-left">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {uploadedRows.map((row) => (
                    <tr
                      key={row.id}
                      className={`group ${
                        selectedRow?.id === row.id ? "bg-[var(--accent-primary-hover)] bg-opacity-10" : ""
                      }`}
                    >
                      <td>
                        {row.matched ? (
                          <span className="inline-block rounded-full bg-gradient-to-r from-[var(--success-green)] to-green-600 px-3 py-1 text-xs font-medium text-white shadow-sm">
                            Matched
                          </span>
                        ) : (
                          <span className="inline-block rounded-full bg-gradient-to-r from-[var(--highlight-amber)] to-orange-500 px-3 py-1 text-xs font-medium text-white shadow-sm">
                            Pending
                          </span>
                        )}
                      </td>
                      <td className="font-semibold text-[var(--foreground)]">{row.customer}</td>
                      <td className="text-[var(--foreground-muted)]">{row.policy_number}</td>
                      <td className="text-right text-[var(--accent-primary)] font-semibold">{formatCurrency(row.commission)}</td>
                      <td>
                        {!row.matched && (
                          <button
                            type="button"
                            onClick={() => findMatches(row)}
                            className="text-sm font-medium text-[var(--accent-primary)] hover:text-[var(--accent-primary-hover)] underline transition-colors"
                          >
                            Find Match
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Match Candidates */}
          <div className="card">
            <div className="mb-6 flex items-center gap-3">
              <div className="p-2 rounded-xl bg-gradient-to-br from-[var(--accent-secondary)] to-[var(--accent-secondary-hover)] shadow-md">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
              </div>
              <h3 className="text-xl font-bold text-[var(--foreground)]">
                {selectedRow
                  ? `Matches for: ${selectedRow.customer || selectedRow.policy_number}`
                  : "Select a transaction to find matches"}
              </h3>
            </div>
            <div className="max-h-[500px] overflow-auto">
              {selectedRow && matchCandidates.length === 0 ? (
                <div className="text-center text-[var(--foreground-muted)] py-8">
                  <div className="flex flex-col items-center gap-3">
                    <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                    <div>
                      <p className="font-semibold">No matching policies found</p>
                      <p className="text-xs">Try adjusting search criteria</p>
                    </div>
                  </div>
                </div>
              ) : matchCandidates.length > 0 ? (
                <table className="table-warm w-full text-sm">
                  <thead>
                    <tr>
                      <th className="text-left">Score</th>
                      <th className="text-left">Customer</th>
                      <th className="text-left">Policy #</th>
                      <th className="text-right">Commission</th>
                      <th className="text-left">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {matchCandidates.map((candidate) => (
                      <tr key={candidate.id} className="group">
                        <td>
                          <span
                            className={`inline-block rounded-full px-3 py-1 text-xs font-medium text-white shadow-sm ${
                              candidate.score >= 50
                                ? "bg-gradient-to-r from-[var(--success-green)] to-green-600"
                                : candidate.score >= 30
                                ? "bg-gradient-to-r from-[var(--highlight-amber)] to-orange-500"
                                : "bg-gradient-to-r from-gray-400 to-gray-500"
                            }`}
                          >
                            {candidate.score}
                          </span>
                        </td>
                        <td className="font-semibold text-[var(--foreground)]">{candidate.customer}</td>
                        <td className="text-[var(--foreground-muted)]">{candidate.policy_number}</td>
                        <td className="text-right text-[var(--accent-primary)] font-semibold">{formatCurrency(candidate.agency_estimated_comm || 0)}</td>
                        <td>
                          <button
                            type="button"
                            onClick={() => confirmMatch(candidate.id)}
                            className="rounded-xl bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] px-3 py-1 text-xs font-medium text-white shadow-lg transition-all"
                          >
                            Match
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-center text-[var(--foreground-muted)] py-8">
                  <div className="flex flex-col items-center gap-3">
                    <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" /></svg>
                    <div>
                      <p className="font-semibold">Ready to find matches</p>
                      <p className="text-xs">Click &quot;Find Match&quot; on a transaction to see potential matches</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {uploadedRows.length === 0 && !loading && (
        <div className="card text-center">
          <div className="flex flex-col items-center gap-6">
            <div className="p-6 rounded-full bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-primary-hover)] shadow-lg">
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
            </div>
            <div>
              <h3 className="text-2xl font-bold text-[var(--foreground)] mb-3">
                Upload a Commission Statement
              </h3>
              <p className="text-[var(--foreground-muted)] text-lg">
                Upload a CSV file with your commission statement to start reconciling transactions.
              </p>
            </div>
            <div
              className={`text-center bg-gradient-to-r from-[var(--background)] to-[var(--background-secondary)] p-4 rounded-xl border-2 border-dashed border-[var(--border-color)] ${isDragging ? 'ring-2 ring-[var(--accent-primary)]' : ''}`}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
            >
              <p className="text-sm text-[var(--foreground-muted)]">
                Drag &amp; drop your CSV file or click &quot;Choose CSV File&quot; above
              </p>
            </div>
          </div>
        </div>
      )}

      <footer className="mt-12 border-t-2 border-[var(--border-color)] bg-gradient-to-r from-[var(--background-secondary)] to-[var(--background)] py-8 text-center">
        <div className="flex items-center justify-center gap-2 mb-3">
          <p className="font-bold text-[var(--accent-primary)]">Metro Point Technology</p>
        </div>
        <p className="text-xs text-[var(--foreground-muted)] mb-2">
          <a href="/terms" className="underline hover:text-[var(--accent-primary)] transition-colors">Terms of Service</a> |{' '}
          <a href="/privacy" className="underline hover:text-[var(--accent-primary)] transition-colors">Privacy Policy</a> |{' '}
          &copy; 2026 Metro Point Technology. All rights reserved.
        </p>
        <div className="flex items-center justify-center gap-2">
          <span className="text-sm">&reg;</span>
          <p className="text-xs text-[var(--foreground-subtle)]">Metro Point is a registered trademark</p>
        </div>
      </footer>
    </div>
  );
}

// Helper functions

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === "," && !inQuotes) {
      result.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }

  result.push(current.trim());
  return result;
}

function findColumnIndex(header: string[], candidates: string[]): number {
  for (const candidate of candidates) {
    const idx = header.findIndex(
      (h) => h === candidate || h.includes(candidate)
    );
    if (idx >= 0) return idx;
  }
  return -1;
}

function parseNumber(value: string | undefined): number {
  if (!value) return 0;
  // Remove currency symbols, commas, etc.
  const cleaned = value.replace(/[^0-9.-]/g, "");
  const num = parseFloat(cleaned);
  return isNaN(num) ? 0 : num;
}
