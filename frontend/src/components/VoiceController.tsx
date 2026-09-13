"use client";

import React, { useState } from "react";

interface VoiceControllerProps {
  isRecording: boolean;
  onToggleRecord: () => void;
  onSubmitText: (text: string) => void;
}

export const VoiceController: React.FC<VoiceControllerProps> = ({
  isRecording,
  onToggleRecord,
  onSubmitText,
}) => {
  const [inputText, setInputText] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onSubmitText(inputText.trim());
    setInputText("");
  };

  return (
    <div className="w-full max-w-xl mx-auto flex flex-col items-center gap-3">
      {/* ─── Modern Floating Command / Prompt Box ─────────────────────── */}
      <form
        onSubmit={handleSubmit}
        className="w-full relative rounded-2xl bg-zinc-950/85 backdrop-blur-2xl border border-white/[0.12] hover:border-white/25 focus-within:border-white/40 shadow-[0_16px_40px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.08)] transition-all duration-300 p-2 flex items-center gap-2 group"
      >
        {/* Left Action Icon */}
        <div className="pl-2 flex items-center text-zinc-400 group-focus-within:text-white transition-colors">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        </div>

        {/* Text Input */}
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Ask anything, query database, or speak..."
          className="flex-1 bg-transparent border-none outline-none text-zinc-100 placeholder:text-zinc-500 text-sm font-sans tracking-normal px-2 py-1.5"
        />

        {/* Right Controls: Integrated Microphone + Send Button */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Microphone Toggle Button */}
          <button
            type="button"
            onClick={onToggleRecord}
            className={`p-2.5 rounded-xl transition-all duration-200 cursor-pointer flex items-center justify-center relative ${
              isRecording
                ? "bg-white text-zinc-950 shadow-[0_0_20px_rgba(255,255,255,0.5)] scale-105"
                : "bg-white/[0.06] hover:bg-white/[0.12] text-zinc-300 hover:text-white border border-white/10"
            }`}
            title={isRecording ? "Click to finish voice input" : "Speak (or hold Spacebar)"}
          >
            {isRecording && (
              <span className="absolute -inset-0.5 rounded-xl border border-white animate-ping opacity-60 pointer-events-none" />
            )}
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </button>

          {/* Send Button */}
          <button
            type="submit"
            disabled={!inputText.trim()}
            className="p-2.5 rounded-xl bg-white text-zinc-950 hover:bg-zinc-200 disabled:opacity-20 disabled:pointer-events-none transition-all duration-200 shadow-sm cursor-pointer"
            title="Execute query"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </form>

      {/* Keyboard Shortcut Hint */}
      <div className="text-[11px] font-mono text-zinc-500 pt-0.5">
        Press <span className="px-1.5 py-0.5 rounded bg-white/10 text-zinc-300 border border-white/10 text-[10px]">Space</span> to speak or <span className="px-1.5 py-0.5 rounded bg-white/10 text-zinc-300 border border-white/10 text-[10px]">Enter</span> to send
      </div>
    </div>
  );
};
