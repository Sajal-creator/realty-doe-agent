'use client';

import React, { useRef, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Smile, Paperclip, Phone, Bot, User } from 'lucide-react';
import { useStore } from '@/store/useStore';
import { formatTimeAgo, cn } from '@/lib/utils';
import LeadProfile from './LeadProfile';

export default function UnifiedInbox() {
  const { leads, selectedLeadId, conversations, typingUsers, agentMode, addMessage } = useStore();
  const [inputText, setInputText] = useState('');
  const [showProfile, setShowProfile] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  const selectedLead = selectedLeadId ? leads.get(selectedLeadId) : null;
  const messages = selectedLeadId ? conversations.get(selectedLeadId) || [] : [];
  const typing = selectedLeadId ? typingUsers.get(selectedLeadId) : null;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!inputText.trim() || !selectedLeadId) return;
    const msg = {
      id: Date.now().toString(),
      session_id: '',
      sender_type: agentMode === 'AGENT' ? 'HUMAN_AGENT' : 'AI',
      content: inputText,
      message_type: 'TEXT',
      timestamp: new Date().toISOString(),
    };
    addMessage(selectedLeadId, msg);
    setInputText('');
    // TODO: send via API
  };

  if (!selectedLead) {
    return (
      <div className="flex items-center justify-center h-full bg-slate-900">
        <div className="text-center">
          <div className="text-6xl mb-4">💬</div>
          <h3 className="text-lg font-medium text-slate-300">Select a lead from the pipeline</h3>
          <p className="text-sm text-slate-500 mt-1">Choose a conversation to start chatting</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-slate-900">
      {/* Chat Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-emerald-600 flex items-center justify-center text-white font-bold">
            {selectedLead.name?.[0] || '?'}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">{selectedLead.name || selectedLead.phone}</h3>
            <p className="text-xs text-slate-400">
              {selectedLead.warmth_tier === 'HOT' ? '🔥' : selectedLead.warmth_tier === 'WARM' ? '⏳' : '❄️'}
              {' '}{selectedLead.warmth_score}% warmth
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowProfile(!showProfile)}
            className={cn(
              'px-3 py-1.5 text-xs rounded-lg transition-colors',
              showProfile ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            )}
          >
            Profile
          </button>
          <button className="px-3 py-1.5 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700">
            {agentMode === 'AI' ? 'Take Over' : 'Hand Back to AI'}
          </button>
        </div>
      </div>

      {/* Messages */}
      <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn('flex', msg.sender_type === 'LEAD' ? 'justify-start' : 'justify-end')}
          >
            <div
              className={cn(
                'max-w-[75%] px-4 py-2 rounded-2xl text-sm',
                msg.sender_type === 'LEAD' && 'bg-slate-800 text-white rounded-bl-sm',
                msg.sender_type === 'AI' && 'bg-blue-600 text-white rounded-br-sm',
                msg.sender_type === 'HUMAN_AGENT' && 'bg-emerald-600 text-white rounded-br-sm',
                msg.sender_type === 'SYSTEM' && 'bg-transparent text-slate-500 italic text-center text-xs'
              )}
            >
              {msg.sender_type === 'AI' && (
                <span className="inline-block mr-1 px-1 py-0.5 bg-blue-800 rounded text-[10px] font-bold">AI</span>
              )}
              {msg.sender_type === 'HUMAN_AGENT' && (
                <span className="inline-block mr-1 px-1 py-0.5 bg-emerald-800 rounded text-[10px]">👤</span>
              )}
              {msg.content}
              <div className="text-[10px] opacity-50 mt-1 text-right">
                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </motion.div>
        ))}

        {/* Typing indicator */}
        {typing && (typing.ai || typing.agent) && (
          <div className="flex justify-start">
            <div className="bg-slate-800 px-4 py-2 rounded-2xl rounded-bl-sm">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Lead Profile (collapsible) */}
      <AnimatePresence>
        {showProfile && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-slate-700/50 overflow-hidden"
          >
            <LeadProfile lead={selectedLead} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input */}
      <div className="px-4 py-3 border-t border-slate-700/50">
        <div className="flex items-center gap-2">
          <button className="p-2 text-slate-400 hover:text-white">
            <Paperclip className="w-5 h-5" />
          </button>
          <button className="p-2 text-slate-400 hover:text-white">
            <Smile className="w-5 h-5" />
          </button>
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={agentMode === 'AI' ? 'AI is handling this...' : 'Type a message...'}
            disabled={agentMode === 'AI'}
            className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-emerald-500 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={agentMode === 'AI' || !inputText.trim()}
            className="p-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
