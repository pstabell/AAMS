import { NextRequest, NextResponse } from "next/server";
import { validateServerSession } from "@/lib/server-auth";
import { resolve } from "path";
import { getCarriers, createCarrier, updateCarrier, deleteCarrier } from "@/lib/carriers";
import { supabase } from "@/lib/supabase";

const DEMO_EMAIL = "demo@agentcommissiontracker.com";

async function resolveUserId(request: NextRequest, body?: any): Promise<{ userId: string; error: null } | { userId: null; error: string }> {
  // SECURITY FIX: Validate session instead of trusting spoofable headers
  const { user, error: authError } = await validateServerSession(request);
  if (authError || !user) {
    return { userId: null, error: "Unauthorized" };
  }
  const headerUserId = user.id;
  if (headerUserId) return { userId: headerUserId, error: null };

  const { searchParams } = new URL(request.url);
  const email = String(
    body?.user_email || searchParams.get("user_email") || DEMO_EMAIL
  )
    .trim()
    .toLowerCase();

  const { data, error } = await supabase
    .from("users")
    .select("id, email")
    .ilike("email", email)
    .maybeSingle();

  if (error || !data?.id) return { userId: null, error: "Unable to identify user." };
  return { userId: data.id as string, error: null };
}

export async function GET(request: NextRequest) {
  const { userId, error } = await resolveUserId(request);

  if (error || !userId) {
    return NextResponse.json({ error: error || "Unauthorized" }, { status: 401 });
  }

  const { data, error: fetchError } = await getCarriers(userId);
  if (fetchError) return NextResponse.json({ error: fetchError }, { status: 500 });

  return NextResponse.json({ data });
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { userId, error } = await resolveUserId(request, body);

    if (error || !userId) return NextResponse.json({ error: error || "Unauthorized" }, { status: 401 });
    if (!body?.name) return NextResponse.json({ error: "Name is required." }, { status: 400 });

    const { data, error: createError } = await createCarrier({ ...body, user_id: userId });
    if (createError) return NextResponse.json({ error: createError }, { status: 400 });

    return NextResponse.json({ data }, { status: 201 });
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { userId, error } = await resolveUserId(request, body);
    if (error || !userId) return NextResponse.json({ error: error || "Unauthorized" }, { status: 401 });

    const { id, ...updates } = body ?? {};
    if (!id) return NextResponse.json({ error: "Carrier ID is required" }, { status: 400 });

    const { data, error: updateError } = await updateCarrier(id, userId, updates);
    if (updateError) return NextResponse.json({ error: updateError }, { status: 400 });

    return NextResponse.json({ data });
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }
}

export async function DELETE(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get("id");
  if (!id) return NextResponse.json({ error: "Carrier ID is required" }, { status: 400 });

  const { userId, error } = await resolveUserId(request);
  if (error || !userId) return NextResponse.json({ error: error || "Unauthorized" }, { status: 401 });

  const { error: deleteError } = await deleteCarrier(id, userId);
  if (deleteError) return NextResponse.json({ error: deleteError }, { status: 400 });

  return NextResponse.json({ success: true });
}
