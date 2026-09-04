"use client";

import React from "react";

interface HeaderProps {
  triplesCount: number;
  onSyncAll: () => void;
  isSyncing: boolean;
}

export const Header: React.FC<HeaderProps> = ({ triplesCount, onSyncAll, isSyncing }) => {
  return (
    <header className="h-16 px-6 flex items-center justify-between border-b border-white/10 bg-slate-950/80 backdrop-blur-xl z-20">
      {/* Left: Brand */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500/20 to-purple-500/20 border border-cyan-500/40 flex items-center justify-center shadow-[0_0_20px_rgba(0,240,255,0.25)]">
          <span className="w-3.5 h-3.5 rounded-full bg-cyan-400 shadow-[0_0_10px_#00f0ff]" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-extrabold tracking-wider text-white">SMAR</h1>
            <span className="font-mono text-[10px] bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 px-1.5 py-0.5 rounded">
              v2.0
            </span>
          </div>
          <p className="text-[10px] tracking-widest text-slate-400 font-semibold uppercase">
            Autonomous Voice & Memory Intelligence
          </p>
        </div>
      </div>

      {/* Center: Telemetry Pills */}
      <div className="hidden md:flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-white/10 font-mono text-xs text-slate-300">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#10b981]" />
          <span>EPSILON 7B</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-white/10 font-mono text-xs text-slate-300">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#10b981]" />
          <span>NALINI (HI/EN)</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-white/10 font-mono text-xs text-slate-300">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#10b981]" />
          <span>KG: {triplesCount} FACTS</span>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={onSyncAll}
          disabled={isSyncing}
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-white/5 hover:bg-cyan-500/15 border border-white/10 hover:border-cyan-500/40 text-slate-200 hover:text-cyan-300 text-xs font-semibold transition-all disabled:opacity-50"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
          </svg>
          <span>{isSyncing ? "Syncing..." : "Sync Context"}</span>
        </button>

        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 font-mono text-xs font-bold text-emerald-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#10b981]" />
          <span>ONLINE</span>
        </div>
      </div>
    </header>
  );
};
