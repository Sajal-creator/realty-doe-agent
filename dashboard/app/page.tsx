"use client";

import { TopBar } from "@/components/TopBar";
import { BottomStatusBar } from "@/components/BottomStatusBar";

export default function DashboardPage() {
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-950">
      {/* Top Bar */}
      <TopBar />

      {/* Main 3-Column Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Column 1: Pipeline Panel */}
        <div className="w-80 min-w-[280px] border-r border-slate-800 flex flex-col overflow-hidden">
          <PipelinePanel />
        </div>

        {/* Column 2: Unified Inbox */}
        <div className="flex-1 min-w-[400px] flex flex-col overflow-hidden">
          <UnifiedInbox />
        </div>

        {/* Column 3: Lead Map + Details */}
        <div className="w-96 min-w-[320px] border-l border-slate-800 flex flex-col overflow-hidden">
          <LeadMap />
        </div>
      </div>

      {/* Bottom Status Bar */}
      <BottomStatusBar />
    </div>
  );
}

// ── Placeholder Panels (full implementations to follow) ──

function PipelinePanel() {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-800">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Pipeline
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-3">
        <PipelineColumn title="✨ New" warmth="new" color="text-violet-400" />
        <PipelineColumn title="🔥 Hot" warmth="hot" color="text-emerald-400" />
        <PipelineColumn title="🌤 Warm" warmth="warm" color="text-amber-400" />
        <PipelineColumn title="❄️ Cold" warmth="cold" color="text-blue-400" />
      </div>
    </div>
  );
}

function PipelineColumn({
  title,
  warmth,
  color,
}: {
  title: string;
  warmth: string;
  color: string;
}) {
  return (
    <div className="glass-panel p-3">
      <h3 className={`text-xs font-semibold ${color} uppercase tracking-wider mb-2`}>
        {title}
      </h3>
      <div className="space-y-2">
        <div className="pipeline-card">
          <div className="text-sm text-gray-300">No leads yet</div>
          <div className="text-xs text-gray-500 mt-1">Leads will appear here</div>
        </div>
      </div>
    </div>
  );
}

function UnifiedInbox() {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Inbox
        </h2>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search conversations..."
            className="bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:ring-1 focus:ring-brand/50 w-64"
          />
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center text-gray-500">
        <div className="text-center">
          <div className="text-4xl mb-2">💬</div>
          <p className="text-sm">Select a lead to view conversation</p>
        </div>
      </div>
    </div>
  );
}

function LeadMap() {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-800">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Lead Map
        </h2>
      </div>
      <div className="flex-1 flex items-center justify-center text-gray-500">
        <div className="text-center">
          <div className="text-4xl mb-2">🗺️</div>
          <p className="text-sm">Map will render here</p>
          <p className="text-xs text-gray-600 mt-1">Requires Mapbox token</p>
        </div>
      </div>
    </div>
  );
}
