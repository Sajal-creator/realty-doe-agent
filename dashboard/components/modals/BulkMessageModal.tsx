'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Send, Eye, Loader2 } from 'lucide-react';

interface BulkMessageModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedLeads: any[];
}

const TOKENS = ['{first_name}', '{neighborhood}', '{budget}', '{property_type}'];

export default function BulkMessageModal({ isOpen, onClose, selectedLeads }: BulkMessageModalProps) {
  const [message, setMessage] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [progress, setProgress] = useState(0);

  const insertToken = (token: string) => {
    setMessage((prev) => prev + token);
  };

  const previewMessage = (lead: any) => {
    return message
      .replace('{first_name}', lead.name?.split(' ')[0] || 'there')
      .replace('{neighborhood}', lead.preferences?.location_preferences?.[0] || 'your area')
      .replace('{budget}', lead.qualification?.budget_max ? `$${(lead.qualification.budget_max / 1000).toFixed(0)}k` : 'your budget')
      .replace('{property_type}', lead.preferences?.property_type || 'home');
  };

  const handleSend = async () => {
    setIsSending(true);
    for (let i = 0; i < selectedLeads.length; i++) {
      setProgress(((i + 1) / selectedLeads.length) * 100);
      await new Promise((r) => setTimeout(r, 200)); // Simulate send delay
    }
    setIsSending(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-2xl p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-white">📤 Bulk Message Composer</h3>
            <button onClick={onClose} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
          </div>

          <p className="text-sm text-slate-400 mb-4">Sending to {selectedLeads.length} leads</p>

          {/* Personalization Tokens */}
          <div className="flex flex-wrap gap-2 mb-3">
            {TOKENS.map((token) => (
              <button
                key={token}
                onClick={() => insertToken(token)}
                className="px-2 py-1 bg-violet-600/20 text-violet-400 border border-violet-600 rounded text-xs hover:bg-violet-600/30"
              >
                {token}
              </button>
            ))}
          </div>

          {/* Message Input */}
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type your message here. Use tokens like {first_name} for personalization..."
            rows={5}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-emerald-500 resize-none mb-4"
          />

          {/* Preview Toggle */}
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="flex items-center gap-1 text-sm text-emerald-400 hover:text-emerald-300 mb-3"
          >
            <Eye className="w-4 h-4" /> {showPreview ? 'Hide' : 'Show'} Preview
          </button>

          {/* Preview */}
          {showPreview && (
            <div className="bg-slate-900 rounded-lg p-4 mb-4 max-h-48 overflow-y-auto space-y-2">
              {selectedLeads.slice(0, 5).map((lead) => (
                <div key={lead.id} className="flex items-start gap-2 text-sm">
                  <span className="text-slate-400 font-medium min-w-[100px]">{lead.name || lead.phone}:</span>
                  <span className="text-white">{previewMessage(lead)}</span>
                </div>
              ))}
              {selectedLeads.length > 5 && (
                <p className="text-xs text-slate-500">...and {selectedLeads.length - 5} more</p>
              )}
            </div>
          )}

          {/* Progress Bar */}
          {isSending && (
            <div className="mb-4">
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-emerald-500 rounded-full"
                  animate={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-xs text-slate-400 mt-1">{Math.round(progress)}% sent</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <button onClick={onClose} className="flex-1 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600">
              Cancel
            </button>
            <button
              onClick={handleSend}
              disabled={!message.trim() || isSending}
              className="flex-1 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Send to {selectedLeads.length} Leads
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
