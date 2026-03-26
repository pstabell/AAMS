import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import {
  calculateSummaryStats,
  calculateCarrierBreakdown,
  calculateMonthlyBreakdown,
} from "@/lib/reports";
import type { Policy } from "@/lib/policies";

const DEMO_EMAIL = "demo@agentcommissiontracker.com";

export const dynamic = "force-dynamic";

function normalizeParam(value: string | null) {
  if (!value) return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export async function GET(request: Request) {
  try {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseAnonKey) {
      return NextResponse.json(
        { error: "Supabase environment variables are missing." },
        { status: 500 }
      );
    }

    const supabase = createClient(supabaseUrl, supabaseAnonKey);

    const { searchParams } = new URL(request.url);
    const dateFrom = normalizeParam(searchParams.get("dateFrom"));
    const dateTo = normalizeParam(searchParams.get("dateTo"));
    const carrier = normalizeParam(searchParams.get("carrier"));
    const agentEmail = normalizeParam(searchParams.get("agentEmail"));

    const emailFilter = agentEmail && agentEmail !== "__all__" ? agentEmail : DEMO_EMAIL;

    let query = supabase
      .from("policies")
      .select("*")
      .eq("user_email", emailFilter);

    if (dateFrom) {
      query = query.gte("effective_date", dateFrom);
    }
    if (dateTo) {
      query = query.lte("effective_date", dateTo);
    }
    if (carrier) {
      query = query.eq("Carrier Name", carrier);
    }

    const { data, error } = await query;

    if (error) {
      console.error("Reports API error:", error);
      return NextResponse.json(
        { error: "Unable to load reports data." },
        { status: 500 }
      );
    }

    // Map raw database records to expected Policy format
    const policies = (data ?? []).map((r: any) => ({
      id: r._id || r.id,
      customer: r["Customer"] || r.customer || "—",
      policy_number: r["Policy Number"] || r.policy_number || "—",
      carrier: r["Carrier Name"] || r.carrier || "—",
      mga: r["MGA Name"] || r.mga || null,
      line_of_business: r["Policy Type"] || r.line_of_business || null,
      premium_sold: Number(r["Premium Sold"] || r.premium_sold || 0),
      policy_gross_comm_pct: Number(r["Policy Gross Comm %"] || r.policy_gross_comm_pct || 0),
      agency_estimated_comm: Number(r["Agent Estimated Comm $"] || r.agency_estimated_comm || 0),
      agent_estimated_comm: Number(r["Agent Estimated Comm $"] || r.agent_estimated_comm || 0),
      agent_paid_amount: Number(r["Agent Paid Amount (STMT)"] || r.agent_paid_amount || 0),
      transaction_type: r["Transaction Type"] || r.transaction_type || "NEW",
      effective_date: r["Effective Date"] || r.effective_date || "",
      policy_origination_date: r["Policy Origination Date"] || r.policy_origination_date || null,
      expiration_date: r["X-DATE"] || r.expiration_date || null,
      statement_date: r["STMT DATE"] || r.statement_date || null,
      user_email: r.user_email || emailFilter,
    })) as Policy[];

    const summary = calculateSummaryStats(policies);
    const carrierBreakdown = calculateCarrierBreakdown(policies);
    const monthlyBreakdown = calculateMonthlyBreakdown(policies);

    return NextResponse.json({
      summary,
      carrierBreakdown,
      monthlyBreakdown,
      policiesCount: policies.length,
    });
  } catch (err) {
    console.error("Reports API unexpected error:", err);
    return NextResponse.json(
      { error: "Unable to load reports data." },
      { status: 500 }
    );
  }
}
