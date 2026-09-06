"use client";

import React from "react";

export interface TableData {
  table: string;
  columns: string[];
  rows: any[][];
  total_count: number;
  displayed_count: number;
  sql?: string;
  elapsed_ms?: number;
}

interface DataTableCardProps {
  data: TableData;
}

export const DataTableCard: React.FC<DataTableCardProps> = ({ data }) => {
  if (!data || !data.columns || !data.rows) return null;

  return (
    <div className="w-full max-w-2xl mt-2.5 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-700/60 shadow-xl overflow-hidden text-left">
      {/* Table Header / Summary */}
      <div className="px-3.5 py-2.5 bg-slate-800/80 border-b border-slate-700/60 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/30">
            Table View
          </span>
          <span className="text-xs font-mono font-semibold text-slate-200">
            {data.table}
          </span>
        </div>
        <div className="text-[11px] font-mono text-slate-400">
          Showing <span className="text-cyan-400 font-semibold">{data.displayed_count}</span> of{" "}
          <span className="text-slate-200">{data.total_count.toLocaleString()}</span> rows
        </div>
      </div>

      {/* Scrollable Table Content */}
      <div className="overflow-x-auto max-h-64 custom-scrollbar">
        <table className="w-full text-left text-xs font-mono border-collapse">
          <thead>
            <tr className="bg-slate-950/60 text-slate-400 border-b border-slate-800 sticky top-0 backdrop-blur-sm">
              {data.columns.map((col, idx) => (
                <th key={idx} className="px-3 py-2 font-semibold uppercase tracking-wider text-[10px]">
                  {col.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {data.rows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className="hover:bg-slate-800/40 transition-colors text-slate-300"
              >
                {row.map((cell, cellIdx) => {
                  const isNum = typeof cell === "number";
                  return (
                    <td
                      key={cellIdx}
                      className={`px-3 py-2 whitespace-nowrap ${isNum ? "text-right font-medium text-emerald-300" : ""}`}
                    >
                      {cell === null || cell === undefined
                        ? "-"
                        : isNum
                        ? cell.toLocaleString()
                        : String(cell)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
