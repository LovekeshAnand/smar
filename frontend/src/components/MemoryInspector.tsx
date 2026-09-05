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

export interface InventoryStatus {
  status?: string;
  ready_to_answer?: boolean;
  message?: string;
  primary_source?: string;
  source_type?: string;
  total_records?: number;
  tables_count?: number;
  tables?: Array<{
    table_name: string;
    row_count: number;
    columns: Array<{ name: string; type: string }>;
  }>;
  schema_triples_in_kg?: number;
  cache_engine?: string;
  is_redis?: boolean;
  cache_hits?: number;
  cache_misses?: number;
}

interface MemoryInspectorProps {
  isOpen: boolean;
  onClose: () => void;
  triples: KGTriple[];
  vectors: VectorMemory[];
  inventoryStatus?: InventoryStatus | null;
  onRefreshGraph: () => void;
  onRefreshVectors: () => void;
  onRefreshInventory?: () => void;
  onUploadFile?: (file: File) => void;
}

export const MemoryInspector: React.FC<MemoryInspectorProps> = ({
  isOpen,
  onClose,
  triples,
  vectors,
  inventoryStatus,
  onRefreshGraph,
  onRefreshVectors,
  onRefreshInventory,
  onUploadFile,
}) => {
  const [activeTab, setActiveTab] = useState<"kg" | "vectors" | "data">("data");
  const [isUploading, setIsUploading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [testQuery, setTestQuery] = useState("");
  const [testResult, setTestResult] = useState<any>(null);
  const [isSearching, setIsSearching] = useState(false);

  if (!isOpen) return null;

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setIsUploading(true);
      try {
        const formData = new FormData();
        Array.from(e.target.files).forEach((file) => {
          formData.append("files", file);
        });

        const res = await fetch("/api/data/upload", {
          method: "POST",
          body: formData,
        });
        if (res.ok) {
          if (onRefreshInventory) onRefreshInventory();
          if (onRefreshGraph) onRefreshGraph();
        }
      } catch (err) {
        console.error("Upload error:", err);
      } finally {
        setIsUploading(false);
      }
    }
  };

  const handleTriggerSync = async () => {
    setIsSyncing(true);
    try {
      const res = await fetch("/api/data/sync", { method: "POST" });
      if (res.ok) {
        if (onRefreshInventory) onRefreshInventory();
        if (onRefreshGraph) onRefreshGraph();
      }
    } catch (err) {
      console.error("Sync error:", err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleRunTestQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await fetch(`/api/inventory/search?q=${encodeURIComponent(testQuery)}`);
      if (res.ok) {
        const data = await res.json();
        setTestResult(data);
      }
    } catch (err) {
      console.error("Query error:", err);
    } finally {
      setIsSearching(false);
    }
  };

  const isReady = inventoryStatus?.ready_to_answer ?? true;
  const totalRows = inventoryStatus?.total_records ?? 0;
  const tablesCount = inventoryStatus?.tables_count ?? inventoryStatus?.tables?.length ?? 0;

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[440px] bg-slate-950/95 backdrop-blur-2xl border-l border-white/10 z-40 flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
      {/* Drawer Top Header */}
      <div className="h-14 px-5 flex items-center justify-between border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-wider text-slate-200 font-bold">
            Cognitive & Data Inspector
          </span>
          <span className="text-[11px] font-mono text-slate-500">
            ({triples.length} KG Facts)
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-slate-400 hover:text-white transition-colors"
          aria-label="Close Drawer"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Tabs */}
      <div className="px-5 py-3 border-b border-white/5 flex gap-2">
        <button
          onClick={() => setActiveTab("data")}
          className={`px-3 py-1 rounded-md text-xs font-mono transition-all ${
            activeTab === "data" ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          Data Sync Engine
        </button>
        <button
          onClick={() => setActiveTab("kg")}
          className={`px-3 py-1 rounded-md text-xs font-mono transition-all ${
            activeTab === "kg" ? "bg-white/15 text-white" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          Knowledge Graph
        </button>
        <button
          onClick={() => setActiveTab("vectors")}
          className={`px-3 py-1 rounded-md text-xs font-mono transition-all ${
            activeTab === "vectors" ? "bg-white/15 text-white" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          Vectors ({vectors.length})
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 custom-scrollbar text-xs">
        {activeTab === "data" && (
          <div className="space-y-4">
            {/* Status Readiness Banner */}
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono text-slate-400">ENGINE STATUS</span>
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${isReady ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
                  <span className={`text-[11px] font-mono font-bold ${isReady ? "text-emerald-400" : "text-amber-400"}`}>
                    {isReady ? "READY TO ANSWER" : "SYNCING DATA..."}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                  <span className="text-slate-500 block text-[10px]">TOTAL RECORDS</span>
                  <span className="text-white font-bold text-sm">{totalRows.toLocaleString()}</span>
                </div>
                <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                  <span className="text-slate-500 block text-[10px]">TABLES DISCOVERED</span>
                  <span className="text-cyan-400 font-bold text-sm">{tablesCount} Tables</span>
                </div>
                <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                  <span className="text-slate-500 block text-[10px]">CACHE LAYER</span>
                  <span className="text-purple-300 font-bold text-[11px]">
                    {inventoryStatus?.is_redis ? "⚡ Redis Docker" : "In-Memory LRU"}
                  </span>
                </div>
                <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                  <span className="text-slate-500 block text-[10px]">KG SCHEMA TRIPLES</span>
                  <span className="text-emerald-300 font-bold text-sm">
                    {inventoryStatus?.schema_triples_in_kg ?? triples.length}
                  </span>
                </div>
              </div>

              <div className="flex gap-2 pt-1">
                <button
                  onClick={handleTriggerSync}
                  disabled={isSyncing}
                  className="flex-1 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 font-mono text-[11px] transition-colors border border-cyan-500/30 disabled:opacity-50"
                >
                  {isSyncing ? "Syncing to KG & DB..." : "↻ Run Sync Engine"}
                </button>
                {onRefreshInventory && (
                  <button
                    onClick={onRefreshInventory}
                    className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white font-mono text-[11px] transition-colors border border-white/5"
                  >
                    Refresh
                  </button>
                )}
              </div>
            </div>

            {/* Universal Multi-File Ingestion Dropzone */}
            <div className="p-3.5 rounded-xl border border-dashed border-cyan-500/30 bg-cyan-500/[0.02] hover:bg-cyan-500/[0.05] transition-colors text-center space-y-2">
              <span className="text-slate-200 font-medium block text-xs">
                Upload Any Unexpected File(s)
              </span>
              <p className="text-[10px] text-slate-400 leading-normal">
                Drop multiple CSV, Excel, or SQLite files. Zero hardcoding: the system will introspect headers, index all columns, and sync into the Knowledge Graph automatically.
              </p>
              <label className="inline-block mt-1 cursor-pointer">
                <input
                  type="file"
                  multiple
                  accept=".csv,.xlsx,.xls,.db,.sqlite"
                  onChange={handleFileInput}
                  disabled={isUploading}
                  className="hidden"
                />
                <span className="px-3.5 py-1.5 rounded-lg bg-cyan-500 text-slate-950 font-bold hover:bg-cyan-400 text-[11px] font-mono transition-colors inline-block shadow-lg shadow-cyan-500/20">
                  {isUploading ? "Ingesting & Syncing to KG..." : "+ Select Files to Ingest"}
                </span>
              </label>
            </div>

            {/* Interactive Data Query Test Box */}
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 space-y-2">
              <span className="text-slate-300 font-mono text-[11px] font-semibold block">
                Test Data Query (Non-Blocking)
              </span>
              <form onSubmit={handleRunTestQuery} className="flex gap-2">
                <input
                  type="text"
                  placeholder="Ask anything about synced data..."
                  value={testQuery}
                  onChange={(e) => setTestQuery(e.target.value)}
                  className="flex-1 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1 text-slate-200 text-xs font-mono focus:outline-none focus:border-cyan-500"
                />
                <button
                  type="submit"
                  disabled={isSearching}
                  className="px-3 py-1 bg-white/10 hover:bg-white/20 text-white rounded-lg text-xs font-mono disabled:opacity-50"
                >
                  {isSearching ? "..." : "Ask"}
                </button>
              </form>

              {testResult && (
                <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/10 font-mono text-[11px] space-y-1.5">
                  <div className="flex justify-between text-slate-400 text-[10px]">
                    <span>Latency: {testResult.elapsed_ms?.toFixed(2)}ms</span>
                    <span>Hits: {testResult.count}</span>
                  </div>
                  <p className="text-cyan-300 italic">
                    "{testResult.spoken_confirmation}"
                  </p>
                </div>
              )}
            </div>

            {/* Discovered Tables & Columns List */}
            {inventoryStatus?.tables && inventoryStatus.tables.length > 0 && (
              <div className="space-y-2">
                <span className="text-slate-400 font-mono text-[11px] block">
                  Discovered Tables ({inventoryStatus.tables.length})
                </span>
                <div className="space-y-1.5 max-h-60 overflow-y-auto custom-scrollbar">
                  {inventoryStatus.tables.map((tbl, i) => (
                    <div key={i} className="p-2 rounded-lg bg-white/[0.02] border border-white/5">
                      <div className="flex justify-between items-center font-mono">
                        <span className="text-purple-300 font-semibold">{tbl.table_name}</span>
                        <span className="text-slate-500 text-[10px]">{tbl.row_count.toLocaleString()} rows</span>
                      </div>
                      <p className="text-[10px] text-slate-500 font-mono truncate mt-0.5">
                        Cols: {tbl.columns.map((c) => c.name).slice(0, 5).join(", ")}
                        {tbl.columns.length > 5 && ` (+${tbl.columns.length - 5} more)`}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "kg" && (
          <div className="space-y-2">
            <div className="flex justify-between items-center text-[11px] text-slate-500 font-mono pb-1">
              <span>Relational Triples & Schema</span>
              <button onClick={onRefreshGraph} className="hover:text-slate-300">
                Refresh
              </button>
            </div>
            {triples.length === 0 ? (
              <p className="text-slate-600 text-center py-8">No facts extracted yet.</p>
            ) : (
              triples.map((t, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/5 space-y-1">
                  <div className="font-mono text-[11px] flex flex-wrap items-center gap-1.5">
                    <span className="text-cyan-400">{t.subject}</span>
                    <span className="text-slate-500">&rarr; {t.predicate} &rarr;</span>
                    <span className="text-purple-300">{t.object}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "vectors" && (
          <div className="space-y-2">
            <div className="flex justify-between items-center text-[11px] text-slate-500 font-mono pb-1">
              <span>Semantic Memory Chunks</span>
              <button onClick={onRefreshVectors} className="hover:text-slate-300">
                Refresh
              </button>
            </div>
            {vectors.length === 0 ? (
              <p className="text-slate-600 text-center py-8">No vectors recorded.</p>
            ) : (
              vectors.map((v) => (
                <div key={v.id} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/5 space-y-1">
                  <span className="text-[10px] font-mono text-emerald-400 uppercase">{v.category}</span>
                  <p className="text-slate-300 text-xs leading-relaxed">{v.content}</p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
};
