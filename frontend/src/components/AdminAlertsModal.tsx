"use client";

import React, { useState, useEffect } from "react";

export interface SecurityAlert {
  id: string;
  timestamp: string;
  user_id: string;
  user_name: string;
  role: string;
  query: string;
  resource_requested: string;
  clearance_required: string;
  severity: string;
  status: "UNRESOLVED" | "RESOLVED";
  resolution_note?: string | null;
  resolved_at?: string | null;
  resolved_by?: string | null;
}

interface TelegramStatus {
  enabled: boolean;
  bot_username: string;
  chat_id: string | null;
  is_paired: boolean;
  last_error: string | null;
  last_dispatched: string | null;
}

interface AdminAlertsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAlertResolved?: () => void;
}

export const AdminAlertsModal: React.FC<AdminAlertsModalProps> = ({
  isOpen,
  onClose,
  onAlertResolved,
}) => {
  const [alerts, setAlerts] = useState<SecurityAlert[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [activeFilter, setActiveFilter] = useState<"ALL" | "UNRESOLVED" | "RESOLVED">("UNRESOLVED");

  // Telegram Integration State
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null);
  const [isSyncingTelegram, setIsSyncingTelegram] = useState<boolean>(false);
  const [isTestingTelegram, setIsTestingTelegram] = useState<boolean>(false);
  const [telegramFeedback, setTelegramFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [customChatId, setCustomChatId] = useState<string>("");
  const [showManualInput, setShowManualInput] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      fetchAlerts();
      fetchTelegramStatus();
    }
  }, [isOpen]);

  const fetchAlerts = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/admin/alerts");
      if (res.ok) {
        const data = await res.json();
        setAlerts(data.alerts || []);
      }
    } catch (e) {
      console.error("Failed to fetch admin alerts:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTelegramStatus = async () => {
    try {
      const res = await fetch("/api/admin/telegram/status");
      if (res.ok) {
        const data = await res.json();
        setTelegramStatus(data);
        if (data.chat_id) {
          setCustomChatId(data.chat_id);
        }
      }
    } catch (e) {
      console.error("Failed to fetch telegram status:", e);
    }
  };

  const handleSyncTelegram = async () => {
    setIsSyncingTelegram(true);
    setTelegramFeedback(null);
    try {
      const res = await fetch("/api/admin/telegram/sync", { method: "POST" });
      const data = await res.json();
      if (data.status === "SUCCESS" && data.detected_chat_id) {
        setTelegramFeedback({
          type: "success",
          text: `Paired successfully! Chat ID: ${data.detected_chat_id}. Confirmation sent to Telegram.`,
        });
        await fetchTelegramStatus();
      } else {
        setTelegramFeedback({
          type: "error",
          text: "No new /start messages found. Open @smar_alert_system_bot in Telegram, press Start, then click Auto-Detect.",
        });
      }
    } catch (e) {
      setTelegramFeedback({
        type: "error",
        text: `Sync request failed: ${String(e)}`,
      });
    } finally {
      setIsSyncingTelegram(false);
    }
  };

  const handleSendTestAlert = async () => {
    setIsTestingTelegram(true);
    setTelegramFeedback(null);
    try {
      const res = await fetch("/api/admin/telegram/test", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setTelegramFeedback({
          type: "success",
          text: "Test notification dispatched to Telegram successfully! Check your bot.",
        });
      } else {
        setTelegramFeedback({
          type: "error",
          text: data.detail || "Failed to dispatch test notification to Telegram.",
        });
      }
    } catch (e) {
      setTelegramFeedback({
        type: "error",
        text: `Error sending test: ${String(e)}`,
      });
    } finally {
      setIsTestingTelegram(false);
    }
  };

  const handleSaveCustomChatId = async () => {
    if (!customChatId.trim()) return;
    try {
      const res = await fetch("/api/admin/telegram/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: customChatId.trim(), enabled: true }),
      });
      if (res.ok) {
        setTelegramFeedback({
          type: "success",
          text: `Chat ID updated to ${customChatId.trim()}. Ready to dispatch!`,
        });
        await fetchTelegramStatus();
        setShowManualInput(false);
      }
    } catch (e) {
      setTelegramFeedback({
        type: "error",
        text: `Failed to save Chat ID: ${String(e)}`,
      });
    }
  };

  const handleResolveAlert = async (alertId: string) => {
    try {
      const res = await fetch(`/api/admin/alerts/${alertId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resolved_by: "lovekesh",
          note: "Reviewed access violation and verified role clearance policy.",
        }),
      });
      if (res.ok) {
        await fetchAlerts();
        if (onAlertResolved) onAlertResolved();
      }
    } catch (e) {
      console.error("Failed to resolve alert:", e);
    }
  };

  if (!isOpen) return null;

  const filteredAlerts = alerts.filter((a) => {
    if (activeFilter === "ALL") return true;
    return a.status === activeFilter;
  });

  const unresolvedCount = alerts.filter((a) => a.status === "UNRESOLVED").length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-2xl bg-zinc-950 border border-purple-500/20 rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.8),0_0_40px_rgba(139,92,246,0.1)] overflow-hidden flex flex-col max-h-[88vh] text-zinc-100">
        
        {/* Modal Header */}
        <div className="px-6 py-5 border-b border-white/[0.08] flex items-center justify-between bg-zinc-900/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.2)]">
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-white tracking-wide">Admin Security & Telemetry Inbox</h3>
                {unresolvedCount > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-bold bg-rose-500 text-white animate-pulse">
                    {unresolvedCount} PENDING
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400">
                Unauthorized data requests & memory clearance breaches logged in real time
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Telegram Live Dispatcher Card */}
        <div className="px-6 py-3.5 border-b border-purple-500/20 bg-gradient-to-r from-purple-950/40 via-zinc-900/50 to-zinc-950">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-sky-500/15 border border-sky-400/30 flex items-center justify-center text-sky-400">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
                </svg>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-zinc-200">Telegram Bot:</span>
                  <a
                    href="https://t.me/smar_alert_system_bot"
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-mono text-purple-300 hover:text-purple-200 underline decoration-purple-500/40"
                  >
                    @{telegramStatus?.bot_username || "smar_alert_system_bot"}
                  </a>
                  {telegramStatus?.is_paired ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                      ACTIVE ({telegramStatus.chat_id})
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-amber-500/15 border border-amber-500/30 text-amber-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                      UNPAIRED
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-zinc-400 mt-0.5">
                  Stream security alerts to Telegram in real time
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={handleSyncTelegram}
                disabled={isSyncingTelegram}
                className="px-2.5 py-1 rounded-lg bg-purple-600/30 hover:bg-purple-600/50 border border-purple-500/40 text-purple-200 text-xs font-mono transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <svg className={`w-3.5 h-3.5 ${isSyncingTelegram ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                </svg>
                {isSyncingTelegram ? "Syncing..." : "Auto-Detect"}
              </button>

              <button
                onClick={handleSendTestAlert}
                disabled={isTestingTelegram || !telegramStatus?.is_paired}
                className="px-2.5 py-1 rounded-lg bg-sky-600/30 hover:bg-sky-600/50 border border-sky-500/40 text-sky-200 text-xs font-mono transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                title={telegramStatus?.is_paired ? "Dispatch test alert to your phone" : "Pair Telegram first"}
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
                {isTestingTelegram ? "Sending..." : "Test Alert"}
              </button>

              <button
                onClick={() => setShowManualInput(!showManualInput)}
                className="px-2 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-mono transition-colors"
                title="Manually enter Chat ID"
              >
                {showManualInput ? "Close" : "Chat ID"}
              </button>
            </div>
          </div>

          {/* Manual Chat ID Input Toggle */}
          {showManualInput && (
            <div className="mt-3 pt-3 border-t border-purple-500/20 flex items-center gap-2">
              <input
                type="text"
                value={customChatId}
                onChange={(e) => setCustomChatId(e.target.value)}
                placeholder="Enter Telegram Chat ID (e.g. 123456789 or -100...)"
                className="flex-1 bg-zinc-900/80 border border-zinc-700 rounded-lg px-3 py-1 text-xs font-mono text-zinc-100 focus:outline-none focus:border-purple-400"
              />
              <button
                onClick={handleSaveCustomChatId}
                className="px-3 py-1 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-mono font-medium transition-colors cursor-pointer"
              >
                Save
              </button>
            </div>
          )}

          {/* Feedback Banner */}
          {telegramFeedback && (
            <div
              className={`mt-2.5 p-2 rounded-lg text-xs font-mono flex items-start justify-between gap-2 ${
                telegramFeedback.type === "success"
                  ? "bg-emerald-950/40 border border-emerald-500/30 text-emerald-300"
                  : "bg-rose-950/40 border border-rose-500/30 text-rose-300"
              }`}
            >
              <span>{telegramFeedback.text}</span>
              <button
                onClick={() => setTelegramFeedback(null)}
                className="text-zinc-400 hover:text-zinc-200"
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {/* Filter Toolbar */}
        <div className="px-6 py-2.5 border-b border-white/[0.08] bg-zinc-900/20 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {(["UNRESOLVED", "RESOLVED", "ALL"] as const).map((filter) => (
              <button
                key={filter}
                onClick={() => setActiveFilter(filter)}
                className={`px-3 py-1 rounded-full text-[11px] font-mono tracking-wider transition-all cursor-pointer ${
                  activeFilter === filter
                    ? "bg-purple-600 text-white font-semibold shadow-sm"
                    : "bg-zinc-900 text-zinc-400 hover:text-zinc-200 border border-zinc-800"
                }`}
              >
                {filter}
              </button>
            ))}
          </div>
          <span className="text-[11px] font-mono text-zinc-500">
            {filteredAlerts.length} incidents logged
          </span>
        </div>

        {/* Alert List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3 custom-scrollbar">
          {isLoading ? (
            <div className="text-center py-12 text-xs font-mono text-zinc-500">Checking audit logs...</div>
          ) : filteredAlerts.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-xs font-mono space-y-1">
              <svg className="w-8 h-8 mx-auto text-zinc-600 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <p>No incidents found in this view.</p>
              <p className="text-[11px] text-zinc-600">All data clearance guardrails are secure.</p>
            </div>
          ) : (
            filteredAlerts.map((alert) => (
              <div
                key={alert.id}
                className={`p-4 rounded-xl border transition-all space-y-2.5 ${
                  alert.status === "UNRESOLVED"
                    ? "bg-rose-950/20 border-rose-500/30 hover:border-rose-500/50 shadow-[0_4px_20px_rgba(244,63,94,0.08)]"
                    : "bg-zinc-900/40 border-white/[0.06] opacity-75"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                        alert.status === "UNRESOLVED"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                          : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      }`}
                    >
                      {alert.status}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-400">
                      {new Date(alert.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                    </span>
                    <span className="text-[10px] font-mono text-purple-400/80">
                      ID: {alert.id}
                    </span>
                  </div>
                  {alert.status === "UNRESOLVED" && (
                    <button
                      onClick={() => handleResolveAlert(alert.id)}
                      className="px-3 py-1 rounded-lg bg-white/10 hover:bg-white text-white hover:text-zinc-950 text-xs font-mono font-medium transition-all cursor-pointer"
                    >
                      Resolve Incident
                    </button>
                  )}
                </div>

                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-zinc-400">User:</span>
                    <span className="font-semibold text-white">{alert.user_name}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-zinc-300 uppercase">
                      {alert.role}
                    </span>
                  </div>
                  <div className="text-xs">
                    <span className="text-zinc-400">Requested Data: </span>
                    <span className="text-rose-300 font-mono text-[11px]">{alert.resource_requested}</span>
                    <span className="text-[10px] font-mono text-zinc-500 ml-2">(Req: {alert.clearance_required})</span>
                  </div>
                </div>

                <div className="bg-black/40 rounded-lg p-2.5 border border-white/[0.05]">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block mb-0.5">Attempted Query</span>
                  <p className="text-xs font-mono text-zinc-200 break-words">&ldquo;{alert.query}&rdquo;</p>
                </div>

                {alert.status === "RESOLVED" && alert.resolved_by && (
                  <div className="text-[10px] font-mono text-zinc-400 flex items-center gap-1.5 pt-1 border-t border-white/[0.05]">
                    <span className="text-emerald-400">✓ Resolved by @{alert.resolved_by}:</span>
                    <span>{alert.resolution_note}</span>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
