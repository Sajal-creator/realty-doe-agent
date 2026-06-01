'use client';

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, MessageCircle, Calendar, Handshake, MoreVertical } from 'lucide-react';
import { useStore } from '@/store/useStore';
import { formatTimeAgo, getWarmthColor, truncateText } from '@/lib/utils';

const COLUMNS = [
  { key: 'new', label: 'New', icon: '🆕', color: 'text-violet-400' },
  { key: 'hot', label: 'Hot', icon: '🔥', color: 'text-red-400' },
  { key: 'warm', label: 'Warm', icon: '⏳', color: 'text-amber-400' },
  { key: 'cold', label: 'Cold', icon: '❄️', color: 'text-blue-400' },
] as const;

export default function PipelinePanel() {
  const { leads, pipeline, selectLead, selectedLeadId } = useStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCards, setSelectedCards] = useState<Set<string>>(new Set());

  const filteredPipeline = useMemo(() => {
    if (!searchQuery) return pipeline;
    const q = searchQuery.toLowerCase();
    const filterIds = (ids: string[]) =>
      ids.filter((id) => {
        const lead = leads.get(id);
        if (!lead) return false;
        return (
          lead.name?.toLowerCase().includes(q) ||
          lead.phone.includes(q) ||
          lead.preferences?.location_preferences?.some((l: string) => l.toLowerCase().includes(q))
        );
      });
    return {
      new: filterIds(pipeline.new),
      hot: filterIds(pipeline.hot),
      warm: filterIds(pipeline.warm),
      cold: filterIds(pipeline.cold),
    };
  }, [leads, pipeline, searchQuery]);

  const handleCardClick = (leadId: string, e: React.MouseEvent) => {
    if (e.shiftKey) {
      setSelectedCards((prev) => {
        const next = new Set(prev);
        if (next.has(leadId)) next.delete(leadId);
        else next.add(leadId);
        return next;
      });
    } else {
      selectLead(leadId);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border-r border-slate-700/50">
      {/* Search */}
      <div className="p-3 border-b border-slate-700/50">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search leads..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-emerald-500"
          />
        </div>
      </div>

      {/* Columns */}
      <div className="flex-1 overflow-y-auto space-y-4 p-3">
        {COLUMNS.map((col) => {
          const ids = filteredPipeline[col.key] || [];
          return (
            <div key={col.key}>
              <div className="flex items-center justify-between mb-2">
                <h3 className={`text-xs font-semibold uppercase tracking-wider ${col.color}`}>
                  {col.icon} {col.label}
                </h3>
                <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full">
                  {ids.length}
                </span>
              </div>

              <AnimatePresence>
                {ids.length === 0 ? (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-center py-6 text-slate-500 text-xs"
                  >
                    No leads here yet
                  </motion.div>
                ) : (
                  ids.map((id) => {
                    const lead = leads.get(id);
                    if (!lead) return null;
                    const isSelected = selectedLeadId === id;
                    const isMultiSelected = selectedCards.has(id);

                    return (
                      <motion.div
                        key={id}
                        layout
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        onClick={(e) => handleCardClick(id, e)}
                        className={`relative mb-2 p-3 rounded-lg cursor-pointer transition-all border ${
                          isSelected
                            ? 'border-emerald-500 bg-slate-800'
                            : isMultiSelected
                            ? 'border-blue-500 bg-slate-800/80'
                            : 'border-slate-700/50 bg-slate-800/50 hover:border-slate-600'
                        }`}
                      >
                        {/* Lead name & time */}
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-white truncate">
                            {lead.name || lead.phone}
                          </span>
                          <span className="text-xs text-slate-500">
                            {lead.last_activity_at ? formatTimeAgo(lead.last_activity_at) : ''}
                          </span>
                        </div>

                        {/* Last message preview */}
                        <p className="text-xs text-slate-400 mb-2 truncate">
                          {truncateText(lead.last_message || '', 60)}
                        </p>

                        {/* Warmth meter */}
                        <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden mb-2">
                          <motion.div
                            className="h-full rounded-full"
                            style={{ backgroundColor: getWarmthColor(lead.warmth_score) }}
                            initial={{ width: 0 }}
                            animate={{ width: `${lead.warmth_score}%` }}
                            transition={{ duration: 0.3, ease: 'easeOut' }}
                          />
                        </div>

                        {/* Quick actions (hover) */}
                        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 flex gap-1">
                          <button className="p-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-300" title="Open chat">
                            <MessageCircle className="w-3 h-3" />
                          </button>
                          <button className="p-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-300" title="Schedule">
                            <Calendar className="w-3 h-3" />
                          </button>
                          <button className="p-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-300" title="Handover">
                            <Handshake className="w-3 h-3" />
                          </button>
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>

      {/* Bulk actions toolbar */}
      <AnimatePresence>
        {selectedCards.size > 0 && (
          <motion.div
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 50, opacity: 0 }}
            className="p-3 bg-slate-800 border-t border-slate-700 flex gap-2"
          >
            <button className="flex-1 py-1.5 bg-emerald-600 text-white text-xs rounded hover:bg-emerald-700">
              Bulk Message ({selectedCards.size})
            </button>
            <button className="flex-1 py-1.5 bg-slate-700 text-white text-xs rounded hover:bg-slate-600">
              Assign Agent
            </button>
            <button
              onClick={() => setSelectedCards(new Set())}
              className="px-3 py-1.5 text-slate-400 text-xs hover:text-white"
            >
              ✕
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
