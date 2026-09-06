"use client";

import React, { useEffect, useRef } from "react";
import { OperationCard, OperationDetails } from "./OperationCard";
import { DataTableCard, TableData } from "./DataTableCard";
import { VisualChartCard, VisualChartData } from "./VisualChartCard";

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

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div
      ref={feedRef}
      className={
        className ||
        "w-full max-w-3xl max-h-[58vh] sm:max-h-[64vh] overflow-y-auto px-2 sm:px-4 py-3 space-y-5 custom-scrollbar transition-all"
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
              <div className="w-full bg-gradient-to-b from-slate-900/80 to-slate-950/80 backdrop-blur-xl border border-slate-800/90 rounded-2xl rounded-tl-sm p-4 sm:p-5 shadow-2xl text-left">
                {/* Assistant Header */}
                <div className="flex items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-slate-800/60">
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

                  <div className="flex items-center gap-2">
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
    </div>
  );
};
