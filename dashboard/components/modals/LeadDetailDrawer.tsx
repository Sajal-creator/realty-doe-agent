'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  XMarkIcon,
  LockClosedIcon,
  PencilSquareIcon,
  ClockIcon,
  ChatBubbleLeftIcon,
  PhoneIcon,
  EnvelopeIcon,
  UserIcon,
} from '@heroicons/react/24/outline';
import { useDashboardStore } from '@/store/dashboardStore';

interface Lead {
  id: string;
  name: string;
  phone: string;
  email?: string | null;
  source: string;
  lead_stage: string;
  warmth_score: number;
  warmth_tier: string;
  role: string;
  qualification?: Record<string, unknown> | null;
  preferences?: Record<string, unknown> | null;
  assigned_agent_id?: string | null;
  last_activity_at?: string | null;
  created_at: string;
}

interface Activity {
  id: string;
  type: string;
  description: string;
  timestamp: string;
}

interface LeadDetailDrawerProps {
  leadId: string;
  onClose: () => void;
}

export default function LeadDetailDrawer({ leadId, onClose }: LeadDetailDrawerProps) {
  const { updateLead, fetchLeadActivity } = useDashboardStore();
  const [lead, setLead] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [notes, setNotes] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [editField, setEditField] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    role: 'buyer',
    lead_stage: 'DISCOVERY',
    notes: '',
  });

  useEffect(() => {
    // Load lead data
    const loadLead = async () => {
      try {
        const res = await fetch(`/api/leads/${leadId}`);
        const data = await res.json();
        setLead(data);
        setFormData({
          name: data.name,
          phone: data.phone,
          email: data.email ?? '',
          role: data.role,
          lead_stage: data.lead_stage,
          notes: data.notes ?? '',
        });
      } catch {}
    };
    loadLead();

    const loadActivity = async () => {
      const data = await fetchLeadActivity(leadId);
      setActivities(data);
    };
    loadActivity();
  }, [leadId, fetchLeadActivity]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateLead(leadId, formData);
    } finally {
      setIsSaving(false);
    }
  };

  const stageOptions = [
    'DISCOVERY', 'QUALIFYING', 'QUALIFIED', 'BROWSING',
    'SELLER_DISCOVERY', 'SELLER_QUALIFIED', 'VIEWING_SCHEDULED',
    'ESCALATED', 'HUMAN_HIJACKED', 'COLD', 'DO_NOT_CONTACT',
  ];

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'message': return ChatBubbleLeftIcon;
      case 'call': return PhoneIcon;
      case 'email': return EnvelopeIcon;
      default: return ClockIcon;
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex justify-end"
    >
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Drawer */}
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="relative w-full max-w-lg h-full bg-gray-900 border-l border-gray-700 shadow-2xl flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="p-6 border-b border-gray-700/50 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center">
              <UserIcon className="w-5 h-5 text-gray-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">{lead?.name ?? 'Loading...'}</h2>
              <p className="text-xs text-gray-400">
                {lead?.source} · {lead?.warmth_tier}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-800 transition-colors">
            <XMarkIcon className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {/* Profile Form */}
          <div className="p-6 border-b border-gray-700/50 space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
              <PencilSquareIcon className="w-4 h-4" />
              Lead Profile
            </h3>

            {/* Name */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">Full Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData((f) => ({ ...f, name: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Phone */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">Phone</label>
              <input
                type="text"
                value={formData.phone}
                onChange={(e) => setFormData((f) => ({ ...f, phone: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Email */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData((f) => ({ ...f, email: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Role */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">Role</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData((f) => ({ ...f, role: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="buyer">Buyer</option>
                <option value="seller">Seller</option>
                <option value="client">Client</option>
              </select>
            </div>

            {/* Stage */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">Stage</label>
              <select
                value={formData.lead_stage}
                onChange={(e) => setFormData((f) => ({ ...f, lead_stage: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {stageOptions.map((s) => (
                  <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Activity Log */}
          <div className="p-6 border-b border-gray-700/50">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2 mb-4">
              <ClockIcon className="w-4 h-4" />
              Activity Log
            </h3>
            <div className="space-y-3">
              {activities.length === 0 ? (
                <p className="text-sm text-gray-500">No activity recorded yet</p>
              ) : (
                activities.map((activity) => {
                  const Icon = getActivityIcon(activity.type);
                  return (
                    <div key={activity.id} className="flex items-start gap-3">
                      <div className="p-1.5 bg-gray-800 rounded-lg shrink-0">
                        <Icon className="w-3.5 h-3.5 text-gray-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-300">{activity.description}</p>
                        <p className="text-xs text-gray-600 mt-0.5">
                          {new Date(activity.timestamp).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Private Notes */}
          <div className="p-6">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2 mb-3">
              <LockClosedIcon className="w-4 h-4" />
              Private Notes
              <span className="text-xs text-gray-600 font-normal">(Agent only)</span>
            </h3>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData((f) => ({ ...f, notes: e.target.value }))}
              rows={4}
              placeholder="Add private notes about this lead..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
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
              'Save Changes'
            )}
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
  );
}
