'use client';

import React from 'react';
import { motion } from 'framer-motion';

interface QualificationMatrixProps {
  qualification: any;
  warmthScore: number;
}

export default function QualificationMatrix({ qualification, warmthScore }: QualificationMatrixProps) {
  const dims = [
    {
      label: 'Budget',
      value: qualification?.budget_max ? Math.min((qualification.budget_max / 1000000) * 100, 100) : 0,
      display: qualification?.budget_max ? `$${(qualification.budget_max / 1000).toFixed(0)}k` : 'Pending',
      color: '#10b981',
      icon: '💰',
    },
    {
      label: 'Timeline',
      value: qualification?.timeline_days ? Math.max(100 - (qualification.timeline_days / 365) * 100, 10) : 0,
      display: qualification?.timeline_days ? `${qualification.timeline_days} days` : 'Pending',
      color: '#f59e0b',
      icon: '⏰',
    },
    {
      label: 'Financing',
      value: qualification?.financial_readiness === 'CASH' ? 100
        : qualification?.financial_readiness === 'PRE_APPROVED' ? 85
        : qualification?.financial_readiness === 'IN_PROGRESS' ? 50
        : qualification?.financial_readiness === 'NOT_YET' ? 20
        : 0,
      display: qualification?.financial_readiness || 'Pending',
      color: '#3b82f6',
      icon: '🏦',
    },
    {
      label: 'Intent',
      value: qualification?.deal_breakers?.length ? Math.min(qualification.deal_breakers.length * 25, 100) : 0,
      display: qualification?.deal_breakers?.length ? `${qualification.deal_breakers.length} criteria` : 'Pending',
      color: '#8b5cf6',
      icon: '🎯',
    },
  ];

  const overallScore = warmthScore;

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">4-D Qualification Matrix</h3>
        <div className="flex items-center gap-2">
          <div className="text-2xl font-bold" style={{ color: overallScore >= 80 ? '#ef4444' : overallScore >= 50 ? '#f59e0b' : '#3b82f6' }}>
            {overallScore}
          </div>
          <div className="text-xs text-slate-400">/100</div>
        </div>
      </div>

      <div className="space-y-3">
        {dims.map((dim) => (
          <div key={dim.label}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-400">{dim.icon} {dim.label}</span>
              <span className="text-xs font-medium text-white">{dim.display}</span>
            </div>
            <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: dim.color }}
                initial={{ width: 0 }}
                animate={{ width: `${dim.value}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Tier Badge */}
      <div className="mt-4 text-center">
        <span className={`inline-block px-4 py-1.5 rounded-full text-sm font-bold ${
          overallScore >= 80 ? 'bg-red-600/20 text-red-400 border border-red-600' :
          overallScore >= 50 ? 'bg-amber-600/20 text-amber-400 border border-amber-600' :
          'bg-blue-600/20 text-blue-400 border border-blue-600'
        }`}>
          {overallScore >= 80 ? '🔥 HOT LEAD' : overallScore >= 50 ? '⏳ WARM LEAD' : '❄️ COLD LEAD'}
        </span>
      </div>
    </div>
  );
}
