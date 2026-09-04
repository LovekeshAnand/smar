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

export const ConversationStream: React.FC<ConversationStreamProps> = ({
  messages,
  onPlayAudio,
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
      className="w-full max-w-xl max-h-[180px] sm:max-h-[220px] overflow-y-auto px-4 py-2 space-y-3 custom-scrollbar text-center"
    >
      {messages.slice(-4).map((m) => (
        <div key={m.id} className="transition-all duration-300 animate-in fade-in">
          {m.role === "user" ? (
            <p className="text-xs sm:text-sm font-sans text-slate-400 font-medium tracking-wide">
              &ldquo;{m.text}&rdquo;
            </p>
          ) : (
            <div className="flex flex-col items-center gap-1.5 mt-1">
              <p className="text-sm sm:text-base font-sans text-slate-100 font-light leading-relaxed">
                {m.text}
              </p>
              {m.audioBase64 && (
                <button
                  onClick={() => onPlayAudio(m.audioBase64!)}
                  className="inline-flex items-center gap-1 text-[11px] text-rose-400/80 hover:text-rose-300 font-mono transition-colors mt-0.5"
                >
                  <svg className="w-2.5 h-2.5 fill-current" viewBox="0 0 24 24">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                  <span>replay</span>
                </button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
