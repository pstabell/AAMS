import { NextRequest, NextResponse } from 'next/server';
import { stripe } from '@/lib/stripe';
import { createServerClient } from '@/lib/supabase';
import { getServerSession } from '@/lib/server-auth';

export async function POST(request: NextRequest) {
  try {
    const session = await getServerSession(request);
    if (!session) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const supabase = createServerClient();
    const { data: user } = await supabase
      .from('users')
      .select('stripe_customer_id')
      .eq('id', session.id)
      .single();

    if (!user?.stripe_customer_id) {
      return NextResponse.json({ error: 'No billing account found.' }, { status: 400 });
    }

    const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3333';

    const portalSession = await stripe.billingPortal.sessions.create({
      customer: user.stripe_customer_id,
      return_url: `${appUrl}/dashboard/account`,
    });

    return NextResponse.json({ url: portalSession.url });
  } catch (error) {
    console.error('[Billing Portal] Error:', error);
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
