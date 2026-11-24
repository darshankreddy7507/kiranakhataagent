"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Bell,
  BookOpenText,
  CheckSquare,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareText,
  Mic,
  Package,
  Search,
  Settings,
  Store,
  Truck,
  UserCircle2,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import { formatINR } from "@/lib/utils";
import { LoginScreen } from "./LoginScreen";
import { StoreSettingsModal } from "./StoreSettingsModal";
import { VoiceCommandModal } from "./VoiceCommandModal";
import { OfflineBanner } from "./ui/state-banners";

const NAV_ITEMS = [
  { href: "/", labelEn: "Home", labelKn: "ಮುಖಪುಟ", icon: LayoutDashboard },
  { href: "/orders", labelEn: "Orders", labelKn: "ಆರ್ಡರ್‌ಗಳು", icon: MessageSquareText },
  { href: "/khata", labelEn: "Customer Khata", labelKn: "ಖಾತೆ ಪುಸ್ತಕ", icon: BookOpenText },
  { href: "/inventory", labelEn: "Stock & Bills", labelKn: "ದಾಸ್ತಾನು", icon: Package },
  { href: "/suppliers", labelEn: "Suppliers", labelKn: "ಸರಬರಾಜುದಾರರು", icon: Truck },
  { href: "/approvals", labelEn: "Approvals", labelKn: "ಅನುಮೋದನೆಗಳು", icon: CheckSquare },
  { href: "/reports", labelEn: "Daily Report", labelKn: "ದಿನದ ವರದಿ", icon: BarChart3 },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const {
    lang,
    toggleLang,
    t,
    notifications,
    voiceModalOpen,
    setVoiceModalOpen,
    settingsModalOpen,
    setSettingsModalOpen,
    shopSettings,
    isAuthenticated,
    signOut,
    isOffline,
  } = useApp();

  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{
    customers: { id: number; name: string; name_kn: string; balance: number }[];
    products: { id: number; name: string; name_kn: string; stock_qty: number; unit: string }[];
    orders: { id: number; order_code: string; customer_name: string; raw_message: string }[];
  } | null>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const q = searchQuery.trim();
    if (!q) return;
    const timer = setTimeout(async () => {
      try {
        const res = await api.search(q);
        setSearchResults(res);
      } catch {
        setSearchResults(null);
      }
    }, 220);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchResults(null);
      }
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  const SidebarContent = (
    <div className="flex h-full flex-col bg-[#173B3F] text-[#E6ECEB]">
      <div className="flex h-14 items-center gap-2.5 border-b border-white/10 px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] bg-[#D9911B] text-[#173B3F]">
          <Store className="h-4 w-4 stroke-[2.2]" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-bold text-white">
            {shopSettings.shop_name}
          </p>
          <p className="truncate font-kannada text-[10px] text-[#B8CBC9]">
            {shopSettings.shop_name_kn}
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-2.5 py-4">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const isApprovals = item.href === "/approvals";
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileNavOpen(false)}
              className={`flex items-center justify-between rounded-[6px] px-3 py-2.5 text-[13px] font-medium transition-colors ${
                active
                  ? "bg-white/15 text-white"
                  : "text-[#C5D5D3] hover:bg-white/8 hover:text-white"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <Icon className="h-4 w-4 shrink-0" />
                <span>{lang === "kn" ? item.labelKn : item.labelEn}</span>
              </span>
              {isApprovals && notifications.pending_approvals > 0 ? (
                <span className="rounded-[4px] bg-[#D9911B] px-1.5 py-0.5 text-[11px] font-bold tabular-nums text-[#173B3F]">
                  {notifications.pending_approvals}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/10 p-2.5 space-y-1">
        <button
          type="button"
          onClick={() => {
            setMobileNavOpen(false);
            setSettingsModalOpen(true);
          }}
          className="flex w-full items-center gap-2.5 rounded-[6px] px-3 py-2 text-xs font-medium text-[#C5D5D3] hover:bg-white/8 hover:text-white cursor-pointer"
        >
          <Settings className="h-4 w-4 shrink-0" />
          <span>{t("Store Settings", "ಅಂಗಡಿ ಸೆಟ್ಟಿಂಗ್ಸ್")}</span>
        </button>
        <button
          type="button"
          onClick={() => {
            setMobileNavOpen(false);
            void signOut();
          }}
          className="flex w-full items-center gap-2.5 rounded-[6px] px-3 py-2 text-xs font-medium text-[#EAB6AE] hover:bg-white/8 hover:text-white cursor-pointer"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          <span>{t("Log Out", "ಲಾಗ್ ಔಟ್")}</span>
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-[#F7F4EE]">
      <aside className="hidden w-56 shrink-0 lg:sticky lg:top-0 lg:block lg:h-screen">
        {SidebarContent}
      </aside>

      {mobileNavOpen ? (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/40"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="relative z-10 w-60">{SidebarContent}</aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        {isOffline ? <OfflineBanner /> : null}

        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-[#E2DDD3] bg-white px-4 lg:px-6">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              className="rounded-[6px] p-1.5 text-[#173B3F] hover:bg-[#F7F4EE] lg:hidden cursor-pointer"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <button
              type="button"
              onClick={() => setSettingsModalOpen(true)}
              className="text-left hover:opacity-80 cursor-pointer"
              title="Click to edit store name & details"
            >
              <h1 className="text-sm font-bold text-[#173B3F] leading-tight">
                {lang === "kn" ? shopSettings.shop_name_kn : shopSettings.shop_name}
              </h1>
            </button>
          </div>

          <div ref={searchRef} className="relative hidden max-w-xs flex-1 md:block">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#708284]" />
            <input
              value={searchQuery}
              onChange={(e) => {
                const val = e.target.value;
                setSearchQuery(val);
                if (!val.trim()) setSearchResults(null);
              }}
              placeholder={t("Search customer or item...", "ಗ್ರಾಹಕ ಅಥವಾ ವಸ್ತು ಹುಡುಕಿ...")}
              className="h-9 w-full rounded-[6px] border border-[#DDD7CA] bg-[#FBF9F5] pl-8 pr-7 text-xs text-[#173B3F] placeholder:text-[#869698] focus:border-[#173B3F] focus:bg-white focus:outline-none"
            />
            {searchQuery ? (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setSearchResults(null);
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#708284] hover:text-[#173B3F] cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            ) : null}

            {searchResults ? (
              <div className="absolute left-0 right-0 top-10 z-40 rounded-[8px] border border-[#E2DDD3] bg-white p-2 shadow-lg text-xs">
                {searchResults.customers.length === 0 &&
                searchResults.products.length === 0 &&
                searchResults.orders.length === 0 ? (
                  <p className="p-2 text-[#708284]">No matching results found.</p>
                ) : (
                  <div className="space-y-1 max-h-72 overflow-auto">
                    {searchResults.customers.map((c) => (
                      <button
                        key={`c-${c.id}`}
                        type="button"
                        onClick={() => {
                          setSearchResults(null);
                          setSearchQuery("");
                          router.push("/khata");
                        }}
                        className="flex w-full items-center justify-between rounded-[5px] px-2.5 py-2 text-left hover:bg-[#F7F4EE] cursor-pointer"
                      >
                        <span className="font-medium text-[#173B3F]">{c.name}</span>
                        <span className="tabular-nums text-[#B84646]">
                          {formatINR(c.balance)} due
                        </span>
                      </button>
                    ))}
                    {searchResults.products.map((p) => (
                      <button
                        key={`p-${p.id}`}
                        type="button"
                        onClick={() => {
                          setSearchResults(null);
                          setSearchQuery("");
                          router.push("/inventory");
                        }}
                        className="flex w-full items-center justify-between rounded-[5px] px-2.5 py-2 text-left hover:bg-[#F7F4EE] cursor-pointer"
                      >
                        <span className="text-[#173B3F]">{p.name}</span>
                        <span className="text-[#4D6265]">
                          {p.stock_qty} {p.unit}
                        </span>
                      </button>
                    ))}
                    {searchResults.orders.map((o) => (
                      <button
                        key={`o-${o.id}`}
                        type="button"
                        onClick={() => {
                          setSearchResults(null);
                          setSearchQuery("");
                          router.push(`/orders?order=${o.id}`);
                        }}
                        className="flex w-full items-center justify-between rounded-[5px] px-2.5 py-2 text-left hover:bg-[#F7F4EE] cursor-pointer"
                      >
                        <span className="font-medium text-[#173B3F]">
                          Order from {o.customer_name}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setVoiceModalOpen(true)}
              className="inline-flex h-8 items-center gap-1.5 rounded-[6px] border border-[#C95534]/35 bg-[#C95534]/10 px-3 text-xs font-semibold text-[#A73F21] hover:bg-[#C95534]/15 cursor-pointer"
            >
              <Mic className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{t("Speak", "ಮಾತನಾಡಿ")}</span>
            </button>

            <button
              type="button"
              onClick={toggleLang}
              className="inline-flex h-8 items-center rounded-[6px] border border-[#CFC8BA] bg-[#FBF9F5] px-2.5 text-xs font-semibold text-[#173B3F] hover:bg-[#EFEAE0] cursor-pointer"
            >
              <span className={lang === "en" ? "text-[#173B3F]" : "text-[#869698]"}>EN</span>
              <span className="mx-1 text-[#CFC8BA]">/</span>
              <span className={`font-kannada ${lang === "kn" ? "text-[#C95534]" : "text-[#869698]"}`}>
                ಕನ್ನಡ
              </span>
            </button>

            <div className="relative">
              <button
                type="button"
                onClick={() => setNotifOpen((v) => !v)}
                className="relative inline-flex h-8 w-8 items-center justify-center rounded-[6px] border border-[#DDD7CA] bg-white text-[#173B3F] hover:bg-[#F7F4EE] cursor-pointer"
                aria-label="Alerts"
              >
                <Bell className="h-4 w-4" />
                {notifications.pending_approvals > 0 ? (
                  <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#D9911B] px-1 text-[10px] font-bold text-[#173B3F]">
                    {notifications.pending_approvals}
                  </span>
                ) : null}
              </button>
              {notifOpen ? (
                <div className="absolute right-0 top-10 z-40 w-72 rounded-[8px] border border-[#E2DDD3] bg-white p-3 shadow-lg text-xs">
                  <div className="flex items-center justify-between border-b border-[#EAE5DC] pb-2">
                    <span className="font-semibold text-[#173B3F]">Waiting for You</span>
                    <Link
                      href="/approvals"
                      onClick={() => setNotifOpen(false)}
                      className="text-[11px] font-semibold text-[#C95534] hover:underline"
                    >
                      View all
                    </Link>
                  </div>
                  <div className="mt-2 space-y-1.5">
                    <p className="text-[#4D6265]">
                      <strong>{notifications.pending_approvals}</strong> approvals ·{" "}
                      <strong>{notifications.low_stock_alerts}</strong> low stock ·{" "}
                      <strong>{notifications.overdue_customers}</strong> overdue
                    </p>
                    {notifications.items.slice(0, 3).map((item) => (
                      <Link
                        key={item.id}
                        href="/approvals"
                        onClick={() => setNotifOpen(false)}
                        className="block rounded-[5px] border border-[#EAE5DC] bg-[#FBF9F5] p-2 hover:border-[#D9911B]"
                      >
                        <p className="font-medium text-[#173B3F]">{item.title}</p>
                      </Link>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            {/* Owner Profile Menu (Store Settings + Log Out) */}
            <div ref={profileRef} className="relative border-l border-[#E2DDD3] pl-2.5">
              <button
                type="button"
                onClick={() => setProfileOpen((v) => !v)}
                className="flex items-center gap-1.5 rounded-[6px] px-1.5 py-1 hover:bg-[#F7F4EE] cursor-pointer"
              >
                <UserCircle2 className="h-6 w-6 text-[#173B3F]" />
                <div className="hidden text-left leading-tight sm:block">
                  <p className="text-xs font-semibold text-[#173B3F]">
                    {shopSettings.owner_name}
                  </p>
                  <p className="text-[10px] text-[#708284]">{t("Owner", "ಮಾಲೀಕರು")}</p>
                </div>
                <ChevronDown className="h-3.5 w-3.5 text-[#708284]" />
              </button>

              {profileOpen ? (
                <div className="absolute right-0 top-10 z-40 w-52 rounded-[8px] border border-[#E2DDD3] bg-white p-1.5 shadow-lg text-xs">
                  <div className="border-b border-[#EFEAE0] px-2.5 py-2">
                    <p className="font-semibold text-[#173B3F]">{shopSettings.owner_name}</p>
                    <p className="truncate text-[11px] text-[#708284]">
                      {shopSettings.shop_name}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setProfileOpen(false);
                      setSettingsModalOpen(true);
                    }}
                    className="mt-1 flex w-full items-center gap-2 rounded-[5px] px-2.5 py-2 text-left text-[#173B3F] hover:bg-[#F7F4EE] cursor-pointer"
                  >
                    <Settings className="h-3.5 w-3.5" />
                    <span>{t("Store Settings", "ಅಂಗಡಿ ಸೆಟ್ಟಿಂಗ್ಸ್")}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setProfileOpen(false);
                      void signOut();
                    }}
                    className="flex w-full items-center gap-2 rounded-[5px] px-2.5 py-2 text-left text-[#B84646] hover:bg-[#FDF6F6] cursor-pointer"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    <span>{t("Log Out", "ಲಾಗ್ ಔಟ್")}</span>
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 p-4 lg:p-6">{children}</main>
      </div>

      <VoiceCommandModal
        open={voiceModalOpen}
        onOpenChange={setVoiceModalOpen}
      />
      <StoreSettingsModal
        open={settingsModalOpen}
        onOpenChange={setSettingsModalOpen}
      />
    </div>
  );
}
