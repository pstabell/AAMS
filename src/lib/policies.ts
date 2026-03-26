import { supabase } from "./supabase";

export type Policy = {
  id: string;
  customer: string;
  policy_number: string;
  carrier: string;
  mga: string | null;
  line_of_business: string | null;
  premium_sold: number;
  policy_gross_comm_pct: number;
  agency_estimated_comm: number;
  agent_estimated_comm: number | null;
  agent_paid_amount: number | null;
  transaction_type: string;
  effective_date: string;
  policy_origination_date: string | null;
  expiration_date: string | null;
  statement_date: string | null;
  invoice_number: string | null;
  notes: string | null;
  user_email: string;
  user_id: string;
  created_at: string | null;
  updated_at: string | null;
  // Reconciliation fields
  reconciliation_status?: string | null;
  is_reconciled?: boolean;
};

/**
 * Map a raw Supabase row (which may use legacy column names) to the
 * normalised Policy shape the rest of the app expects.
 */
function mapRowToPolicy(r: any): Policy {
  return {
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
    reconciliation_status: r.reconciliation_status ?? null,
    is_reconciled: r.is_reconciled ?? false,
  };
}

export type PolicyCreateInput = {
  customer: string;
  policy_number: string;
  carrier: string;
  mga?: string | null;
  line_of_business?: string | null;
  premium_sold: number;
  policy_gross_comm_pct: number;
  agency_estimated_comm: number;
  agent_estimated_comm?: number | null;
  agent_paid_amount?: number | null;
  transaction_type: string;
  effective_date: string;
  policy_origination_date?: string | null;
  expiration_date?: string | null;
  statement_date?: string | null;
  invoice_number?: string | null;
  notes?: string | null;
  user_email: string;
  user_id: string;
};

export type PolicyUpdateInput = Partial<
  Omit<PolicyCreateInput, "user_email" | "user_id">
>;

type GetPoliciesParams = {
  userEmail: string;
  search?: string;
  page?: number;
  pageSize?: number;
  orderBy?: keyof Policy;
  orderDirection?: "asc" | "desc";
};

function formatError(error: unknown) {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

// Map normalised order-by keys to actual DB column names
const ORDER_BY_MAP: Record<string, string> = {
  effective_date: "Effective Date",
  customer: "Customer",
  carrier: "Carrier Name",
  policy_number: "Policy Number",
  premium_sold: "Premium Sold",
  transaction_type: "Transaction Type",
};

export async function getPolicies({
  userEmail,
  search,
  page = 1,
  pageSize = 10,
  orderBy = "effective_date",
  orderDirection = "desc",
}: GetPoliciesParams) {
  const from = (page - 1) * pageSize;
  const to = from + pageSize - 1;

  const dbOrderCol = ORDER_BY_MAP[orderBy as string] ?? orderBy as string;

  let query = supabase
    .from("policies")
    .select("*", { count: "exact" })
    .eq("user_email", userEmail)
    .order(dbOrderCol, { ascending: orderDirection === "asc" })
    .range(from, to);

  if (search) {
    const trimmed = search.trim();
    if (trimmed) {
      query = query.or(
        `Customer.ilike.%${trimmed}%,Policy Number.ilike.%${trimmed}%`
      );
    }
  }

  const { data, error, count } = await query;

  if (error) {
    return { data: [] as Policy[], count: 0, error: formatError(error) };
  }

  return {
    data: (data ?? []).map(mapRowToPolicy),
    count: count ?? 0,
    error: null,
  };
}

export async function getPolicy(id: string, userEmail: string) {
  // Try _id first (legacy key), fall back to id
  let { data, error } = await supabase
    .from("policies")
    .select("*")
    .eq("_id", id)
    .eq("user_email", userEmail)
    .maybeSingle();

  if ((error || !data) && !isNaN(Number(id))) {
    // _id is numeric in the legacy DB
  } else if (error) {
    return { data: null as Policy | null, error: formatError(error) };
  }

  if (!data) {
    // Try with 'id' column as fallback
    const res = await supabase
      .from("policies")
      .select("*")
      .eq("id", id)
      .eq("user_email", userEmail)
      .maybeSingle();
    data = res.data;
    error = res.error;
  }

  if (error) {
    return { data: null as Policy | null, error: formatError(error) };
  }

  return { data: data ? mapRowToPolicy(data) : null, error: null };
}

export async function createPolicy(payload: PolicyCreateInput) {
  const { data, error } = await supabase
    .from("policies")
    .insert({
      ...payload,
      agent_estimated_comm: payload.agent_estimated_comm ?? 0,
    })
    .select("*")
    .single();

  if (error) {
    return { data: null as Policy | null, error: formatError(error) };
  }

  return { data: data as Policy, error: null };
}

export async function updatePolicy(
  id: string,
  userEmail: string,
  updates: PolicyUpdateInput
) {
  const { data, error } = await supabase
    .from("policies")
    .update(updates)
    .eq("id", id)
    .eq("user_email", userEmail)
    .select("*")
    .single();

  if (error) {
    return { data: null as Policy | null, error: formatError(error) };
  }

  return { data: data as Policy, error: null };
}

export async function deletePolicy(id: string, userEmail: string) {
  const { error } = await supabase
    .from("policies")
    .delete()
    .eq("id", id)
    .eq("user_email", userEmail);

  if (error) {
    return { error: formatError(error) };
  }

  return { error: null };
}

// Policy Revenue Ledger functions

export type PRLFilters = {
  userEmail: string;
  dateFrom?: string | null;
  dateTo?: string | null;
  carrier?: string | null;
  transactionType?: string | null;
  search?: string | null;
  page?: number;
  pageSize?: number;
};

export type PRLSummary = {
  totalPolicies: number;
  totalPremium: number;
  totalAgencyComm: number;
  totalAgentComm: number;
  totalPaid: number;
  totalBalance: number;
};

export async function getPoliciesForPRL({
  userEmail,
  dateFrom,
  dateTo,
  carrier,
  transactionType,
  search,
  page = 1,
  pageSize = 25,
}: PRLFilters) {
  const from = (page - 1) * pageSize;
  const to = from + pageSize - 1;

  let query = supabase
    .from("policies")
    .select("*", { count: "exact" })
    .eq("user_email", userEmail)
    .order("Effective Date", { ascending: false })
    .range(from, to);

  if (dateFrom) {
    query = query.gte("Effective Date", dateFrom);
  }
  if (dateTo) {
    query = query.lte("Effective Date", dateTo);
  }
  if (carrier) {
    query = query.eq("Carrier Name", carrier);
  }
  if (transactionType) {
    query = query.eq("Transaction Type", transactionType);
  }
  if (search?.trim()) {
    query = query.or(
      `Customer.ilike.%${search.trim()}%,Policy Number.ilike.%${search.trim()}%`
    );
  }

  const { data, error, count } = await query;

  if (error) {
    return { data: [] as Policy[], count: 0, error: formatError(error) };
  }

  return {
    data: (data ?? []).map(mapRowToPolicy),
    count: count ?? 0,
    error: null,
  };
}

export async function getPRLSummary({
  userEmail,
  dateFrom,
  dateTo,
  carrier,
  transactionType,
}: Omit<PRLFilters, "page" | "pageSize" | "search">): Promise<{
  data: PRLSummary | null;
  error: string | null;
}> {
  // Select with legacy column names
  let query = supabase
    .from("policies")
    .select(
      `Premium Sold, Agency Estimated Comm/Revenue (CRM), Agent Estimated Comm $, Agent Paid Amount (STMT)`
    )
    .eq("user_email", userEmail);

  if (dateFrom) {
    query = query.gte("Effective Date", dateFrom);
  }
  if (dateTo) {
    query = query.lte("Effective Date", dateTo);
  }
  if (carrier) {
    query = query.eq("Carrier Name", carrier);
  }
  if (transactionType) {
    query = query.eq("Transaction Type", transactionType);
  }

  const { data, error } = await query;

  if (error) {
    return { data: null, error: formatError(error) };
  }

  const summary: PRLSummary = {
    totalPolicies: data?.length ?? 0,
    totalPremium: 0,
    totalAgencyComm: 0,
    totalAgentComm: 0,
    totalPaid: 0,
    totalBalance: 0,
  };

  (data ?? []).forEach((row: any) => {
    summary.totalPremium += Number(row["Premium Sold"]) || 0;
    summary.totalAgencyComm += Number(row["Agency Estimated Comm/Revenue (CRM)"]) || 0;
    summary.totalAgentComm += Number(row["Agent Estimated Comm $"]) || 0;
    summary.totalPaid += Number(row["Agent Paid Amount (STMT)"]) || 0;
  });

  summary.totalBalance = summary.totalAgentComm - summary.totalPaid;

  return { data: summary, error: null };
}

export async function getDistinctCarriers(
  userEmail: string
): Promise<{ data: string[]; error: string | null }> {
  const { data, error } = await supabase
    .from("policies")
    .select("Carrier Name")
    .eq("user_email", userEmail)
    .not("Carrier Name", "is", null);

  if (error) {
    return { data: [], error: formatError(error) };
  }

  const carriers = [
    ...new Set((data ?? []).map((row: any) => row["Carrier Name"]).filter(Boolean)),
  ].sort();

  return { data: carriers as string[], error: null };
}
