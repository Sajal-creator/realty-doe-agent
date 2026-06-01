"use client";

import { useEffect, useRef, useCallback } from "react";
import { io, Socket } from "socket.io-client";
import { useStore } from "@/store/useStore";
import type { Lead, Message, Notification } from "@/lib/api";

const SOCKET_URL = process.env.NEXT_PUBLIC_WS_URL ?? "http://localhost:3001";

export function useSocket() {
  const socketRef = useRef<Socket | null>(null);

  const {
    addLead,
    updateLead,
    removeLead,
    addMessage,
    setTyping,
    setAgentMode,
    addNotification,
    setConnectionStatus,
    setLeads,
  } = useStore();

  const handleLeadNew = useCallback(
    (lead: Lead) => {
      console.log("[ws] lead.new", lead.id);
      addLead(lead);
    },
    [addLead]
  );

  const handleLeadQualified = useCallback(
    (data: { lead: Lead; score: number }) => {
      console.log("[ws] lead.qualified", data.lead.id, data.score);
      updateLead(data.lead.id, { ...data.lead, score: data.score });
    },
    [updateLead]
  );

  const handleWarmthUpdated = useCallback(
    (data: { leadId: string; warmth: Lead["warmth"]; reason?: string }) => {
      console.log("[ws] lead.warmth_updated", data.leadId, data.warmth);
      updateLead(data.leadId, { warmth: data.warmth });
    },
    [updateLead]
  );

  const handleStageChanged = useCallback(
    (data: { leadId: string; stage: string; previousStage?: string }) => {
      console.log("[ws] lead.stage_changed", data.leadId, data.stage);
      updateLead(data.leadId, { stage: data.stage });
    },
    [updateLead]
  );

  const handleConversationMessage = useCallback(
    (data: { leadId: string; message: Message }) => {
      console.log("[ws] conversation.message", data.leadId, data.message.direction);
      addMessage(data.leadId, data.message);
    },
    [addMessage]
  );

  const handleConversationTyping = useCallback(
    (data: { leadId: string; isTyping: boolean }) => {
      setTyping(data.leadId, data.isTyping);
    },
    [setTyping]
  );

  const handleAgentTakeover = useCallback(
    (data: { leadId: string; mode: "AI" | "AGENT" }) => {
      console.log("[ws] agent.takeover", data.leadId, data.mode);
      setAgentMode(data.mode);
    },
    [setAgentMode]
  );

  const handleHandoverRequest = useCallback(
    (data: { leadId: string; reason: string; urgency: string }) => {
      console.log("[ws] handover.request", data.leadId, data.reason);
      addNotification({
        id: `handover-${data.leadId}-${Date.now()}`,
        type: "handover",
        title: "Human Handover Requested",
        body: `${data.reason} (Urgency: ${data.urgency})`,
        leadId: data.leadId,
        read: false,
        createdAt: new Date().toISOString(),
      });
    },
    [addNotification]
  );

  const handleAppointmentBooked = useCallback(
    (data: { leadId: string; appointmentId: string; datetime: string }) => {
      console.log("[ws] appointment.booked", data.leadId);
      addNotification({
        id: `appt-${data.appointmentId}`,
        type: "appointment",
        title: "Appointment Booked",
        body: `New appointment scheduled for ${new Date(data.datetime).toLocaleString()}`,
        leadId: data.leadId,
        read: false,
        createdAt: new Date().toISOString(),
      });
    },
    [addNotification]
  );

  const handleTicketCreated = useCallback(
    (data: { leadId: string; ticketId: string; subject: string }) => {
      console.log("[ws] ticket.created", data.ticketId);
      addNotification({
        id: `ticket-${data.ticketId}`,
        type: "ticket",
        title: "Support Ticket Created",
        body: data.subject,
        leadId: data.leadId,
        read: false,
        createdAt: new Date().toISOString(),
      });
    },
    [addNotification]
  );

  const handleNurtureSent = useCallback(
    (data: { leadId: string; campaignId: string; channel: string }) => {
      console.log("[ws] nurture.sent", data.leadId, data.channel);
    },
    []
  );

  const handleConnectionStatus = useCallback(
    (status: "connected" | "reconnecting" | "disconnected") => {
      console.log("[ws] connection.status", status);
      setConnectionStatus(status);
    },
    [setConnectionStatus]
  );

  useEffect(() => {
    const socket: Socket = io(SOCKET_URL, {
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: Infinity,
    });

    socketRef.current = socket;

    // Connection events
    socket.on("connect", () => {
      console.log("[ws] Connected:", socket.id);
      handleConnectionStatus("connected");
    });

    socket.on("disconnect", (reason) => {
      console.log("[ws] Disconnected:", reason);
      handleConnectionStatus("disconnected");
    });

    socket.on("reconnect_attempt", () => {
      handleConnectionStatus("reconnecting");
    });

    // Lead events
    socket.on("lead.new", handleLeadNew);
    socket.on("lead.qualified", handleLeadQualified);
    socket.on("lead.warmth_updated", handleWarmthUpdated);
    socket.on("lead.stage_changed", handleStageChanged);

    // Conversation events
    socket.on("conversation.message", handleConversationMessage);
    socket.on("conversation.typing", handleConversationTyping);

    // Agent events
    socket.on("agent.takeover", handleAgentTakeover);
    socket.on("handover.request", handleHandoverRequest);

    // System events
    socket.on("appointment.booked", handleAppointmentBooked);
    socket.on("ticket.created", handleTicketCreated);
    socket.on("nurture.sent", handleNurtureSent);

    return () => {
      socket.removeAllListeners();
      socket.disconnect();
      socketRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return socketRef;
}
