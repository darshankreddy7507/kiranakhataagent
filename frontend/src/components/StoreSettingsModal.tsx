"use client";

import { useState } from "react";
import { Check, Store } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type { ShopSettings } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { ErrorBanner, SuccessBanner } from "./ui/state-banners";

function StoreSettingsForm({
  shopSettings,
  onClose,
  onSaved,
}: {
  shopSettings: ShopSettings;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [shopName, setShopName] = useState(shopSettings.shop_name);
  const [shopNameKn, setShopNameKn] = useState(shopSettings.shop_name_kn);
  const [ownerName, setOwnerName] = useState(shopSettings.owner_name);
  const [ownerPhone, setOwnerPhone] = useState(shopSettings.owner_phone);
  const [upiId, setUpiId] = useState(shopSettings.upi_id);
  const [creditLimit, setCreditLimit] = useState(String(shopSettings.default_credit_limit));
  const [newPin, setNewPin] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const handleSave = async () => {
    if (!shopName.trim() || !ownerName.trim()) {
      setError("Store name and owner name are required.");
      return;
    }
    setSaving(true);
    setError(null);
    setSavedMsg(null);
    try {
      await api.updateSettings({
        shop_name: shopName.trim(),
        shop_name_kn: shopNameKn.trim() || shopName.trim(),
        owner_name: ownerName.trim(),
        owner_phone: ownerPhone.trim(),
        upi_id: upiId.trim(),
        default_credit_limit: Math.max(500, Number(creditLimit) || 3000),
        owner_pin: newPin.trim() ? newPin.trim() : undefined,
      });
      await onSaved();
      setSavedMsg("Store details updated!");
      setTimeout(onClose, 500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save store settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3.5 p-5 text-xs">
      <div className="flex items-center justify-between rounded-[6px] border border-[#E2DDD3] bg-[#FBF9F5] px-3 py-2">
        <span className="font-medium text-[#173B3F]">Messaging Channels</span>
        <div className="flex items-center gap-1.5">
          {shopSettings.telegram_connected ? (
            <Badge variant="green">Telegram Bot Live</Badge>
          ) : (
            <Badge variant="neutral">Telegram Not Configured</Badge>
          )}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="font-semibold text-[#173B3F]">Store Name (English)</label>
          <input
            value={shopName}
            onChange={(e) => setShopName(e.target.value)}
            className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs text-[#173B3F]"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="font-semibold text-[#173B3F]">Store Name (Kannada)</label>
          <input
            value={shopNameKn}
            onChange={(e) => setShopNameKn(e.target.value)}
            className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 font-kannada text-xs text-[#173B3F]"
          />
        </div>

        <div>
          <label className="font-semibold text-[#173B3F]">Owner Name</label>
          <input
            value={ownerName}
            onChange={(e) => setOwnerName(e.target.value)}
            className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs text-[#173B3F]"
          />
        </div>

        <div>
          <label className="font-semibold text-[#173B3F]">Shop Phone</label>
          <input
            value={ownerPhone}
            onChange={(e) => setOwnerPhone(e.target.value)}
            className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs text-[#173B3F]"
          />
        </div>

        <div>
          <label className="font-semibold text-[#173B3F]">Shop UPI ID</label>
          <input
            value={upiId}
            onChange={(e) => setUpiId(e.target.value)}
            className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs text-[#173B3F]"
          />
        </div>

        <div>
          <label className="font-semibold text-[#173B3F]">Default Credit Limit (₹)</label>
          <input
            type="number"
            min={500}
            value={creditLimit}
            onChange={(e) => setCreditLimit(e.target.value)}
            className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs tabular-nums text-[#173B3F]"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="font-semibold text-[#173B3F]">
            Change Login PIN (optional, default is 1234)
          </label>
          <input
            type="password"
            value={newPin}
            onChange={(e) => setNewPin(e.target.value)}
            placeholder="Leave blank to keep current PIN"
            className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] px-3 text-xs text-[#173B3F]"
          />
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      {savedMsg ? <SuccessBanner message={savedMsg} /> : null}

      <div className="flex justify-end gap-2 pt-2">
        <Button variant="outline" size="sm" onClick={onClose}>
          Cancel
        </Button>
        <Button size="sm" variant="success" onClick={() => void handleSave()} disabled={saving}>
          <Check className="h-3.5 w-3.5" />
          {saving ? "Saving..." : "Save Store Details"}
        </Button>
      </div>
    </div>
  );
}

export function StoreSettingsModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { t, shopSettings, refreshSettings } = useApp();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Store className="h-4 w-4 text-[#173B3F]" />
            {t("Store Settings", "ಅಂಗಡಿ ವಿವರಗಳು")}
          </DialogTitle>
        </DialogHeader>
        {open ? (
          <StoreSettingsForm
            key={`${shopSettings.shop_name}-${shopSettings.owner_name}`}
            shopSettings={shopSettings}
            onClose={() => onOpenChange(false)}
            onSaved={refreshSettings}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
