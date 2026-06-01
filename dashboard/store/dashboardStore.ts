import { create } from 'zustand';

// ─── Types ───────────────────────────────────────────────────────
export interface Lead {
  id: string;
  name: string;
  phone: string;
  email?: string | null;
  source: string;
  lead_stage: string;
  warmth_score: number;
  warmth_tier: string;
  role: string;
  qualification?: Record<string, unknown> | null;
  preferences?: Record<string, unknown> | null;
  assigned_agent_id?: string | null;
  last_activity_at?: string | null;
  created_at: string;
}

export interface Message {
  id: string;
  session_id: string;
  sender_type: 'LEAD' | 'AI' | 'HUMAN_AGENT' | 'SYSTEM';
  content: string;
  message_type: string;
  timestamp: string;
}

export interface Session {
  id: string;
  lead_id: string;
  agent_id?: string | null;
  status: string;
  conversation_mode: string;
  summary?: string | null;
  lead?: Lead;
  started_at: string;
  ended_at?: string | null;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  message?: string | null;
  lead_id?: string | null;
  lead?: { name: string } | null;
  is_read: boolean;
  created_at: string;
}

export interface AgentProfile {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  status: string;
}

export interface TimeSlot {
  start: string;
  end: string;
  available: boolean;
}

// ─── Store ───────────────────────────────────────────────────────
interface DashboardState {
  // Agent
  agentProfile: AgentProfile | null;
  updateAgentProfile: (data: Partial<AgentProfile>) => Promise<void>;

  // Session
  activeSession: Session | null;
  messages: Message[];
  fetchMessages: (sessionId: string) => Promise<void>;
  sendMessage: (sessionId: string, content: string) => Promise<void>;
  hijackSession: (sessionId: string) => Promise<void>;

  // Notifications
  notifications: Notification[];
  markNotificationRead: (id: string) => void;
  markAllRead: () => void;
  soundEnabled: boolean;
  setSoundEnabled: (enabled: boolean) => void;

  // Leads
  updateLead: (id: string, data: Partial<Lead>) => Promise<void>;
  fetchLeadActivity: (leadId: string) => Promise<Array<{ id: string; type: string; description: string; timestamp: string }>>;

  // Calendar
  availableSlots: TimeSlot[] | null;
  fetchAvailableSlots: (leadId: string, date: string) => Promise<void>;
  bookAppointment: (data: { lead_id: string; scheduled_at: string; property_address?: string }) => Promise<void>;

  // Bulk Messages
  sendBulkMessages: (messages: Array<{ leadId: string; content: string }>) => Promise<void>;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  // Agent
  agentProfile: null,
  updateAgentProfile: async (data) => {
    const res = await fetch('/api/agent/profile', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (res.ok) {
      const updated = await res.json();
      set({ agentProfile: updated });
    }
  },

  // Session
  activeSession: null,
  messages: [],
  fetchMessages: async (sessionId) => {
    try {
      const res = await fetch(`/api/sessions/${sessionId}/messages`);
      if (res.ok) {
        const data = await res.json();
        set({ messages: data });
      }
    } catch {}
  },
  sendMessage: async (sessionId, content) => {
    try {
      const res = await fetch(`/api/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, sender_type: 'HUMAN_AGENT' }),
      });
      if (res.ok) {
        const msg = await res.json();
        set((s) => ({ messages: [...s.messages, msg] }));
      }
    } catch {}
  },
  hijackSession: async (sessionId) => {
    try {
      const res = await fetch(`/api/sessions/${sessionId}/hijack`, { method: 'POST' });
      if (res.ok) {
        const session = await res.json();
        set({ activeSession: session });
      }
    } catch {}
  },

  // Notifications
  notifications: [],
  markNotificationRead: (id) => {
    set((s) => ({
      notifications: s.notifications.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
    }));
    fetch(`/api/notifications/${id}/read`, { method: 'POST' }).catch(() => {});
  },
  markAllRead: () => {
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, is_read: true })),
    }));
    fetch('/api/notifications/read-all', { method: 'POST' }).catch(() => {});
  },
  soundEnabled: true,
  setSoundEnabled: (enabled) => set({ soundEnabled: enabled }),

  // Leads
  updateLead: async (id, data) => {
    const res = await fetch(`/api/leads/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to update lead');
  },
  fetchLeadActivity: async (leadId) => {
    try {
      const res = await fetch(`/api/leads/${leadId}/activity`);
      if (res.ok) return await res.json();
    } catch {}
    return [];
  },

  // Calendar
  availableSlots: null,
  fetchAvailableSlots: async (leadId, date) => {
    try {
      const res = await fetch(`/api/calendar/slots?lead_id=${leadId}&date=${date}`);
      if (res.ok) {
        const data = await res.json();
        set({ availableSlots: data });
      }
    } catch {
      set({ availableSlots: null });
    }
  },
  bookAppointment: async (data) => {
    const res = await fetch('/api/appointments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to book appointment');
  },

  // Bulk Messages
  sendBulkMessages: async (messages) => {
    for (const msg of messages) {
      await fetch(`/api/leads/${msg.leadId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: msg.content }),
      }).catch(() => {});
    }
  },
}));
