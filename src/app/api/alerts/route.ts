import { NextRequest, NextResponse } from 'next/server';
import { createServerClient } from '@/lib/supabase';
import { getServerSession } from '@/lib/server-auth';

// GET: fetch alerts for current user
export async function GET(request: NextRequest) {
  try {
    const session = await getServerSession(request);
    if (!session) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const supabase = createServerClient();
    const { data: alerts } = await supabase
      .from('alerts')
      .select('*')
      .eq('user_id', session.id)
      .order('created_at', { ascending: false })
      .limit(20);

    const unreadCount = (alerts || []).filter(a => !a.is_read).length;

    return NextResponse.json({ alerts: alerts || [], unreadCount });
  } catch (error) {
    console.error('[Alerts] Error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

// PATCH: mark alerts as read
export async function PATCH(request: NextRequest) {
  try {
    const session = await getServerSession(request);
    if (!session) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { alertIds } = await request.json();
    if (!alertIds || !Array.isArray(alertIds)) {
      return NextResponse.json({ error: 'alertIds array required' }, { status: 400 });
    }

    const supabase = createServerClient();
    await supabase
      .from('alerts')
      .update({ is_read: true })
      .in('id', alertIds)
      .eq('user_id', session.id);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('[Alerts] Error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
