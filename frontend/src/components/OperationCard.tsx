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
  breakdown?: Record<string, any>;
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
  const [showSql, setShowSql] = useState(false);
  const [copied, setCopied] = useState(false);

  const getBadgeStyle = () => {
    switch (details.operation) {
      case "AGGREGATION":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
      case "INSERT":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "UPDATE":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "DELETE":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      case "TABULAR":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      default:
        return "bg-slate-500/10 text-slate-400 border-slate-500/30";
    }
  };

  const copySql = () => {
    if (details.sql) {
      navigator.clipboard.writeText(details.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="w-full max-w-lg mt-2.5 p-3 rounded-xl bg-slate-900/80 backdrop-blur-md border border-slate-700/60 shadow-lg text-left transition-all">
      {/* Header Bar */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border ${getBadgeStyle()}`}>
            {details.function ? `${details.function} ${details.operation}` : details.operation}
          </span>
          <span className="text-xs font-mono text-slate-300">
            table: <strong className="text-cyan-300 font-semibold">{details.table}</strong>
          </span>
        </div>
        {details.elapsed_ms !== undefined && (
          <span className="text-[10px] font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded">
            ⚡ {details.elapsed_ms}ms
          </span>
        )}
      </div>

      {/* Main Metric / Result Display */}
      {details.operation === "AGGREGATION" && details.formatted_value && (
        <div className="my-1.5 p-2 rounded-lg bg-slate-800/50 border border-slate-700/40">
          <div className="text-[11px] text-slate-400 font-mono">
            {details.function} of {details.column} {details.group_by ? `by ${details.group_by}` : ""}
          </div>
          <div className="text-lg sm:text-xl font-bold font-mono text-emerald-400 mt-0.5">
            {details.formatted_value}
          </div>
          {details.total_rows_evaluated !== undefined && (
            <div className="text-[10px] text-slate-400 font-sans mt-0.5">
              Evaluated across {details.total_rows_evaluated.toLocaleString()} rows
            </div>
          )}
        </div>
      )}

      {/* UPDATE Diff Display */}
      {details.operation === "UPDATE" && details.diff && (
        <div className="my-1.5 p-2 rounded-lg bg-slate-800/60 border border-amber-500/20 space-y-1">
          <div className="text-[11px] font-mono text-amber-400 font-medium">Field Modifications:</div>
          {Object.entries(details.diff).map(([col, d]) => (
            <div key={col} className="text-xs font-mono flex items-center gap-2 flex-wrap">
              <span className="text-slate-300">{col}:</span>
              <span className="line-through text-rose-400/80 bg-rose-950/40 px-1.5 py-0.5 rounded">
                {String(d.before)}
              </span>
              <span className="text-slate-500">→</span>
              <span className="font-semibold text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded">
                {String(d.after)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* INSERT Details */}
      {details.operation === "INSERT" && details.inserted_id && (
        <div className="my-1.5 p-2 rounded-lg bg-emerald-950/20 border border-emerald-500/20">
          <span className="text-xs text-emerald-300 font-mono">
            ✓ Inserted row ID: <strong>#{String(details.inserted_id)}</strong>
          </span>
        </div>
      )}

      {/* DELETE Details */}
      {details.operation === "DELETE" && details.deleted_record && (
        <div className="my-1.5 p-2 rounded-lg bg-rose-950/20 border border-rose-500/20">
          <span className="text-xs text-rose-300 font-mono">
            ✓ Deleted entry matching criteria
          </span>
        </div>
      )}

      {/* Collapsible SQL Query */}
      {details.sql && (
        <div className="mt-2 pt-2 border-t border-slate-800">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowSql(!showSql)}
              className="text-[11px] font-mono text-slate-400 hover:text-slate-200 transition-colors inline-flex items-center gap-1"
            >
              <span>{showSql ? "▼ Hide SQL" : "▶ View Executed SQL"}</span>
            </button>
            {showSql && (
              <button
                onClick={copySql}
                className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                {copied ? "Copied!" : "Copy SQL"}
              </button>
            )}
          </div>
          {showSql && (
            <pre className="mt-1.5 p-2 rounded bg-slate-950 text-[11px] font-mono text-slate-300 overflow-x-auto border border-slate-800 leading-relaxed">
              {details.sql}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};
