"use client";

import { useState } from "react";
import { Lock, Store } from "lucide-react";
import { useApp } from "@/lib/language";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { ErrorBanner } from "./ui/state-banners";

export function LoginScreen() {
  const { shopSettings, signIn, t } = useApp();
  const [pin, setPin] = useState("1234");
  const [ownerName, setOwnerName] = useState(shopSettings.owner_name);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await signIn(pin, ownerName.trim() || undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F4EE] p-4">
      <Card className="w-full max-w-sm">
        <CardContent className="p-6 space-y-5">
          <div className="flex flex-col items-center text-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-[8px] bg-[#173B3F] text-[#D9911B]">
              <Store className="h-6 w-6" />
            </div>
            <h1 className="mt-3 text-base font-bold text-[#173B3F]">
              {shopSettings.shop_name}
            </h1>
            <p className="font-kannada text-xs text-[#4D6265]">
              {shopSettings.shop_name_kn}
            </p>
            <p className="mt-2 text-xs text-[#708284]">
              {t("Sign in to open your shop ledger", "ಅಂಗಡಿ ಖಾತೆ ತೆರೆಯಲು ಸೈನ್ ಇನ್ ಮಾಡಿ")}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3 text-xs">
            <div>
              <label className="font-semibold text-[#173B3F]">Owner Name</label>
              <input
                value={ownerName}
                onChange={(e) => setOwnerName(e.target.value)}
                className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-3 text-xs text-[#173B3F]"
              />
            </div>

            <div>
              <label className="font-semibold text-[#173B3F]">Shop PIN</label>
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                placeholder="Enter PIN (default: 1234)"
                className="mt-1 h-9 w-full rounded-[6px] border border-[#CFC8BA] bg-white px-3 text-xs tracking-widest text-[#173B3F]"
              />
              <p className="mt-1 text-[11px] text-[#708284]">Demo PIN: 1234</p>
            </div>

            {error ? <ErrorBanner message={error} /> : null}

            <Button type="submit" variant="primary" className="w-full h-9" disabled={loading}>
              <Lock className="h-3.5 w-3.5" />
              {loading ? "Opening Shop..." : "Sign In"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
