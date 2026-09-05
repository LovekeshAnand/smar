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
  primary_source: string;
  source_type: string;
  total_records: number;
  cache_hits: number;
  cache_misses: number;
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
  const [activeTab, setActiveTab] = useState<"kg" | "vectors" | "data">("kg");
  const [isUploading, setIsUploading] = useState(false);

  if (!isOpen) return null;

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0] && onUploadFile) {
      setIsUploading(true);
      try {
        await onUploadFile(e.target.files[0]);
      } finally {
        setIsUploading(false);
      }
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-96 bg-slate-950/95 backdrop-blur-2xl border-l border-white/10 z-40 flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
      {/* Drawer Top */}
      <div className="h-14 px-5 flex items-center justify-between border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-wider text-slate-300 font-semibold">
            Context Memory
          </span>
          <span className="text-[11px] font-mono text-slate-500">({triples.length} facts)</span>
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
        <button
          onClick={() => setActiveTab("data")}
          className={`px-3 py-1 rounded-md text-xs font-mono transition-all ${
            activeTab === "data" ? "bg-white/15 text-white" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          Data Layer
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-3 custom-scrollbar text-xs">
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

        {activeTab === "data" && (
          <div className="space-y-3">
            <div className="flex justify-between items-center text-[11px] text-slate-500 font-mono pb-1">
              <span>Connected Data Source</span>
              {onRefreshInventory && (
                <button onClick={onRefreshInventory} className="hover:text-slate-300">
                  Refresh
                </button>
              )}
            </div>

            {inventoryStatus && (
              <div className="p-3 rounded-lg bg-white/[0.03] border border-white/10 space-y-2 font-mono">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Active Source:</span>
                  <span className="text-cyan-400 font-semibold truncate max-w-[180px]">
                    {inventoryStatus.primary_source}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Total Records:</span>
                  <span className="text-emerald-400 font-bold">
                    {inventoryStatus.total_records.toLocaleString()} rows
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">KG Cache Hits / Misses:</span>
                  <span className="text-purple-300">
                    {inventoryStatus.cache_hits} / {inventoryStatus.cache_misses}
                  </span>
                </div>
              </div>
            )}

            {/* Universal File Ingestion Dropzone */}
            <div className="p-3.5 rounded-lg border border-dashed border-white/20 bg-white/[0.01] hover:border-cyan-500/50 transition-colors text-center space-y-2">
              <span className="text-slate-300 font-medium block">Adapt to Any CSV / Excel</span>
              <p className="text-[10px] text-slate-500 leading-normal">
                Upload any warehouse or inventory spreadsheet to auto-index and introspect schema on-the-fly.
              </p>
              <label className="inline-block mt-1 cursor-pointer">
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileInput}
                  disabled={isUploading}
                  className="hidden"
                />
                <span className="px-3 py-1.5 rounded-md bg-white/10 hover:bg-white/20 text-[11px] font-mono text-cyan-300 transition-colors inline-block">
                  {isUploading ? "Indexing..." : "Select CSV / Excel File"}
                </span>
              </label>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
