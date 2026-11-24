"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  IndianRupee,
  MessageSquareText,
  Mic,
  PackageOpen,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";
import { ApprovalCard } from "@/components/ApprovalCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorBanner, LoadingBlock, SuccessBanner } from "@/components/ui/state-banners";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type { OverviewResponse } from "@/lib/types";
import { formatINR, formatTime } from "@/lib/utils";

function orderStatusBadge(status: string) {
  switch (status) {
    case "completed":
      return <Badge variant="green">Done</Badge>;
    case "confirmation_pending":
      return <Badge variant="marigold">Send Reply</Badge>;
    case "credit_warning":
      return <Badge variant="red">Over Limit</Badge>;
    case "needs_substitute":
      return <Badge variant="terracotta">Pick Replacement</Badge>;
    case "awaiting_payment":
      return <Badge variant="marigold">Payment Asked</Badge>;
    case "pending_approval":
      return <Badge variant="marigold">Needs Approval</Badge>;
    case "cancelled":
    case "rejected":
      return <Badge variant="neutral">Cancelled</Badge>;
    default:
      return <Badge variant="neutral">{status}</Badge>;
  }
}

export default function OverviewPage() {
  const { lang, t, setVoiceModalOpen, setSettingsModalOpen, shopSettings, refreshNotifications, realtimeTick } = useApp();
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bannerMsg, setBannerMsg] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const res = await api.getOverview();
      setError(null);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load shop summary");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => loadData());
  }, [loadData, realtimeTick]);

  const handleApprovalDone = (msg: string) => {
    setBannerMsg(msg);
    void loadData();
    void refreshNotifications();
  };

  if (loading) return <LoadingBlock label="Opening Sri Lakshmi Kirana Stores..." />;
  if (error || !data) {
    return <ErrorBanner message={error || "Unable to load"} onRetry={() => void loadData()} />;
  }

  const kpis = [
    {
      label: t("Sales Today", "ಇಂದಿನ ಮಾರಾಟ"),
      value: formatINR(data.kpis.today_sales),
      icon: TrendingUp,
      tone: "text-[#173B3F]",
      href: "/reports",
    },
    {
      label: t("Credit Given", "ಖಾತೆಗೆ ಕೊಟ್ಟಿದ್ದು"),
      value: formatINR(data.kpis.credit_given_today),
      icon: IndianRupee,
      tone: "text-[#C95534]",
      href: "/khata",
    },
    {
      label: t("Collected Today", "ಇಂದು ಬಂದ ಹಣ"),
      value: formatINR(data.kpis.payments_collected_today),
      icon: CheckCircle2,
      tone: "text-[#2F7D5B]",
      href: "/khata",
    },
    {
      label: t("Low Stock", "ಕಡಿಮೆ ಸ್ಟಾಕ್"),
      value: String(data.kpis.low_stock_alerts),
      icon: PackageOpen,
      tone: "text-[#D9911B]",
      href: "/inventory",
    },
    {
      label: t("Overdue", "ಬಾಕಿ ಗ್ರಾಹಕರು"),
      value: String(data.kpis.overdue_customers),
      icon: AlertTriangle,
      tone: "text-[#B84646]",
      href: "/khata",
    },
  ];

  const ownerFirst = shopSettings.owner_name.split(" ")[0] || "Manjunath";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#173B3F]">
            {t(`Good Day, ${ownerFirst}`, `ನಮಸ್ಕಾರ, ${ownerFirst}`)}
          </h2>
          <p className="text-xs text-[#4D6265]">
            {shopSettings.shop_name} ·{" "}
            {t(
              "Review pending items below. Nothing changes without your approval.",
              "ಕೆಳಗಿನ ಪಟ್ಟಿಯನ್ನು ಪರಿಶೀಲಿಸಿ. ನಿಮ್ಮ ಒಪ್ಪಿಗೆಯ ನಂತರವೇ ಬದಲಾಗುತ್ತದೆ."
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setSettingsModalOpen(true)}>
            {t("Store Settings", "ಅಂಗಡಿ ಸೆಟ್ಟಿಂಗ್ಸ್")}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setVoiceModalOpen(true)}>
            <Mic className="h-3.5 w-3.5 text-[#C95534]" />
            {t("Speak Command", "ಧ್ವನಿ ಆಜ್ಞೆ")}
          </Button>
          <Button variant="primary" size="sm" asChild>
            <Link href="/orders">
              <MessageSquareText className="h-3.5 w-3.5" />
              {t("Check Orders", "ಆರ್ಡರ್ ನೋಡಿ")}
            </Link>
          </Button>
        </div>
      </div>

      {bannerMsg ? (
        <SuccessBanner message={bannerMsg} onDismiss={() => setBannerMsg(null)} />
      ) : null}

      {/* 5 Simple Stat Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {kpis.map((item) => {
          const Icon = item.icon;
          return (
            <Link key={item.label} href={item.href}>
              <Card className="h-full transition-colors hover:border-[#CFC8BA]">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-[#4D6265]">{item.label}</span>
                    <Icon className={`h-4 w-4 ${item.tone}`} />
                  </div>
                  <p className={`mt-2 text-xl font-bold tabular-nums ${item.tone}`}>
                    {item.value}
                  </p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      {/* Needs Your Approval */}
      <Card className="border-[#D9911B]/50">
        <CardHeader className="bg-[#FDF9F1]">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-[#D9911B]" />
            <CardTitle>
              {t("Needs Your Approval", "ನಿಮ್ಮ ಒಪ್ಪಿಗೆಗಾಗಿ ಕಾಯುತ್ತಿದೆ")} (
              {data.needs_approval.length})
            </CardTitle>
          </div>
          <Link
            href="/approvals"
            className="inline-flex items-center gap-1 text-xs font-semibold text-[#C95534] hover:underline"
          >
            {t("See all", "ಎಲ್ಲಾ ನೋಡಿ")}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </CardHeader>
        <CardContent className="space-y-3 p-4">
          {data.needs_approval.length === 0 ? (
            <EmptyState
              title="You're all caught up!"
              description="No pending approvals right now."
              action={
                <Button size="sm" variant="outline" asChild>
                  <Link href="/orders">Open WhatsApp Orders</Link>
                </Button>
              }
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {data.needs_approval.slice(0, 4).map((approval) => (
                <ApprovalCard
                  key={approval.id}
                  approval={approval}
                  onDecided={handleApprovalDone}
                  compact
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Today's Orders + Quick Summary */}
      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-7">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-[#173B3F]" />
              <CardTitle>{t("Recent Orders", "ಇತ್ತೀಚಿನ ಆರ್ಡರ್‌ಗಳು")}</CardTitle>
            </div>
            <Link href="/orders" className="text-xs font-semibold text-[#173B3F] hover:underline">
              {t("Open Inbox", "ಎಲ್ಲಾ ನೋಡಿ")}
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-[#EFEAE0]">
              {data.today_timeline.slice(0, 5).map((order) => (
                <Link
                  key={order.id}
                  href={`/orders?order=${order.id}`}
                  className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-[#FBF9F5]"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-[#173B3F]">
                        {lang === "kn" ? order.customer_name_kn : order.customer_name}
                      </span>
                      {order.channel === "whatsapp_voice" ? (
                        <Badge variant="teal">Voice</Badge>
                      ) : null}
                      {order.is_repeat_order ? (
                        <Badge variant="neutral">Repeat</Badge>
                      ) : null}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-[#4D6265]">
                      {order.english_translation}
                    </p>
                  </div>
                  <div className="shrink-0 text-right space-y-1">
                    <p className="text-xs font-bold tabular-nums text-[#173B3F]">
                      {formatINR(order.total_amount)}
                    </p>
                    <div className="flex items-center justify-end gap-2">
                      <span className="text-[10px] text-[#708284]">{formatTime(order.created_at)}</span>
                      {orderStatusBadge(order.status)}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-5">
          <CardHeader>
            <CardTitle>{t("Today's Summary", "ಇಂದಿನ ಸಾರಾಂಶ")}</CardTitle>
            <Link href="/reports" className="text-xs font-semibold text-[#C95534] hover:underline">
              {t("Listen / Full Report", "ಪೂರ್ಣ ವರದಿ")}
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-[6px] border border-[#E2DDD3] bg-[#FBF9F5] p-3">
              <p className="font-kannada text-xs leading-relaxed text-[#173B3F]">
                {data.daily_summary.text_kn}
              </p>
            </div>
            <p className="text-xs leading-relaxed text-[#4D6265]">
              {data.daily_summary.text_en}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
