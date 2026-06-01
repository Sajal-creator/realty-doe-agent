'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bell, X, Check, CheckCheck, Flame, Calendar, MessageCircle, AlertTriangle } from 'lucide-react';
import { useStore } from '@/store/useStore';
import { formatTimeAgo } from '@/lib/utils';

const NOTIFICATION_ICONS: Record<string, React.ReactNode> = {
  HANDOVER_REQUEST: <AlertTriangle className="w-4 h-4 text-red-400" />,
  NEW_HOT_LEAD: <Flame className="w-4 h-4 text-orange-400" />,
  APPOINTMENT_BOOKED: <Calendar className="w-4 h-4 text-emerald-400" />,
  TICKET_CREATED: <MessageCircle className="w-4 h-4 text-blue-400" />,
  LEAD_REPLY: <MessageCircle className="w-4 h-4 text-violet-400" />,
};

export default function NotificationPanel() {
  const { notifications, markNotificationRead } = useStore();
  const [isOpen, setIsOpen] = useState(false);
  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="relative">
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-slate-400 hover:text-white transition-colors"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 rounded-full text-[10px] text-white flex items-center justify-center font-bold"
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </motion.span>
        )}
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            className="absolute right-0 top-12 w-80 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
              <h3 className="text-sm font-semibold text-white">Notifications</h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => notifications.forEach((n) => !n.is_read && markNotificationRead(n.id))}
                  className="text-xs text-emerald-400 hover:text-emerald-300"
                >
                  Mark all read
                </button>
                <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* List */}
            <div className="max-h-96 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="py-8 text-center text-slate-500 text-sm">
                  <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  No notifications yet
                </div>
              ) : (
                notifications.slice(0, 20).map((notif) => (
                  <motion.div
                    key={notif.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    onClick={() => markNotificationRead(notif.id)}
                    className={`flex items-start gap-3 px-4 py-3 border-b border-slate-700/50 cursor-pointer hover:bg-slate-700/50 transition-colors ${
                      !notif.is_read ? 'bg-slate-700/20' : ''
                    }`}
                  >
                    <div className="mt-0.5">
                      {NOTIFICATION_ICONS[notif.type] || <Bell className="w-4 h-4 text-slate-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white">{notif.title}</p>
                      <p className="text-xs text-slate-400 truncate">{notif.message}</p>
                      <p className="text-xs text-slate-500 mt-1">{formatTimeAgo(notif.created_at)}</p>
                    </div>
                    {!notif.is_read && (
                      <span className="w-2 h-2 bg-emerald-400 rounded-full mt-2 flex-shrink-0" />
                    )}
                  </motion.div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
