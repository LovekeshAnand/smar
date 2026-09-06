"use client";

import React, { useState } from "react";

export interface VisualChartData {
  image_base64: string;
  chart_type: string;
  title: string;
  description?: string;
}

interface VisualChartCardProps {
  chart: VisualChartData;
}

export const VisualChartCard: React.FC<VisualChartCardProps> = ({ chart }) => {
  const [isZoomed, setIsZoomed] = useState(false);

  if (!chart || !chart.image_base64) return null;

  const downloadImage = () => {
    const link = document.createElement("a");
    link.href = chart.image_base64;
    link.download = `${(chart.title || "chart").toLowerCase().replace(/\s+/g, "_")}.png`;
    link.click();
  };

  return (
    <div className="w-full max-w-lg mt-2.5 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-700/60 shadow-xl overflow-hidden text-left transition-all">
      {/* Chart Header */}
      <div className="px-3.5 py-2 bg-slate-800/80 border-b border-slate-700/60 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            📊 Visual Chart ({chart.chart_type})
          </span>
          <span className="text-xs font-mono font-medium text-slate-200 truncate max-w-[200px]">
            {chart.title}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsZoomed(true)}
            className="text-[11px] font-mono text-slate-400 hover:text-slate-200 bg-slate-800 px-2 py-0.5 rounded transition-colors"
            title="Expand Chart"
          >
            🔍 Zoom
          </button>
          <button
            onClick={downloadImage}
            className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 bg-slate-800 px-2 py-0.5 rounded transition-colors"
            title="Download PNG"
          >
            ⬇ Save
          </button>
        </div>
      </div>

      {/* Render Image */}
      <div className="p-2 flex justify-center bg-slate-950/40">
        <img
          src={chart.image_base64}
          alt={chart.title || "Data Chart"}
          className="rounded-lg max-h-72 w-auto object-contain cursor-pointer hover:opacity-95 transition-opacity"
          onClick={() => setIsZoomed(true)}
        />
      </div>

      {/* Description / Subtitle */}
      {chart.description && (
        <div className="px-3 py-1.5 bg-slate-900/60 border-t border-slate-800 text-[11px] text-slate-400 font-sans">
          {chart.description}
        </div>
      )}

      {/* Modal Zoom View */}
      {isZoomed && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in"
          onClick={() => setIsZoomed(false)}
        >
          <div
            className="relative max-w-4xl max-h-[90vh] p-3 rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-2 px-2">
              <h3 className="text-sm font-mono text-slate-200 font-semibold">{chart.title}</h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={downloadImage}
                  className="text-xs font-mono text-cyan-400 hover:text-cyan-300 px-2 py-1 rounded bg-slate-800"
                >
                  Download PNG
                </button>
                <button
                  onClick={() => setIsZoomed(false)}
                  className="text-xs font-mono text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800"
                >
                  ✕ Close
                </button>
              </div>
            </div>
            <img
              src={chart.image_base64}
              alt={chart.title}
              className="max-h-[80vh] w-auto object-contain rounded-lg"
            />
          </div>
        </div>
      )}
    </div>
  );
};
