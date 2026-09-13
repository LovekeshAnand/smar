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

  useEffect(() => {
    if (isOpen) {
      fetchAlerts();
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4">
      <div className="w-full max-w-2xl bg-zinc-950 border border-white/[0.12] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] text-zinc-100 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-5 border-b border-white/[0.08] flex items-center justify-between bg-zinc-900/40">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-white">Admin Security Inbox</h3>
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

        {/* Filter Toolbar */}
        <div className="px-6 py-2.5 border-b border-white/[0.08] bg-zinc-900/20 flex items-center gap-2">
          {(["UNRESOLVED", "RESOLVED", "ALL"] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={`px-3 py-1 rounded-full text-[11px] font-mono tracking-wider transition-all cursor-pointer ${
                activeFilter === filter
                  ? "bg-white text-zinc-950 font-semibold shadow-sm"
                  : "bg-zinc-900 text-zinc-400 hover:text-zinc-200 border border-zinc-800"
              }`}
            >
              {filter}
            </button>
          ))}
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
                    ? "bg-rose-950/20 border-rose-500/30 hover:border-rose-500/50"
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
                      {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
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
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/10 text-zinc-300 uppercase">
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
