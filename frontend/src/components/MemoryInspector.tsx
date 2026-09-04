"use client";

import React, { useState } from "react";

export interface KGTriple {
  subject: string;
  predicate: string;
  object: string;
  confidence: number;
  updated_at: number;
}

export interface VectorMemory {
  id: number;
  content: string;
  category: string;
  updated_at: number;
}

export interface ConnectorInfo {
  name: string;
  connected: boolean;
  status: string;
}

interface MemoryInspectorProps {
  triples: KGTriple[];
  vectors: VectorMemory[];
  connectors: Record<string, ConnectorInfo>;
  onRefreshGraph: () => void;
  onRefreshVectors: () => void;
  onRefreshConnectors: () => void;
  onSyncAll: () => void;
  isSyncing: boolean;
}

export const MemoryInspector: React.FC<MemoryInspectorProps> = ({
  triples,
  vectors,
  connectors,
  onRefreshGraph,
  onRefreshVectors,
  onRefreshConnectors,
  onSyncAll,
  isSyncing,
}) => {
  const [activeTab, setActiveTab] = useState<"kg" | "vectors" | "connectors">("kg");

  return (
    <div className="flex flex-col h-full bg-slate-950/70 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
      {/* Tab Navigation */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-white/10 bg-slate-900/50">
        <div className="flex gap-1 p-1 bg-black/40 rounded-lg">
          <button
            onClick={() => setActiveTab("kg")}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
              activeTab === "kg" ? "bg-slate-800 text-white shadow" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Knowledge Graph
          </button>
          <button
            onClick={() => setActiveTab("vectors")}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
              activeTab === "vectors" ? "bg-slate-800 text-white shadow" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Vector Memory
          </button>
          <button
            onClick={() => setActiveTab("connectors")}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
              activeTab === "connectors" ? "bg-slate-800 text-white shadow" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Connectors
          </button>
        </div>
      </div>

      {/* Tab 1: Knowledge Graph */}
      {activeTab === "kg" && (
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-black/20 border-b border-white/5 font-mono text-xs text-slate-400">
            <span>Active Triples: {triples.length}</span>
            <button
              onClick={onRefreshGraph}
              className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-[11px] transition-colors"
            >
              Refresh
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2.5 custom-scrollbar">
            {triples.length === 0 ? (
              <div className="text-center py-12 text-xs text-slate-500">No relational facts extracted yet.</div>
            ) : (
              triples.map((t, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-lg bg-slate-900/60 border border-white/5 hover:border-cyan-500/30 transition-all text-xs"
                >
                  <div className="flex items-center flex-wrap gap-1.5 font-mono mb-1.5">
                    <span className="px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 font-semibold">{t.subject}</span>
                    <span className="text-amber-400 font-medium">&mdash;[{t.predicate}]&rarr;</span>
                    <span className="px-2 py-0.5 rounded bg-purple-500/15 text-purple-300 font-semibold">{t.object}</span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-slate-500">
                    <span>Confidence: {(t.confidence * 100).toFixed(0)}%</span>
                    <span>
                      {new Date(t.updated_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Vector Memory */}
      {activeTab === "vectors" && (
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-black/20 border-b border-white/5 font-mono text-xs text-slate-400">
            <span>Semantic Chunks: {vectors.length}</span>
            <button
              onClick={onRefreshVectors}
              className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-[11px] transition-colors"
            >
              Refresh
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2.5 custom-scrollbar">
            {vectors.length === 0 ? (
              <div className="text-center py-12 text-xs text-slate-500">No semantic vector chunks recorded yet.</div>
            ) : (
              vectors.map((v) => (
                <div key={v.id} className="p-2.5 rounded-lg bg-slate-900/60 border border-white/5 text-xs space-y-1">
                  <div className="font-mono text-[10px] text-emerald-400 uppercase tracking-wider">{v.category}</div>
                  <div className="text-slate-200 leading-relaxed text-xs">{v.content}</div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Connectors Hub */}
      {activeTab === "connectors" && (
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-black/20 border-b border-white/5 font-mono text-xs text-slate-400">
            <span>External Feeds & Intent Bus</span>
            <div className="flex gap-2">
              <button
                onClick={onSyncAll}
                disabled={isSyncing}
                className="px-2 py-0.5 rounded bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-300 text-[11px] font-semibold transition-colors disabled:opacity-50"
              >
                {isSyncing ? "Syncing..." : "Sync Feeds"}
              </button>
              <button
                onClick={onRefreshConnectors}
                className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-[11px] transition-colors"
              >
                Health
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2.5 custom-scrollbar">
            {Object.entries(connectors).map(([key, c]) => (
              <div
                key={key}
                className="p-3 rounded-xl bg-slate-900/60 border border-white/5 flex items-center justify-between hover:border-white/15 transition-colors"
              >
                <div>
                  <h4 className="text-xs font-semibold text-slate-100">{c.name}</h4>
                  <div className="flex items-center gap-1.5 mt-1 font-mono text-[11px]">
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        c.connected ? "bg-emerald-400 shadow-[0_0_6px_#10b981]" : "bg-slate-500"
                      }`}
                    />
                    <span className={c.connected ? "text-emerald-400" : "text-slate-500"}>
                      {c.connected ? "Connected & Active" : "Configured / Standby"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
