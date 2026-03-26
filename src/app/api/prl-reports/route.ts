import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";
import { validateServerSession } from "@/lib/server-auth";
import { calculatePolicyCommission, PolicyCommissionInput } from "@/lib/commission-rules";

export const dynamic = "force-dynamic";

type PRLTransaction = {
  id: string;
  policyNumber: string;
  effectiveDate: string;
  statementMonth: string;
  customer: string;
  carrier: string;
  lineOfBusiness: string;
  transactionType: string;
  status: string;
  premiumSold: number;
  agencyCommission: number;
  agentCommission: number;
  paidAmount: number;
  balance: number;
  indicator: 'STMT' | 'VOID' | 'END' | 'CAN' | 'OTHER';
};

type PRLPolicy = {
  policyNumber: string;
  customer: string;
  carrier: string;
  lineOfBusiness: string;
  effectiveDate: string;
  lastStatementMonth: string;
  transactionCount: number;
  totalPremium: number;
  totalAgencyComm: number;
  totalAgentComm: number;
  totalPaid: number;
  balance: number;
  hasVoids: boolean;
  hasEndorsements: boolean;
  hasCancellations: boolean;
};

type PRLSummary = {
  totalPolicies: number;
  totalTransactions: number;
  totalPremium: number;
  totalAgencyComm: number;
  totalAgentComm: number;
  totalPaid: number;
  totalBalance: number;
  statementMonths: string[];
  transactionCounts: {
    stmt: number;
    void: number;
    end: number;
    can: number;
    other: number;
  };
};

type ReportParameters = {
  reportGenerated: string;
  reportType: string;
  viewMode: 'aggregated' | 'detailed';
  statementMonth: string | null;
  balanceFilter: 'all' | 'positive' | 'negative' | 'zero';
  totalRecords: number;
  selectedColumns: string[];
  dataAggregation: string;
};

type PRLReportsResponse = {
  viewMode: 'aggregated' | 'detailed';
  summary: PRLSummary;
  transactions?: PRLTransaction[];
  policies?: PRLPolicy[];
  parameters: ReportParameters;
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
};

function normalizeParam(value: string | null) {
  if (!value) return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function addNumber(value: number | null | undefined) {
  return Number(value) || 0;
}

function getTransactionIndicator(
  transactionType: string | null, 
  status: string | null
): 'STMT' | 'VOID' | 'END' | 'CAN' | 'OTHER' {
  const type = (transactionType || '').toLowerCase();
  const stat = (status || '').toLowerCase();
  
  if (stat.includes('void') || type.includes('void')) return 'VOID';
  if (type.includes('cancellation') || type.includes('cancel')) return 'CAN';
  if (type.includes('endorsement') || type.includes('endorse')) return 'END';
  if (type.includes('statement') || type.includes('reconciliation')) return 'STMT';
  return 'OTHER';
}

function formatStatementMonth(date: string | null): string {
  if (!date) return '';
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const dateFrom = normalizeParam(searchParams.get("dateFrom"));
    const dateTo = normalizeParam(searchParams.get("dateTo"));
    const statementMonth = normalizeParam(searchParams.get("statementMonth"));
    const viewMode = (searchParams.get("viewMode") as 'aggregated' | 'detailed') || 'aggregated';
    const balanceFilter = (searchParams.get("balanceFilter") as 'all' | 'positive' | 'negative' | 'zero') || 'all';
    const page = Math.max(1, parseInt(searchParams.get("page") || "1"));
    const limit = Math.min(1000, Math.max(10, parseInt(searchParams.get("limit") || "50")));
    // SECURITY FIX: Get user email from validated session instead of spoofable parameter
    const { user, error: authError } = await validateServerSession(request);
    if (authError || !user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const userEmail = user.email;

    const supabase = createServerClient();

    let query = supabase
      .from("policies")
      .select("*")
      .eq("user_email", userEmail)
      .order("Effective Date", { ascending: false });

    if (dateFrom) {
      query = query.gte("Effective Date", dateFrom);
    }
    if (dateTo) {
      query = query.lte("Effective Date", dateTo);
    }
    if (statementMonth) {
      const yearMonth = statementMonth.split('-');
      if (yearMonth.length === 2) {
        const startDate = `${yearMonth[0]}-${yearMonth[1]}-01`;
        const endDate = new Date(parseInt(yearMonth[0]), parseInt(yearMonth[1]), 0).toISOString().split('T')[0];
        query = query.gte("Effective Date", startDate).lte("Effective Date", endDate);
      }
    }

    const { data, error } = await query;

    if (error) {
      console.error("PRL reports API error:", error);
      return NextResponse.json(
        { error: "Unable to load PRL reports data." },
        { status: 500 }
      );
    }

    // Process raw data into transactions with commission calculation
    const allTransactions: PRLTransaction[] = [];

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for (const row of (data || []) as any[]) {
      // Map legacy column names to normalised names
      const policyNumber = row["Policy Number"] ?? row.policy_number ?? '';
      const effectiveDate = row["Effective Date"] ?? row.effective_date ?? '';
      const customerName = row["Customer"] ?? row.customer ?? '';
      const carrierName = row["Carrier Name"] ?? row.carrier ?? 'Unknown';
      const lineOfBusiness = row["Policy Type"] ?? row.line_of_business ?? 'Unspecified';
      const transactionType = row["Transaction Type"] ?? row.transaction_type ?? '';
      const policyOriginationDate = row["Policy Origination Date"] ?? row.policy_origination_date ?? effectiveDate;
      const rowId = row._id ?? row.id;

      const premium = addNumber(row["Premium Sold"] ?? row.premium_sold);
      const paid = addNumber(row["Agent Paid Amount (STMT)"] ?? row.agent_paid_amount);

      // Use stored values as fallback, but prefer calculated values
      let agencyComm = addNumber(row["Agency Estimated Comm/Revenue (CRM)"] ?? row.agency_estimated_comm);
      let agentComm = addNumber(row["Agent Estimated Comm $"] ?? row.agent_estimated_comm);

      // Calculate commission using rules engine if we have sufficient data
      if (premium > 0 && transactionType) {
        const commissionInput: PolicyCommissionInput = {
          premiumSold: premium,
          policyGrossCommPct: agencyComm > 0 ? (agencyComm / premium) * 100 : 10,
          transactionType: transactionType,
          carrier: carrierName,
          policyOriginationDate: policyOriginationDate,
          effectiveDate: effectiveDate,
          agentPaidAmount: paid,
          userId: user.id,
          policyId: rowId,
          agentId: row.agent_id,
          carrierId: row.carrier_id,
        };

        try {
          const { data: commissionResult, error: commissionError } = await calculatePolicyCommission(commissionInput);

          if (!commissionError && commissionResult) {
            agencyComm = commissionResult.agencyCommission;
            agentComm = commissionResult.agentCommission;
          }
        } catch (error) {
          console.warn(`Commission calculation failed for policy ${policyNumber}:`, error);
          // Fall back to stored values
        }
      }

      allTransactions.push({
        id: rowId,
        policyNumber,
        effectiveDate,
        statementMonth: formatStatementMonth(effectiveDate),
        customer: customerName,
        carrier: carrierName,
        lineOfBusiness,
        transactionType,
        status: row.reconciliation_status || '',
        premiumSold: premium,
        agencyCommission: agencyComm,
        agentCommission: agentComm,
        paidAmount: paid,
        balance: agentComm - paid,
        indicator: getTransactionIndicator(transactionType, row.reconciliation_status),
      });
    }

    // Apply balance filter
    let filteredTransactions = allTransactions;
    if (balanceFilter !== 'all') {
      filteredTransactions = allTransactions.filter(t => {
        switch (balanceFilter) {
          case 'positive': return t.balance > 0;
          case 'negative': return t.balance < 0;
          case 'zero': return t.balance === 0;
          default: return true;
        }
      });
    }

    // Calculate summary
    const summary: PRLSummary = {
      totalPolicies: new Set(allTransactions.map(t => t.policyNumber)).size,
      totalTransactions: allTransactions.length,
      totalPremium: allTransactions.reduce((sum, t) => sum + t.premiumSold, 0),
      totalAgencyComm: allTransactions.reduce((sum, t) => sum + t.agencyCommission, 0),
      totalAgentComm: allTransactions.reduce((sum, t) => sum + t.agentCommission, 0),
      totalPaid: allTransactions.reduce((sum, t) => sum + t.paidAmount, 0),
      totalBalance: allTransactions.reduce((sum, t) => sum + t.balance, 0),
      statementMonths: [...new Set(allTransactions.map(t => t.statementMonth))].sort(),
      transactionCounts: {
        stmt: allTransactions.filter(t => t.indicator === 'STMT').length,
        void: allTransactions.filter(t => t.indicator === 'VOID').length,
        end: allTransactions.filter(t => t.indicator === 'END').length,
        can: allTransactions.filter(t => t.indicator === 'CAN').length,
        other: allTransactions.filter(t => t.indicator === 'OTHER').length,
      },
    };

    const reportParameters: ReportParameters = {
      reportGenerated: new Date().toISOString(),
      reportType: 'Policy Revenue Ledger',
      viewMode,
      statementMonth,
      balanceFilter,
      totalRecords: filteredTransactions.length,
      selectedColumns: [], // Will be populated by frontend
      dataAggregation: viewMode === 'aggregated' ? 'By Policy Number' : 'Individual Transactions',
    };

    // Calculate pagination
    const total = filteredTransactions.length;
    const totalPages = Math.ceil(total / limit);
    const offset = (page - 1) * limit;

    if (viewMode === 'detailed') {
      // Return paginated transactions
      const paginatedTransactions = filteredTransactions.slice(offset, offset + limit);
      
      return NextResponse.json({
        viewMode: 'detailed',
        summary,
        transactions: paginatedTransactions,
        parameters: reportParameters,
        pagination: { page, limit, total, totalPages },
      } as PRLReportsResponse);

    } else {
      // Aggregate by policy
      const policyMap = new Map<string, PRLPolicy>();
      
      filteredTransactions.forEach(transaction => {
        const existing = policyMap.get(transaction.policyNumber);
        if (existing) {
          existing.transactionCount++;
          existing.totalPremium += transaction.premiumSold;
          existing.totalAgencyComm += transaction.agencyCommission;
          existing.totalAgentComm += transaction.agentCommission;
          existing.totalPaid += transaction.paidAmount;
          existing.balance += transaction.balance;
          existing.hasVoids = existing.hasVoids || transaction.indicator === 'VOID';
          existing.hasEndorsements = existing.hasEndorsements || transaction.indicator === 'END';
          existing.hasCancellations = existing.hasCancellations || transaction.indicator === 'CAN';
          if (transaction.statementMonth > existing.lastStatementMonth) {
            existing.lastStatementMonth = transaction.statementMonth;
          }
        } else {
          policyMap.set(transaction.policyNumber, {
            policyNumber: transaction.policyNumber,
            customer: transaction.customer,
            carrier: transaction.carrier,
            lineOfBusiness: transaction.lineOfBusiness,
            effectiveDate: transaction.effectiveDate,
            lastStatementMonth: transaction.statementMonth,
            transactionCount: 1,
            totalPremium: transaction.premiumSold,
            totalAgencyComm: transaction.agencyCommission,
            totalAgentComm: transaction.agentCommission,
            totalPaid: transaction.paidAmount,
            balance: transaction.balance,
            hasVoids: transaction.indicator === 'VOID',
            hasEndorsements: transaction.indicator === 'END',
            hasCancellations: transaction.indicator === 'CAN',
          });
        }
      });

      const policies = Array.from(policyMap.values());
      const paginatedPolicies = policies.slice(offset, offset + limit);

      return NextResponse.json({
        viewMode: 'aggregated',
        summary,
        policies: paginatedPolicies,
        parameters: reportParameters,
        pagination: { page, limit, total: policies.length, totalPages: Math.ceil(policies.length / limit) },
      } as PRLReportsResponse);
    }

  } catch (err) {
    console.error("PRL reports API unexpected error:", err);
    return NextResponse.json(
      { error: "Unable to load PRL reports data." },
      { status: 500 }
    );
  }
}