"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Camera,
  Check,
  FileText,
  Package,
  Plus,
  Search,
  Truck,
  Upload,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState, ErrorBanner, LoadingBlock, SuccessBanner } from "@/components/ui/state-banners";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type { Approval, Product, Supplier, SupplierBill } from "@/lib/types";
import { formatDate, formatINR } from "@/lib/utils";

function stockBadge(status: Product["stock_status"]) {
  if (status === "out_of_stock") return <Badge variant="red">Out of Stock</Badge>;
  if (status === "low_stock") return <Badge variant="marigold">Low Stock</Badge>;
  return <Badge variant="green">In Stock</Badge>;
}

export default function InventoryPage() {
  const { lang, t, refreshNotifications, realtimeTick } = useApp();
  const [tab, setTab] = useState<"stock" | "bill_ocr">("stock");
  const [products, setProducts] = useState<Product[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [bills, setBills] = useState<SupplierBill[]>([]);
  const [filter, setFilter] = useState<"all" | "low" | "out_of_stock">("all");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const [reorderTarget, setReorderTarget] = useState<Product | null>(null);
  const [reorderQty, setReorderQty] = useState<number>(10);
  const [reorderApproval, setReorderApproval] = useState<Approval | null>(null);
  const [busy, setBusy] = useState(false);

  // Add Inventory modal state
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [addMode, setAddMode] = useState<"existing" | "new">("existing");
  const [addProductId, setAddProductId] = useState<number>(0);
  const [addQty, setAddQty] = useState<string>("10");
  const [addNote, setAddNote] = useState<string>("");
  const [newName, setNewName] = useState("");
  const [newNameKn, setNewNameKn] = useState("");
  const [newCategory, setNewCategory] = useState("Staples");
  const [newUnit, setNewUnit] = useState("kg");
  const [newPrice, setNewPrice] = useState("60");
  const [newStockQty, setNewStockQty] = useState("15");
  const [newReorderLevel, setNewReorderLevel] = useState("5");
  const [newSupplierId, setNewSupplierId] = useState<number>(1);

  const [billFile, setBillFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [prods, billList, supRes] = await Promise.all([
        api.listInventory("all"),
        api.listBills(),
        api.listSuppliers(),
      ]);
      setError(null);
      setProducts(prods);
      setBills(billList);
      setSuppliers(supRes.suppliers);
      if (prods.length > 0 && addProductId === 0) setAddProductId(prods[0].id);
      if (supRes.suppliers.length > 0) setNewSupplierId(supRes.suppliers[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load stock");
    } finally {
      setLoading(false);
    }
  }, [addProductId]);

  useEffect(() => {
    void Promise.resolve().then(() => loadData());
  }, [loadData, realtimeTick]);

  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      if (filter === "low" && p.stock_status === "in_stock") return false;
      if (filter === "out_of_stock" && p.stock_status !== "out_of_stock") return false;
      if (query.trim()) {
        const q = query.trim().toLowerCase();
        return (
          p.name.toLowerCase().includes(q) ||
          p.name_kn.includes(query.trim()) ||
          p.supplier_name.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [products, filter, query]);

  const openAddStockFor = (prod?: Product) => {
    setAddMode("existing");
    if (prod) {
      setAddProductId(prod.id);
    } else if (products.length > 0 && !addProductId) {
      setAddProductId(products[0].id);
    }
    setAddQty("10");
    setAddNote("");
    setAddModalOpen(true);
  };

  const handleSaveAddInventory = async () => {
    setBusy(true);
    setError(null);
    try {
      if (addMode === "existing") {
        const qty = Number(addQty);
        if (!addProductId || !qty || qty <= 0) {
          setError("Please select an item and enter a valid quantity.");
          setBusy(false);
          return;
        }
        const updated = await api.addInventoryStock({
          product_id: addProductId,
          quantity_added: qty,
          note: addNote.trim() || undefined,
        });
        setBanner(
          `Added +${qty} ${updated.unit} to ${updated.name}. Total stock is now ${updated.stock_qty} ${updated.unit}.`
        );
      } else {
        if (!newName.trim() || Number(newPrice) <= 0) {
          setError("Please enter an item name and valid price.");
          setBusy(false);
          return;
        }
        const created = await api.createInventoryProduct({
          name: newName.trim(),
          name_kn: newNameKn.trim() || undefined,
          category: newCategory,
          unit: newUnit,
          price: Number(newPrice),
          stock_qty: Math.max(0, Number(newStockQty) || 0),
          reorder_level: Math.max(0, Number(newReorderLevel) || 5),
          supplier_id: newSupplierId,
        });
        setBanner(`Added new item "${created.name}" (${created.stock_qty} ${created.unit}) to shop stock.`);
        setNewName("");
        setNewNameKn("");
      }
      setAddModalOpen(false);
      await loadData();
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add inventory");
    } finally {
      setBusy(false);
    }
  };

  const openReorderModal = (prod: Product) => {
    setReorderTarget(prod);
    setReorderQty(prod.default_reorder_qty);
    setReorderApproval(null);
  };

  const handleDraftReorder = async () => {
    if (!reorderTarget) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.createSupplierOrderDraft({
        supplier_id: reorderTarget.supplier_id,
        product_ids: [reorderTarget.id],
        items: [{ product_id: reorderTarget.id, ordered_qty: reorderQty }],
      });
      setReorderApproval(res.approval);
      setBanner(`Order prepared for ${reorderTarget.name}. Review & send below.`);
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not prepare order");
    } finally {
      setBusy(false);
    }
  };

  const handleApproveReorderNow = async () => {
    if (!reorderApproval) return;
    setBusy(true);
    try {
      await api.decideApproval(reorderApproval.id, { decision: "approve" });
      setBanner("Supplier WhatsApp order sent!");
      setReorderApproval({ ...reorderApproval, status: "approved" });
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send order");
    } finally {
      setBusy(false);
    }
  };

  const handleBillUpload = async (scenarioOverride?: string) => {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      if (billFile && !scenarioOverride) {
        form.append("file", billFile);
      }
      form.append("scenario", scenarioOverride || "kaveri_staples");
      const res = await api.uploadBill(form);
      setBanner(`Read bill #${res.bill.invoice_number}. Check items below and click Add to Stock.`);
      setBillFile(null);
      await loadData();
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read bill");
    } finally {
      setUploading(false);
    }
  };

  const handleApproveBill = async (bill: SupplierBill) => {
    if (!bill.approval_id) return;
    setBusy(true);
    setError(null);
    try {
      await api.decideApproval(bill.approval_id, { decision: "approve" });
      setBanner(`Added ${bill.extracted_items.length} items from bill ${bill.invoice_number} to stock!`);
      await loadData();
      await refreshNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add stock");
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <LoadingBlock label="Loading shop stock..." />;

  const lowCount = products.filter((p) => p.stock_status !== "in_stock").length;
  const outCount = products.filter((p) => p.stock_status === "out_of_stock").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#173B3F] flex items-center gap-2">
            <Package className="h-5 w-5 text-[#173B3F]" />
            {t("Shop Stock & Bill Scan", "ದಾಸ್ತಾನು ಮತ್ತು ಬಿಲ್ ಸ್ಕ್ಯಾನ್")}
          </h2>
          <p className="text-xs text-[#4D6265]">
            {t(
              "Check what is running low, order from suppliers, or scan a wholesale bill.",
              "ಕಡಿಮೆ ಇರುವ ವಸ್ತುಗಳನ್ನು ನೋಡಿ, ಆರ್ಡರ್ ಮಾಡಿ ಅಥವಾ ಬಿಲ್ ಫೋಟೋ ಸೇರಿಸಿ."
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setTab("bill_ocr")}>
            <Camera className="h-3.5 w-3.5" />
            Scan Supplier Bill
          </Button>
          <Button size="sm" variant="success" onClick={() => openAddStockFor()}>
            <Plus className="h-3.5 w-3.5" />
            Add Inventory
          </Button>
        </div>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void loadData()} /> : null}
      {banner ? <SuccessBanner message={banner} onDismiss={() => setBanner(null)} /> : null}

      <div className="flex flex-wrap gap-1.5 border-b border-[#E2DDD3] pb-2">
        <button
          type="button"
          onClick={() => setTab("stock")}
          className={`rounded-[6px] px-3 py-1.5 text-xs font-semibold cursor-pointer ${
            tab === "stock"
              ? "bg-[#173B3F] text-white"
              : "border border-[#DDD7CA] bg-white text-[#4D6265] hover:bg-[#FBF9F5]"
          }`}
        >
          Shop Stock ({products.length})
        </button>
        <button
          type="button"
          onClick={() => setTab("bill_ocr")}
          className={`rounded-[6px] px-3 py-1.5 text-xs font-semibold cursor-pointer ${
            tab === "bill_ocr"
              ? "bg-[#173B3F] text-white"
              : "border border-[#DDD7CA] bg-white text-[#4D6265] hover:bg-[#FBF9F5]"
          }`}
        >
          Scan Supplier Bill ({bills.length})
        </button>
      </div>

      {tab === "stock" ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5">
              {[
                { key: "all", label: `All Items (${products.length})` },
                { key: "low", label: `Low Stock (${lowCount})` },
                { key: "out_of_stock", label: `Out of Stock (${outCount})` },
              ].map((chip) => (
                <button
                  key={chip.key}
                  type="button"
                  onClick={() => setFilter(chip.key as typeof filter)}
                  className={`rounded-[5px] border px-2.5 py-1 text-xs font-medium cursor-pointer ${
                    filter === chip.key
                      ? "border-[#173B3F] bg-[#173B3F] text-white"
                      : "border-[#DDD7CA] bg-white text-[#4D6265] hover:bg-[#FBF9F5]"
                  }`}
                >
                  {chip.label}
                </button>
              ))}
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#708284]" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search item or supplier..."
                className="h-8 w-full rounded-[6px] border border-[#CFC8BA] bg-white pl-8 pr-3 text-xs text-[#173B3F]"
              />
            </div>
          </div>

          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[#E2DDD3] bg-[#FBF9F5] text-[11px] font-semibold text-[#4D6265]">
                  <tr>
                    <th className="px-4 py-3">Item</th>
                    <th className="px-4 py-3 text-right">Price</th>
                    <th className="px-4 py-3 text-right">In Stock</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EFEAE0]">
                  {filteredProducts.map((p) => (
                    <tr key={p.id} className="hover:bg-[#FBF9F5]">
                      <td className="px-4 py-3">
                        <p className="font-semibold text-[#173B3F]">
                          {lang === "kn" ? p.name_kn : p.name}
                        </p>
                        <p className="text-[11px] text-[#708284]">
                          {p.supplier_name} · Restocked {formatDate(p.last_restocked_at)}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums">
                        {formatINR(p.price)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="font-bold tabular-nums text-[#173B3F]">
                          {p.stock_qty} {p.unit}
                        </span>
                        <p className="text-[10px] text-[#708284]">
                          Min: {p.reorder_level} {p.unit}
                        </p>
                      </td>
                      <td className="px-4 py-3">{stockBadge(p.stock_status)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openAddStockFor(p)}
                          >
                            <Plus className="h-3 w-3" />
                            Add Stock
                          </Button>
                          {p.stock_status !== "in_stock" ? (
                            <Button
                              size="sm"
                              variant="marigold"
                              onClick={() => openReorderModal(p)}
                            >
                              <Truck className="h-3 w-3" />
                              Order
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
        </>
      ) : (
        <div className="grid gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-4 w-4 text-[#C95534]" />
                Upload Supplier Bill Photo
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <label className="flex flex-col items-center justify-center rounded-[8px] border border-dashed border-[#C9C1B2] bg-[#FBF9F5] p-6 text-center cursor-pointer hover:border-[#173B3F]">
                <Camera className="h-6 w-6 text-[#173B3F]" />
                <span className="mt-2 font-semibold text-[#173B3F]">
                  {billFile ? billFile.name : "Tap to choose bill photo"}
                </span>
                <span className="mt-0.5 text-[11px] text-[#708284]">
                  JPG or PNG image
                </span>
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => setBillFile(e.target.files?.[0] || null)}
                />
              </label>

              {billFile ? (
                <Button
                  className="w-full"
                  onClick={() => void handleBillUpload()}
                  disabled={uploading}
                >
                  <FileText className="h-3.5 w-3.5" />
                  {uploading ? "Reading Bill..." : "Read Uploaded Bill"}
                </Button>
              ) : null}

              <div className="border-t border-[#EFEAE0] pt-3 space-y-2">
                <p className="text-[11px] font-medium text-[#708284]">
                  Or test with a sample supplier bill:
                </p>
                <div className="grid gap-1.5">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void handleBillUpload("kaveri_staples")}
                    disabled={uploading}
                  >
                    Try Kaveri Agro Bill (Atta, Rice, Dal, Sugar)
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void handleBillUpload("ganesh_oil")}
                    disabled={uploading}
                  >
                    Try Sri Ganesh Oil Bill (Oil, Ghee, Spices)
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="lg:col-span-7 space-y-3">
            {bills.length === 0 ? (
              <EmptyState
                title="No bills scanned yet"
                description="Upload a photo or click one of the sample bills on the left."
              />
            ) : (
              bills.map((bill) => (
                <Card key={bill.id}>
                  <CardHeader className="bg-[#FBF9F5]">
                    <div>
                      <div className="flex items-center gap-2">
                        <CardTitle>{bill.supplier_name_extracted}</CardTitle>
                        <Badge variant={bill.status === "approved" ? "green" : "marigold"}>
                          {bill.status === "approved" ? "Added to Stock" : "Check & Approve"}
                        </Badge>
                      </div>
                      <p className="mt-0.5 text-[11px] text-[#708284]">
                        Bill #{bill.invoice_number} · {bill.bill_date}
                      </p>
                    </div>
                    <p className="text-base font-bold tabular-nums text-[#173B3F]">
                      {formatINR(bill.total_amount)}
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="divide-y divide-[#EFEAE0] rounded-[6px] border border-[#E2DDD3] text-xs">
                      {bill.extracted_items.map((item, i) => (
                        <div key={i} className="flex items-center justify-between px-3 py-2">
                          <span className="font-medium text-[#173B3F]">
                            {item.matched_product_name}
                          </span>
                          <div className="flex items-center gap-4 tabular-nums">
                            <span className="text-[#2F7D5B] font-semibold">
                              +{item.quantity} {item.unit}
                            </span>
                            <span className="font-bold text-[#173B3F]">
                              {formatINR(item.line_total)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>

                    {bill.status === "pending_approval" ? (
                      <div className="flex justify-end">
                        <Button
                          size="sm"
                          variant="success"
                          onClick={() => void handleApproveBill(bill)}
                          disabled={busy}
                        >
                          <Check className="h-3.5 w-3.5" />
                          Approve &amp; Add to Stock
                        </Button>
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </div>
      )}

      {/* Reorder Modal */}
      <Dialog open={Boolean(reorderTarget)} onOpenChange={(o) => !o && setReorderTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Order Stock — {reorderTarget?.name}</DialogTitle>
          </DialogHeader>
          {reorderTarget ? (
            <div className="space-y-3 p-5 text-xs">
              <p className="text-[#4D6265]">
                Supplier: <strong className="text-[#173B3F]">{reorderTarget.supplier_name}</strong> ·
                In stock: <strong>{reorderTarget.stock_qty} {reorderTarget.unit}</strong>
              </p>
              <div>
                <label className="font-semibold text-[#173B3F]">
                  Quantity to order ({reorderTarget.unit})
                </label>
                <input
                  type="number"
                  min={1}
                  value={reorderQty}
                  onChange={(e) => setReorderQty(Math.max(1, Number(e.target.value)))}
                  className="mt-1 h-8 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs tabular-nums"
                />
              </div>

              {reorderApproval ? (
                <div className="space-y-2 rounded-[6px] border border-[#D9911B]/45 bg-[#FDF9F1] p-3">
                  <p className="font-semibold text-[#173B3F]">WhatsApp message to supplier:</p>
                  <p className="font-kannada text-xs whitespace-pre-line text-[#4D6265]">
                    {String(reorderApproval.payload?.whatsapp_draft_kn || "")}
                  </p>
                  {reorderApproval.status === "pending" ? (
                    <div className="flex justify-end">
                      <Button
                        size="sm"
                        variant="success"
                        onClick={() => void handleApproveReorderNow()}
                        disabled={busy}
                      >
                        <Check className="h-3.5 w-3.5" />
                        Send WhatsApp Order
                      </Button>
                    </div>
                  ) : (
                    <Badge variant="green">Sent to Supplier</Badge>
                  )}
                </div>
              ) : null}

              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setReorderTarget(null)}>
                  Close
                </Button>
                {!reorderApproval ? (
                  <Button size="sm" onClick={() => void handleDraftReorder()} disabled={busy}>
                    Prepare Order
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Add Inventory Modal (Add Stock to Existing Item OR Create New Item) */}
      <Dialog open={addModalOpen} onOpenChange={setAddModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("Add Inventory", "ಹೊಸ ಸ್ಟಾಕ್ ಸೇರಿಸಿ")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 p-5 text-xs">
            <div className="flex gap-1.5 border-b border-[#EAE5DC] pb-2">
              <button
                type="button"
                onClick={() => setAddMode("existing")}
                className={`rounded-[6px] px-3 py-1.5 text-xs font-semibold cursor-pointer ${
                  addMode === "existing"
                    ? "bg-[#173B3F] text-white"
                    : "bg-[#FBF9F5] text-[#4D6265] border border-[#DDD7CA]"
                }`}
              >
                Add to Existing Item
              </button>
              <button
                type="button"
                onClick={() => setAddMode("new")}
                className={`rounded-[6px] px-3 py-1.5 text-xs font-semibold cursor-pointer ${
                  addMode === "new"
                    ? "bg-[#173B3F] text-white"
                    : "bg-[#FBF9F5] text-[#4D6265] border border-[#DDD7CA]"
                }`}
              >
                Add New Item
              </button>
            </div>

            {addMode === "existing" ? (
              <div className="space-y-3">
                <div>
                  <label className="font-semibold text-[#173B3F]">Select Item</label>
                  <select
                    value={addProductId}
                    onChange={(e) => setAddProductId(Number(e.target.value))}
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-2.5 text-xs text-[#173B3F]"
                  >
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} — Currently {p.stock_qty} {p.unit}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="font-semibold text-[#173B3F]">
                    New Stock Received (
                    {products.find((p) => p.id === addProductId)?.unit || "units"})
                  </label>
                  <div className="mt-1 flex gap-2">
                    <input
                      type="number"
                      min={1}
                      step="any"
                      value={addQty}
                      onChange={(e) => setAddQty(e.target.value)}
                      className="h-9 flex-1 rounded-[6px] border border-[#CFC8BA] bg-white px-3 text-xs tabular-nums text-[#173B3F]"
                    />
                    {[5, 10, 25].map((preset) => (
                      <Button
                        key={preset}
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setAddQty(String(preset))}
                      >
                        +{preset}
                      </Button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="font-semibold text-[#173B3F]">
                    Note (optional)
                  </label>
                  <input
                    value={addNote}
                    onChange={(e) => setAddNote(e.target.value)}
                    placeholder="e.g. Morning wholesale delivery"
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-3 text-xs text-[#173B3F]"
                  />
                </div>
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <label className="font-semibold text-[#173B3F]">Item Name *</label>
                  <input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g. Ragi Flour 1 kg"
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs text-[#173B3F]"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="font-semibold text-[#173B3F]">
                    Kannada Name (optional)
                  </label>
                  <input
                    value={newNameKn}
                    onChange={(e) => setNewNameKn(e.target.value)}
                    placeholder="e.g. ರಾಗಿ ಹಿಟ್ಟು 1 ಕೆಜಿ"
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 font-kannada text-xs text-[#173B3F]"
                  />
                </div>
                <div>
                  <label className="font-semibold text-[#173B3F]">Selling Price (₹) *</label>
                  <input
                    type="number"
                    min={1}
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs tabular-nums"
                  />
                </div>
                <div>
                  <label className="font-semibold text-[#173B3F]">Unit</label>
                  <select
                    value={newUnit}
                    onChange={(e) => setNewUnit(e.target.value)}
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-2 text-xs"
                  >
                    <option value="kg">kg</option>
                    <option value="litre">litre</option>
                    <option value="pack">pack</option>
                    <option value="bag">bag</option>
                    <option value="bar">bar</option>
                    <option value="jar">jar</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-[#173B3F]">Opening Stock</label>
                  <input
                    type="number"
                    min={0}
                    value={newStockQty}
                    onChange={(e) => setNewStockQty(e.target.value)}
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs tabular-nums"
                  />
                </div>
                <div>
                  <label className="font-semibold text-[#173B3F]">Low Stock Alert At</label>
                  <input
                    type="number"
                    min={0}
                    value={newReorderLevel}
                    onChange={(e) => setNewReorderLevel(e.target.value)}
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs tabular-nums"
                  />
                </div>
                <div>
                  <label className="font-semibold text-[#173B3F]">Category</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-2 text-xs"
                  >
                    <option value="Staples">Staples</option>
                    <option value="Grains & Rice">Grains &amp; Rice</option>
                    <option value="Atta & Flours">Atta &amp; Flours</option>
                    <option value="Pulses & Dals">Pulses &amp; Dals</option>
                    <option value="Oils & Ghee">Oils &amp; Ghee</option>
                    <option value="Spices">Spices</option>
                    <option value="Beverages">Beverages</option>
                    <option value="Personal Care">Personal Care</option>
                    <option value="Household">Household</option>
                    <option value="Snacks">Snacks</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-[#173B3F]">Supplier</label>
                  <select
                    value={newSupplierId}
                    onChange={(e) => setNewSupplierId(Number(e.target.value))}
                    className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-2 text-xs"
                  >
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setAddModalOpen(false)}>
                Cancel
              </Button>
              <Button
                size="sm"
                variant="success"
                onClick={() => void handleSaveAddInventory()}
                disabled={busy}
              >
                <Check className="h-3.5 w-3.5" />
                {busy
                  ? "Saving..."
                  : addMode === "existing"
                  ? "Save Stock"
                  : "Add New Item"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
