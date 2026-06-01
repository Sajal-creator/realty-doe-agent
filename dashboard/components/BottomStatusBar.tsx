"use client";

import {
  Wifi,
  WifiOff,
  Loader2,
  Bot,
  User,
  Clock,
  Activity,
} from "lucide-react";
import { cn, formatTimeAgo } from "@/lib/utils";
import { useStore } from "@/store/useStore";
import type { ConnectionStatus } from "@/store/useStore";

export function BottomStatusBar() {
  const connectionStatus = useStore((s) => s.connectionStatus);
  const lastSyncAt = useStore((s) => s.lastSyncAt);
  const agentMode = useStore((s) => s.agentMode);
  const leads = useStore((s) => s.leads);

  return (
    <footer className="h-8 border-t border-slate-800 bg-slate-900/60 backdrop-blur-sm flex items-center px-4 text-xs text-gray-500 gap-6 z-40">
      {/* Connection Status */}
      <ConnectionIndicator status={connectionStatus} />

      {/* Last Sync */}
      <div className="flex items-center gap-1.5">
        <Clock className="h-3 w-3" />
        <span>
          {lastSyncAt
            ? `Synced ${formatTimeAgo(lastSyncAt)}`
            : "Not synced"}
        </span>
      </div>

      {/* Lead Count */}
      <div className="flex items-center gap-1.5">
        <Activity className="h-3 w-3" />
        <span>{leads.size} leads</span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Agent Mode */}
      <div
        className={cn(
          "flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium",
          agentMode === "AI"
            ? "bg-brand/10 text-brand"
            : "bg-amber-500/10 text-amber-400"
        )}
      >
        {agentMode === "AI" ? (
          <>
            <Bot className="h-3 w-3" />
            <span>AI Automation</span>
          </>
        ) : (
          <>
            <User className="h-3 w-3" />
            <span>Human Agent</span>
          </>
        )}
      </div>

      {/* Version */}
      <span className="text-gray-600">v0.1.0</span>
    </footer>
  );
}

// ── Connection Indicator ───────────────────────────────

function ConnectionIndicator({ status }: { status: ConnectionStatus }) {
  const config: Record<
    ConnectionStatus,
    { icon: React.ElementType; color: string; label: string; pulse?: boolean }
  > = {
    connected: {
      icon: Wifi,
      color: "text-emerald-400",
      label: "Connected",
      pulse: true,
    },
    reconnecting: {
      icon: Loader2,
      color: "text-amber-400",
      label: "Reconnecting",
    },
    disconnected: {
      icon: WifiOff,
      color: "text-red-400",
      label: "Disconnected",
    },
  };

  const { icon: Icon, color, label, pulse } = config[status];

  return (
    <div className={cn("flex items-center gap-1.5", color)}>
      <span className="relative flex items-center">
        {pulse && (
          <span className="absolute h-2 w-2 rounded-full bg-emerald-400 animate-ping opacity-50" />
        )}
        <Icon
          className={cn(
            "h-3 w-3 relative",
            status === "reconnecting" && "animate-spin"
          )}
        />
      </span>
      <span>{label}</span>
    </div>
  );
}
