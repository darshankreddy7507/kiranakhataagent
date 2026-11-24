"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  MessageSquare,
  Mic,
  Pause,
  Play,
  Plus,
  Send,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState, ErrorBanner, LoadingBlock, SuccessBanner } from "@/components/ui/state-banners";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type { Customer, WhatsAppOrder } from "@/lib/types";
import { formatINR, formatTime } from "@/lib/utils";

export default function OrdersPage() {
  const { lang, t, shopSettings, refreshNotifications, realtimeTick } = useApp();
  const [orders, setOrders] = useState<WhatsAppOrder[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState<"all" | "open" | "completed">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const [editedDraftKn, setEditedDraftKn] = useState<string | null>(null);
  const [editedSubId, setEditedSubId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [playingAudioId, setPlayingAudioId] = useState<number | null>(null);

  // Add test order dialog
  const [simModalOpen, setSimModalOpen] = useState(false);
  const [simCustomerId, setSimCustomerId] = useState<number>(1);
  const [simChannel, setSimChannel] = useState<"whatsapp_text" | "whatsapp_voice">("whatsapp_text");
  const [simMessage, setSimMessage] = useState("Anna, 1 kg sakkare mattu 1 kg toor dal kodi. Khatege haaki.");

  const loadData = useCallback(async () => {
    try {
      const [ordList, custList] = await Promise.all([
        api.listOrders("all"),
        api.listCustomers(),
      ]);
      setError(null);
      setOrders(ordList);
      setCustomers(custList);
      if (custList.length > 0) setSimCustomerId(custList[0].id);
      const urlOrderId =
        typeof window !== "undefined"
          ? Number(new URLSearchParams(window.location.search).get("order") || 0)
          : 0;
      setSelectedId((prev) => prev ?? (urlOrderId || ordList[0]?.id || null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load orders");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => loadData());
  }, [loadData, realtimeTick]);

  const filteredOrders = useMemo(() => {
    if (filter === "all") return orders;
    if (filter === "completed") return orders.filter((o) => o.status === "completed");
    return orders.filter((o) =>
      ["pending_approval", "credit_warning", "needs_substitute", "confirmation_pending"].includes(o.status)
    );
  }, [orders, filter]);

  const selectedOrder = useMemo(
    () => orders.find((o) => o.id === selectedId) || filteredOrders[0] || null,
    [orders, filteredOrders, selectedId]
  );

  const missingItem = selectedOrder?.parsed_items.find((i) => !i.available);
  const draftKn = editedDraftKn ?? (selectedOrder?.draft_reply_kn || "");
  const draftEn = selectedOrder?.draft_reply_en || "";
  const selectedSubId = editedSubId ?? (missingItem?.substitute_options?.[0]?.product_id ?? null);

  const handleQtyChange = (idx: number, delta: number) => {
    if (!selectedOrder) return;
    const updatedItems = selectedOrder.parsed_items.map((item, i) => {
      if (i !== idx) return item;
      const nextQty = Math.max(1, item.qty + delta);
      return {
        ...item,
        qty: nextQty,
        line_total: Math.round(nextQty * item.unit_price),
      };
    });
    const newTotal = updatedItems.reduce((sum, i) => sum + i.line_total, 0);
    setOrders((prev) =>
      prev.map((o) =>
        o.id === selectedOrder.id
          ? { ...o, parsed_items: updatedItems, total_amount: newTotal }
          : o
      )
    );
  };

  const handleApplySubstitute = async () => {
    if (!selectedOrder || !selectedSubId) return;
    const itemOut = selectedOrder.parsed_items.find((i) => !i.available);
    if (!itemOut?.product_id) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.selectSubstitute(selectedOrder.id, {
        original_product_id: itemOut.product_id,
        substitute_product_id: selectedSubId,
        draft_reply_kn: editedDraftKn !== null ? editedDraftKn : undefined,
      });
      setEditedDraftKn(null);
      setEditedSubId(null);
      setBanner(`Replacement selected for ${res.order.customer_name}. Now confirm the order below.`);
      await loadData();
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update replacement");
    } finally {
      setSubmitting(false);
    }
  };

  const handleOrderDecision = async (
    decision: "approve" | "ask_payment" | "cancel",
    autoSendReply = false
  ) => {
    if (!selectedOrder) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.decideOrder(selectedOrder.id, {
        decision,
        edited_items: selectedOrder.parsed_items as unknown as Record<string, unknown>[],
        draft_reply_kn: draftKn,
        draft_reply_en: draftEn,
        auto_send_reply: autoSendReply,
      });
      if (decision === "approve") {
        setBanner(
          autoSendReply
            ? `Done! Confirmed ${selectedOrder.order_code}, updated stock/khata, and sent Kannada reply to ${selectedOrder.customer_name}.`
            : "Order confirmed & stock/khata updated. Review & send the Kannada reply below."
        );
      } else if (decision === "ask_payment") {
        setBanner("Payment reminder prepared. Approve it in Approvals or Khata.");
      } else {
        setBanner("Order cancelled.");
      }
      await loadData();
      await refreshNotifications();
      if (res.order) setSelectedId(res.order.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update order");
    } finally {
      setSubmitting(false);
    }
  };

  const handleApproveSendMessage = async () => {
    if (!selectedOrder) return;
    const msgApproval = selectedOrder.related_approvals.find(
      (a) => a.action_type === "send_whatsapp" && a.status === "pending"
    );
    if (!msgApproval) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.decideApproval(msgApproval.id, {
        decision: "approve",
        edited_payload: { body_kn: draftKn, body_en: draftEn },
      });
      setBanner(`WhatsApp reply sent to ${selectedOrder.customer_name}!`);
      await loadData();
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send reply");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSimulateIncoming = async () => {
    if (!simMessage.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.simulateIncomingOrder({
        customer_id: simCustomerId,
        channel: simChannel,
        raw_message: simMessage.trim(),
      });
      setSimModalOpen(false);
      setSelectedId(created.id);
      setBanner(`New order from ${created.customer_name} added.`);
      await loadData();
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add order");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleVoiceNotePlayback = (order: WhatsAppOrder) => {
    if (playingAudioId === order.id) {
      setPlayingAudioId(null);
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      return;
    }
    setPlayingAudioId(order.id);
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(order.audio_transcript_kn || order.raw_message);
      utter.lang = "kn-IN";
      utter.rate = 0.95;
      utter.onend = () => setPlayingAudioId(null);
      utter.onerror = () => setPlayingAudioId(null);
      window.speechSynthesis.speak(utter);
    } else {
      setTimeout(() => setPlayingAudioId(null), (order.audio_duration_sec || 5) * 1000);
    }
  };

  if (loading) return <LoadingBlock label="Loading WhatsApp messages..." />;

  const pendingSendApproval = selectedOrder?.related_approvals.find(
    (a) => a.action_type === "send_whatsapp" && a.status === "pending"
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-[#173B3F]">
              {t("Customer Orders", "ಗ್ರಾಹಕರ ಆರ್ಡರ್‌ಗಳು")}
            </h2>
            {shopSettings.telegram_connected ? (
              <Badge variant="green">Telegram Live</Badge>
            ) : null}
          </div>
          <p className="text-xs text-[#4D6265]">
            {t(
              "Pick an order on the left, review items, and confirm & reply in one click.",
              "ಎಡಭಾಗದಲ್ಲಿ ಆರ್ಡರ್ ಆಯ್ಕೆಮಾಡಿ, ಒಂದೇ ಕ್ಲಿಕ್‌ನಲ್ಲಿ ದೃಢೀಕರಿಸಿ ಉತ್ತರ ಕಳುಹಿಸಿ."
            )}
          </p>
        </div>
        <Button size="sm" onClick={() => setSimModalOpen(true)}>
          <Plus className="h-3.5 w-3.5" />
          New Test Order
        </Button>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void loadData()} /> : null}
      {banner ? <SuccessBanner message={banner} onDismiss={() => setBanner(null)} /> : null}

      <div className="flex flex-wrap gap-1.5">
        {[
          { key: "all", label: `All (${orders.length})` },
          {
            key: "open",
            label: `To Do (${
              orders.filter((o) =>
                ["pending_approval", "credit_warning", "needs_substitute", "confirmation_pending"].includes(o.status)
              ).length
            })`,
          },
          { key: "completed", label: "Completed" },
        ].map((chip) => (
          <button
            key={chip.key}
            type="button"
            onClick={() => setFilter(chip.key as typeof filter)}
            className={`rounded-[5px] border px-3 py-1 text-xs font-medium cursor-pointer ${
              filter === chip.key
                ? "border-[#173B3F] bg-[#173B3F] text-white"
                : "border-[#DDD7CA] bg-white text-[#4D6265] hover:bg-[#FBF9F5]"
            }`}
          >
            {chip.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        {/* Left: Clean Customer List */}
        <Card className="lg:col-span-4 overflow-hidden">
          <div className="max-h-[680px] divide-y divide-[#EFEAE0] overflow-y-auto">
            {filteredOrders.length === 0 ? (
              <div className="p-4">
                <EmptyState
                  title="No orders here"
                  description="Switch tab or add a test WhatsApp order."
                />
              </div>
            ) : (
              filteredOrders.map((o) => {
                const isSelected = selectedOrder?.id === o.id;
                return (
                  <button
                    key={o.id}
                    type="button"
                    onClick={() => {
                      setSelectedId(o.id);
                      setEditedDraftKn(null);
                      setEditedSubId(null);
                    }}
                    className={`w-full px-4 py-3.5 text-left transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-[#F2EDE2] border-l-4 border-l-[#173B3F]"
                        : "hover:bg-[#FBF9F5]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-[#173B3F]">
                        {lang === "kn" ? o.customer_name_kn : o.customer_name}
                      </span>
                      <span className="text-[11px] text-[#708284]">{formatTime(o.created_at)}</span>
                    </div>

                    <p className="mt-1 line-clamp-2 font-kannada text-xs text-[#4D6265]">
                      {o.raw_message}
                    </p>

                    <div className="mt-2 flex items-center justify-between gap-2">
                      <div className="flex flex-wrap gap-1">
                        {o.channel.startsWith("telegram") ? (
                          <Badge variant="teal">Telegram</Badge>
                        ) : null}
                        {o.channel.endsWith("_voice") ? (
                          <Badge variant="teal">
                            <Mic className="h-2.5 w-2.5" /> Voice
                          </Badge>
                        ) : null}
                        {o.is_repeat_order ? <Badge variant="neutral">Repeat</Badge> : null}
                        {o.status === "credit_warning" ? (
                          <Badge variant="red">Over Limit</Badge>
                        ) : o.status === "needs_substitute" ? (
                          <Badge variant="terracotta">Item Out of Stock</Badge>
                        ) : o.status === "confirmation_pending" ? (
                          <Badge variant="marigold">Send Reply</Badge>
                        ) : o.status === "completed" ? (
                          <Badge variant="green">Done</Badge>
                        ) : (
                          <Badge variant="marigold">Needs Approval</Badge>
                        )}
                      </div>
                      <span className="text-xs font-bold tabular-nums text-[#173B3F]">
                        {formatINR(o.total_amount)}
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </Card>

        {/* Right: Calm 3-Step Order Workspace */}
        <div className="lg:col-span-8">
          {!selectedOrder ? (
            <EmptyState
              title="Pick an order"
              description="Select any customer on the left to review and confirm."
            />
          ) : (
            <Card>
              <CardHeader className="bg-[#FBF9F5]">
                <div>
                  <CardTitle className="text-base">
                    {selectedOrder.customer_name}{" "}
                    <span className="font-kannada font-normal text-[#4D6265]">
                      ({selectedOrder.customer_name_kn})
                    </span>
                  </CardTitle>
                  <p className="mt-0.5 text-xs text-[#4D6265]">
                    {selectedOrder.customer_phone} ·{" "}
                    {selectedOrder.payment_intent === "credit" ? "Put on Khata" : "Cash / UPI"}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[11px] text-[#708284]">Total</p>
                  <p className="text-xl font-bold tabular-nums text-[#173B3F]">
                    {formatINR(selectedOrder.total_amount)}
                  </p>
                </div>
              </CardHeader>

              <CardContent className="space-y-5 p-5">
                {/* 1. Customer Message */}
                <div className="rounded-[8px] border border-[#D4DFD8] bg-[#F5F9F6] p-3.5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#2F7D5B]">
                    <span className="flex items-center gap-1.5">
                      <MessageSquare className="h-3.5 w-3.5" />
                      {selectedOrder.channel === "telegram_voice"
                        ? "Customer Telegram Voice Note"
                        : selectedOrder.channel === "telegram_text"
                        ? "Customer Telegram Message"
                        : selectedOrder.channel === "whatsapp_voice"
                        ? "Customer Voice Note"
                        : "Customer WhatsApp Message"}
                    </span>
                    {selectedOrder.is_repeat_order ? (
                      <Badge variant="neutral">Same as last week</Badge>
                    ) : null}
                  </div>

                  {selectedOrder.channel.endsWith("_voice") ? (
                    <div className="mt-2.5 flex items-center gap-3 rounded-[6px] border border-[#C6D8CC] bg-white p-2.5">
                      <button
                        type="button"
                        onClick={() => toggleVoiceNotePlayback(selectedOrder)}
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#173B3F] text-white hover:bg-[#102B2E] cursor-pointer"
                        aria-label="Play voice note"
                      >
                        {playingAudioId === selectedOrder.id ? (
                          <Pause className="h-3.5 w-3.5" />
                        ) : (
                          <Play className="h-3.5 w-3.5 ml-0.5" />
                        )}
                      </button>
                      <div className="text-xs">
                        <p className="font-kannada font-medium text-[#173B3F]">
                          &ldquo;{selectedOrder.audio_transcript_kn || selectedOrder.raw_message}&rdquo;
                        </p>
                        <p className="mt-0.5 text-[11px] text-[#708284]">
                          Meaning: {selectedOrder.english_translation}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="mt-2 font-kannada text-sm font-medium text-[#173B3F]">
                        &ldquo;{selectedOrder.raw_message}&rdquo;
                      </p>
                      <p className="mt-1 text-xs text-[#4D6265]">
                        Meaning: {selectedOrder.english_translation}
                      </p>
                    </>
                  )}
                </div>

                {/* 2. Items List */}
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-wide text-[#4D6265]">
                      Items Requested
                    </h3>
                    <span className="text-[11px] text-[#708284]">
                      Use - / + to adjust quantity
                    </span>
                  </div>
                  <div className="divide-y divide-[#EFEAE0] rounded-[8px] border border-[#E2DDD3]">
                    {selectedOrder.parsed_items.map((item, idx) => (
                      <div
                        key={`${item.product_id}-${idx}`}
                        className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2.5 text-xs"
                      >
                        <div>
                          <p className="font-semibold text-[#173B3F]">
                            {item.matched_product_name || item.requested_name}
                          </p>
                          <div className="mt-0.5 flex items-center gap-2">
                            {item.available ? (
                              <span className="text-[11px] text-[#2F7D5B]">
                                In stock ({item.stock_qty} {item.unit})
                              </span>
                            ) : (
                              <Badge variant="red">Out of Stock</Badge>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-4">
                          {["pending_approval", "credit_warning"].includes(selectedOrder.status) ? (
                            <div className="inline-flex items-center gap-1.5 rounded-[5px] border border-[#CFC8BA] bg-[#FBF9F5] px-1.5 py-0.5">
                              <button
                                type="button"
                                onClick={() => handleQtyChange(idx, -1)}
                                className="px-1 font-bold text-[#173B3F] cursor-pointer"
                              >
                                -
                              </button>
                              <span className="min-w-[40px] text-center font-medium tabular-nums">
                                {item.qty} {item.unit}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleQtyChange(idx, 1)}
                                className="px-1 font-bold text-[#173B3F] cursor-pointer"
                              >
                                +
                              </button>
                            </div>
                          ) : (
                            <span className="tabular-nums text-[#4D6265]">
                              {item.qty} {item.unit}
                            </span>
                          )}
                          <span className="w-16 text-right font-bold tabular-nums text-[#173B3F]">
                            {formatINR(item.line_total)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 3. One Clear Next Step */}
                {selectedOrder.status === "needs_substitute" && missingItem ? (
                  <div className="rounded-[8px] border border-[#C95534]/45 bg-[#FFF8F5] p-4 space-y-3">
                    <p className="text-xs font-bold text-[#9D3E23]">
                      {missingItem.matched_product_name} is out of stock. Pick a replacement:
                    </p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {missingItem.substitute_options.map((sub) => {
                        const checked = selectedSubId === sub.product_id;
                        return (
                          <label
                            key={sub.product_id}
                            className={`flex items-start gap-2.5 rounded-[6px] border p-3 cursor-pointer ${
                              checked
                                ? "border-[#173B3F] bg-white ring-1 ring-[#173B3F]"
                                : "border-[#E2DDD3] bg-[#FBF9F5]"
                            }`}
                          >
                            <input
                              type="radio"
                              name="sub-choice"
                              checked={checked}
                              onChange={() => setEditedSubId(sub.product_id)}
                              className="mt-0.5 accent-[#173B3F]"
                            />
                            <div className="text-xs">
                              <p className="font-semibold text-[#173B3F]">{sub.name}</p>
                              <p className="mt-1 text-[#4D6265]">
                                <strong>{formatINR(sub.price)}</strong> · {sub.comparison_label}
                              </p>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void handleOrderDecision("cancel")}
                        disabled={submitting}
                      >
                        Cancel Order
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => void handleApplySubstitute()}
                        disabled={submitting || !selectedSubId}
                      >
                        Use Selected &amp; Continue
                      </Button>
                    </div>
                  </div>
                ) : selectedOrder.credit_exceeded &&
                  ["credit_warning", "pending_approval"].includes(selectedOrder.status) ? (
                  <div className="rounded-[8px] border border-[#B84646]/50 bg-[#FDF6F6] p-4 space-y-3">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#B84646]" />
                      <div className="text-xs">
                        <p className="font-bold text-[#8D2D2D]">
                          Credit Limit Reached for {selectedOrder.customer_name}
                        </p>
                        <p className="mt-1 text-[#4D6265]">
                          Already owes <strong>{formatINR(selectedOrder.customer_balance)}</strong>{" "}
                          (Limit: {formatINR(selectedOrder.customer_credit_limit)}). Adding{" "}
                          <strong>{formatINR(selectedOrder.total_amount)}</strong> makes it{" "}
                          <strong>{formatINR(selectedOrder.projected_balance)}</strong>.
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void handleOrderDecision("cancel")}
                        disabled={submitting}
                      >
                        <X className="h-3.5 w-3.5" />
                        Cancel Order
                      </Button>
                      <Button
                        size="sm"
                        variant="marigold"
                        onClick={() => void handleOrderDecision("ask_payment")}
                        disabled={submitting}
                      >
                        Ask for Payment First
                      </Button>
                      <Button
                        size="sm"
                        variant="success"
                        onClick={() => void handleOrderDecision("approve")}
                        disabled={submitting}
                      >
                        <Check className="h-3.5 w-3.5" />
                        Approve Credit Anyway
                      </Button>
                    </div>
                  </div>
                ) : selectedOrder.status === "pending_approval" ? (
                  <div className="space-y-3 rounded-[8px] border border-[#D9911B]/50 bg-[#FDF9F1] p-4">
                    <div>
                      <p className="text-xs font-bold text-[#173B3F]">
                        Ready to confirm &amp; reply to {selectedOrder.customer_name}?
                      </p>
                      <p className="text-[11px] text-[#4D6265]">
                        Edit the Kannada reply if needed, then click Confirm &amp; Send Reply.
                      </p>
                    </div>
                    <textarea
                      value={draftKn}
                      onChange={(e) => setEditedDraftKn(e.target.value)}
                      rows={2}
                      className="w-full rounded-[6px] border border-[#CFC8BA] bg-white p-2.5 font-kannada text-xs text-[#173B3F]"
                    />
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void handleOrderDecision("cancel")}
                        disabled={submitting}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void handleOrderDecision("approve", false)}
                        disabled={submitting}
                      >
                        <Check className="h-3.5 w-3.5" />
                        Confirm Only
                      </Button>
                      <Button
                        size="sm"
                        variant="success"
                        onClick={() => void handleOrderDecision("approve", true)}
                        disabled={submitting}
                      >
                        <Send className="h-3.5 w-3.5" />
                        Confirm &amp; Send Reply
                      </Button>
                    </div>
                  </div>
                ) : selectedOrder.status === "confirmation_pending" && pendingSendApproval ? (
                  <div className="space-y-3 rounded-[8px] border border-[#2F7D5B]/45 bg-[#F2F8F5] p-4">
                    <div>
                      <p className="text-xs font-bold text-[#1E563D]">
                        Order Confirmed! Send this Kannada reply to {selectedOrder.customer_name}:
                      </p>
                    </div>
                    <textarea
                      value={draftKn}
                      onChange={(e) => setEditedDraftKn(e.target.value)}
                      rows={2}
                      className="w-full rounded-[6px] border border-[#BBD4C6] bg-white p-2.5 font-kannada text-xs text-[#173B3F]"
                    />
                    <div className="flex justify-end">
                      <Button
                        size="sm"
                        variant="success"
                        onClick={() => void handleApproveSendMessage()}
                        disabled={submitting}
                      >
                        <Send className="h-3.5 w-3.5" />
                        Send WhatsApp Reply
                      </Button>
                    </div>
                  </div>
                ) : selectedOrder.status === "completed" ? (
                  <div className="flex items-center gap-2 rounded-[6px] border border-[#2F7D5B]/35 bg-[#2F7D5B]/10 px-4 py-3 text-xs font-semibold text-[#1E563D]">
                    <CheckCircle2 className="h-4 w-4" />
                    Order completed and WhatsApp confirmation sent.
                  </div>
                ) : null}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Simple Add Test Order Dialog */}
      <Dialog open={simModalOpen} onOpenChange={setSimModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Test WhatsApp Order</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 p-5 text-xs">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="font-semibold text-[#173B3F]">Customer</label>
                <select
                  value={simCustomerId}
                  onChange={(e) => setSimCustomerId(Number(e.target.value))}
                  className="mt-1 h-8 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-2 text-xs text-[#173B3F]"
                >
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({formatINR(c.current_balance)} due)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="font-semibold text-[#173B3F]">Message Type</label>
                <select
                  value={simChannel}
                  onChange={(e) =>
                    setSimChannel(e.target.value as "whatsapp_text" | "whatsapp_voice")
                  }
                  className="mt-1 h-8 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-2 text-xs text-[#173B3F]"
                >
                  <option value="whatsapp_text">Text Message</option>
                  <option value="whatsapp_voice">Voice Note</option>
                </select>
              </div>
            </div>
            <div>
              <label className="font-semibold text-[#173B3F]">Order Message</label>
              <textarea
                value={simMessage}
                onChange={(e) => setSimMessage(e.target.value)}
                rows={3}
                className="mt-1 w-full rounded-[6px] border border-[#CFC8BA] p-2 font-kannada text-xs text-[#173B3F]"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setSimModalOpen(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={() => void handleSimulateIncoming()} disabled={submitting}>
                Add Order
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
