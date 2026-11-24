"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  Edit3,
  MessageSquare,
  PackagePlus,
  ReceiptIndianRupee,
  Truck,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type { Approval } from "@/lib/types";
import { formatDateTime, formatINR } from "@/lib/utils";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

const ACTION_META: Record<
  Approval["action_type"],
  { label: string; labelKn: string; icon: React.ComponentType<{ className?: string }> }
> = {
  order_fulfill: { label: "Customer Order", labelKn: "ಗ್ರಾಹಕರ ಆರ್ಡರ್", icon: ReceiptIndianRupee },
  credit_override: { label: "Credit Limit Check", labelKn: "ಕ್ರೆಡಿಟ್ ಮಿತಿ", icon: AlertTriangle },
  send_whatsapp: { label: "WhatsApp Reply", labelKn: "ವಾಟ್ಸಾಪ್ ಉತ್ತರ", icon: MessageSquare },
  payment_reminder: { label: "Payment Reminder", labelKn: "ಪಾವತಿ ನೆನಪು", icon: MessageSquare },
  payment_thank_you: { label: "Thank-You Message", labelKn: "ಧನ್ಯವಾದ ಸಂದೇಶ", icon: MessageSquare },
  supplier_reorder: { label: "Supplier Reorder", labelKn: "ಸರಬರಾಜು ಆರ್ಡರ್", icon: Truck },
  bill_stock_intake: { label: "Bill Stock Add", labelKn: "ಬಿಲ್ ಸ್ಟಾಕ್ ಸೇರ್ಪಡೆ", icon: PackagePlus },
  voice_khata_entry: { label: "Voice Khata Entry", labelKn: "ಧ್ವನಿ ಖಾತೆ", icon: ReceiptIndianRupee },
};

export function ApprovalCard({
  approval,
  onDecided,
  compact = false,
}: {
  approval: Approval;
  onDecided: (message: string) => void;
  compact?: boolean;
}) {
  const { lang, refreshNotifications } = useApp();
  const payload = approval.payload || {};
  const initialMsgKn =
    (typeof payload.body_kn === "string" && payload.body_kn) ||
    (typeof payload.draft_reply_kn === "string" && payload.draft_reply_kn) ||
    (typeof payload.whatsapp_draft_kn === "string" && payload.whatsapp_draft_kn) ||
    "";

  const [editing, setEditing] = useState(false);
  const [editedMsgKn, setEditedMsgKn] = useState(initialMsgKn);
  const [showDetails, setShowDetails] = useState(false);
  const [submitting, setSubmitting] = useState<"approve" | "reject" | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const meta = ACTION_META[approval.action_type] || ACTION_META.order_fulfill;
  const Icon = meta.icon;

  const handleDecision = async (decision: "approve" | "reject") => {
    setSubmitting(decision);
    setErr(null);
    try {
      const edited_payload: Record<string, unknown> = {};
      if (editedMsgKn && editedMsgKn !== initialMsgKn) {
        if ("body_kn" in payload) edited_payload.body_kn = editedMsgKn;
        if ("draft_reply_kn" in payload) edited_payload.draft_reply_kn = editedMsgKn;
        if ("whatsapp_draft_kn" in payload) edited_payload.whatsapp_draft_kn = editedMsgKn;
      }
      const res = await api.decideApproval(approval.id, {
        decision,
        edited_payload: Object.keys(edited_payload).length ? edited_payload : undefined,
      });
      await refreshNotifications();
      const followText = res.follow_up_approval
        ? " Kannada reply is now ready to send."
        : "";
      onDecided(
        `${decision === "approve" ? "Approved" : "Skipped"}: ${approval.title}.${followText}`
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save your choice");
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div
      className={`rounded-[8px] border bg-white p-4 transition-colors ${
        approval.status === "pending"
          ? approval.risk_level === "high"
            ? "border-[#B84646]/45 bg-[#FFFDFB]"
            : "border-[#D9911B]/50"
          : "border-[#E2DDD3]"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <div
            className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] ${
              approval.risk_level === "high"
                ? "bg-[#B84646]/12 text-[#B84646]"
                : "bg-[#D9911B]/15 text-[#9A6309]"
            }`}
          >
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="neutral">{lang === "kn" ? meta.labelKn : meta.label}</Badge>
              {approval.risk_level === "high" ? (
                <Badge variant="red">Needs Extra Check</Badge>
              ) : null}
              {approval.status !== "pending" ? (
                <Badge variant={approval.status === "approved" ? "green" : "red"}>
                  {approval.status === "approved" ? "Approved" : "Skipped"}
                </Badge>
              ) : null}
            </div>
            <h3 className="mt-1.5 text-sm font-semibold text-[#173B3F]">
              {lang === "kn" && approval.title_kn ? approval.title_kn : approval.title}
            </h3>
          </div>
        </div>

        {approval.amount_impact != null ? (
          <div className="text-right shrink-0">
            <p className="text-base font-bold tabular-nums text-[#173B3F]">
              {formatINR(approval.amount_impact)}
            </p>
          </div>
        ) : null}
      </div>

      {/* Plain-English explanation */}
      <p className="mt-2.5 text-xs leading-relaxed text-[#4D6265]">{approval.reason}</p>

      {/* Message preview / editor when approval sends a WhatsApp message */}
      {initialMsgKn && !compact ? (
        <div className="mt-3 rounded-[6px] border border-[#D4DFD8] bg-[#F5F9F6] p-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[#2F7D5B]">
              Message to send on WhatsApp
            </span>
            {approval.status === "pending" ? (
              <button
                type="button"
                onClick={() => setEditing((v) => !v)}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-[#C95534] hover:underline cursor-pointer"
              >
                <Edit3 className="h-3 w-3" />
                {editing ? "Done" : "Edit message"}
              </button>
            ) : null}
          </div>
          {editing ? (
            <textarea
              value={editedMsgKn}
              onChange={(e) => setEditedMsgKn(e.target.value)}
              rows={3}
              className="mt-1.5 w-full rounded-[5px] border border-[#CFC8BA] bg-white p-2 font-kannada text-xs text-[#173B3F] focus:border-[#173B3F] focus:outline-none"
            />
          ) : (
            <p className="mt-1.5 font-kannada text-xs leading-relaxed text-[#173B3F] whitespace-pre-line">
              {editedMsgKn}
            </p>
          )}
        </div>
      ) : null}

      {err ? <p className="mt-2 text-xs font-medium text-[#B84646]">{err}</p> : null}

      {approval.status === "pending" ? (
        <div className="mt-3.5 flex flex-wrap items-center justify-between gap-2 border-t border-[#EFEAE0] pt-3">
          <button
            type="button"
            onClick={() => setShowDetails((v) => !v)}
            className="inline-flex items-center gap-1 text-[11px] text-[#708284] hover:text-[#173B3F] cursor-pointer"
          >
            {showDetails ? "Hide details" : "Why this?"}
            {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => void handleDecision("reject")}
              disabled={submitting !== null}
            >
              <X className="h-3.5 w-3.5" />
              {submitting === "reject" ? "Skipping..." : "Skip"}
            </Button>
            <Button
              size="sm"
              variant="success"
              onClick={() => void handleDecision("approve")}
              disabled={submitting !== null}
            >
              <Check className="h-3.5 w-3.5" />
              {submitting === "approve" ? "Saving..." : "Approve"}
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex items-center justify-between border-t border-[#EFEAE0] pt-2 text-[11px] text-[#708284]">
          <span>{approval.decided_by || "Owner"}</span>
          <span>{formatDateTime(approval.decided_at)}</span>
        </div>
      )}

      {showDetails ? (
        <div className="mt-2.5 rounded-[5px] border border-[#E2DDD3] bg-[#FBF9F5] p-2.5 text-[11px] text-[#4D6265]">
          <p>
            <strong>Reference:</strong> {approval.approval_code} ·{" "}
            <strong>Action:</strong> {approval.mcp_tool_name}
          </p>
          <pre className="mt-1.5 max-h-28 overflow-auto font-mono text-[10px] text-[#708284]">
            {JSON.stringify(approval.source_data, null, 2)}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
