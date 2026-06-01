'use client';

import { Component, ReactNode, useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  WifiIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  MagnifyingGlassIcon,
  RocketLaunchIcon,
  UsersIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

// ─── WebSocket Disconnect Overlay ────────────────────────────────
export function WebSocketOverlay() {
  const [countdown, setCountdown] = useState(10);
  const [isRetrying, setIsRetrying] = useState(false);

  useEffect(() => {
    if (countdown <= 0) {
      setIsRetrying(true);
      // Simulate retry
      setTimeout(() => {
        setCountdown(10);
        setIsRetrying(false);
      }, 2000);
      return;
    }
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-[200] bg-gray-900/95 backdrop-blur-md flex items-center justify-center"
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        className="text-center max-w-md p-8"
      >
        <motion.div
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="inline-flex p-4 bg-amber-900/30 rounded-full mb-6"
        >
          <WifiIcon className="w-10 h-10 text-amber-400" />
        </motion.div>
        <h2 className="text-2xl font-bold text-white mb-2">Connection Lost</h2>
        <p className="text-gray-400 mb-6">
          Unable to reach the server. Retrying in {countdown} seconds...
        </p>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => {
            setCountdown(0);
          }}
          disabled={isRetrying}
          className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl font-semibold text-sm transition-colors"
        >
          {isRetrying ? (
            <>
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
              />
              Retrying...
            </>
          ) : (
            <>
              <ArrowPathIcon className="w-4 h-4" />
              Retry Now
            </>
          )}
        </motion.button>
      </motion.div>
    </motion.div>
  );
}

// ─── API Failure Inline Retry ────────────────────────────────────
interface ApiRetryButtonProps {
  onRetry: () => void;
  message?: string;
}

export function ApiRetryButton({ onRetry, message = 'Failed to load data' }: ApiRetryButtonProps) {
  const [isRetrying, setIsRetrying] = useState(false);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await onRetry();
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <div className="flex items-center gap-3 p-4 bg-red-900/20 border border-red-800/30 rounded-xl">
      <ExclamationTriangleIcon className="w-5 h-5 text-red-400 shrink-0" />
      <span className="text-sm text-red-300 flex-1">{message}</span>
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={handleRetry}
        disabled={isRetrying}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-red-800/30 hover:bg-red-800/50 text-red-300 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
      >
        {isRetrying ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
            className="w-3 h-3 border-2 border-red-400/30 border-t-red-400 rounded-full"
          />
        ) : (
          <ArrowPathIcon className="w-3 h-3" />
        )}
        Retry
      </motion.button>
    </div>
  );
}

// ─── Empty Search Results ────────────────────────────────────────
interface EmptySearchProps {
  query: string;
  onClear: () => void;
}

export function EmptySearchResults({ query, onClear }: EmptySearchProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 px-4"
    >
      <div className="p-4 bg-gray-800 rounded-full mb-4">
        <MagnifyingGlassIcon className="w-8 h-8 text-gray-500" />
      </div>
      <h3 className="text-lg font-semibold text-white mb-1">No results found</h3>
      <p className="text-sm text-gray-400 mb-4 text-center">
        No matches for &ldquo;{query}&rdquo;. Try a different search term.
      </p>
      <button
        onClick={onClear}
        className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
      >
        Clear search
      </button>
    </motion.div>
  );
}

// ─── Zero-State Onboarding ───────────────────────────────────────
interface OnboardingStep {
  title: string;
  description: string;
  icon: React.ElementType;
}

const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    title: 'Connect WhatsApp',
    description: 'Bind your WhatsApp Business number to start receiving leads.',
    icon: WifiIcon,
  },
  {
    title: 'Set Up Your Calendar',
    description: 'Connect Google Calendar so AI can auto-schedule viewings.',
    icon: RocketLaunchIcon,
  },
  {
    title: 'Configure Notifications',
    description: 'Choose which alerts you want to receive and how.',
    icon: ExclamationTriangleIcon,
  },
  {
    title: 'Start Engaging Leads',
    description: 'Your AI assistant will qualify leads and notify you when they\'re ready.',
    icon: UsersIcon,
  },
];

export function ZeroStateOnboarding() {
  const [currentStep, setCurrentStep] = useState(0);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col items-center justify-center py-20 px-4 max-w-lg mx-auto"
    >
      <motion.div
        key={currentStep}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="text-center mb-8"
      >
        {(() => {
          const step = ONBOARDING_STEPS[currentStep];
          const Icon = step.icon;
          return (
            <>
              <div className="inline-flex p-5 bg-blue-900/30 rounded-2xl mb-6">
                <Icon className="w-12 h-12 text-blue-400" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-3">{step.title}</h2>
              <p className="text-gray-400 leading-relaxed">{step.description}</p>
            </>
          );
        })()}
      </motion.div>

      {/* Progress dots */}
      <div className="flex gap-2 mb-8">
        {ONBOARDING_STEPS.map((_, i) => (
          <button
            key={i}
            onClick={() => setCurrentStep(i)}
            className={`w-2 h-2 rounded-full transition-colors ${
              i === currentStep ? 'bg-blue-500 w-6' : 'bg-gray-700 hover:bg-gray-600'
            }`}
          />
        ))}
      </div>

      {/* Navigation */}
      <div className="flex gap-3">
        {currentStep > 0 && (
          <button
            onClick={() => setCurrentStep((s) => s - 1)}
            className="px-5 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl text-sm font-medium transition-colors"
          >
            Back
          </button>
        )}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => {
            if (currentStep < ONBOARDING_STEPS.length - 1) {
              setCurrentStep((s) => s + 1);
            }
          }}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition-colors"
        >
          {currentStep === ONBOARDING_STEPS.length - 1 ? 'Get Started' : 'Next'}
        </motion.button>
      </div>
    </motion.div>
  );
}

// ─── Concurrent Agent Warning ────────────────────────────────────
export function ConcurrentAgentWarning({ agentName }: { agentName: string }) {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="fixed top-4 right-4 z-[150] bg-amber-900/90 border border-amber-700 rounded-xl shadow-2xl p-4 max-w-sm"
    >
      <div className="flex items-start gap-3">
        <UsersIcon className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-amber-200">Concurrent Access Detected</p>
          <p className="text-xs text-amber-300/80 mt-1">
            {agentName} is also viewing this session. Changes may conflict.
          </p>
        </div>
        <button onClick={() => setVisible(false)} className="p-1 hover:bg-amber-800 rounded transition-colors">
          <XMarkIcon className="w-4 h-4 text-amber-400" />
        </button>
      </div>
    </motion.div>
  );
}

// ─── Error Boundary (Class Component) ────────────────────────────
interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="min-h-[200px] flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <div className="inline-flex p-4 bg-red-900/30 rounded-2xl mb-4">
              <ExclamationTriangleIcon className="w-8 h-8 text-red-400" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Something went wrong</h3>
            <p className="text-sm text-gray-400 mb-4">
              {this.state.error?.message ?? 'An unexpected error occurred'}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <ArrowPathIcon className="w-4 h-4" />
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
