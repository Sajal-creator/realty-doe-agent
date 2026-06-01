import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Realty Doe — AI CRM Dashboard",
  description: "Real Estate AI automation command center",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans bg-slate-950 text-gray-100 antialiased`}
      >
        <SocketProvider>
          <NotificationSoundManager>
            {children}
          </NotificationSoundManager>
        </SocketProvider>
      </body>
    </html>
  );
}

// ── Socket.IO Provider (client-side) ───────────────────

"use client";

import { useSocket } from "@/hooks/useSocket";

function SocketProvider({ children }: { children: React.ReactNode }) {
  useSocket();
  return <>{children}</>;
}

// ── Notification Sound Manager (client-side) ───────────

import { useEffect, useRef } from "react";
import { useStore } from "@/store/useStore";

function NotificationSoundManager({ children }: { children: React.ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const notifications = useStore((s) => s.notifications);
  const prevCountRef = useRef(notifications.length);

  useEffect(() => {
    // Create audio element on mount
    audioRef.current = new Audio("/sounds/notification.mp3");
    audioRef.current.volume = 0.5;
  }, []);

  useEffect(() => {
    if (notifications.length > prevCountRef.current) {
      const unread = notifications.find((n) => !n.read);
      if (unread && audioRef.current) {
        audioRef.current.play().catch(() => {
          // Autoplay blocked — ignore silently
        });
      }
    }
    prevCountRef.current = notifications.length;
  }, [notifications]);

  return <>{children}</>;
}
