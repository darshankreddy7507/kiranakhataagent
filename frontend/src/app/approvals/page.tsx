"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckSquare, History } from "lucide-react";
import { ApprovalCard } from "@/components/ApprovalCard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorBanner, LoadingBlock, SuccessBanner } from "@/components/ui/state-banners";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type { Approval, AuditLog } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

type TabKey = "pending" | "approved" | "rejected" | "audit";

const EVENT_LABELS: Record<string, { label: string; variant: "teal" | "green" | "red" | "marigold" }> = {
  approval_created: { label: "Suggested", variant: "marigold" },
  approved: { label: "Approved", variant: "green" },
  rejected: { label: "Skipped", variant: "red" },
  inventory_updated: { label: "Stock Updated", variant: "teal" },
  khata_created: { label: "Khata Updated", variant: "teal" },
  whatsapp_sent: { label: "WhatsApp Sent", variant: "green" },
  payment_matched: { label: "Payment Received", variant: "green" },
  supplier_order_sent: { label: "Supplier Ordered", variant: "green" },
  bill_posted: { label: "Bill Added", variant: "green" },
  daily_summary_generated: { label: "Daily Report", variant: "teal" },
};

export default function ApprovalsPage() {
  const { t, refreshNotifications, realtimeTick } = useApp();
  const [tab, setTab] = useState<TabKey>("pending");
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [allApps, logs] = await Promise.all([
        api.listApprovals("all"),
        api.listAuditLogs(100),
      ]);
      setError(null);
      setApprovals(allApps);
      setAuditLogs(logs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load approvals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => loadData());
  }, [loadData, realtimeTick]);

  const handleDecided = (msg: string) => {
    setBanner(msg);
    void loadData();
    void refreshNotifications();
  };

  if (loading) return <LoadingBlock label="Loading approval list..." />;

  const pendingList = approvals.filter((a) => a.status === "pending");
  const approvedList = approvals.filter((a) => a.status === "approved");
  const rejectedList = approvals.filter((a) => a.status === "rejected");

  const activeApprovals =
    tab === "pending" ? pendingList : tab === "approved" ? approvedList : rejectedList;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold text-[#173B3F] flex items-center gap-2">
          <CheckSquare className="h-5 w-5 text-[#D9911B]" />
          {t("Approvals", "ಅನುಮೋದನೆಗಳು")}
        </h2>
        <p className="text-xs text-[#4D6265]">
          {t(
            "Review and approve actions before anything is saved or sent.",
            "ಯಾವುದೇ ಬದಲಾವಣೆ ಅಥವಾ ಸಂದೇಶ ಕಳುಹಿಸುವ ಮೊದಲು ಇಲ್ಲಿ ಅನುಮೋದಿಸಿ."
          )}
        </p>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void loadData()} /> : null}
      {banner ? <SuccessBanner message={banner} onDismiss={() => setBanner(null)} /> : null}

      <div className="flex flex-wrap gap-1.5 border-b border-[#E2DDD3] pb-2">
        {(
          [
            { key: "pending", label: `Waiting for You (${pendingList.length})` },
            { key: "approved", label: `Approved (${approvedList.length})` },
            { key: "rejected", label: `Skipped (${rejectedList.length})` },
            { key: "audit", label: `Activity History (${auditLogs.length})` },
          ] as const
        ).map((tItem) => (
          <button
            key={tItem.key}
            type="button"
            onClick={() => setTab(tItem.key)}
            className={`rounded-[6px] px-3 py-1.5 text-xs font-semibold cursor-pointer ${
              tab === tItem.key
                ? "bg-[#173B3F] text-white"
                : "bg-white text-[#4D6265] border border-[#DDD7CA] hover:bg-[#FBF9F5]"
            }`}
          >
            {tItem.label}
          </button>
        ))}
      </div>

      {tab === "audit" ? (
        <Card className="overflow-hidden">
          <div className="flex items-center gap-2 border-b border-[#EAE5DC] bg-[#FBF9F5] px-4 py-2.5 text-xs font-semibold text-[#173B3F]">
            <History className="h-4 w-4" />
            Recent Shop Activity
          </div>
          <div className="divide-y divide-[#EFEAE0]">
            {auditLogs.map((log) => {
              const meta = EVENT_LABELS[log.event_type] || {
                label: log.event_type,
                variant: "teal" as const,
              };
              return (
                <div
                  key={log.id}
                  className="flex flex-wrap items-start justify-between gap-3 px-4 py-3 text-xs hover:bg-[#FBF9F5]"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <Badge variant={meta.variant}>{meta.label}</Badge>
                      <span className="font-medium text-[#173B3F]">{log.summary}</span>
                    </div>
                    {log.summary_kn ? (
                      <p className="font-kannada text-[11px] text-[#708284]">{log.summary_kn}</p>
                    ) : null}
                  </div>
                  <span className="shrink-0 text-[11px] text-[#708284]">
                    {formatDateTime(log.created_at)}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      ) : activeApprovals.length === 0 ? (
        <EmptyState
          title={tab === "pending" ? "Nothing waiting for you" : "No items here"}
          description="When new WhatsApp orders, reminders, or stock updates arrive, they will show up here."
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {activeApprovals.map((a) => (
            <ApprovalCard key={a.id} approval={a} onDecided={handleDecided} />
          ))}
        </div>
      )}
    </div>
  );
}
