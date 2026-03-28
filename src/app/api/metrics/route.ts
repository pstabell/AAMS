import { NextRequest, NextResponse } from 'next/server';
import { createServerClient } from '@/lib/supabase';
import { getServerSession } from '@/lib/server-auth';

export async function GET(request: NextRequest) {
  try {
    const session = await getServerSession(request);
    if (!session) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const supabase = createServerClient();

    // Fetch cached metrics
    const { data: metrics } = await supabase
      .from('user_metrics')
      .select('*')
      .eq('user_id', session.id)
      .single();

    // Fetch carrier scores
    const { data: carriers } = await supabase
      .from('carrier_scores')
      .select('*')
      .eq('user_id', session.id)
      .order('overall_score', { ascending: false });

    // Fetch recent alerts (unread first)
    const { data: alerts } = await supabase
      .from('alerts')
      .select('*')
      .eq('user_id', session.id)
      .order('created_at', { ascending: false })
      .limit(10);

    // Fetch trend snapshots (last 12 weeks)
    const { data: trends } = await supabase
      .from('metric_snapshots')
      .select('*')
      .eq('user_id', session.id)
      .order('snapshot_date', { ascending: false })
      .limit(12);

    return NextResponse.json({
      metrics: metrics || {
        policy_retention_rate: null,
        commission_recovery_rate: null,
        avg_days_to_payment: null,
        discrepancy_rate: null,
        book_growth_rate: null,
        total_policies: 0,
        total_premium: 0,
        total_expected_commission: 0,
        total_received_commission: 0,
        total_outstanding: 0,
      },
      carriers: carriers || [],
      alerts: alerts || [],
      trends: (trends || []).reverse(),
    });
  } catch (error) {
    console.error('[Metrics] Error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
