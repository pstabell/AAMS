/**
 * Reports Utility Library
 * 
 * Provides data aggregation and export functionality for commission reports.
 */

import { supabase } from "./supabase";
import type { Policy } from "./policies";
import { formatCurrency, formatDate, formatPercent } from "./calculations";

// Report types
export type ReportType = "summary" | "detailed" | "carrier" | "monthly";

export type ReportFilters = {
  userEmail: string;
  agentEmail?: string | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  carrier?: string | null;
  reportType?: ReportType;
};

// Summary stats type
export type SummaryStats = {
  totalPolicies: number;
  totalPremium: number;
  totalAgencyComm: number;
  totalAgentComm: number;
  totalPaid: number;
  totalBalance: number;
  newBusinessCount: number;
  renewalCount: number;
  endorsementCount: number;
  cancellationCount: number;
};

// Carrier breakdown type
export type CarrierBreakdown = {
  carrier: string;
  policyCount: number;
  totalPremium: number;
  totalAgencyComm: number;
  totalAgentComm: number;
  avgCommPct: number;
};

// Monthly breakdown type
export type MonthlyBreakdown = {
  month: string; // YYYY-MM format
  monthLabel: string; // "Jan 2024" format
  policyCount: number;
  totalPremium: number;
  totalAgencyComm: number;
  totalAgentComm: number;
};

// Time period stats type
export type PeriodStats = {
  thisMonth: SummaryStats;
  thisQuarter: SummaryStats;
  yearToDate: SummaryStats;
};

function formatError(error: unknown) {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

/**
 * Get all policies for report generation (no pagination)
 */
export async function getReportPolicies({
  userEmail,
  agentEmail,
  dateFrom,
  dateTo,
  carrier,
}: ReportFilters) {
  let query = supabase
    .from("policies")
    .select("*")
    .order("Effective Date", { ascending: false });

  if (agentEmail !== "__all__") {
    const emailFilter = agentEmail || userEmail;
    query = query.eq("user_email", emailFilter);
  }

  if (dateFrom) {
    query = query.gte("Effective Date", dateFrom);
  }
  if (dateTo) {
    query = query.lte("Effective Date", dateTo);
  }
  if (carrier) {
    query = query.eq("Carrier Name", carrier);
  }

  const { data, error } = await query;

  if (error) {
    return { data: [] as Policy[], error: formatError(error) };
  }

  // Map raw legacy rows to normalised Policy shape
  return {
    data: (data ?? []).map((r: any) => ({
      id: r._id ?? r.id,
      customer: r["Customer"] ?? r.customer ?? "",
      policy_number: r["Policy Number"] ?? r.policy_number ?? "",
      carrier: r["Carrier Name"] ?? r.carrier ?? "",
      mga: r["MGA Name"] ?? r.mga ?? null,
      line_of_business: r["Policy Type"] ?? r.line_of_business ?? null,
      premium_sold: Number(r["Premium Sold"] ?? r.premium_sold ?? 0),
      policy_gross_comm_pct: Number(r["Policy Gross Comm %"] ?? r.policy_gross_comm_pct ?? 0),
      agency_estimated_comm: Number(r["Agency Estimated Comm/Revenue (CRM)"] ?? r.agency_estimated_comm ?? 0),
      agent_estimated_comm: Number(r["Agent Estimated Comm $"] ?? r.agent_estimated_comm ?? 0),
      agent_paid_amount: Number(r["Agent Paid Amount (STMT)"] ?? r.agent_paid_amount ?? 0),
      transaction_type: r["Transaction Type"] ?? r.transaction_type ?? "",
      effective_date: r["Effective Date"] ?? r.effective_date ?? "",
      policy_origination_date: r["Policy Origination Date"] ?? r.policy_origination_date ?? null,
      expiration_date: r["X-DATE"] ?? r.expiration_date ?? null,
      statement_date: r["STMT DATE"] ?? r.statement_date ?? null,
      invoice_number: r.invoice_number ?? null,
      notes: r["NOTES"] ?? r.notes ?? null,
      user_email: r.user_email ?? "",
      user_id: r.user_id ?? "",
      created_at: r.created_at ?? null,
      updated_at: r.updated_at ?? null,
    })) as Policy[],
    error: null,
  };
}

/**
 * Calculate summary statistics from policies
 */
export function calculateSummaryStats(policies: Policy[]): SummaryStats {
  const stats: SummaryStats = {
    totalPolicies: policies.length,
    totalPremium: 0,
    totalAgencyComm: 0,
    totalAgentComm: 0,
    totalPaid: 0,
    totalBalance: 0,
    newBusinessCount: 0,
    renewalCount: 0,
    endorsementCount: 0,
    cancellationCount: 0,
  };

  policies.forEach((policy) => {
    stats.totalPremium += Number(policy.premium_sold) || 0;
    stats.totalAgencyComm += Number(policy.agency_estimated_comm) || 0;
    stats.totalAgentComm += Number(policy.agent_estimated_comm) || 0;
    stats.totalPaid += Number(policy.agent_paid_amount) || 0;

    // Count by transaction type
    const txType = policy.transaction_type?.toUpperCase();
    if (txType === "NEW" || txType === "NBS") {
      stats.newBusinessCount++;
    } else if (txType === "RWL") {
      stats.renewalCount++;
    } else if (txType === "END" || txType === "PCH") {
      stats.endorsementCount++;
    } else if (txType === "CAN") {
      stats.cancellationCount++;
    }
  });

  stats.totalBalance = stats.totalAgentComm - stats.totalPaid;

  return stats;
}

/**
 * Calculate carrier breakdown from policies
 */
export function calculateCarrierBreakdown(policies: Policy[]): CarrierBreakdown[] {
  const carrierMap = new Map<string, { 
    policyCount: number; 
    totalPremium: number; 
    totalAgencyComm: number;
    totalAgentComm: number;
    commPctSum: number;
  }>();

  policies.forEach((policy) => {
    const carrier = policy.carrier || "Unknown";
    const existing = carrierMap.get(carrier) || {
      policyCount: 0,
      totalPremium: 0,
      totalAgencyComm: 0,
      totalAgentComm: 0,
      commPctSum: 0,
    };

    existing.policyCount++;
    existing.totalPremium += Number(policy.premium_sold) || 0;
    existing.totalAgencyComm += Number(policy.agency_estimated_comm) || 0;
    existing.totalAgentComm += Number(policy.agent_estimated_comm) || 0;
    existing.commPctSum += Number(policy.policy_gross_comm_pct) || 0;

    carrierMap.set(carrier, existing);
  });

  const breakdown: CarrierBreakdown[] = [];
  carrierMap.forEach((data, carrier) => {
    breakdown.push({
      carrier,
      policyCount: data.policyCount,
      totalPremium: data.totalPremium,
      totalAgencyComm: data.totalAgencyComm,
      totalAgentComm: data.totalAgentComm,
      avgCommPct: data.policyCount > 0 ? data.commPctSum / data.policyCount : 0,
    });
  });

  // Sort by total premium descending
  return breakdown.sort((a, b) => b.totalPremium - a.totalPremium);
}

/**
 * Calculate monthly breakdown from policies
 */
export function calculateMonthlyBreakdown(policies: Policy[]): MonthlyBreakdown[] {
  const monthMap = new Map<string, {
    policyCount: number;
    totalPremium: number;
    totalAgencyComm: number;
    totalAgentComm: number;
  }>();

  policies.forEach((policy) => {
    if (!policy.effective_date) return;

    const date = new Date(policy.effective_date);
    const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;

    const existing = monthMap.get(monthKey) || {
      policyCount: 0,
      totalPremium: 0,
      totalAgencyComm: 0,
      totalAgentComm: 0,
    };

    existing.policyCount++;
    existing.totalPremium += Number(policy.premium_sold) || 0;
    existing.totalAgencyComm += Number(policy.agency_estimated_comm) || 0;
    existing.totalAgentComm += Number(policy.agent_estimated_comm) || 0;

    monthMap.set(monthKey, existing);
  });

  const breakdown: MonthlyBreakdown[] = [];
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  monthMap.forEach((data, monthKey) => {
    const [year, month] = monthKey.split("-");
    const monthLabel = `${monthNames[parseInt(month) - 1]} ${year}`;

    breakdown.push({
      month: monthKey,
      monthLabel,
      policyCount: data.policyCount,
      totalPremium: data.totalPremium,
      totalAgencyComm: data.totalAgencyComm,
      totalAgentComm: data.totalAgentComm,
    });
  });

  // Sort chronologically
  return breakdown.sort((a, b) => a.month.localeCompare(b.month));
}

/**
 * Get period stats (this month, this quarter, year to date)
 */
export async function getPeriodStats(userEmail: string): Promise<{
  data: PeriodStats | null;
  error: string | null;
}> {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth();
  const currentQuarter = Math.floor(currentMonth / 3);

  // Date ranges
  const thisMonthStart = `${currentYear}-${String(currentMonth + 1).padStart(2, "0")}-01`;
  const thisQuarterStart = `${currentYear}-${String(currentQuarter * 3 + 1).padStart(2, "0")}-01`;
  const ytdStart = `${currentYear}-01-01`;
  const today = now.toISOString().split("T")[0];

  // Fetch all policies for the year
  const { data: policies, error } = await getReportPolicies({
    userEmail,
    dateFrom: ytdStart,
    dateTo: today,
  });

  if (error) {
    return { data: null, error };
  }

  // Filter for each period
  const thisMonthPolicies = policies.filter(
    (p) => p.effective_date && p.effective_date >= thisMonthStart
  );
  const thisQuarterPolicies = policies.filter(
    (p) => p.effective_date && p.effective_date >= thisQuarterStart
  );
  const ytdPolicies = policies; // Already filtered by YTD

  return {
    data: {
      thisMonth: calculateSummaryStats(thisMonthPolicies),
      thisQuarter: calculateSummaryStats(thisQuarterPolicies),
      yearToDate: calculateSummaryStats(ytdPolicies),
    },
    error: null,
  };
}

/**
 * Convert policies to CSV format
 */
export function policiesToCSV(policies: Policy[]): string {
  const headers = [
    "Policy Number",
    "Customer",
    "Carrier",
    "MGA",
    "Line of Business",
    "Transaction Type",
    "Effective Date",
    "Expiration Date",
    "Premium Sold",
    "Gross Comm %",
    "Agency Commission",
    "Agent Commission",
    "Agent Paid",
    "Balance Due",
    "Invoice Number",
    "Statement Date",
    "Notes",
  ];

  const rows = policies.map((p) => [
    p.policy_number || "",
    p.customer || "",
    p.carrier || "",
    p.mga || "",
    p.line_of_business || "",
    p.transaction_type || "",
    p.effective_date || "",
    p.expiration_date || "",
    p.premium_sold?.toString() || "0",
    p.policy_gross_comm_pct?.toString() || "0",
    p.agency_estimated_comm?.toString() || "0",
    p.agent_estimated_comm?.toString() || "0",
    p.agent_paid_amount?.toString() || "0",
    ((p.agent_estimated_comm || 0) - (p.agent_paid_amount || 0)).toString(),
    p.invoice_number || "",
    p.statement_date || "",
    p.notes || "",
  ]);

  // Escape values for CSV
  const escapeCSV = (val: string) => {
    if (val.includes(",") || val.includes('"') || val.includes("\n")) {
      return `"${val.replace(/"/g, '""')}"`;
    }
    return val;
  };

  const csvLines = [
    headers.map(escapeCSV).join(","),
    ...rows.map((row) => row.map(escapeCSV).join(",")),
  ];

  return csvLines.join("\n");
}

/**
 * Convert carrier breakdown to CSV
 */
export function carrierBreakdownToCSV(breakdown: CarrierBreakdown[]): string {
  const headers = [
    "Carrier",
    "Policy Count",
    "Total Premium",
    "Agency Commission",
    "Agent Commission",
    "Avg Comm %",
  ];

  const rows = breakdown.map((b) => [
    b.carrier,
    b.policyCount.toString(),
    b.totalPremium.toFixed(2),
    b.totalAgencyComm.toFixed(2),
    b.totalAgentComm.toFixed(2),
    b.avgCommPct.toFixed(2),
  ]);

  const escapeCSV = (val: string) => {
    if (val.includes(",") || val.includes('"') || val.includes("\n")) {
      return `"${val.replace(/"/g, '""')}"`;
    }
    return val;
  };

  const csvLines = [
    headers.map(escapeCSV).join(","),
    ...rows.map((row) => row.map(escapeCSV).join(",")),
  ];

  return csvLines.join("\n");
}

/**
 * Convert monthly breakdown to CSV
 */
export function monthlyBreakdownToCSV(breakdown: MonthlyBreakdown[]): string {
  const headers = [
    "Month",
    "Policy Count",
    "Total Premium",
    "Agency Commission",
    "Agent Commission",
  ];

  const rows = breakdown.map((b) => [
    b.monthLabel,
    b.policyCount.toString(),
    b.totalPremium.toFixed(2),
    b.totalAgencyComm.toFixed(2),
    b.totalAgentComm.toFixed(2),
  ]);

  const escapeCSV = (val: string) => {
    if (val.includes(",") || val.includes('"') || val.includes("\n")) {
      return `"${val.replace(/"/g, '""')}"`;
    }
    return val;
  };

  const csvLines = [
    headers.map(escapeCSV).join(","),
    ...rows.map((row) => row.map(escapeCSV).join(",")),
  ];

  return csvLines.join("\n");
}

/**
 * Download a file with the given content
 */
export function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
