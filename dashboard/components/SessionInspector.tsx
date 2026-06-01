'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { X, Zap, Bot, User } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SessionInspectorProps {
  session: any;
  onClose: () => void;
  onHijack: (sessionId: string) => void;
}

export default function SessionInspector({ session, onClose, onHijack }: SessionInspectorProps) {
  const messages = session?.messages || [];
  const lead = session?.lead || {};
  const qualification = lead.qualification || {};

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="grid grid-cols-2 gap-4 p-6 bg-slate-900 text-white rounded-xl border border-slate-700 max-h-[80vh]"
    >
      {/* Left Pane: AI Qualification Dashboard */}
      <div className="space-y-4 border-r border-slate-700 pr-4 overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold font-sans">AI Qualification Dashboard</h2>
          <button onClick={onClose} className="p-1 hover:bg-slate-800 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Priority Score */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Overall Priority Match</span>
            <span className="font-bold text-emerald-400">{lead.priorityScore || lead.warmth_score || 0}%</span>
          </div>
          <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-emerald-500"
              initial={{ width: 0 }}
              animate={{ width: `${lead.priorityScore || lead.warmth_score || 0}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>

        {/* Session Summary */}
        <div className="bg-slate-800 p-4 rounded-md">
          <h3 className="text-sm font-semibold text-slate-400 mb-1">⚡ Instant Session Summary</h3>
          <p className="text-sm leading-relaxed">{session.summary || 'AI is calculating summary...'}</p>
        </div>

        {/* 4-D Matrix Grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-slate-800 p-3 rounded">
            <div className="text-slate-400 mb-1">💰 Budget Max</div>
            <div className="text-lg font-bold">${qualification.budget_max ? (qualification.budget_max / 1000).toFixed(0) + 'k' : 'Pending'}</div>
          </div>
          <div className="bg-slate-800 p-3 rounded">
            <div className="text-slate-400 mb-1">🏦 Financing</div>
            <div className="text-lg font-bold">{qualification.financial_readiness || 'Pending'}</div>
          </div>
          <div className="bg-slate-800 p-3 rounded">
            <div className="text-slate-400 mb-1">⏰ Timeline</div>
            <div className="text-lg font-bold">{qualification.timeline_days ? `${qualification.timeline_days}d` : 'Pending'}</div>
          </div>
          <div className="bg-slate-800 p-3 rounded">
            <div className="text-slate-400 mb-1">🚫 Deal Breakers</div>
            <div className="text-sm">{qualification.deal_breakers?.length || 0} set</div>
          </div>
        </div>

        {/* Generate Briefing Button */}
        <button className="w-full py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 text-sm font-medium">
          🧠 Generate Instant Briefing
        </button>
      </div>

      {/* Right Pane: Live Chat Stream */}
      <div className="flex flex-col">
        <div className="flex justify-between items-center pb-2 border-b border-slate-700">
          <span className="text-sm text-emerald-400 flex items-center gap-1">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            Live Conversation Stream
          </span>
          <button
            onClick={() => onHijack(session.id)}
            className="px-3 py-1.5 bg-red-600 text-white text-xs rounded-lg hover:bg-red-700 font-medium"
          >
            🚨 Hijack Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto my-2 space-y-2">
          {messages.map((msg: any) => (
            <div
              key={msg.id}
              className={cn(
                'p-2 max-w-[80%] rounded-lg text-sm',
                msg.sender_type === 'LEAD' ? 'bg-slate-800 mr-auto' : 'bg-blue-600 ml-auto'
              )}
            >
              <p className="text-xs font-semibold text-slate-400 mb-0.5">
                {msg.sender_type === 'LEAD' ? '👤 Lead' : msg.sender_type === 'AI' ? '🤖 AI' : '🧑‍💼 Agent'}
              </p>
              <p>{msg.content}</p>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
