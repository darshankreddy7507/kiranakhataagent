"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Phone, Send, Truck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorBanner, LoadingBlock, SuccessBanner } from "@/components/ui/state-banners";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type { Approval, Product, Supplier, SupplierOrder } from "@/lib/types";
import { formatDateTime, formatINR } from "@/lib/utils";

export default function SuppliersPage() {
  const { lang, t, refreshNotifications, realtimeTick } = useApp();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [lowStock, setLowStock] = useState<Product[]>([]);
  const [orders, setOrders] = useState<SupplierOrder[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [qtys, setQtys] = useState<Record<number, number>>({});
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null);
  const [editedDraftMsgKn, setEditedDraftMsgKn] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [supRes, poList, appList] = await Promise.all([
        api.listSuppliers(),
        api.listSupplierOrders(),
        api.listApprovals("pending"),
      ]);
      setError(null);
      setSuppliers(supRes.suppliers);
      setLowStock(supRes.low_stock_products);
      setOrders(poList);
      setApprovals(appList.filter((a) => a.action_type === "supplier_reorder"));

      const initQtys: Record<number, number> = {};
      for (const p of supRes.low_stock_products) {
        initQtys[p.id] = p.default_reorder_qty;
      }
      setQtys((prev) => ({ ...initQtys, ...prev }));
      if (!selectedSupplierId && supRes.suppliers.length > 0) {
        setSelectedSupplierId(supRes.suppliers[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load suppliers");
    } finally {
      setLoading(false);
    }
  }, [selectedSupplierId]);

  useEffect(() => {
    void Promise.resolve().then(() => loadData());
  }, [loadData, realtimeTick]);

  const activeSupplier = suppliers.find((s) => s.id === selectedSupplierId) || suppliers[0] || null;
  const supplierLowStock = useMemo(
    () => lowStock.filter((p) => !activeSupplier || p.supplier_id === activeSupplier.id),
    [lowStock, activeSupplier]
  );

  const defaultDraftMsgKn = useMemo(() => {
    if (!activeSupplier || supplierLowStock.length === 0) return "";
    const lines = supplierLowStock
      .map(
        (p) =>
          `• ${p.name_kn} (${p.name}): ${qtys[p.id] ?? p.default_reorder_qty} ${p.unit}`
      )
      .join("\n");
    return `ನಮಸ್ಕಾರ ${activeSupplier.contact_person} ಅವರೆ (${activeSupplier.name_kn}).\nಶ್ರೀ ಲಕ್ಷ್ಮೀ ಕಿರಾಣಾ ಸ್ಟೋರ್ಸ್‌ಗೆ ಈ ಕೆಳಗಿನ ಸ್ಟಾಕ್ ಕಳಿಸಿ:\n${lines}\nದಯವಿಟ್ಟು ಬಿಲ್ ಜೊತೆ ಕಳಿಸಿ.`;
  }, [activeSupplier, supplierLowStock, qtys]);

  const draftMsgKn = editedDraftMsgKn ?? defaultDraftMsgKn;

  const handleCreateDraft = async () => {
    if (!activeSupplier || supplierLowStock.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await api.createSupplierOrderDraft({
        supplier_id: activeSupplier.id,
        product_ids: supplierLowStock.map((p) => p.id),
        items: supplierLowStock.map((p) => ({
          product_id: p.id,
          ordered_qty: qtys[p.id] ?? p.default_reorder_qty,
        })),
        whatsapp_draft_kn: draftMsgKn,
      });
      setEditedDraftMsgKn(null);
      setBanner(`Order prepared for ${activeSupplier.name}. Click Approve & Send on the right.`);
      await loadData();
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not prepare order");
    } finally {
      setBusy(false);
    }
  };

  const handleApprovePO = async (po: SupplierOrder) => {
    const app = approvals.find((a) => a.entity_id === po.id && a.status === "pending");
    if (!app) return;
    setBusy(true);
    setError(null);
    try {
      await api.decideApproval(app.id, { decision: "approve" });
      setBanner(`WhatsApp order sent to ${po.supplier_name}!`);
      await loadData();
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send order");
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <LoadingBlock label="Loading suppliers..." />;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold text-[#173B3F] flex items-center gap-2">
          <Truck className="h-5 w-5 text-[#173B3F]" />
          {t("Suppliers", "ಸರಬರಾಜುದಾರರು")}
        </h2>
        <p className="text-xs text-[#4D6265]">
          {t(
            "Select a supplier to reorder low-stock items on WhatsApp.",
            "ಕಡಿಮೆ ಇರುವ ವಸ್ತುಗಳನ್ನು ಮರು-ಆರ್ಡರ್ ಮಾಡಲು ಸರಬರಾಜುದಾರರನ್ನು ಆಯ್ಕೆಮಾಡಿ."
          )}
        </p>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void loadData()} /> : null}
      {banner ? <SuccessBanner message={banner} onDismiss={() => setBanner(null)} /> : null}

      <div className="grid gap-3 md:grid-cols-3">
        {suppliers.map((sup) => {
          const isActive = activeSupplier?.id === sup.id;
          return (
            <button
              key={sup.id}
              type="button"
              onClick={() => {
                setSelectedSupplierId(sup.id);
                setEditedDraftMsgKn(null);
              }}
              className={`rounded-[8px] border p-4 text-left transition-colors cursor-pointer ${
                isActive
                  ? "border-[#173B3F] bg-white ring-1 ring-[#173B3F]"
                  : "border-[#E2DDD3] bg-white hover:border-[#CFC8BA]"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-bold text-[#173B3F]">
                  {lang === "kn" ? sup.name_kn : sup.name}
                </h3>
                {sup.low_stock_product_count > 0 ? (
                  <Badge variant="marigold">{sup.low_stock_product_count} low</Badge>
                ) : (
                  <Badge variant="green">Stocked</Badge>
                )}
              </div>
              <p className="mt-1 text-xs text-[#4D6265]">{sup.category_focus}</p>
              <p className="mt-2.5 flex items-center gap-1.5 text-[11px] text-[#708284]">
                <Phone className="h-3 w-3" />
                {sup.contact_person} · {sup.phone}
              </p>
            </button>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-6">
          <CardHeader className="bg-[#FBF9F5]">
            <CardTitle>Low Stock from {activeSupplier?.name}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {supplierLowStock.length === 0 ? (
              <EmptyState
                title="All items are well stocked"
                description="Nothing from this supplier is running low right now."
              />
            ) : (
              <>
                <div className="divide-y divide-[#EFEAE0] rounded-[6px] border border-[#E2DDD3]">
                  {supplierLowStock.map((p) => (
                    <div key={p.id} className="flex items-center justify-between gap-3 px-3 py-2.5 text-xs">
                      <div>
                        <p className="font-semibold text-[#173B3F]">{p.name}</p>
                        <p className="text-[11px] text-[#708284]">
                          Left: <strong>{p.stock_qty} {p.unit}</strong> (Min {p.reorder_level})
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <input
                          type="number"
                          min={1}
                          value={qtys[p.id] ?? p.default_reorder_qty}
                          onChange={(e) =>
                            setQtys((prev) => ({
                              ...prev,
                              [p.id]: Math.max(1, Number(e.target.value)),
                            }))
                          }
                          className="h-8 w-20 rounded-[5px] border border-[#CFC8BA] px-2 text-right text-xs tabular-nums"
                        />
                        <span className="text-[11px] text-[#708284]">{p.unit}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-[#4D6265]">
                    WhatsApp Message (Kannada)
                  </label>
                  <textarea
                    value={draftMsgKn}
                    onChange={(e) => setEditedDraftMsgKn(e.target.value)}
                    rows={4}
                    className="mt-1 w-full rounded-[6px] border border-[#CFC8BA] p-2.5 font-kannada text-xs text-[#173B3F]"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-xs text-[#4D6265]">
                    Estimated cost:{" "}
                    <strong className="text-[#173B3F]">
                      {formatINR(
                        supplierLowStock.reduce(
                          (s, p) => s + (qtys[p.id] ?? p.default_reorder_qty) * p.cost_price,
                          0
                        )
                      )}
                    </strong>
                  </span>
                  <Button size="sm" onClick={() => void handleCreateDraft()} disabled={busy}>
                    <Send className="h-3.5 w-3.5" />
                    Prepare Order
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-6">
          <CardHeader className="bg-[#FBF9F5]">
            <CardTitle>Supplier Orders ({orders.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {orders.length === 0 ? (
              <EmptyState
                title="No supplier orders yet"
                description="Prepare an order on the left to send it on WhatsApp."
              />
            ) : (
              orders.map((po) => (
                <div
                  key={po.id}
                  className="rounded-[8px] border border-[#E2DDD3] bg-[#FCFBF8] p-3.5 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-[#173B3F]">{po.supplier_name}</span>
                    <Badge
                      variant={
                        po.status === "approved_sent"
                          ? "green"
                          : po.status === "rejected"
                          ? "red"
                          : "marigold"
                      }
                    >
                      {po.status === "approved_sent"
                        ? "Sent"
                        : po.status === "pending_approval"
                        ? "Needs Approval"
                        : po.status === "rejected"
                        ? "Skipped"
                        : po.status}
                    </Badge>
                  </div>
                  <p className="font-kannada text-xs whitespace-pre-line text-[#4D6265]">
                    {po.whatsapp_draft_kn}
                  </p>
                  <div className="flex items-center justify-between border-t border-[#EAE5DC] pt-2">
                    <span className="text-[11px] text-[#708284]">
                      Est. {formatINR(po.total_estimated_cost)} · {formatDateTime(po.created_at)}
                    </span>
                    {po.status === "pending_approval" ? (
                      <Button
                        size="sm"
                        variant="success"
                        onClick={() => void handleApprovePO(po)}
                        disabled={busy}
                      >
                        <Check className="h-3.5 w-3.5" />
                        Approve &amp; Send
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
