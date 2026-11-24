"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  BarChart3,
  ChevronDown,
  ChevronUp,
  Clock,
  Pause,
  Play,
  RefreshCw,
  Volume2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBanner, LoadingBlock, SuccessBanner } from "@/components/ui/state-banners";
import { api } from "@/lib/api";
import { useApp } from "@/lib/language";
import type { ReportsResponse } from "@/lib/types";
import { formatDateTime, formatINR } from "@/lib/utils";

export default function ReportsPage() {
  const { t } = useApp();
  const [data, setData] = useState<ReportsResponse | null>(null);
  const [mcpTools, setMcpTools] = useState<{ name: string; access: string; description: string }[]>([]);
  const [adapters, setAdapters] = useState<{ adapter: string; mode: string; configured: boolean; note: string }[]>([]);
  const [showTech, setShowTech] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);

  const loadData = useCallback(async () => {
    try {
      const [rep, toolsRes, healthRes] = await Promise.all([
        api.getReports(),
        api.getMcpTools(),
        api.getAdaptersHealth(),
      ]);
      setError(null);
      setData(rep);
      setMcpTools(toolsRes.tools);
      setAdapters(healthRes.adapters);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load daily report");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => loadData());
  }, [loadData]);

  useEffect(() => {
    if (!isPlaying) return;
    const timer = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          setIsPlaying(false);
          return 0;
        }
        return p + 5;
      });
    }, 400);
    return () => clearInterval(timer);
  }, [isPlaying]);

  const handleGenerateNow = async () => {
    setGenerating(true);
    setError(null);
    try {
      const updated = await api.generateDailySummary();
      setData((prev) => (prev ? { ...prev, daily_summary: updated } : prev));
      setBanner("Updated today's 9 PM report.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update report");
    } finally {
      setGenerating(false);
    }
  };

  const toggleVoicePlayback = () => {
    if (!data) return;
    if (isPlaying) {
      setIsPlaying(false);
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      return;
    }
    setProgress(5);
    setIsPlaying(true);
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(data.daily_summary.voice_script_kn);
      utter.lang = "kn-IN";
      utter.rate = 0.95;
      utter.onend = () => {
        setIsPlaying(false);
        setProgress(100);
      };
      window.speechSynthesis.speak(utter);
    }
  };

  if (loading) return <LoadingBlock label="Loading daily report..." />;
  if (error || !data) {
    return <ErrorBanner message={error || "Could not load report"} onRetry={() => void loadData()} />;
  }

  const s = data.daily_summary;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#173B3F] flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-[#173B3F]" />
            {t("9 PM Daily Report", "ರಾತ್ರಿ 9 ಗಂಟೆಯ ದಿನದ ವರದಿ")}
          </h2>
          <p className="text-xs text-[#4D6265]">
            {t(
              "Today's sales, money collected, top overdue customers, and Kannada audio summary.",
              "ಇಂದಿನ ಮಾರಾಟ, ಬಂದ ಹಣ, ಬಾಕಿ ಗ್ರಾಹಕರು ಮತ್ತು ಕನ್ನಡ ಧ್ವನಿ ವರದಿ."
            )}
          </p>
        </div>
        <Button size="sm" onClick={() => void handleGenerateNow()} disabled={generating}>
          <RefreshCw className={`h-3.5 w-3.5 ${generating ? "animate-spin" : ""}`} />
          {generating ? "Updating..." : "Generate Summary Now"}
        </Button>
      </div>

      {banner ? <SuccessBanner message={banner} onDismiss={() => setBanner(null)} /> : null}

      {/* 9 PM Summary Card */}
      <Card>
        <CardHeader className="bg-[#FBF9F5]">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-[#D9911B]" />
            <CardTitle>Summary for {s.summary_date}</CardTitle>
          </div>
          <span className="text-[11px] text-[#708284]">
            Updated {formatDateTime(s.created_at)}
          </span>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-[6px] border border-[#E2DDD3] bg-[#FCFBF8] p-3">
              <p className="text-[11px] text-[#708284]">Total Sales</p>
              <p className="mt-1 text-base font-bold tabular-nums text-[#173B3F]">
                {formatINR(s.total_sales)}
              </p>
            </div>
            <div className="rounded-[6px] border border-[#E2DDD3] bg-[#FCFBF8] p-3">
              <p className="text-[11px] text-[#708284]">Credit Sales</p>
              <p className="mt-1 text-base font-bold tabular-nums text-[#C95534]">
                {formatINR(s.credit_sales)}
              </p>
            </div>
            <div className="rounded-[6px] border border-[#E2DDD3] bg-[#FCFBF8] p-3">
              <p className="text-[11px] text-[#708284]">Collected</p>
              <p className="mt-1 text-base font-bold tabular-nums text-[#2F7D5B]">
                {formatINR(s.payments_collected)}
              </p>
            </div>
            <div className="rounded-[6px] border border-[#E2DDD3] bg-[#FCFBF8] p-3">
              <p className="text-[11px] text-[#708284]">Low Stock</p>
              <p className="mt-1 text-base font-bold tabular-nums text-[#D9911B]">
                {s.low_stock_count} items
              </p>
            </div>
            <div className="rounded-[6px] border border-[#E2DDD3] bg-[#FCFBF8] p-3">
              <p className="text-[11px] text-[#708284]">Top Overdue</p>
              <p className="mt-1 text-base font-bold tabular-nums text-[#B84646]">
                {s.top_overdue.length} people
              </p>
            </div>
            <div className="rounded-[6px] border border-[#E2DDD3] bg-[#FCFBF8] p-3">
              <p className="text-[11px] text-[#708284]">Pending</p>
              <p className="mt-1 text-base font-bold tabular-nums text-[#173B3F]">
                {s.pending_approvals_count} tasks
              </p>
            </div>
          </div>

          {/* Listen in Kannada */}
          <div className="rounded-[8px] border border-[#173B3F]/25 bg-[#F2EDE2] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={toggleVoicePlayback}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#173B3F] text-white hover:bg-[#102B2E] cursor-pointer"
                  aria-label={isPlaying ? "Pause Kannada summary" : "Play Kannada summary"}
                >
                  {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
                </button>
                <div>
                  <p className="text-xs font-bold text-[#173B3F] flex items-center gap-1.5">
                    <Volume2 className="h-3.5 w-3.5 text-[#C95534]" />
                    Listen to Summary in Kannada
                  </p>
                  <p className="font-kannada text-xs text-[#4D6265] mt-0.5">
                    {s.voice_script_kn}
                  </p>
                </div>
              </div>
              <Badge variant={isPlaying ? "marigold" : "teal"}>
                {isPlaying ? "Playing..." : "Tap Play"}
              </Badge>
            </div>
            <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-[#DFD7C6]">
              <div
                className="h-full bg-[#C95534] transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-[6px] border border-[#E2DDD3] bg-[#FBF9F5] p-3.5">
              <p className="text-[11px] font-bold text-[#708284]">ಕನ್ನಡ ಸಾರಾಂಶ</p>
              <p className="mt-1 font-kannada text-xs leading-relaxed text-[#173B3F]">
                {s.text_kn}
              </p>
            </div>
            <div className="rounded-[6px] border border-[#E2DDD3] bg-white p-3.5">
              <p className="text-[11px] font-bold text-[#708284]">English Summary</p>
              <p className="mt-1 text-xs leading-relaxed text-[#4D6265]">{s.text_en}</p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-[6px] border border-[#E2DDD3] p-3">
              <h4 className="text-xs font-semibold text-[#173B3F]">Top 3 Overdue Customers</h4>
              <div className="mt-2 divide-y divide-[#EFEAE0] text-xs">
                {s.top_overdue.map((c) => (
                  <div key={c.id} className="flex items-center justify-between py-1.5">
                    <span>
                      <strong>{c.name}</strong> ({c.days_overdue}d overdue)
                    </span>
                    <span className="font-bold tabular-nums text-[#B84646]">
                      {formatINR(c.balance)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-[6px] border border-[#E2DDD3] p-3">
              <h4 className="text-xs font-semibold text-[#173B3F]">Low-Stock Items</h4>
              <div className="mt-2 divide-y divide-[#EFEAE0] text-xs">
                {s.low_stock_items.map((p) => (
                  <div key={p.id} className="flex items-center justify-between py-1.5">
                    <span>{p.name}</span>
                    <span className="font-semibold tabular-nums text-[#D9911B]">
                      {p.stock_qty} / {p.reorder_level} {p.unit}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Clean Charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>This Week&apos;s Sales &amp; Collections (₹)</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.seven_day_series}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EAE5DC" />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#4D6265" }} />
                <YAxis tick={{ fontSize: 11, fill: "#4D6265" }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="total_sales" name="Sales" fill="#173B3F" radius={[3, 3, 0, 0]} />
                <Bar dataKey="credit_sales" name="Credit" fill="#C95534" radius={[3, 3, 0, 0]} />
                <Bar dataKey="payments_collected" name="Collected" fill="#2F7D5B" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Overdue Khata Breakdown (₹)</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.khata_aging}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EAE5DC" />
                <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: "#4D6265" }} />
                <YAxis tick={{ fontSize: 11, fill: "#4D6265" }} />
                <Tooltip />
                <Bar dataKey="amount" name="Pending ₹" fill="#D9911B" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Collapsible Technical / System Info (cleanly tucked away for normal users) */}
      <div className="rounded-[8px] border border-[#E2DDD3] bg-white">
        <button
          type="button"
          onClick={() => setShowTech((v) => !v)}
          className="flex w-full items-center justify-between px-4 py-3 text-xs font-semibold text-[#4D6265] hover:text-[#173B3F] cursor-pointer"
        >
          <span>System &amp; MCP Connections (Advanced)</span>
          {showTech ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        {showTech ? (
          <div className="grid gap-4 border-t border-[#EAE5DC] p-4 lg:grid-cols-2">
            <div className="space-y-2">
              <p className="text-xs font-bold text-[#173B3F]">
                MCP Tools ({mcpTools.length})
              </p>
              <div className="max-h-60 overflow-y-auto divide-y divide-[#EFEAE0] rounded-[6px] border border-[#E2DDD3]">
                {mcpTools.map((tool) => (
                  <div key={tool.name} className="flex items-start justify-between gap-2 px-3 py-2 text-xs">
                    <div>
                      <p className="font-mono font-semibold text-[#173B3F]">{tool.name}</p>
                      <p className="text-[11px] text-[#4D6265]">{tool.description}</p>
                    </div>
                    <Badge variant={tool.access === "approval_gated" ? "marigold" : "teal"}>
                      {tool.access}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-bold text-[#173B3F]">Connected Services</p>
              <div className="divide-y divide-[#EFEAE0] rounded-[6px] border border-[#E2DDD3]">
                {adapters.map((a) => (
                  <div key={a.adapter} className="flex items-start justify-between gap-2 px-3 py-2 text-xs">
                    <div>
                      <p className="font-semibold text-[#173B3F]">{a.adapter}</p>
                      <p className="text-[11px] text-[#4D6265]">{a.note}</p>
                    </div>
                    <Badge variant={a.mode === "mock" ? "neutral" : "green"}>{a.mode}</Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
