"use client";

import { AlertCircle, CheckCircle2, Inbox, Loader2, WifiOff } from "lucide-react";
import { Button } from "./button";

export function LoadingBlock({ label = "Loading ledger data..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[8px] border border-[#E2DDD3] bg-white px-6 py-12 text-center">
      <Loader2 className="h-5 w-5 animate-spin text-[#173B3F]" />
      <p className="mt-2.5 text-xs font-medium text-[#4D6265]">{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[8px] border border-dashed border-[#D6CFC2] bg-[#FCFBF8] px-6 py-10 text-center">
      <Inbox className="h-6 w-6 text-[#708284]" />
      <p className="mt-2 text-sm font-semibold text-[#173B3F]">{title}</p>
      <p className="mt-1 max-w-md text-xs text-[#4D6265]">{description}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export function SuccessBanner({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[6px] border border-[#2F7D5B]/35 bg-[#2F7D5B]/10 px-3.5 py-2.5 text-xs text-[#1E563D]">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 shrink-0 text-[#2F7D5B]" />
        <span className="font-medium">{message}</span>
      </div>
      {onDismiss ? (
        <button
          onClick={onDismiss}
          className="text-[11px] font-semibold underline hover:opacity-80 cursor-pointer"
        >
          Dismiss
        </button>
      ) : null}
    </div>
  );
}

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[6px] border border-[#B84646]/35 bg-[#B84646]/10 px-3.5 py-2.5 text-xs text-[#8D2D2D]">
      <div className="flex items-center gap-2">
        <AlertCircle className="h-4 w-4 shrink-0 text-[#B84646]" />
        <span>{message}</span>
      </div>
      {onRetry ? (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function OfflineBanner() {
  return (
    <div className="flex items-center gap-2 border-b border-[#D9911B]/40 bg-[#D9911B]/15 px-4 py-1.5 text-xs font-medium text-[#7D5106]">
      <WifiOff className="h-3.5 w-3.5 shrink-0" />
      <span>
        Offline / backend disconnected. Changes cannot be synced until FastAPI server is reachable.
      </span>
    </div>
  );
}
