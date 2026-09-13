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
    <div className="w-full max-w-xl mt-3 rounded-2xl bg-zinc-950/95 backdrop-blur-xl border border-purple-500/20 hover:border-purple-500/40 shadow-[0_8px_30px_rgba(0,0,0,0.7),inset_0_1px_0_rgba(168,85,247,0.15)] overflow-hidden text-left transition-all">
      {/* Chart Header */}
      <div className="px-4 py-2.5 bg-zinc-900/60 border-b border-white/[0.08] flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/30 font-medium">
            {chart.chart_type.toUpperCase()}
          </span>
          <span className="text-xs font-mono font-medium text-zinc-100 truncate max-w-[240px]">
            {chart.title}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsZoomed(true)}
            className="text-[11px] font-mono text-zinc-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1 rounded-lg border border-zinc-800 transition-colors cursor-pointer"
            title="Expand Chart"
          >
            Zoom
          </button>
          <button
            onClick={downloadImage}
            className="text-[11px] font-mono text-white bg-purple-600 hover:bg-purple-500 px-3 py-1 rounded-lg border border-purple-400/40 shadow-sm transition-colors cursor-pointer font-medium"
            title="Download PNG"
          >
            Save PNG
          </button>
        </div>
      </div>

      {/* Render Image */}
      <div className="p-3 flex justify-center bg-zinc-950/40">
        <img
          src={chart.image_base64}
          alt={chart.title || "Data Chart"}
          className="rounded-xl max-h-80 w-auto object-contain cursor-pointer hover:opacity-95 transition-opacity"
          onClick={() => setIsZoomed(true)}
        />
      </div>

      {/* Description / Subtitle */}
      {chart.description && (
        <div className="px-4 py-2 bg-zinc-900/30 border-t border-white/[0.06] text-[11px] text-zinc-400 font-sans flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
          <span>{chart.description}</span>
        </div>
      )}

      {/* Modal Zoom View */}
      {isZoomed && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in"
          onClick={() => setIsZoomed(false)}
        >
          <div
            className="relative max-w-4xl max-h-[90vh] p-4 rounded-2xl bg-zinc-950 border border-purple-500/30 shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-3 px-1">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  {chart.chart_type}
                </span>
                <h3 className="text-sm font-mono text-white font-semibold">{chart.title}</h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={downloadImage}
                  className="text-xs font-mono text-white bg-purple-600 hover:bg-purple-500 px-3 py-1 rounded-lg transition-colors cursor-pointer"
                >
                  Download PNG
                </button>
                <button
                  onClick={() => setIsZoomed(false)}
                  className="text-xs font-mono text-zinc-400 hover:text-white px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 transition-colors cursor-pointer"
                >
                  ✕ Close
                </button>
              </div>
            </div>
            <img
              src={chart.image_base64}
              alt={chart.title}
              className="max-h-[78vh] w-auto object-contain rounded-xl border border-white/[0.06]"
            />
          </div>
        </div>
      )}
    </div>
  );
};
