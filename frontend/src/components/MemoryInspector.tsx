"use client";

import React, { useState, useRef } from "react";

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
  currentUsername?: string;
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
  currentUsername = "lovekesh",
}) => {
  const [activeTab, setActiveTab] = useState<"kg" | "vectors" | "data">("data");
  const [isUploading, setIsUploading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [testQuery, setTestQuery] = useState("");
  const [testResult, setTestResult] = useState<any>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadFeedback, setUploadFeedback] = useState<string | null>(null);
  const [kgFilter, setKgFilter] = useState<"all" | "personal" | "schema">("all");
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileSelect = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const newFiles = Array.from(files);
    setSelectedFiles((prev) => [...prev, ...newFiles]);
  };

  const removeFileFromQueue = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUploadSelectedFiles = async () => {
    if (selectedFiles.length === 0) return;
    setIsUploading(true);
    setUploadFeedback(`Uploading & syncing ${selectedFiles.length} surprise data file(s)...`);

    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => {
        formData.append("files", file);
      });

      const uploadUrl = typeof window !== "undefined" && window.location.port === "3000"
        ? `http://${window.location.hostname}:5000/api/data/upload`
        : "/api/data/upload";

      const res = await fetch(uploadUrl, {
        method: "POST",
        body: formData,
      });

      const rawText = await res.text();
      let data: any = {};
      try {
        data = JSON.parse(rawText);
      } catch {
        data = { detail: rawText.slice(0, 200) };
      }

      if (res.ok) {
        setUploadFeedback(`Success! Synced ${selectedFiles.length} file(s). System is ready to answer!`);
        setSelectedFiles([]);
        if (onRefreshInventory) onRefreshInventory();
        if (onRefreshGraph) onRefreshGraph();
        if (onRefreshVectors) onRefreshVectors();
        setTimeout(() => setUploadFeedback(null), 4000);
      } else {
        setUploadFeedback(`Upload issue: ${data.detail || data.message || "Error during sync"}`);
      }
    } catch (err: any) {
      console.error("Upload error:", err);
      setUploadFeedback(`Network error: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleTriggerSync = async () => {
    setIsSyncing(true);
    try {
      const syncUrl = typeof window !== "undefined" && window.location.port === "3000"
        ? `http://${window.location.hostname}:5000/api/data/sync`
        : "/api/data/sync";
      const res = await fetch(syncUrl, { method: "POST" });
      if (res.ok) {
        if (onRefreshInventory) onRefreshInventory();
        if (onRefreshGraph) onRefreshGraph();
        if (onRefreshVectors) onRefreshVectors();
      }
    } catch (err) {
      console.error("Sync error:", err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleResetData = async () => {
    if (!confirm("Wipe all data and reset to uninitialized?")) return;
    try {
      const resetUrl = typeof window !== "undefined" && window.location.port === "3000"
        ? `http://${window.location.hostname}:5000/api/data/reset`
        : "/api/data/reset";
      await fetch(resetUrl, { method: "POST" });
      if (onRefreshInventory) onRefreshInventory();
      if (onRefreshGraph) onRefreshGraph();
      if (onRefreshVectors) onRefreshVectors();
      setUploadFeedback("Data layer reset to uninitialized.");
      setTimeout(() => setUploadFeedback(null), 3000);
    } catch (err) {
      console.error("Reset error:", err);
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

  // Filter triples based on tab
  const filteredTriples = triples.filter((t) => {
    if (kgFilter === "all") return true;
    const isSchema = t.predicate.startsWith("HAS_COLUMN") || t.predicate === "IS_DATATYPE" || t.predicate === "PRIMARY_KEY";
    if (kgFilter === "schema") return isSchema;
    if (kgFilter === "personal") return !isSchema;
    return true;
  });

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[460px] bg-slate-950/95 backdrop-blur-2xl border-l border-white/10 z-40 flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
      {/* Drawer Top Header */}
      <div className="h-14 px-5 flex items-center justify-between border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-wider text-slate-200 font-bold">
            Cognitive & Data Inspector
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
            @{currentUsername}
          </span>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white flex items-center justify-center transition-colors text-xs font-mono"
        >
          ✕
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-white/5 bg-white/[0.02] p-1 gap-1">
        <button
          onClick={() => setActiveTab("data")}
          className={`flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-colors flex items-center justify-center gap-1.5 ${
            activeTab === "data" ? "bg-white/10 text-white font-bold" : "text-slate-400 hover:text-white"
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${isReady ? "bg-emerald-400" : "bg-amber-400"}`} />
          Surprise Data ({tablesCount})
        </button>
        <button
          onClick={() => setActiveTab("kg")}
          className={`flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-colors ${
            activeTab === "kg" ? "bg-white/10 text-white font-bold" : "text-slate-400 hover:text-white"
          }`}
        >
          Graph ({triples.length})
        </button>
        <button
          onClick={() => setActiveTab("vectors")}
          className={`flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-colors ${
            activeTab === "vectors" ? "bg-white/10 text-white font-bold" : "text-slate-400 hover:text-white"
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
                <span className="text-[11px] font-mono text-slate-400">SYNC ENGINE READINESS</span>
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
                <button
                  onClick={handleResetData}
                  className="px-2.5 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 font-mono text-[11px] transition-colors border border-red-500/20"
                  title="Wipe data and reset status"
                >
                  Reset
                </button>
              </div>
            </div>

            {/* Universal Multi-File Ingestion Dropzone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                handleFileSelect(e.dataTransfer.files);
              }}
              className={`p-4 rounded-xl border-2 border-dashed transition-all text-center space-y-2.5 ${
                isDragging
                  ? "border-cyan-400 bg-cyan-500/10 scale-[1.01]"
                  : "border-cyan-500/30 bg-cyan-500/[0.02] hover:bg-cyan-500/[0.05]"
              }`}
            >
              <div className="w-9 h-9 rounded-full bg-cyan-500/20 text-cyan-300 flex items-center justify-center mx-auto">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>

              <div>
                <span className="text-slate-100 font-bold block text-xs">
                  Upload Surprise Data (Multi-File Ingestion)
                </span>
                <p className="text-[10px] text-slate-400 leading-normal mt-0.5">
                  Select or drag & drop multiple files at once. Zero hardcoding: system automatically discovers schemas, indexes columns, writes to KG, and prepares answers.
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-1.5 py-1">
                <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-white/5 text-slate-300 border border-white/10">.CSV</span>
                <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-white/5 text-slate-300 border border-white/10">.TSV</span>
                <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-white/5 text-slate-300 border border-white/10">.XLSX</span>
                <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-white/5 text-slate-300 border border-white/10">.JSON</span>
                <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-white/5 text-slate-300 border border-white/10">.PARQUET</span>
                <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-white/5 text-slate-300 border border-white/10">.SQLITE</span>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".csv,.tsv,.txt,.xlsx,.xls,.json,.jsonl,.ndjson,.parquet,.db,.sqlite,.sqlite3"
                onChange={(e) => handleFileSelect(e.target.files)}
                className="hidden"
              />

              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="px-4 py-2 rounded-xl bg-cyan-500 text-slate-950 font-bold hover:bg-cyan-400 text-xs font-mono transition-colors shadow-lg shadow-cyan-500/20 disabled:opacity-50"
              >
                + Select Multiple Files
              </button>
            </div>

            {/* Selected Files Queue */}
            {selectedFiles.length > 0 && (
              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-cyan-500/30 space-y-2 animate-in fade-in duration-200">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono font-bold text-white">
                    Queue: {selectedFiles.length} file(s) ready
                  </span>
                  <button
                    onClick={() => setSelectedFiles([])}
                    className="text-[10px] font-mono text-slate-400 hover:text-red-400 transition-colors"
                  >
                    Clear All
                  </button>
                </div>

                <div className="space-y-1.5 max-h-36 overflow-y-auto custom-scrollbar">
                  {selectedFiles.map((file, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02] border border-white/5 text-[11px] font-mono"
                    >
                      <div className="truncate pr-2">
                        <span className="text-cyan-300">{file.name}</span>
                        <span className="text-slate-500 text-[10px] ml-2">
                          ({(file.size / 1024).toFixed(1)} KB)
                        </span>
                      </div>
                      <button
                        onClick={() => removeFileFromQueue(idx)}
                        className="text-slate-500 hover:text-red-400 px-1 text-xs"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>

                <button
                  onClick={handleUploadSelectedFiles}
                  disabled={isUploading}
                  className="w-full py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 text-slate-950 font-bold font-mono text-xs hover:opacity-90 transition-opacity shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                >
                  {isUploading ? "Uploading & Syncing to KG..." : `⚡ Ingest & Sync All (${selectedFiles.length} Files)`}
                </button>
              </div>
            )}

            {/* Feedback notification */}
            {uploadFeedback && (
              <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 font-mono text-[11px]">
                {uploadFeedback}
              </div>
            )}

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
                    <div key={i} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/5">
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
              <span>Relational Facts ({filteredTriples.length})</span>
              <button onClick={onRefreshGraph} className="hover:text-slate-300">
                Refresh
              </button>
            </div>

            {/* Filter pills */}
            <div className="flex gap-1.5 pb-2">
              <button
                onClick={() => setKgFilter("all")}
                className={`px-2 py-0.5 rounded-full text-[10px] font-mono ${
                  kgFilter === "all" ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30" : "bg-white/5 text-slate-400"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setKgFilter("personal")}
                className={`px-2 py-0.5 rounded-full text-[10px] font-mono ${
                  kgFilter === "personal" ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30" : "bg-white/5 text-slate-400"
                }`}
              >
                Personal (@{currentUsername})
              </button>
              <button
                onClick={() => setKgFilter("schema")}
                className={`px-2 py-0.5 rounded-full text-[10px] font-mono ${
                  kgFilter === "schema" ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30" : "bg-white/5 text-slate-400"
                }`}
              >
                Schema Triples
              </button>
            </div>

            {filteredTriples.length === 0 ? (
              <p className="text-slate-600 text-center py-8">No facts match filter.</p>
            ) : (
              filteredTriples.map((t, idx) => (
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
              <span>Semantic Memory Chunks ({vectors.length})</span>
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
