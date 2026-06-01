/**
 * REST API client for the Realty Doe backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001";

interface ApiOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
}

async function apiFetch<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {} } = opts;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });

  if (!res.ok) {
    const errBody = await res.text().catch(() => "");
    throw new Error(`API ${method} ${path} failed (${res.status}): ${errBody}`);
  }

  return res.json() as Promise<T>;
}

// ── Leads ──────────────────────────────────────────────

export interface Lead {
  id: string;
  name: string;
  phone: string;
  email?: string;
  warmth: "hot" | "warm" | "cold" | "new";
  stage: string;
  source?: string;
  budget?: string;
  location?: string;
  notes?: string;
  tags?: string[];
  lastContactAt?: string;
  createdAt: string;
  updatedAt: string;
  lat?: number;
  lng?: number;
  score?: number;
}

export interface Message {
  id: string;
  leadId: string;
  direction: "incoming" | "outgoing" | "system";
  content: string;
  timestamp: string;
  read: boolean;
  type?: "text" | "image" | "audio" | "document";
  mediaUrl?: string;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  leadId?: string;
  read: boolean;
  createdAt: string;
}

export async function fetchLeads(filters?: {
  warmth?: string;
  stage?: string;
  search?: string;
}): Promise<Lead[]> {
  const params = new URLSearchParams();
  if (filters?.warmth) params.set("warmth", filters.warmth);
  if (filters?.stage) params.set("stage", filters.stage);
  if (filters?.search) params.set("search", filters.search);
  const qs = params.toString();
  return apiFetch<Lead[]>(`/api/leads${qs ? `?${qs}` : ""}`);
}

export async function fetchMessages(
  leadId: string,
  opts?: { limit?: number; before?: string }
): Promise<Message[]> {
  const params = new URLSearchParams();
  if (opts?.limit) params.set("limit", String(opts.limit));
  if (opts?.before) params.set("before", opts.before);
  const qs = params.toString();
  return apiFetch<Message[]>(`/api/leads/${leadId}/messages${qs ? `?${qs}` : ""}`);
}

export async function sendMessage(
  leadId: string,
  content: string,
  type: string = "text"
): Promise<Message> {
  return apiFetch<Message>(`/api/leads/${leadId}/messages`, {
    method: "POST",
    body: { content, type },
  });
}

export async function toggleAgentMode(leadId?: string): Promise<{
  mode: "AI" | "AGENT";
  leadId?: string;
}> {
  return apiFetch("/api/agent/mode", {
    method: "POST",
    body: { leadId },
  });
}

export async function bookAppointment(data: {
  leadId: string;
  datetime: string;
  duration?: number;
  notes?: string;
}): Promise<{ id: string; status: string }> {
  return apiFetch("/api/appointments", {
    method: "POST",
    body: data,
  });
}

export async function updateLead(
  leadId: string,
  updates: Partial<Lead>
): Promise<Lead> {
  return apiFetch<Lead>(`/api/leads/${leadId}`, {
    method: "PATCH",
    body: updates,
  });
}

export async function fetchNotifications(): Promise<Notification[]> {
  return apiFetch<Notification[]>("/api/notifications");
}

export async function markNotificationRead(
  notificationId: string
): Promise<void> {
  await apiFetch(`/api/notifications/${notificationId}/read`, {
    method: "POST",
  });
}
