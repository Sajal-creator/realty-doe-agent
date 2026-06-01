'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ChevronLeft, ChevronRight, Check, Loader2 } from 'lucide-react';

interface ScheduleModalProps {
  isOpen: boolean;
  onClose: () => void;
  leadName: string;
  propertyAddress: string;
  onConfirm: (date: string, time: string) => void;
}

const TIME_SLOTS = ['9:00 AM', '10:00 AM', '11:00 AM', '1:00 PM', '2:00 PM', '3:00 PM', '4:00 PM', '5:00 PM'];

export default function ScheduleModal({ isOpen, onClose, leadName, propertyAddress, onConfirm }: ScheduleModalProps) {
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [selectedTime, setSelectedTime] = useState<string | null>(null);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [isLoading, setIsLoading] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);

  const daysInMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getDate();
  const firstDay = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1).getDay();

  const handleConfirm = async () => {
    if (!selectedDate || !selectedTime) return;
    setIsLoading(true);
    await onConfirm(selectedDate.toISOString().split('T')[0], selectedTime);
    setIsLoading(false);
    setIsConfirmed(true);
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
          className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-lg p-6"
        >
          {isConfirmed ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 bg-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Viewing Scheduled! 🎉</h3>
              <p className="text-slate-400">
                {leadName} has been confirmed for {selectedDate?.toLocaleDateString()} at {selectedTime}
              </p>
              <p className="text-slate-500 text-sm mt-1">{propertyAddress}</p>
              <button onClick={onClose} className="mt-6 px-6 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700">
                Done
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-white">📅 Schedule Viewing</h3>
                <button onClick={onClose} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
              </div>

              <p className="text-sm text-slate-400 mb-1">Lead: <span className="text-white">{leadName}</span></p>
              <p className="text-sm text-slate-400 mb-4">Property: <span className="text-white">{propertyAddress}</span></p>

              {/* Mini Calendar */}
              <div className="bg-slate-900 rounded-lg p-4 mb-4">
                <div className="flex items-center justify-between mb-3">
                  <button onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1))}>
                    <ChevronLeft className="w-4 h-4 text-slate-400" />
                  </button>
                  <span className="text-sm font-medium text-white">
                    {currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' })}
                  </span>
                  <button onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1))}>
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  </button>
                </div>

                <div className="grid grid-cols-7 gap-1 text-center text-xs">
                  {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((d) => (
                    <div key={d} className="text-slate-500 py-1">{d}</div>
                  ))}
                  {Array.from({ length: firstDay }).map((_, i) => <div key={`empty-${i}`} />)}
                  {Array.from({ length: daysInMonth }).map((_, i) => {
                    const day = i + 1;
                    const date = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), day);
                    const isPast = date < new Date(new Date().setHours(0, 0, 0, 0));
                    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
                    const isSelected = selectedDate?.toDateString() === date.toDateString();

                    return (
                      <button
                        key={day}
                        disabled={isPast || isWeekend}
                        onClick={() => setSelectedDate(date)}
                        className={`py-1.5 rounded text-sm transition-colors ${
                          isSelected ? 'bg-emerald-600 text-white' :
                          isPast || isWeekend ? 'text-slate-600 cursor-not-allowed' :
                          'text-slate-300 hover:bg-slate-700'
                        }`}
                      >
                        {day}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Time Slots */}
              <div className="grid grid-cols-4 gap-2 mb-6">
                {TIME_SLOTS.map((slot) => (
                  <button
                    key={slot}
                    onClick={() => setSelectedTime(slot)}
                    className={`py-2 rounded-lg text-xs font-medium transition-colors ${
                      selectedTime === slot ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    {slot}
                  </button>
                ))}
              </div>

              {/* Confirm */}
              <button
                onClick={handleConfirm}
                disabled={!selectedDate || !selectedTime || isLoading}
                className="w-full py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Confirm Viewing
              </button>
            </>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
