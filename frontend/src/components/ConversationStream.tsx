"use client";

import React, { useEffect, useRef, useState } from "react";
import { OperationCard, OperationDetails } from "./OperationCard";
import { DataTableCard, TableData } from "./DataTableCard";
import { VisualChartCard, VisualChartData } from "./VisualChartCard";

export interface DbContext {
  database: string;
  table: string;
  row_id?: string;
  row_identifier?: string;
  operation?: string;
  primary_key?: string;
  affected_rows?: number;
  sql?: string;
  elapsed_ms?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: string;
  audioBase64?: string | null;
  contextUsed?: string | null;
  operationDetails?: OperationDetails | null;
  tableData?: TableData | null;
  visualChart?: VisualChartData | null;
  dbContext?: DbContext | null;
}

interface ConversationStreamProps {
  messages: ChatMessage[];
  onPlayAudio: (audioBase64: string) => void;
  className?: string;
}

export const ConversationStream: React.FC<ConversationStreamProps> = ({
  messages,
  onPlayAudio,
  className,
}) => {
  const feedRef = useRef<HTMLDivElement | null>(null);
  const [selectedProvenance, setSelectedProvenance] = useState<DbContext | null>(null);
  const [copiedSql, setCopiedSql] = useState(false);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  const handleCopySql = (sqlText: string) => {
    navigator.clipboard.writeText(sqlText);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  return (
    <div
      ref={feedRef}
      className={
        className ||
        "w-full max-w-3xl max-h-[58vh] sm:max-h-[64vh] overflow-y-auto px-2 sm:px-4 py-3 space-y-5 custom-scrollbar transition-all relative"
      }
    >
      {messages.map((m) => (
        <div key={m.id} className="transition-all duration-300 animate-in fade-in slide-in-from-bottom-2">
          {m.role === "user" ? (
            /* User Message Bubble - Right Aligned */
            <div className="flex justify-end w-full">
              <div className="max-w-xl bg-gradient-to-r from-cyan-950/50 via-slate-900/80 to-blue-950/50 border border-cyan-500/30 rounded-2xl rounded-tr-sm px-4 py-3 shadow-lg text-left">
                <div className="flex items-center justify-between gap-3 mb-1.5">
                  <span className="text-[10px] font-mono text-cyan-400 font-semibold uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                    You
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">{m.timestamp}</span>
                </div>
                <p className="text-sm sm:text-base font-sans text-cyan-50 font-normal leading-relaxed">
                  {m.text}
                </p>
              </div>
            </div>
          ) : (
            /* Assistant Message Container - Left Aligned with Full Breadth */
            <div className="flex justify-start w-full">
              <div className="w-full bg-gradient-to-b from-slate-900/85 via-slate-900/90 to-slate-950/90 backdrop-blur-xl border border-slate-800/90 hover:border-slate-700/80 rounded-2xl rounded-tl-sm p-4 sm:p-5 shadow-2xl text-left transition-all">
                {/* Assistant Header */}
                <div className="flex items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-slate-800/60 flex-wrap">
                  {/* Left: Assistant Identity */}
                  <div className="flex items-center gap-2">
                    <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-sm shadow-cyan-500/30">
                      <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                    </div>
                    <span className="text-xs font-mono font-semibold text-slate-200 tracking-wide">
                      SMAR AI
                    </span>
                    <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/30 px-1.5 py-0.5 rounded">
                      online
                    </span>
                  </div>

                  {/* Right Actions & Live Database Provenance Badge */}
                  <div className="flex items-center gap-2.5 flex-wrap">
                    {/* TOP RIGHT: Target Database & Row Operation Badge */}
                    {m.dbContext && (
                      <button
                        type="button"
                        onClick={() => setSelectedProvenance(m.dbContext!)}
                        className="group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-mono 
                                   bg-slate-950/80 hover:bg-slate-900 border border-cyan-500/40 hover:border-cyan-400 
                                   text-slate-200 hover:text-cyan-200 shadow-md shadow-cyan-950/30 transition-all cursor-pointer"
                        title="Click to view full database query provenance, table, row, and executed SQL"
                      >
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
                        </span>
                        <svg className="w-3 h-3 text-cyan-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <ellipse cx="12" cy="5" rx="9" ry="3" />
                          <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                        </svg>
                        <span className="text-cyan-300 font-semibold">{m.dbContext.database}</span>
                        <span className="text-slate-600">/</span>
                        <span className="text-slate-200 font-medium">{m.dbContext.table}</span>
                        {m.dbContext.row_id && (
                          <>
                            <span className="text-slate-600">•</span>
                            <span className="text-amber-300 font-semibold bg-amber-950/50 border border-amber-700/50 px-1.5 py-0.2 rounded text-[10px]">
                              {m.dbContext.row_id}
                            </span>
                          </>
                        )}
                        {m.dbContext.elapsed_ms !== undefined && (
                          <>
                            <span className="text-slate-600">•</span>
                            <span className="text-emerald-400 font-medium">{m.dbContext.elapsed_ms}ms</span>
                          </>
                        )}
                        <svg className="w-3 h-3 text-slate-400 group-hover:text-cyan-300 transition-transform group-hover:translate-x-0.5 ml-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="9 18 15 12 9 6" />
                        </svg>
                      </button>
                    )}

                    <span className="text-[10px] font-mono text-slate-500">{m.timestamp}</span>

                    {m.audioBase64 && (
                      <button
                        onClick={() => onPlayAudio(m.audioBase64!)}
                        className="inline-flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300 bg-cyan-950/30 hover:bg-cyan-950/60 border border-cyan-800/40 px-2 py-0.5 rounded-md font-mono transition-all"
                        title="Replay spoken voice"
                      >
                        <svg className="w-2.5 h-2.5 fill-current" viewBox="0 0 24 24">
                          <polygon points="5 3 19 12 5 21 5 3" />
                        </svg>
                        <span>listen</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Assistant Spoken Response Text */}
                <p className="text-sm sm:text-base font-sans text-slate-100 font-light leading-relaxed">
                  {m.text}
                </p>

                {/* Dynamic Operations Card */}
                {m.operationDetails && (
                  <div className="mt-3">
                    <OperationCard details={m.operationDetails} />
                  </div>
                )}

                {/* Dynamic Visual Chart Card */}
                {m.visualChart && (
                  <div className="mt-3">
                    <VisualChartCard chart={m.visualChart} />
                  </div>
                )}

                {/* Dynamic Table Card (if separate from operation card) */}
                {m.tableData && !m.operationDetails?.sample_records && (
                  <div className="mt-3">
                    <DataTableCard data={m.tableData} />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ))}

      {/* Enterprise Operation & Data Provenance Inspector Modal */}
      {selectedProvenance && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in">
          <div className="w-full max-w-xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl p-5 text-left space-y-4 animate-in zoom-in-95">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shadow-sm">
                  <svg className="w-4 h-4 text-cyan-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <ellipse cx="12" cy="5" rx="9" ry="3" />
                    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white tracking-wide">
                    Operation & Row Provenance Trace
                  </h3>
                  <p className="text-[11px] font-mono text-cyan-400">
                    Adaptive Smart Data Layer • Zero Hardcoding
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedProvenance(null)}
                className="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Grid Attributes */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                <span className="text-[10px] font-mono uppercase text-slate-500">Connected Database</span>
                <div className="font-mono text-cyan-300 font-semibold flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  {selectedProvenance.database}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                <span className="text-[10px] font-mono uppercase text-slate-500">Target Table</span>
                <div className="font-mono text-white font-semibold flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-cyan-400" />
                  {selectedProvenance.table}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                <span className="text-[10px] font-mono uppercase text-slate-500">Target Record / Row</span>
                <div className="font-mono text-amber-300 font-semibold truncate">
                  {selectedProvenance.row_identifier || selectedProvenance.row_id || "Direct Record"}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                <span className="text-[10px] font-mono uppercase text-slate-500">Operation & Latency</span>
                <div className="font-mono text-emerald-300 font-semibold flex items-center gap-2">
                  <span>{selectedProvenance.operation || "RECORD_LOOKUP"}</span>
                  {selectedProvenance.elapsed_ms !== undefined && (
                    <span className="text-[10px] text-slate-400 bg-slate-800 px-1.5 py-0.2 rounded">
                      {selectedProvenance.elapsed_ms}ms
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Exact Executed SQL */}
            {selectedProvenance.sql && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase text-slate-400 tracking-wider">
                    Executed SQL Statement
                  </span>
                  <button
                    onClick={() => handleCopySql(selectedProvenance.sql!)}
                    className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 bg-cyan-950/40 hover:bg-cyan-950/70 border border-cyan-800/50 px-2.5 py-0.5 rounded transition-all flex items-center gap-1"
                  >
                    {copiedSql ? (
                      <>
                        <span className="text-emerald-400">✓</span> Copied!
                      </>
                    ) : (
                      <>
                        <span>📋</span> Copy SQL
                      </>
                    )}
                  </button>
                </div>
                <pre className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-cyan-200 overflow-x-auto custom-scrollbar leading-relaxed">
                  {selectedProvenance.sql}
                </pre>
              </div>
            )}

            {/* Footer Notice */}
            <div className="pt-2 flex items-center justify-between text-[11px] font-mono text-slate-400 border-t border-slate-800/80">
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                100% Deterministic Ground Truth
              </span>
              <button
                onClick={() => setSelectedProvenance(null)}
                className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition-colors"
              >
                Close Trace
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
