/**
 * Global Zustand store for the Realty Doe CRM dashboard.
 * Manages all app state: leads, conversations, pipeline, notifications, UI state.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import type { Lead, Message, Notification } from "@/lib/api";

// ── Types ──────────────────────────────────────────────

export type Warmth = "hot" | "warm" | "cold" | "new";
export type AgentMode = "AI" | "AGENT";
export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

export interface Conversation {
  leadId: string;
  messages: Message[];
  lastMessage?: Message;
  unreadCount: number;
}

export interface MapViewState {
  latitude: number;
  longitude: number;
  zoom: number;
}

export interface Filters {
  warmth?: Warmth | "all";
  stage?: string;
  search?: string;
  dateRange?: { from: Date; to: Date };
}

export interface TypingUser {
  leadId: string;
  isTyping: boolean;
  timestamp: number;
}

// ── Store Shape ────────────────────────────────────────

interface DashboardState {
  // Leads
  leads: Map<string, Lead>;
  selectedLeadId: string | null;

  // Pipeline
  pipelineNew: string[];
  pipelineHot: string[];
  pipelineWarm: string[];
  pipelineCold: string[];

  // Conversations
  conversations: Map<string, Conversation>;
  typingUsers: Map<string, TypingUser>;

  // Agent
  agentMode: AgentMode;

  // Notifications
  notifications: Notification[];

  // Map
  mapViewState: MapViewState;

  // Filters
  filters: Filters;

  // Connection
  connectionStatus: ConnectionStatus;
  lastSyncAt: Date | null;

  // ── Actions ──────────────────────────────────────────
  addLead: (lead: Lead) => void;
  updateLead: (id: string, updates: Partial<Lead>) => void;
  removeLead: (id: string) => void;
  setLeads: (leads: Lead[]) => void;
  selectLead: (id: string | null) => void;

  moveLeadPipeline: (
    leadId: string,
    fromWarmth: Warmth,
    toWarmth: Warmth,
    targetIndex?: number
  ) => void;

  addMessage: (leadId: string, message: Message) => void;
  setMessages: (leadId: string, messages: Message[]) => void;

  setTyping: (leadId: string, isTyping: boolean) => void;
  toggleAgentMode: () => void;
  setAgentMode: (mode: AgentMode) => void;

  addNotification: (notification: Notification) => void;
  markNotificationRead: (id: string) => void;
  setNotifications: (notifications: Notification[]) => void;

  setConnectionStatus: (status: ConnectionStatus) => void;
  updateMapView: (view: Partial<MapViewState>) => void;
  setFilters: (filters: Partial<Filters>) => void;
}

// ── Helper: classify lead into pipeline ────────────────

function pipelineForWarmth(warmth: Warmth): keyof Pick<DashboardState, "pipelineNew" | "pipelineHot" | "pipelineWarm" | "pipelineCold"> {
  const map: Record<Warmth, "pipelineNew" | "pipelineHot" | "pipelineWarm" | "pipelineCold"> = {
    new: "pipelineNew",
    hot: "pipelineHot",
    warm: "pipelineWarm",
    cold: "pipelineCold",
  };
  return map[warmth];
}

// ── Store ──────────────────────────────────────────────

export const useStore = create<DashboardState>()(
  devtools(
    (set, get) => ({
      // ── Initial State ────────────────────────────────
      leads: new Map(),
      selectedLeadId: null,

      pipelineNew: [],
      pipelineHot: [],
      pipelineWarm: [],
      pipelineCold: [],

      conversations: new Map(),
      typingUsers: new Map(),

      agentMode: "AI",

      notifications: [],

      mapViewState: {
        latitude: 37.7749,
        longitude: -122.4194,
        zoom: 10,
      },

      filters: {
        warmth: "all",
      },

      connectionStatus: "disconnected",
      lastSyncAt: null,

      // ── Actions ──────────────────────────────────────

      addLead: (lead) =>
        set((state) => {
          const leads = new Map(state.leads);
          leads.set(lead.id, lead);

          const pipelineKey = pipelineForWarmth(lead.warmth);
          const pipeline = [...state[pipelineKey]];
          if (!pipeline.includes(lead.id)) {
            pipeline.push(lead.id);
          }

          return { leads, [pipelineKey]: pipeline, lastSyncAt: new Date() };
        }),

      updateLead: (id, updates) =>
        set((state) => {
          const leads = new Map(state.leads);
          const existing = leads.get(id);
          if (!existing) return {};

          const updated = { ...existing, ...updates, updatedAt: new Date().toISOString() };
          leads.set(id, updated);

          // If warmth changed, move between pipelines
          const partial: Partial<DashboardState> = { leads };
          if (updates.warmth && updates.warmth !== existing.warmth) {
            const oldKey = pipelineForWarmth(existing.warmth);
            const newKey = pipelineForWarmth(updates.warmth);
            partial[oldKey] = (state[oldKey] as string[]).filter((lid) => lid !== id);
            partial[newKey] = [...(state[newKey] as string[]), id];
          }

          return partial;
        }),

      removeLead: (id) =>
        set((state) => {
          const leads = new Map(state.leads);
          const lead = leads.get(id);
          if (!lead) return {};

          leads.delete(id);
          const pipelineKey = pipelineForWarmth(lead.warmth);
          return {
            leads,
            [pipelineKey]: (state[pipelineKey] as string[]).filter((lid) => lid !== id),
            selectedLeadId: state.selectedLeadId === id ? null : state.selectedLeadId,
          };
        }),

      setLeads: (leadsArray) =>
        set(() => {
          const leads = new Map<string, Lead>();
          const pipelineNew: string[] = [];
          const pipelineHot: string[] = [];
          const pipelineWarm: string[] = [];
          const pipelineCold: string[] = [];

          for (const lead of leadsArray) {
            leads.set(lead.id, lead);
            switch (lead.warmth) {
              case "new": pipelineNew.push(lead.id); break;
              case "hot": pipelineHot.push(lead.id); break;
              case "warm": pipelineWarm.push(lead.id); break;
              case "cold": pipelineCold.push(lead.id); break;
            }
          }

          return { leads, pipelineNew, pipelineHot, pipelineWarm, pipelineCold, lastSyncAt: new Date() };
        }),

      selectLead: (id) => set({ selectedLeadId: id }),

      moveLeadPipeline: (leadId, fromWarmth, toWarmth, targetIndex) =>
        set((state) => {
          const fromKey = pipelineForWarmth(fromWarmth);
          const toKey = pipelineForWarmth(toWarmth);

          const fromList = (state[fromKey] as string[]).filter((id) => id !== leadId);
          const toList = [...(state[toKey] as string[])];

          if (targetIndex !== undefined) {
            toList.splice(targetIndex, 0, leadId);
          } else {
            toList.push(leadId);
          }

          // Update lead warmth
          const leads = new Map(state.leads);
          const lead = leads.get(leadId);
          if (lead) {
            leads.set(leadId, { ...lead, warmth: toWarmth, updatedAt: new Date().toISOString() });
          }

          return { leads, [fromKey]: fromList, [toKey]: toList };
        }),

      addMessage: (leadId, message) =>
        set((state) => {
          const conversations = new Map(state.conversations);
          const existing = conversations.get(leadId) ?? {
            leadId,
            messages: [],
            unreadCount: 0,
          };

          const updated: Conversation = {
            ...existing,
            messages: [...existing.messages, message],
            lastMessage: message,
            unreadCount:
              message.direction === "incoming"
                ? existing.unreadCount + 1
                : existing.unreadCount,
          };

          conversations.set(leadId, updated);
          return { conversations };
        }),

      setMessages: (leadId, messages) =>
        set((state) => {
          const conversations = new Map(state.conversations);
          const existing = conversations.get(leadId);
          const last = messages[messages.length - 1];

          conversations.set(leadId, {
            leadId,
            messages,
            lastMessage: last,
            unreadCount: existing?.unreadCount ?? 0,
          });

          return { conversations };
        }),

      setTyping: (leadId, isTyping) =>
        set((state) => {
          const typingUsers = new Map(state.typingUsers);
          if (isTyping) {
            typingUsers.set(leadId, { leadId, isTyping: true, timestamp: Date.now() });
          } else {
            typingUsers.delete(leadId);
          }
          return { typingUsers };
        }),

      toggleAgentMode: () =>
        set((state) => ({
          agentMode: state.agentMode === "AI" ? "AGENT" : "AI",
        })),

      setAgentMode: (mode) => set({ agentMode: mode }),

      addNotification: (notification) =>
        set((state) => ({
          notifications: [notification, ...state.notifications],
        })),

      markNotificationRead: (id) =>
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
        })),

      setNotifications: (notifications) => set({ notifications }),

      setConnectionStatus: (status) =>
        set({ connectionStatus: status, ...(status === "connected" ? { lastSyncAt: new Date() } : {}) }),

      updateMapView: (view) =>
        set((state) => ({
          mapViewState: { ...state.mapViewState, ...view },
        })),

      setFilters: (filters) =>
        set((state) => ({
          filters: { ...state.filters, ...filters },
        })),
    }),
    { name: "realty-doe-dashboard" }
  )
);
