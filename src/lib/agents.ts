import { supabase } from "./supabase";

// App-facing type (used by UI components in contacts page)
export type AgentContact = {
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

export type AgentCreateInput = {
  name: string;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  notes?: string | null;
  active?: boolean;
  user_id: string;
};

export type AgentUpdateInput = Partial<Omit<AgentCreateInput, "user_id">>;

// ----- DB schema mapping helpers -----
// The live agents table is actually an agency-membership table with columns:
//   id, agency_id, user_id, name, email, role, is_active, created_at, updated_at
// We map it to the AgentContact shape for the contacts directory UI.

/* eslint-disable @typescript-eslint/no-explicit-any */
function dbRowToAgentContact(row: any): AgentContact {
  return {
    id: row.id,
    name: row.name,
    contact_name: row.name ?? null,
    contact_email: row.email ?? null,
    contact_phone: null, // not stored in agents table
    notes: null,         // not stored in agents table
    active: row.is_active ?? true,
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

export async function getAgents(userId: string) {
  const { data, error } = await supabase
    .from("agents")
    .select("*")
    .eq("user_id", userId)
    .order("name", { ascending: true });

  if (error) {
    return { data: [] as AgentContact[], error: formatError(error) };
  }

  return { data: (data ?? []).map(dbRowToAgentContact), error: null };
}

export async function getAgent(id: string, userId: string) {
  const { data, error } = await supabase
    .from("agents")
    .select("*")
    .eq("id", id)
    .eq("user_id", userId)
    .maybeSingle();

  if (error) {
    return { data: null as AgentContact | null, error: formatError(error) };
  }

  return {
    data: data ? dbRowToAgentContact(data) : null,
    error: null,
  };
}

export async function createAgent(payload: AgentCreateInput) {
  const { data, error } = await supabase
    .from("agents")
    .insert({
      name: payload.name,
      email: payload.contact_email || null,
      is_active: payload.active ?? true,
      user_id: payload.user_id,
    })
    .select("*")
    .single();

  if (error) {
    return { data: null as AgentContact | null, error: formatError(error) };
  }

  return { data: dbRowToAgentContact(data), error: null };
}

export async function updateAgent(
  id: string,
  userId: string,
  updates: AgentUpdateInput
) {
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const dbUpdates: Record<string, any> = {
    updated_at: new Date().toISOString(),
  };
  /* eslint-enable @typescript-eslint/no-explicit-any */

  if (updates.name !== undefined) dbUpdates.name = updates.name;
  if (updates.contact_email !== undefined) dbUpdates.email = updates.contact_email;
  if (updates.active !== undefined) dbUpdates.is_active = updates.active;

  const { data, error } = await supabase
    .from("agents")
    .update(dbUpdates)
    .eq("id", id)
    .eq("user_id", userId)
    .select("*")
    .single();

  if (error) {
    return { data: null as AgentContact | null, error: formatError(error) };
  }

  return { data: dbRowToAgentContact(data), error: null };
}

export async function deleteAgent(id: string, userId: string) {
  const { error } = await supabase
    .from("agents")
    .delete()
    .eq("id", id)
    .eq("user_id", userId);

  if (error) {
    return { error: formatError(error) };
  }

  return { error: null };
}
