"use client";

import { useState, useRef, useEffect } from "react";
import {
  Bell,
  Settings,
  LogOut,
  ChevronDown,
  Bot,
  User,
  X,
} from "lucide-react";
import { cn, formatTimeAgo, stringToColor, getInitials } from "@/lib/utils";
import { useStore } from "@/store/useStore";
import type { Notification } from "@/lib/api";

export function TopBar() {
  const notifications = useStore((s) => s.notifications);
  const markNotificationRead = useStore((s) => s.markNotificationRead);
  const agentMode = useStore((s) => s.agentMode);
  const toggleAgentMode = useStore((s) => s.toggleAgentMode);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifications(false);
      }
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setShowProfile(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm flex items-center px-6 z-50">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-brand/20 flex items-center justify-center">
          <Bot className="h-5 w-5 text-brand" />
        </div>
        <div>
          <h1 className="text-base font-bold text-white leading-tight">
            Realty Doe
          </h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-widest">
            AI Command Center
          </p>
        </div>
      </div>

      {/* Center: Agent Mode Toggle */}
      <div className="flex-1 flex justify-center">
        <button
          onClick={toggleAgentMode}
          className={cn(
            "flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium transition-all",
            agentMode === "AI"
              ? "bg-brand/20 text-brand border border-brand/30"
              : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
          )}
        >
          {agentMode === "AI" ? (
            <>
              <Bot className="h-4 w-4" />
              <span>AI Mode</span>
            </>
          ) : (
            <>
              <User className="h-4 w-4" />
              <span>Human Mode</span>
            </>
          )}
          <span className="text-[10px] ml-1 opacity-60">● LIVE</span>
        </button>
      </div>

      {/* Right: Notifications, Settings, Logout */}
      <div className="flex items-center gap-2">
        {/* Notification Bell */}
        <div ref={notifRef} className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative h-9 w-9 rounded-lg hover:bg-slate-800 flex items-center justify-center transition-colors"
          >
            <Bell className="h-5 w-5 text-gray-400" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 h-4 min-w-[16px] flex items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white px-1 animate-pulse-glow">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>

          {/* Notification Dropdown */}
          {showNotifications && (
            <NotificationDropdown
              notifications={notifications}
              onRead={markNotificationRead}
              onClose={() => setShowNotifications(false)}
            />
          )}
        </div>

        {/* Settings */}
        <button className="h-9 w-9 rounded-lg hover:bg-slate-800 flex items-center justify-center transition-colors">
          <Settings className="h-5 w-5 text-gray-400" />
        </button>

        {/* Profile / Logout */}
        <div ref={profileRef} className="relative">
          <button
            onClick={() => setShowProfile(!showProfile)}
            className="flex items-center gap-2 ml-2 pl-3 border-l border-slate-800"
          >
            <div
              className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold text-white"
              style={{ backgroundColor: stringToColor("Agent Doe") }}
            >
              {getInitials("Agent Doe")}
            </div>
            <ChevronDown className="h-3.5 w-3.5 text-gray-500" />
          </button>

          {showProfile && (
            <div className="absolute right-0 top-full mt-2 w-48 glass-panel p-1.5 z-50">
              <div className="px-3 py-2 border-b border-slate-700/50 mb-1">
                <p className="text-sm font-medium text-gray-200">Agent Doe</p>
                <p className="text-xs text-gray-500">agent@realtydoe.com</p>
              </div>
              <button className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-slate-800 transition-colors">
                <LogOut className="h-4 w-4" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

// ── Notification Dropdown ──────────────────────────────

function NotificationDropdown({
  notifications,
  onRead,
  onClose,
}: {
  notifications: Notification[];
  onRead: (id: string) => void;
  onClose: () => void;
}) {
  return (
    <div className="absolute right-0 top-full mt-2 w-80 glass-panel shadow-xl z-50 max-h-96 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
        <h3 className="text-sm font-semibold text-gray-200">Notifications</h3>
        <button
          onClick={onClose}
          className="h-6 w-6 rounded hover:bg-slate-700 flex items-center justify-center"
        >
          <X className="h-3.5 w-3.5 text-gray-400" />
        </button>
      </div>
      <div className="overflow-y-auto scrollbar-thin flex-1">
        {notifications.length === 0 ? (
          <div className="p-6 text-center text-gray-500 text-sm">
            No notifications
          </div>
        ) : (
          notifications.map((n) => (
            <button
              key={n.id}
              onClick={() => onRead(n.id)}
              className={cn(
                "w-full text-left px-4 py-3 border-b border-slate-800/50 hover:bg-slate-800/40 transition-colors",
                !n.read && "bg-slate-800/20"
              )}
            >
              <div className="flex items-start gap-2">
                {!n.read && (
                  <span className="mt-1.5 h-2 w-2 rounded-full bg-brand flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-200 truncate">
                    {n.title}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">
                    {n.body}
                  </p>
                  <p className="text-[10px] text-gray-500 mt-1">
                    {formatTimeAgo(n.createdAt)}
                  </p>
                </div>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
