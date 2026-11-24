"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDownLeft,
  ArrowUpRight,
  BellRing,
  BookOpenText,
  Check,
  CreditCard,
  IndianRupee,
  PhoneCall,
  Send,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState, ErrorBanner, LoadingBlock, SuccessBanner } from "@/components/ui/state-banners";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type {
  Approval,
  Customer,
  CustomerDetail,
  OverdueQueueItem,
  PaymentLink,
} from "@/lib/types";
import { formatDate, formatDateTime, formatINR } from "@/lib/utils";

function stageBadge(stage: number) {
  if (stage === 0) return <Badge variant="green">On Time</Badge>;
  if (stage === 1) return <Badge variant="neutral">1st Gentle Reminder</Badge>;
  if (stage === 2) return <Badge variant="marigold">2nd Follow-up</Badge>;
  if (stage === 3) return <Badge variant="terracotta">3rd Firm Request</Badge>;
  return <Badge variant="red">Call Customer</Badge>;
}

export default function KhataPage() {
  const { lang, t, refreshNotifications, realtimeTick } = useApp();
  const [tab, setTab] = useState<"ledger" | "overdue" | "links">("ledger");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [overdueQueue, setOverdueQueue] = useState<OverdueQueueItem[]>([]);
  const [paymentLinks, setPaymentLinks] = useState<PaymentLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [payModalOpen, setPayModalOpen] = useState(false);
  const [payCustomerId, setPayCustomerId] = useState<number>(0);
  const [payAmount, setPayAmount] = useState<string>("500");
  const [payLinkId, setPayLinkId] = useState<number | undefined>(undefined);
  const [paySubmitting, setPaySubmitting] = useState(false);
  const [thankYouApproval, setThankYouApproval] = useState<Approval | null>(null);
  const [paymentResultNote, setPaymentResultNote] = useState<string | null>(null);

  const [editedReminders, setEditedReminders] = useState<Record<number, string>>({});
  const [dirtyReminders, setDirtyReminders] = useState<Record<number, boolean>>({});
  const [draftedApprovalByCustomer, setDraftedApprovalByCustomer] = useState<Record<number, Approval>>({});
  const [busyCustomerId, setBusyCustomerId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [custs, queue, links] = await Promise.all([
        api.listCustomers(),
        api.getOverdueQueue(),
        api.listPaymentLinks(),
      ]);
      setError(null);
      setCustomers(custs);
      setOverdueQueue(queue);
      setPaymentLinks(links);
      setEditedReminders((prev) => {
        const next: Record<number, string> = {};
        for (const item of queue) {
          const cid = item.customer.id;
          next[cid] = dirtyReminders[cid] && prev[cid] ? prev[cid] : item.preview_kn;
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load khata");
    } finally {
      setLoading(false);
    }
  }, [dirtyReminders]);

  useEffect(() => {
    void Promise.resolve().then(() => loadData());
  }, [loadData, realtimeTick]);

  const openCustomerDrawer = async (customerId: number) => {
    setDrawerOpen(true);
    setDetailLoading(true);
    try {
      const res = await api.getCustomerDetail(customerId);
      setDetail(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load history");
    } finally {
      setDetailLoading(false);
    }
  };

  const openSimulatePayment = (cust: Customer, link?: PaymentLink | null) => {
    setPayCustomerId(cust.id);
    setPayLinkId(link?.id);
    setPayAmount(
      cust.current_balance > 500
        ? String(Math.round(cust.current_balance / 2))
        : String(cust.current_balance)
    );
    setThankYouApproval(null);
    setPaymentResultNote(null);
    setPayModalOpen(true);
  };

  const handleSimulatePayment = async () => {
    const amt = Number(payAmount);
    if (!amt || amt <= 0) {
      setError("Please enter an amount greater than ₹0");
      return;
    }
    setPaySubmitting(true);
    setError(null);
    try {
      const res = await api.simulatePayment({
        payment_link_id: payLinkId,
        customer_id: payCustomerId,
        amount_paid: amt,
      });
      setThankYouApproval(res.thank_you_approval);
      const msg = `Recorded ${formatINR(res.amount_paid)} payment for ${res.customer.name}. Balance is now ${formatINR(
        res.new_balance
      )}.`;
      setPaymentResultNote(msg);
      setBanner(msg);
      await loadData();
      await refreshNotifications();
      if (drawerOpen && detail?.customer.id === res.customer.id) {
        const refreshedDetail = await api.getCustomerDetail(res.customer.id);
        setDetail(refreshedDetail);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record payment");
    } finally {
      setPaySubmitting(false);
    }
  };

  const handleApproveThankYou = async () => {
    if (!thankYouApproval) return;
    setPaySubmitting(true);
    try {
      await api.decideApproval(thankYouApproval.id, { decision: "approve" });
      setBanner("Thank-you WhatsApp message sent!");
      setThankYouApproval({ ...thankYouApproval, status: "approved" });
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send message");
    } finally {
      setPaySubmitting(false);
    }
  };

  const handleQueueReminder = async (item: OverdueQueueItem) => {
    setBusyCustomerId(item.customer.id);
    setError(null);
    try {
      const app = await api.draftReminder({
        customer_id: item.customer.id,
        custom_message_kn: editedReminders[item.customer.id] || item.preview_kn,
        custom_message_en: item.preview_en,
      });
      setDraftedApprovalByCustomer((prev) => ({ ...prev, [item.customer.id]: app }));
      setBanner(`Reminder ready for ${item.customer.name}. Click Send to confirm.`);
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not prepare reminder");
    } finally {
      setBusyCustomerId(null);
    }
  };

  const handleApproveReminderSend = async (customerId: number) => {
    const app = draftedApprovalByCustomer[customerId];
    if (!app) return;
    setBusyCustomerId(customerId);
    try {
      await api.decideApproval(app.id, {
        decision: "approve",
        edited_payload: { body_kn: editedReminders[customerId] },
      });
      setBanner("Reminder sent!");
      setDraftedApprovalByCustomer((prev) => {
        const next = { ...prev };
        delete next[customerId];
        return next;
      });
      await loadData();
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send reminder");
    } finally {
      setBusyCustomerId(null);
    }
  };

  if (loading) return <LoadingBlock label="Opening customer khata..." />;

  const totalOutstanding = customers.reduce((s, c) => s + c.current_balance, 0);
  const overLimitCount = customers.filter((c) => c.over_limit).length;
  const activeLinksCount = paymentLinks.filter((l) => l.status !== "paid").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#173B3F] flex items-center gap-2">
            <BookOpenText className="h-5 w-5 text-[#173B3F]" />
            {t("Customer Khata", "ಗ್ರಾಹಕರ ಖಾತೆ ಪುಸ್ತಕ")}
          </h2>
          <p className="text-xs text-[#4D6265]">
            {t(
              "See who owes money, send polite reminders, and record UPI payments.",
              "ಬಾಕಿ ಹಣ, ಸೌಮ್ಯ ನೆನಪು ಮತ್ತು UPI ಪಾವತಿ ದಾಖಲೆ."
            )}
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => {
            const target = customers.find((c) => c.current_balance > 0) || customers[0];
            if (target) openSimulatePayment(target);
          }}
        >
          <CreditCard className="h-3.5 w-3.5" />
          Record Payment
        </Button>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void loadData()} /> : null}
      {banner ? <SuccessBanner message={banner} onDismiss={() => setBanner(null)} /> : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card>
          <CardContent className="p-3.5">
            <p className="text-xs text-[#4D6265]">Total to Collect</p>
            <p className="mt-1 text-lg font-bold tabular-nums text-[#173B3F]">
              {formatINR(totalOutstanding)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3.5">
            <p className="text-xs text-[#4D6265]">Over Credit Limit</p>
            <p className="mt-1 text-lg font-bold tabular-nums text-[#B84646]">
              {overLimitCount} customers
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3.5">
            <p className="text-xs text-[#4D6265]">Overdue Accounts</p>
            <p className="mt-1 text-lg font-bold tabular-nums text-[#D9911B]">
              {overdueQueue.length} customers
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3.5">
            <p className="text-xs text-[#4D6265]">Open UPI Links</p>
            <p className="mt-1 text-lg font-bold tabular-nums text-[#2F7D5B]">
              {activeLinksCount} active
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-wrap gap-1.5 border-b border-[#E2DDD3] pb-2">
        {(
          [
            { key: "ledger", label: `Customers (${customers.length})` },
            { key: "overdue", label: `Send Reminders (${overdueQueue.length})` },
            { key: "links", label: `UPI Payment Links (${paymentLinks.length})` },
          ] as const
        ).map((tItem) => (
          <button
            key={tItem.key}
            type="button"
            onClick={() => setTab(tItem.key)}
            className={`rounded-[6px] px-3 py-1.5 text-xs font-semibold cursor-pointer ${
              tab === tItem.key
                ? "bg-[#173B3F] text-white"
                : "border border-[#DDD7CA] bg-white text-[#4D6265] hover:bg-[#FBF9F5]"
            }`}
          >
            {tItem.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Simple 5-Column Customer Ledger */}
      {tab === "ledger" ? (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#E2DDD3] bg-[#FBF9F5] text-[11px] font-semibold text-[#4D6265]">
                <tr>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3 text-right">Balance Due</th>
                  <th className="px-4 py-3">Credit Limit</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EFEAE0]">
                {customers.map((c) => (
                  <tr key={c.id} className="hover:bg-[#FBF9F5]">
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => void openCustomerDrawer(c.id)}
                        className="text-left hover:underline cursor-pointer"
                      >
                        <p className="font-semibold text-[#173B3F]">
                          {lang === "kn" ? c.name_kn : c.name}
                        </p>
                        <p className="text-[11px] text-[#708284]">
                          {c.phone} · Last paid {formatDate(c.last_payment_date)}
                        </p>
                      </button>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <p
                        className={`text-sm font-bold tabular-nums ${
                          c.over_limit
                            ? "text-[#B84646]"
                            : c.current_balance > 0
                            ? "text-[#173B3F]"
                            : "text-[#2F7D5B]"
                        }`}
                      >
                        {formatINR(c.current_balance)}
                      </p>
                      {c.over_limit ? (
                        <Badge variant="red" className="mt-0.5">
                          <AlertTriangle className="h-2.5 w-2.5" /> Over Limit
                        </Badge>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-[#4D6265]">
                      {formatINR(c.credit_limit)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="space-y-1">
                        {stageBadge(c.reminder_stage)}
                        {c.days_overdue > 0 ? (
                          <p className="text-[11px] text-[#708284]">{c.days_overdue} days overdue</p>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => void openCustomerDrawer(c.id)}
                        >
                          History
                        </Button>
                        {c.current_balance > 0 ? (
                          <Button
                            size="sm"
                            variant="success"
                            onClick={() => openSimulatePayment(c)}
                          >
                            Record Payment
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {/* Tab 2: Send Reminders */}
      {tab === "overdue" ? (
        <div className="space-y-3">
          {overdueQueue.length === 0 ? (
            <EmptyState
              title="No overdue payments"
              description="All customer balances are on time."
            />
          ) : (
            overdueQueue.map((item) => {
              const cid = item.customer.id;
              const drafted = draftedApprovalByCustomer[cid];
              const isStage4 = item.recommended_stage >= 4;
              return (
                <Card
                  key={cid}
                  className={isStage4 ? "border-[#B84646]/45" : "border-[#E2DDD3]"}
                >
                  <CardContent className="p-4 space-y-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-bold text-[#173B3F]">
                            {item.customer.name}
                          </h3>
                          {stageBadge(item.recommended_stage)}
                        </div>
                        <p className="mt-0.5 text-xs text-[#4D6265]">
                          {item.customer.days_overdue} days overdue · {item.customer.phone}
                        </p>
                      </div>
                      <p className="text-base font-bold tabular-nums text-[#B84646]">
                        {formatINR(item.customer.current_balance)}
                      </p>
                    </div>

                    <div>
                      <label className="text-[11px] font-semibold text-[#4D6265]">
                        {isStage4
                          ? "Call Note (Recommended to call customer directly)"
                          : "Message to send in Kannada (with UPI link)"}
                      </label>
                      <textarea
                        value={editedReminders[cid] ?? item.preview_kn}
                        onChange={(e) => {
                          setDirtyReminders((prev) => ({ ...prev, [cid]: true }));
                          setEditedReminders((prev) => ({ ...prev, [cid]: e.target.value }));
                        }}
                        rows={2}
                        className="mt-1 w-full rounded-[6px] border border-[#CFC8BA] bg-white p-2.5 font-kannada text-xs text-[#173B3F]"
                      />
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openSimulatePayment(item.customer, item.payment_link)}
                      >
                        <IndianRupee className="h-3.5 w-3.5 text-[#2F7D5B]" />
                        Mark Paid
                      </Button>

                      {drafted ? (
                        <Button
                          size="sm"
                          variant="success"
                          onClick={() => void handleApproveReminderSend(cid)}
                          disabled={busyCustomerId === cid}
                        >
                          <Check className="h-3.5 w-3.5" />
                          {isStage4 ? "Confirm Call Task" : "Approve & Send Reminder"}
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant={isStage4 ? "danger" : "marigold"}
                          onClick={() => void handleQueueReminder(item)}
                          disabled={busyCustomerId === cid}
                        >
                          {isStage4 ? (
                            <>
                              <PhoneCall className="h-3.5 w-3.5" />
                              Schedule Call
                            </>
                          ) : (
                            <>
                              <BellRing className="h-3.5 w-3.5" />
                              Prepare Reminder
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      ) : null}

      {/* Tab 3: UPI Payment Links */}
      {tab === "links" ? (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#E2DDD3] bg-[#FBF9F5] text-[11px] font-semibold text-[#4D6265]">
                <tr>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Payment Link</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3 text-right">Paid</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EFEAE0]">
                {paymentLinks.map((link) => {
                  const cust = customers.find((c) => c.id === link.customer_id);
                  return (
                    <tr key={link.id} className="hover:bg-[#FBF9F5]">
                      <td className="px-4 py-3 font-semibold text-[#173B3F]">
                        {link.customer_name}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-[#4D6265]">
                        {link.short_url}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatINR(link.amount_requested)}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums text-[#2F7D5B]">
                        {formatINR(link.amount_paid)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          variant={
                            link.status === "paid"
                              ? "green"
                              : link.status === "partial"
                              ? "marigold"
                              : "neutral"
                          }
                        >
                          {link.status === "paid"
                            ? "Paid"
                            : link.status === "partial"
                            ? "Partial"
                            : "Waiting"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {link.status !== "paid" && cust ? (
                          <Button
                            size="sm"
                            variant="success"
                            onClick={() => openSimulatePayment(cust, link)}
                          >
                            Mark Paid
                          </Button>
                        ) : (
                          <span className="text-[11px] text-[#708284]">
                            {formatDateTime(link.paid_at)}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {/* Customer History Drawer */}
      <Dialog open={drawerOpen} onOpenChange={setDrawerOpen}>
        <DialogContent drawer>
          <DialogHeader>
            <DialogTitle>
              {detail ? `${detail.customer.name} — Khata History` : "Customer History"}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {detailLoading || !detail ? (
              <LoadingBlock label="Loading customer history..." />
            ) : (
              <>
                <div className="flex items-center justify-between rounded-[8px] border border-[#E2DDD3] bg-white p-4">
                  <div>
                    <p className="text-xs text-[#708284]">Current Balance</p>
                    <p
                      className={`text-xl font-bold tabular-nums ${
                        detail.customer.over_limit ? "text-[#B84646]" : "text-[#173B3F]"
                      }`}
                    >
                      {formatINR(detail.customer.current_balance)}
                    </p>
                    <p className="text-[11px] text-[#708284]">
                      Credit Limit: {formatINR(detail.customer.credit_limit)}
                    </p>
                  </div>
                  {detail.customer.current_balance > 0 ? (
                    <Button
                      size="sm"
                      variant="success"
                      onClick={() =>
                        openSimulatePayment(
                          detail.customer,
                          detail.payment_links.find((l) => l.status !== "paid")
                        )
                      }
                    >
                      Record Payment
                    </Button>
                  ) : null}
                </div>

                <div className="divide-y divide-[#EFEAE0] rounded-[8px] border border-[#E2DDD3] bg-white">
                  {detail.entries.map((entry) => {
                    const isPayment = entry.amount < 0;
                    return (
                      <div key={entry.id} className="flex items-start justify-between gap-3 p-3 text-xs">
                        <div className="flex items-start gap-2">
                          {isPayment ? (
                            <ArrowDownLeft className="mt-0.5 h-4 w-4 shrink-0 text-[#2F7D5B]" />
                          ) : (
                            <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-[#C95534]" />
                          )}
                          <div>
                            <p className="font-medium text-[#173B3F]">{entry.description}</p>
                            <p className="text-[10px] text-[#708284]">
                              {formatDateTime(entry.created_at)}
                            </p>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <p
                            className={`font-bold tabular-nums ${
                              isPayment ? "text-[#2F7D5B]" : "text-[#C95534]"
                            }`}
                          >
                            {isPayment ? "-" : "+"}
                            {formatINR(Math.abs(entry.amount))}
                          </p>
                          <p className="text-[10px] tabular-nums text-[#708284]">
                            Bal: {formatINR(entry.balance_after)}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Record Payment Modal */}
      <Dialog open={payModalOpen} onOpenChange={setPayModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record Customer Payment</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 p-5 text-xs">
            <div>
              <label className="font-semibold text-[#173B3F]">Customer</label>
              <select
                value={payCustomerId}
                onChange={(e) => {
                  const cid = Number(e.target.value);
                  setPayCustomerId(cid);
                  setPayLinkId(undefined);
                  const found = customers.find((c) => c.id === cid);
                  if (found) setPayAmount(String(found.current_balance));
                }}
                className="mt-1 h-8 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-2 text-xs text-[#173B3F]"
              >
                {customers
                  .filter((c) => c.current_balance > 0)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} — Owes {formatINR(c.current_balance)}
                    </option>
                  ))}
              </select>
            </div>

            <div>
              <label className="font-semibold text-[#173B3F]">Amount Received (₹)</label>
              <div className="mt-1 flex gap-2">
                <input
                  type="number"
                  min={1}
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                  className="h-8 flex-1 rounded-[6px] border border-[#CFC8BA] bg-white px-3 text-xs tabular-nums text-[#173B3F]"
                />
                {(() => {
                  const c = customers.find((x) => x.id === payCustomerId);
                  if (!c) return null;
                  return (
                    <>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setPayAmount(String(Math.round(c.current_balance / 2)))}
                      >
                        Half
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setPayAmount(String(c.current_balance))}
                      >
                        Full
                      </Button>
                    </>
                  );
                })()}
              </div>
            </div>

            {paymentResultNote ? <SuccessBanner message={paymentResultNote} /> : null}

            {thankYouApproval ? (
              <div className="space-y-2 rounded-[6px] border border-[#2F7D5B]/40 bg-[#F2F8F5] p-3">
                <p className="font-bold text-[#1E563D]">Send Kannada Thank-You on WhatsApp?</p>
                <p className="font-kannada text-xs text-[#173B3F]">
                  {String(thankYouApproval.payload?.body_kn || "")}
                </p>
                {thankYouApproval.status === "pending" ? (
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      variant="success"
                      onClick={() => void handleApproveThankYou()}
                      disabled={paySubmitting}
                    >
                      <Send className="h-3.5 w-3.5" />
                      Send Thank-You
                    </Button>
                  </div>
                ) : (
                  <Badge variant="green">Sent</Badge>
                )}
              </div>
            ) : null}

            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" size="sm" onClick={() => setPayModalOpen(false)}>
                Close
              </Button>
              <Button
                size="sm"
                variant="success"
                onClick={() => void handleSimulatePayment()}
                disabled={paySubmitting}
              >
                {paySubmitting ? "Saving..." : "Mark Payment Received"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
