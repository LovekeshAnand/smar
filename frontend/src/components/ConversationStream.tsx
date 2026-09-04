"use client";

import React, { useEffect, useRef } from "react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: string;
  audioBase64?: string | null;
  contextUsed?: string | null;
  workIntent?: {
    action?: string;
    target?: string;
    success?: boolean;
  } | null;
}

interface ConversationStreamProps {
  messages: ChatMessage[];
  onPlayAudio: (audioBase64: string) => void;
}

export const ConversationStream: React.FC<ConversationStreamProps> = ({ messages, onPlayAudio }) => {
  const feedRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="flex flex-col h-full bg-slate-950/70 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-slate-900/50">
        <div className="flex items-center gap-2 text-slate-200">
          <svg className="w-4 h-4 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          <h2 className="text-sm font-semibold tracking-wide">Conversation Stream</h2>
        </div>
        <span className="font-mono text-xs text-slate-500">{messages.length} messages</span>
      </div>

      {/* Messages Feed */}
      <div ref={feedRef} className="flex-1 overflow-y-auto p-4 space-y-3.5 custom-scrollbar">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`p-3.5 rounded-xl border text-sm transition-all duration-200 animate-in fade-in slide-in-from-bottom-2 ${
              m.role === "user"
                ? "bg-cyan-950/20 border-cyan-500/30 border-l-4 border-l-cyan-400 text-slate-100"
                : "bg-rose-950/20 border-rose-500/30 border-l-4 border-l-rose-400 text-slate-100"
            }`}
          >
            {/* Meta */}
            <div className="flex items-center justify-between mb-1.5 font-mono text-xs">
              <span className={`font-bold ${m.role === "user" ? "text-cyan-400" : "text-rose-400"}`}>
                {m.role === "user" ? "You" : "SMAR (Nalini)"}
              </span>
              <span className="text-slate-500 text-[11px]">{m.timestamp}</span>
            </div>

            {/* Body */}
            <div className="leading-relaxed text-slate-200 text-xs sm:text-sm whitespace-pre-wrap">{m.text}</div>

            {/* Actions & badges */}
            {m.role === "assistant" && (
              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                {m.audioBase64 && (
                  <button
                    onClick={() => onPlayAudio(m.audioBase64!)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-rose-500/15 hover:bg-rose-500/30 border border-rose-500/30 text-rose-300 text-xs font-semibold transition-colors"
                  >
                    <svg className="w-3 h-3 fill-current" viewBox="0 0 24 24">
                      <polygon points="5 3 19 12 5 21 5 3" />
                    </svg>
                    <span>Play Voice</span>
                  </button>
                )}

                {m.contextUsed && m.contextUsed.trim() && (
                  <span
                    className="px-2 py-0.5 rounded bg-purple-500/15 border border-purple-500/30 text-purple-300 text-[11px] font-mono cursor-help"
                    title={m.contextUsed}
                  >
                    Context Grounded
                  </span>
                )}

                {m.workIntent && m.workIntent.action && (
                  <div className="w-full mt-1 px-2.5 py-1.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono flex items-center gap-2">
                    <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>
                      Action Dispatched: <strong>{m.workIntent.action}</strong> &rarr; {m.workIntent.target}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
