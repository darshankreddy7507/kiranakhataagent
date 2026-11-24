"use client";

import { useState, useSyncExternalStore } from "react";
import { Check, Loader2, Mic, MicOff, Send } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type { VoiceCommandResult } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { ErrorBanner, SuccessBanner } from "./ui/state-banners";

const PRESET_COMMANDS = [
  {
    label: "Add ₹500 to Ramesh's khata",
    command: "Ramesh ge 500 khatege haki.",
  },
  {
    label: "Check Suresh's balance",
    command: "Suresh eshtu baki iddane?",
  },
  {
    label: "Check Sugar stock",
    command: "Sakkare stock eshtu ide?",
  },
  {
    label: "Send reminder to Ramesh",
    command: "Ramesh ge reminder kalisu.",
  },
];

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
}

export function VoiceCommandModal({
  open,
  onOpenChange,
  onExecuted,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onExecuted?: () => void;
}) {
  const { t, refreshNotifications } = useApp();
  const [commandText, setCommandText] = useState("Ramesh ge 500 khatege haki.");
  const [listening, setListening] = useState(false);
  const speechSupported = useSyncExternalStore(
    () => () => {},
    () => {
      const w = window as unknown as Record<string, unknown>;
      return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
    },
    () => false
  );
  const [loading, setLoading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [result, setResult] = useState<VoiceCommandResult | null>(null);

  const handleRunCommand = async (textOverride?: string) => {
    const query = (textOverride ?? commandText).trim();
    if (!query) return;
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await api.runVoiceCommand(query);
      setResult(res);
      await refreshNotifications();
      onExecuted?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not understand that command");
    } finally {
      setLoading(false);
    }
  };

  const handleMicCapture = () => {
    setError(null);
    const w = window as unknown as Record<string, new () => SpeechRecognitionLike>;
    const SpeechCtor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!SpeechCtor) {
      setListening(true);
      setTimeout(() => {
        const sim = "Ramesh ge 500 khatege haki.";
        setCommandText(sim);
        setListening(false);
        void handleRunCommand(sim);
      }, 900);
      return;
    }

    const recognition = new SpeechCtor();
    recognition.lang = "kn-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    setListening(true);

    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript || "";
      setCommandText(transcript);
      setListening(false);
      void handleRunCommand(transcript);
    };
    recognition.onerror = () => {
      setListening(false);
      setError("Microphone not available — tap one of the quick buttons below or type.");
    };
    recognition.onend = () => setListening(false);
    recognition.start();
  };

  const handleApproveCreated = async () => {
    if (!result?.created_approval) return;
    setApproving(true);
    setError(null);
    try {
      await api.decideApproval(result.created_approval.id, {
        decision: "approve",
        decision_note: "Approved from voice command",
      });
      setSuccessMsg("Done! Saved to shop khata.");
      setResult((prev) =>
        prev && prev.created_approval
          ? {
              ...prev,
              created_approval: { ...prev.created_approval, status: "approved" },
            }
          : prev
      );
      await refreshNotifications();
      onExecuted?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setApproving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mic className="h-4 w-4 text-[#C95534]" />
            {t("Speak or Type a Shop Command", "ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಿ ಅಥವಾ ಟೈಪ್ ಮಾಡಿ")}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 p-5">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant={listening ? "marigold" : "primary"}
              onClick={handleMicCapture}
              disabled={listening}
              className="shrink-0"
            >
              {listening ? (
                <>
                  <MicOff className="h-3.5 w-3.5 animate-pulse" />
                  Listening...
                </>
              ) : (
                <>
                  <Mic className="h-3.5 w-3.5" />
                  {speechSupported ? "Speak" : "Try Voice"}
                </>
              )}
            </Button>
            <input
              value={commandText}
              onChange={(e) => setCommandText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleRunCommand();
              }}
              placeholder="e.g. Ramesh ge 500 khatege haki."
              className="h-9 flex-1 rounded-[6px] border border-[#CFC8BA] bg-white px-3 text-xs text-[#173B3F] focus:border-[#173B3F] focus:outline-none"
            />
            <Button
              type="button"
              onClick={() => void handleRunCommand()}
              disabled={loading || !commandText.trim()}
            >
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              Go
            </Button>
          </div>

          <div>
            <p className="mb-1.5 text-[11px] font-medium text-[#708284]">
              Quick examples (tap to run):
            </p>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {PRESET_COMMANDS.map((p) => (
                <button
                  key={p.command}
                  type="button"
                  onClick={() => {
                    setCommandText(p.command);
                    void handleRunCommand(p.command);
                  }}
                  className="rounded-[6px] border border-[#DDD7CA] bg-[#FBF9F5] px-3 py-2 text-left text-xs hover:border-[#173B3F]/40 hover:bg-[#EFEAE0] cursor-pointer"
                >
                  <p className="font-semibold text-[#173B3F]">{p.label}</p>
                  <p className="mt-0.5 text-[11px] text-[#708284]">&ldquo;{p.command}&rdquo;</p>
                </button>
              ))}
            </div>
          </div>

          {error ? <ErrorBanner message={error} /> : null}
          {successMsg ? <SuccessBanner message={successMsg} /> : null}

          {result ? (
            <div className="space-y-2.5 rounded-[8px] border border-[#E2DDD3] bg-[#FBF9F5] p-3.5 text-xs">
              <p className="font-semibold text-[#173B3F]">{result.summary_en}</p>
              <p className="font-kannada text-[#4D6265]">{result.summary_kn}</p>

              {result.created_approval ? (
                <div className="flex items-center justify-between gap-3 rounded-[6px] border border-[#D9911B]/40 bg-[#FDF9F1] p-2.5">
                  <span className="text-xs font-medium text-[#7A4F04]">
                    Confirm before saving?
                  </span>
                  {result.created_approval.status === "pending" ? (
                    <Button
                      size="sm"
                      variant="success"
                      onClick={handleApproveCreated}
                      disabled={approving}
                    >
                      <Check className="h-3.5 w-3.5" />
                      {approving ? "Saving..." : "Yes, Save Now"}
                    </Button>
                  ) : (
                    <Badge variant="green">Saved</Badge>
                  )}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
