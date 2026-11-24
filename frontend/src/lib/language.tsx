"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { Language, ShopSettings } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface NotificationSummary {
  total_count: number;
  pending_approvals: number;
  low_stock_alerts: number;
  overdue_customers: number;
  items: { id: number; code: string; title: string; risk_level: string; action_type: string }[];
}

interface AppContextValue {
  lang: Language;
  setLang: (lang: Language) => void;
  toggleLang: () => void;
  t: (en: string, kn: string) => string;
  notifications: NotificationSummary;
  refreshNotifications: () => Promise<void>;
  voiceModalOpen: boolean;
  setVoiceModalOpen: (open: boolean) => void;
  settingsModalOpen: boolean;
  setSettingsModalOpen: (open: boolean) => void;
  shopSettings: ShopSettings;
  refreshSettings: () => Promise<void>;
  isAuthenticated: boolean;
  signOut: () => Promise<void>;
  signIn: (pin: string, ownerName?: string) => Promise<void>;
  isOffline: boolean;
  realtimeTick: number;
  lastRealtimeEvent: string | null;
}

const DEFAULT_NOTIFS: NotificationSummary = {
  total_count: 0,
  pending_approvals: 0,
  low_stock_alerts: 0,
  overdue_customers: 0,
  items: [],
};

const DEFAULT_SETTINGS: ShopSettings = {
  shop_name: "Kirana Khata Agent",
  shop_name_kn: "ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್",
  owner_name: "Manjunath Gowda",
  owner_phone: "+91 98450 11223",
  upi_id: "kiranakhata@okicici",
  default_credit_limit: 3000,
  telegram_connected: false,
};

const AppContext = createContext<AppContextValue>({
  lang: "en",
  setLang: () => {},
  toggleLang: () => {},
  t: (en) => en,
  notifications: DEFAULT_NOTIFS,
  refreshNotifications: async () => {},
  voiceModalOpen: false,
  setVoiceModalOpen: () => {},
  settingsModalOpen: false,
  setSettingsModalOpen: () => {},
  shopSettings: DEFAULT_SETTINGS,
  refreshSettings: async () => {},
  isAuthenticated: true,
  signOut: async () => {},
  signIn: async () => {},
  isOffline: false,
  realtimeTick: 0,
  lastRealtimeEvent: null,
});

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Language>("en");
  const [notifications, setNotifications] = useState<NotificationSummary>(DEFAULT_NOTIFS);
  const [shopSettings, setShopSettings] = useState<ShopSettings>(DEFAULT_SETTINGS);
  const [voiceModalOpen, setVoiceModalOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [realtimeTick, setRealtimeTick] = useState(0);
  const [lastRealtimeEvent, setLastRealtimeEvent] = useState<string | null>(null);

  const refreshSettings = useCallback(async () => {
    try {
      const s = await api.getSettings();
      setShopSettings(s);
    } catch {
      // keep existing settings fallback
    }
  }, []);

  const refreshNotifications = useCallback(async () => {
    try {
      const data = await api.getNotifications();
      setNotifications(data);
      setIsOffline(false);
    } catch {
      setIsOffline(typeof navigator !== "undefined" ? !navigator.onLine : true);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => {
      if (!active) return;
      if (typeof window !== "undefined" && window.localStorage.getItem("kirana_logged_out") === "1") {
        setIsAuthenticated(false);
      }
      void refreshSettings();
      void refreshNotifications();
    });

    const timer = setInterval(() => {
      void refreshNotifications();
    }, 15000);
    const handleOnline = () => {
      setIsOffline(false);
      void refreshNotifications();
      void refreshSettings();
    };
    const handleOffline = () => setIsOffline(true);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    let es: EventSource | null = null;
    if (typeof EventSource !== "undefined") {
      es = new EventSource(`${API_BASE}/api/events/stream`);
      es.onmessage = (evt) => {
        try {
          const parsed = JSON.parse(evt.data);
          if (parsed?.event && parsed.event !== "connected") {
            setLastRealtimeEvent(parsed.event);
            setRealtimeTick((n) => n + 1);
            void refreshNotifications();
            if (parsed.event === "settings_updated") {
              void refreshSettings();
            }
          }
        } catch {
          // ignore keepalive parse
        }
      };
    }

    return () => {
      active = false;
      clearInterval(timer);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      es?.close();
    };
  }, [refreshNotifications, refreshSettings]);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // allow client logout even if offline
    }
    if (typeof window !== "undefined") {
      window.localStorage.setItem("kirana_logged_out", "1");
    }
    setIsAuthenticated(false);
  }, []);

  const signIn = useCallback(async (pin: string, ownerName?: string) => {
    const res = await api.login({ pin, owner_name: ownerName });
    setShopSettings(res.settings);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("kirana_logged_out");
    }
    setIsAuthenticated(true);
  }, []);

  const toggleLang = useCallback(() => {
    setLang((prev) => (prev === "en" ? "kn" : "en"));
  }, []);

  const t = useCallback(
    (en: string, kn: string) => (lang === "kn" ? kn : en),
    [lang]
  );

  return (
    <AppContext.Provider
      value={{
        lang,
        setLang,
        toggleLang,
        t,
        notifications,
        refreshNotifications,
        voiceModalOpen,
        setVoiceModalOpen,
        settingsModalOpen,
        setSettingsModalOpen,
        shopSettings,
        refreshSettings,
        isAuthenticated,
        signOut,
        signIn,
        isOffline,
        realtimeTick,
        lastRealtimeEvent,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
