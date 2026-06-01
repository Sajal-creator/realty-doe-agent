'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  XMarkIcon,
  UserCircleIcon,
  BellIcon,
  CalendarDaysIcon,
  PhoneIcon,
  MoonIcon,
  SpeakerWaveIcon,
  CheckCircleIcon,
  LinkIcon,
} from '@heroicons/react/24/outline';
import { useDashboardStore } from '@/store/dashboardStore';

interface SettingsModalProps {
  onClose: () => void;
}

export default function SettingsModal({ onClose }: SettingsModalProps) {
  const { agentProfile, updateAgentProfile, soundEnabled, setSoundEnabled } = useDashboardStore();

  const [profile, setProfile] = useState({
    name: agentProfile?.name ?? '',
    email: agentProfile?.email ?? '',
    phone: agentProfile?.phone ?? '',
  });

  const [notifications, setNotifications] = useState({
    NEW_HOT_LEAD: true,
    HANDOVER_REQUEST: true,
    APPOINTMENT_BOOKED: true,
    TICKET_CREATED: true,
    LEAD_REPLY: true,
  });

  const [calendarConnected, setCalendarConnected] = useState(false);
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [darkMode, setDarkMode] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateAgentProfile(profile);
    } finally {
      setIsSaving(false);
    }
  };

  const toggleNotification = (key: string) => {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key as keyof typeof prev] }));
  };

  const notificationLabels: Record<string, string> = {
    NEW_HOT_LEAD: 'New Hot Lead',
    HANDOVER_REQUEST: 'Handover Request',
    APPOINTMENT_BOOKED: 'Appointment Booked',
    TICKET_CREATED: 'Ticket Created',
    LEAD_REPLY: 'Lead Reply',
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="p-6 border-b border-gray-700/50 flex items-center justify-between shrink-0">
          <h2 className="text-lg font-bold text-white">Settings</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-800 transition-colors">
            <XMarkIcon className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto divide-y divide-gray-700/50">
          {/* Agent Profile */}
          <div className="p-6 space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
              <UserCircleIcon className="w-4 h-4" />
              Agent Profile
            </h3>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Name</label>
              <input
                type="text"
                value={profile.name}
                onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Email</label>
              <input
                type="email"
                value={profile.email}
                onChange={(e) => setProfile((p) => ({ ...p, email: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Phone</label>
              <input
                type="text"
                value={profile.phone}
                onChange={(e) => setProfile((p) => ({ ...p, phone: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Notification Preferences */}
          <div className="p-6 space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
              <BellIcon className="w-4 h-4" />
              Notification Preferences
            </h3>
            <div className="space-y-3">
              {Object.entries(notificationLabels).map(([key, label]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">{label}</span>
                  <button
                    onClick={() => toggleNotification(key)}
                    className={`relative w-10 h-5 rounded-full transition-colors ${
                      notifications[key as keyof typeof notifications] ? 'bg-blue-600' : 'bg-gray-700'
                    }`}
                  >
                    <motion.div
                      animate={{
                        x: notifications[key as keyof typeof notifications] ? 20 : 2,
                      }}
                      transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                      className="absolute top-0.5 w-4 h-4 bg-white rounded-full"
                    />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Calendar Integration */}
          <div className="p-6 space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
              <CalendarDaysIcon className="w-4 h-4" />
              Calendar Integration
            </h3>
            {calendarConnected ? (
              <div className="flex items-center gap-2 text-sm text-emerald-400">
                <CheckCircleIcon className="w-5 h-5" />
                Google Calendar connected
              </div>
            ) : (
              <button
                onClick={() => setCalendarConnected(true)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-sm text-gray-300 transition-colors"
              >
                <LinkIcon className="w-4 h-4" />
                Connect Google Calendar
              </button>
            )}
          </div>

          {/* WhatsApp Binding */}
          <div className="p-6 space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
              <PhoneIcon className="w-4 h-4" />
              WhatsApp Number
            </h3>
            <input
              type="text"
              value={whatsappNumber}
              onChange={(e) => setWhatsappNumber(e.target.value)}
              placeholder="+1 (555) 000-0000"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Dark Mode */}
          <div className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MoonIcon className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-300">Dark Mode</span>
              </div>
              <button
                onClick={() => setDarkMode(!darkMode)}
                className={`relative w-10 h-5 rounded-full transition-colors ${
                  darkMode ? 'bg-blue-600' : 'bg-gray-700'
                }`}
              >
                <motion.div
                  animate={{ x: darkMode ? 20 : 2 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  className="absolute top-0.5 w-4 h-4 bg-white rounded-full"
                />
              </button>
            </div>
          </div>

          {/* Sound Effects */}
          <div className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <SpeakerWaveIcon className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-300">Sound Effects</span>
              </div>
              <button
                onClick={() => setSoundEnabled(!soundEnabled)}
                className={`relative w-10 h-5 rounded-full transition-colors ${
                  soundEnabled ? 'bg-blue-600' : 'bg-gray-700'
                }`}
              >
                <motion.div
                  animate={{ x: soundEnabled ? 20 : 2 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  className="absolute top-0.5 w-4 h-4 bg-white rounded-full"
                />
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-700/50 shrink-0">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            disabled={isSaving}
            onClick={handleSave}
            className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl font-semibold text-sm transition-colors flex items-center justify-center gap-2"
          >
            {isSaving ? (
              <>
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                  className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
                />
                Saving...
              </>
            ) : (
              'Save Settings'
            )}
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
  );
}
