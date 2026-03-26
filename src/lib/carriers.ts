import { supabase } from "./supabase";

// App-facing type (used by UI components)
export type Carrier = {
  id: string;
  name: string;
  code: string;
  contact_name?: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  website: string | null;
  notes: string | null;
  active: boolean;
  user_id: string;
  created_at: string;
  updated_at: string;
};

export type CarrierCreateInput = {
  name: string;
  code: string;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  website?: string | null;
  notes?: string | null;
  active?: boolean;
  user_id: string;
};

export type CarrierUpdateInput = Partial<Omit<CarrierCreateInput, "user_id">>;

// ----- DB schema mapping helpers -----
// The live Supabase table uses legacy column names from the original ACT app:
//   carrier_id, carrier_name, naic_code, producer_code, parent_company,
//   status ("Active"/"Inactive"), notes, user_email, user_id,
//   created_at, updated_at

/* eslint-disable @typescript-eslint/no-explicit-any */
function dbRowToCarrier(row: any): Carrier {
  return {
    id: row.carrier_id,
    name: row.carrier_name,
    code: row.producer_code ?? row.naic_code ?? "",
    contact_name: row.parent_company ?? null,
    contact_email: null, // not stored in legacy schema
    contact_phone: null, // not stored in legacy schema
    website: null,       // not stored in legacy schema
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

export async function getCarriers(userId: string) {
  const { data, error } = await supabase
    .from("carriers")
    .select("*")
    .eq("user_id", userId)
    .order("carrier_name", { ascending: true });

  if (error) {
    return { data: [] as Carrier[], error: formatError(error) };
  }

  return { data: (data ?? []).map(dbRowToCarrier), error: null };
}

export async function getCarrier(id: string, userId: string) {
  const { data, error } = await supabase
    .from("carriers")
    .select("*")
    .eq("carrier_id", id)
    .eq("user_id", userId)
    .maybeSingle();

  if (error) {
    return { data: null as Carrier | null, error: formatError(error) };
  }

  return {
    data: data ? dbRowToCarrier(data) : null,
    error: null,
  };
}

export async function createCarrier(payload: CarrierCreateInput) {
  const { data, error } = await supabase
    .from("carriers")
    .insert({
      carrier_name: payload.name,
      producer_code: payload.code || null,
      parent_company: payload.contact_name || null,
      status: (payload.active ?? true) ? "Active" : "Inactive",
      notes: payload.notes || null,
      user_id: payload.user_id,
    })
    .select("*")
    .single();

  if (error) {
    return { data: null as Carrier | null, error: formatError(error) };
  }

  return { data: dbRowToCarrier(data), error: null };
}

export async function updateCarrier(
  id: string,
  userId: string,
  updates: CarrierUpdateInput
) {
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const dbUpdates: Record<string, any> = {
    updated_at: new Date().toISOString(),
  };
  /* eslint-enable @typescript-eslint/no-explicit-any */

  if (updates.name !== undefined) dbUpdates.carrier_name = updates.name;
  if (updates.code !== undefined) dbUpdates.producer_code = updates.code;
  if (updates.contact_name !== undefined) dbUpdates.parent_company = updates.contact_name;
  if (updates.notes !== undefined) dbUpdates.notes = updates.notes;
  if (updates.active !== undefined) dbUpdates.status = updates.active ? "Active" : "Inactive";

  const { data, error } = await supabase
    .from("carriers")
    .update(dbUpdates)
    .eq("carrier_id", id)
    .eq("user_id", userId)
    .select("*")
    .single();

  if (error) {
    return { data: null as Carrier | null, error: formatError(error) };
  }

  return { data: dbRowToCarrier(data), error: null };
}

export async function deleteCarrier(id: string, userId: string) {
  const { error } = await supabase
    .from("carriers")
    .delete()
    .eq("carrier_id", id)
    .eq("user_id", userId);

  if (error) {
    return { error: formatError(error) };
  }

  return { error: null };
}
