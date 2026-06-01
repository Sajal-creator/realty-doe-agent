/* Shared types for the Real Estate AI CRM Dashboard */

// ──── Enums (mirror backend) ────

export type LeadStage =
  | 'DISCOVERY' | 'QUALIFYING' | 'QUALIFIED' | 'BROWSING'
  | 'SELLER_DISCOVERY' | 'SELLER_QUALIFIED' | 'VIEWING_SCHEDULED'
  | 'ESCALATED' | 'HUMAN_HIJACKED' | 'COLD' | 'DO_NOT_CONTACT';

export type WarmthTier = 'HOT' | 'WARM' | 'COLD';
export type LeadSource = 'FACEBOOK' | 'ZILLOW' | 'QR' | 'ORGANIC' | 'REFERRAL';
export type LeadRole = 'buyer' | 'seller' | 'client';
export type SenderType = 'LEAD' | 'AI' | 'HUMAN_AGENT' | 'SYSTEM';
export type MessageType = 'TEXT' | 'VOICE' | 'IMAGE' | 'FLOW_RESPONSE' | 'TEMPLATE';
export type SessionStatus = 'AI_MANAGED' | 'AGENT_ACTIVE' | 'HUMAN_HIJACKED' | 'CLOSED';
export type ConversationMode = 'AI' | 'AGENT';

// ──── Data Models ────

export interface Lead {
  id: string;
  name: string;
  phone: string;
  email?: string | null;
  source: LeadSource;
  lead_stage: LeadStage;
  warmth_score: number; // 0-100
  warmth_tier: WarmthTier;
  qualification?: QualificationMatrix | null;
  preferences?: LeadPreferences | null;
  assigned_agent_id?: string | null;
  role: LeadRole;
  last_activity_at?: string | null;
  last_message_preview?: string;
  neighborhood?: string;
  lat?: number | null;
  lng?: number | null;
}

export interface QualificationMatrix {
  budget?: number;
  timeline?: string;
  pre_approved?: boolean;
  motivation?: number; // 1-10
  urgency?: number; // 1-10
  decision_authority?: number; // 1-10
  readiness?: number; // 1-10
}

export interface LeadPreferences {
  budget_min?: number;
  budget_max?: number;
  timeline?: string;
  pre_approval?: boolean;
  preferred_locations?: string[];
  deal_breakers?: string[];
  property_type?: string;
  bedrooms_min?: number;
  bathrooms_min?: number;
}

export interface Message {
  id: string;
  session_id: string;
  sender_type: SenderType;
  content: string;
  message_type: MessageType;
  media_url?: string | null;
  metadata?: Record<string, unknown> | null;
  timestamp: string;
}

export interface Session {
  id: string;
  lead_id: string;
  agent_id?: string | null;
  status: SessionStatus;
  conversation_mode: ConversationMode;
  summary?: string | null;
  context_snapshot?: Record<string, unknown> | null;
  started_at: string;
  ended_at?: string | null;
}

export interface Agent {
  id: string;
  name: string;
  email: string;
  avatar_url?: string;
  active_leads: number;
}

// ──── Pipeline Kanban ────

export interface PipelineColumn {
  id: string;
  title: string;
  tier: WarmthTier | 'NEW';
  color: string;
  icon: string;
  leads: Lead[];
}

// ──── Activity Event ────

export interface ActivityEvent {
  id: string;
  lead_id: string;
  type: 'message' | 'stage_change' | 'warmth_change' | 'appointment' | 'note' | 'call';
  description: string;
  timestamp: string;
  message_id?: string;
  metadata?: Record<string, unknown>;
}

// ──── WebSocket Events ────

export interface WSEvent {
  event: string;
  data: unknown;
}

export interface WarmthUpdatedEvent {
  lead_id: string;
  warmth_score: number;
  warmth_tier: WarmthTier;
}

export interface NewMessageEvent {
  message: Message;
  lead_id: string;
}

export interface TypingEvent {
  lead_id: string;
  is_typing: boolean;
}

export interface StageChangedEvent {
  lead_id: string;
  old_stage: LeadStage;
  new_stage: LeadStage;
}
