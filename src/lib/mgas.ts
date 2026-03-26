import { supabase } from "./supabase";

// App-facing type (used by UI components)
export type MGA = {
  id: string;
  name: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  notes: string | null;
  active: boolean;
  user_id: string;
  created_at: string;
  updated_at: string;
};

export type MGACreateInput = {
  name: string;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  notes?: string | null;
  active?: boolean;
  user_id: string;
};

export type MGAUpdateInput = Partial<Omit<MGACreateInput, "user_id">>;

// ----- DB schema mapping helpers -----
// The live Supabase table uses legacy column names from the original ACT app:
//   mga_id, mga_name, contact_info (jsonb), appointment_date,
//   status ("Active"/"Inactive"), notes, user_email, user_id,
//   created_at, updated_at

/* eslint-disable @typescript-eslint/no-explicit-any */
function dbRowToMGA(row: any): MGA {
  const ci = row.contact_info ?? {};
  return {
    id: row.mga_id,
    name: row.mga_name,
    contact_name: ci.contact_name ?? ci.name ?? null,
    contact_email: ci.contact_email ?? ci.email ?? null,
    contact_phone: ci.contact_phone ?? ci.phone ?? null,
    notes: row.notes ?? null,
    active: row.status === "Active",
    user_id: row.user_id,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function formatError(error: unknown) {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null && "message" in error) {
    return (error as { message: string }).message;
  }
  return "Something went wrong. Please try again.";
}

export async function getMGAs(userId: string) {
  const { data, error } = await supabase
    .from("mgas")
    .select("*")
    .eq("user_id", userId)
    .order("mga_name", { ascending: true });

  if (error) {
    return { data: [] as MGA[], error: formatError(error) };
  }

  return { data: (data ?? []).map(dbRowToMGA), error: null };
}

export async function getMGA(id: string, userId: string) {
  const { data, error } = await supabase
    .from("mgas")
    .select("*")
    .eq("mga_id", id)
    .eq("user_id", userId)
    .maybeSingle();

  if (error) {
    return { data: null as MGA | null, error: formatError(error) };
  }

  return {
    data: data ? dbRowToMGA(data) : null,
    error: null,
  };
}

export async function createMGA(payload: MGACreateInput) {
  const contactInfo: Record<string, string> = {};
  if (payload.contact_name) contactInfo.contact_name = payload.contact_name;
  if (payload.contact_email) contactInfo.contact_email = payload.contact_email;
  if (payload.contact_phone) contactInfo.contact_phone = payload.contact_phone;

  const { data, error } = await supabase
    .from("mgas")
    .insert({
      mga_name: payload.name,
      contact_info: contactInfo,
      status: (payload.active ?? true) ? "Active" : "Inactive",
      notes: payload.notes || null,
      user_id: payload.user_id,
    })
    .select("*")
    .single();

  if (error) {
    return { data: null as MGA | null, error: formatError(error) };
  }

  return { data: dbRowToMGA(data), error: null };
}

export async function updateMGA(id: string, userId: string, updates: MGAUpdateInput) {
  // First fetch existing record to merge contact_info
  const { data: existing } = await supabase
    .from("mgas")
    .select("contact_info")
    .eq("mga_id", id)
    .eq("user_id", userId)
    .maybeSingle();

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const dbUpdates: Record<string, any> = {
    updated_at: new Date().toISOString(),
  };
  /* eslint-enable @typescript-eslint/no-explicit-any */

  if (updates.name !== undefined) dbUpdates.mga_name = updates.name;
  if (updates.notes !== undefined) dbUpdates.notes = updates.notes;
  if (updates.active !== undefined) dbUpdates.status = updates.active ? "Active" : "Inactive";

  // Merge contact fields into the contact_info JSON
  if (updates.contact_name !== undefined || updates.contact_email !== undefined || updates.contact_phone !== undefined) {
    const ci = (existing?.contact_info as Record<string, string>) ?? {};
    if (updates.contact_name !== undefined) ci.contact_name = updates.contact_name ?? "";
    if (updates.contact_email !== undefined) ci.contact_email = updates.contact_email ?? "";
    if (updates.contact_phone !== undefined) ci.contact_phone = updates.contact_phone ?? "";
    dbUpdates.contact_info = ci;
  }

  const { data, error } = await supabase
    .from("mgas")
    .update(dbUpdates)
    .eq("mga_id", id)
    .eq("user_id", userId)
    .select("*")
    .single();

  if (error) {
    return { data: null as MGA | null, error: formatError(error) };
  }

  return { data: dbRowToMGA(data), error: null };
}

export async function deleteMGA(id: string, userId: string) {
  const { error } = await supabase
    .from("mgas")
    .delete()
    .eq("mga_id", id)
    .eq("user_id", userId);

  if (error) {
    return { error: formatError(error) };
  }

  return { error: null };
}
