'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Edit2, Calendar, Home, StickyNote, Tag, ChevronDown } from 'lucide-react';

interface LeadProfileProps {
  lead: any;
}

export default function LeadProfile({ lead }: LeadProfileProps) {
  const qualification = lead.qualification || {};
  const [editingField, setEditingField] = useState<string | null>(null);

  const fields = [
    { key: 'budget_max', label: 'Budget', value: qualification.budget_max ? `$${(qualification.budget_max / 1000).toFixed(0)}k` : 'Pending', icon: '💰' },
    { key: 'timeline', label: 'Timeline', value: qualification.timeline_days ? `${qualification.timeline_days} days` : 'Pending', icon: '⏰' },
    { key: 'financing', label: 'Financing', value: qualification.financial_readiness || 'Pending', icon: '🏦' },
    { key: 'deal_breakers', label: 'Deal Breakers', value: qualification.deal_breakers?.join(', ') || 'None specified', icon: '🚫' },
  ];

  const locations = lead.preferences?.location_preferences || [];
  const propertyType = lead.preferences?.property_type || 'Any';

  return (
    <div className="p-4 bg-slate-900 max-h-[240px] overflow-y-auto">
      {/* Info Cards Grid */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        {fields.map((f) => (
          <div key={f.key} className="bg-slate-800 rounded-lg p-3 relative group">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-400">{f.icon} {f.label}</span>
              <button
                onClick={() => setEditingField(editingField === f.key ? null : f.key)}
                className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-500 hover:text-white transition-opacity"
              >
                <Edit2 className="w-3 h-3" />
              </button>
            </div>
            <p className="text-sm font-medium text-white">{f.value}</p>
          </div>
        ))}
      </div>

      {/* Warmth Gauge */}
      <div className="bg-slate-800 rounded-lg p-3 mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-slate-400">Warmth Score</span>
          <span className="text-lg font-bold text-white">{lead.warmth_score}%</span>
        </div>
        <div className="relative h-24 w-24 mx-auto">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="45" fill="none" stroke="#334155" strokeWidth="8" />
            <circle
              cx="50" cy="50" r="45" fill="none"
              stroke={lead.warmth_score >= 80 ? '#ef4444' : lead.warmth_score >= 50 ? '#f59e0b' : '#3b82f6'}
              strokeWidth="8"
              strokeDasharray={`${(lead.warmth_score / 100) * 283} 283`}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-2xl font-bold text-white">{lead.warmth_score}</span>
          </div>
        </div>
      </div>

      {/* Location & Property Type */}
      <div className="flex flex-wrap gap-2 mb-4">
        {locations.map((loc: string, i: number) => (
          <span key={i} className="px-2 py-1 bg-slate-800 rounded-full text-xs text-slate-300">📍 {loc}</span>
        ))}
        <span className="px-2 py-1 bg-slate-800 rounded-full text-xs text-slate-300">🏠 {propertyType}</span>
      </div>

      {/* Quick Actions */}
      <div className="flex gap-2">
        <button className="flex-1 flex items-center justify-center gap-1 py-2 bg-emerald-600 text-white text-xs rounded-lg hover:bg-emerald-700">
          <Calendar className="w-3 h-3" /> Book Viewing
        </button>
        <button className="flex-1 flex items-center justify-center gap-1 py-2 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700">
          <Home className="w-3 h-3" /> Send Listings
        </button>
        <button className="flex-1 flex items-center justify-center gap-1 py-2 bg-slate-700 text-white text-xs rounded-lg hover:bg-slate-600">
          <StickyNote className="w-3 h-3" /> Add Note
        </button>
        <button className="flex-1 flex items-center justify-center gap-1 py-2 bg-amber-600 text-white text-xs rounded-lg hover:bg-amber-700">
          <Tag className="w-3 h-3" /> Stage
        </button>
      </div>
    </div>
  );
}
