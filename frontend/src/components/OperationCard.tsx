"use client";

import React, { useState } from "react";

export interface OperationDetails {
  operation: "AGGREGATION" | "INSERT" | "UPDATE" | "DELETE" | "TABULAR";
  table: string;
  function?: string;
  column?: string;
  group_by?: string | null;
  value?: any;
  formatted_value?: string;
  total_rows_evaluated?: number;
  filter_condition?: string | null;
  breakdown?: Record<string, any>;
  sample_records?: Record<string, any>[];
  status?: string;
  inserted_id?: any;
  affected_rows?: number;
  diff?: Record<string, { before: any; after: any }>;
  before?: Record<string, any>;
  after?: Record<string, any>;
  deleted_record?: Record<string, any>;
  sql?: string;
  elapsed_ms?: number;
}

interface OperationCardProps {
  details: OperationDetails;
}

export const OperationCard: React.FC<OperationCardProps> = ({ details }) => {
  const [activeTab, setActiveTab] = useState<"kpi" | "records" | "sql">("kpi");
  const [copied, setCopied] = useState(false);

  const getBadgeStyle = () => {
    switch (details.operation) {
      case "AGGREGATION":
        return "bg-cyan-500/15 text-cyan-300 border-cyan-500/40 shadow-cyan-500/10";
      case "INSERT":
        return "bg-emerald-500/15 text-emerald-300 border-emerald-500/40 shadow-emerald-500/10";
      case "UPDATE":
        return "bg-amber-500/15 text-amber-300 border-amber-500/40 shadow-amber-500/10";
      case "DELETE":
        return "bg-rose-500/15 text-rose-300 border-rose-500/40 shadow-rose-500/10";
      case "TABULAR":
        return "bg-purple-500/15 text-purple-300 border-purple-500/40 shadow-purple-500/10";
      default:
        return "bg-slate-500/15 text-slate-300 border-slate-500/40";
    }
  };

  const copySql = () => {
    if (details.sql) {
      navigator.clipboard.writeText(details.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const hasRecords = Boolean(details.sample_records && details.sample_records.length > 0);

  return (
    <div className="w-full mt-3 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-950/90 backdrop-blur-xl border border-slate-700/70 shadow-2xl overflow-hidden transition-all text-left">
      {/* Top Banner Header */}
      <div className="px-4 py-3 bg-slate-800/40 border-b border-slate-800/80 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-[11px] font-mono font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md border shadow-sm ${getBadgeStyle()}`}>
            {details.function ? `${details.function} ${details.operation}` : details.operation}
          </span>
          <span className="text-xs font-mono text-slate-300 flex items-center gap-1.5">
            <span className="text-slate-500 font-sans">table:</span>
            <span className="text-cyan-300 font-semibold bg-cyan-950/40 border border-cyan-800/40 px-2 py-0.5 rounded">
              {details.table}
            </span>
          </span>
          {details.filter_condition && (
            <span className="text-[10px] font-mono text-amber-300 bg-amber-950/40 border border-amber-800/40 px-2 py-0.5 rounded">
              WHERE {details.filter_condition}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {details.elapsed_ms !== undefined && (
            <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/30 px-2.5 py-0.5 rounded-full flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {details.elapsed_ms}ms
            </span>
          )}
        </div>
      </div>

      {/* Segmented View Switcher Tabs */}
      <div className="px-4 pt-2.5 flex items-center gap-2 border-b border-slate-800/60 bg-slate-900/40">
        <button
          onClick={() => setActiveTab("kpi")}
          className={`text-xs font-medium px-3 py-1.5 rounded-t-lg border-b-2 transition-all flex items-center gap-1.5 ${
            activeTab === "kpi"
              ? "border-cyan-400 text-cyan-300 bg-slate-800/60 font-semibold"
              : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
          }`}
        >
          <span>⚡ Result & Overview</span>
        </button>

        {hasRecords && (
          <button
            onClick={() => setActiveTab("records")}
            className={`text-xs font-medium px-3 py-1.5 rounded-t-lg border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === "records"
                ? "border-cyan-400 text-cyan-300 bg-slate-800/60 font-semibold"
                : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
            }`}
          >
            <span>📋 Source Records ({details.sample_records?.length})</span>
          </button>
        )}

        <button
          onClick={() => setActiveTab("sql")}
          className={`text-xs font-medium px-3 py-1.5 rounded-t-lg border-b-2 transition-all flex items-center gap-1.5 ${
            activeTab === "sql"
              ? "border-cyan-400 text-cyan-300 bg-slate-800/60 font-semibold"
              : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
          }`}
        >
          <span>🔍 SQL Query</span>
        </button>
      </div>

      {/* Tab 1: KPI & Summary View */}
      {activeTab === "kpi" && (
        <div className="p-4 space-y-3">
          {/* Main Aggregation Display */}
          {details.operation === "AGGREGATION" && details.formatted_value && (
            <div className="p-4 rounded-xl bg-gradient-to-br from-slate-800/70 to-slate-900/80 border border-slate-700/60 shadow-inner">
              <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                <span className="uppercase tracking-wide font-medium text-cyan-400/90">
                  {details.function === "COUNT" && (!details.column || details.column === "*" || details.column.toLowerCase().endsWith("id") || details.column.toLowerCase() === details.table.toLowerCase())
                    ? `COUNT OF ${details.table}`
                    : `${details.function} OF ${details.column}`} {details.group_by ? `(BY ${details.group_by.toUpperCase()})` : ""}
                </span>
                {details.total_rows_evaluated !== undefined && (
                  <span className="text-[11px] text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700/60">
                    {details.total_rows_evaluated} record{details.total_rows_evaluated === 1 ? "" : "s"} evaluated
                  </span>
                )}
              </div>

              <div className="flex items-baseline gap-3 mt-2">
                <div className="text-3xl sm:text-4xl font-extrabold font-mono text-transparent bg-clip-text bg-gradient-to-r from-emerald-300 via-teal-200 to-cyan-300 tracking-tight">
                  {details.formatted_value}
                </div>
                {details.group_by && details.breakdown && (
                  <span className="text-xs font-mono text-slate-400">
                    (Top {Object.keys(details.breakdown).length} stores total)
                  </span>
                )}
              </div>

              {details.group_by && details.breakdown && (
                <div className="mt-3 pt-3 border-t border-slate-700/50">
                  <div className="text-[11px] font-mono text-slate-400 mb-2 uppercase tracking-wider">
                    Breakdown by {details.group_by}:
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-40 overflow-y-auto custom-scrollbar pr-1">
                    {Object.entries(details.breakdown).map(([k, v]) => (
                      <div key={k} className="p-2 rounded bg-slate-900/60 border border-slate-800 flex justify-between items-center text-xs font-mono">
                        <span className="text-slate-400 truncate mr-1">{k}</span>
                        <span className="text-emerald-400 font-semibold">
                          {typeof v === "number" ? v.toLocaleString() : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* UPDATE Diff Display */}
          {details.operation === "UPDATE" && details.diff && (
            <div className="p-3.5 rounded-xl bg-slate-800/60 border border-amber-500/30 space-y-2">
              <div className="text-xs font-mono text-amber-400 font-semibold flex items-center gap-1.5">
                <span>🔄 Field Modifications Applied:</span>
              </div>
              <div className="space-y-1.5">
                {Object.entries(details.diff).map(([col, d]) => (
                  <div key={col} className="text-xs font-mono flex items-center gap-2 p-1.5 rounded bg-slate-900/60 border border-slate-800/80">
                    <span className="text-slate-300 font-medium min-w-24">{col}:</span>
                    <span className="line-through text-rose-400/90 bg-rose-950/50 px-2 py-0.5 rounded border border-rose-800/40">
                      {String(d.before)}
                    </span>
                    <span className="text-slate-500">→</span>
                    <span className="font-bold text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-800/40">
                      {String(d.after)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* INSERT Details */}
          {details.operation === "INSERT" && details.inserted_id && (
            <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/40 flex items-center justify-between">
              <span className="text-sm text-emerald-300 font-mono">
                ✓ Successfully inserted record with ID: <strong>#{String(details.inserted_id)}</strong>
              </span>
              <span className="text-xs font-mono text-emerald-400 bg-emerald-900/40 px-2 py-1 rounded">
                +1 Row
              </span>
            </div>
          )}

          {/* DELETE Details */}
          {details.operation === "DELETE" && (
            <div className="p-3.5 rounded-xl bg-rose-950/30 border border-rose-500/40 flex items-center justify-between">
              <span className="text-sm text-rose-300 font-mono">
                ✓ Successfully deleted record from <strong>{details.table}</strong>
              </span>
              <span className="text-xs font-mono text-rose-400 bg-rose-900/40 px-2 py-1 rounded">
                -1 Row
              </span>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Source Records Table View */}
      {activeTab === "records" && hasRecords && (
        <div className="p-4">
          <div className="text-xs font-mono text-slate-400 mb-2 flex items-center justify-between">
            <span>Evaluating Records ({details.sample_records?.length}):</span>
            <span className="text-cyan-400 font-medium">Included in calculation</span>
          </div>
          <div className="max-h-56 overflow-auto border border-slate-700/60 rounded-xl custom-scrollbar">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead className="bg-slate-800/90 text-slate-300 sticky top-0 border-b border-slate-700">
                <tr>
                  {Object.keys(details.sample_records![0]).map((k) => (
                    <th key={k} className="px-3 py-2 font-semibold">
                      {k}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 bg-slate-900/50">
                {details.sample_records!.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                    {Object.entries(row).map(([k, v]) => (
                      <td key={k} className="px-3 py-2 text-slate-300">
                        {k.toLowerCase().includes("salary") || k.toLowerCase().includes("price") || k.toLowerCase().includes("amount") ? (
                          <span className="text-emerald-400 font-semibold">
                            {typeof v === "number" ? `$${v.toLocaleString()}` : String(v)}
                          </span>
                        ) : (
                          String(v ?? "—")
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: SQL Execution Query */}
      {activeTab === "sql" && (
        <div className="p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">Parameterized SQL Execution:</span>
            <button
              onClick={copySql}
              className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 bg-slate-800 px-2 py-1 rounded border border-slate-700 transition-colors"
            >
              {copied ? "✓ Copied!" : "📋 Copy SQL"}
            </button>
          </div>
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-cyan-300 overflow-x-auto leading-relaxed">
            {details.sql || "No SQL statement recorded."}
          </div>
        </div>
      )}
    </div>
  );
};
