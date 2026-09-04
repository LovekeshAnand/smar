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
    <div className="w-full flex flex-col items-center gap-3">
      {/* Big glowing Push-to-Talk button */}
      <button
        onClick={onToggleRecord}
        className="relative w-16 h-16 rounded-full flex items-center justify-center group focus:outline-none"
        aria-label="Toggle Microphone"
      >
        {/* Expanding pulse ripple ring when recording */}
        {isRecording && (
          <span className="absolute inset-0 rounded-full border-2 border-rose-500/80 animate-ping pointer-events-none" />
        )}

        <div
          className={`w-14 h-14 rounded-full flex items-center justify-center text-white transition-all duration-300 shadow-xl ${
            isRecording
              ? "bg-gradient-to-br from-rose-500 to-red-600 shadow-[0_0_35px_rgba(244,63,94,0.7)] scale-105"
              : "bg-gradient-to-br from-cyan-500 to-indigo-600 shadow-[0_0_25px_rgba(14,165,233,0.5)] group-hover:scale-105 group-hover:shadow-[0_0_35px_rgba(0,240,255,0.7)]"
          }`}
        >
          <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        </div>
      </button>

      <div className="text-xs text-slate-400 font-sans">
        Click mic or press <kbd className="px-1.5 py-0.5 rounded bg-white/10 border border-white/10 font-mono text-[11px] text-slate-300">Space</kbd> to talk
      </div>

      {/* Fallback Text Input Form */}
      <form onSubmit={handleSubmit} className="w-full max-w-md">
        <div className="flex items-center bg-slate-900/80 border border-white/10 focus-within:border-cyan-400 focus-within:shadow-[0_0_20px_rgba(0,240,255,0.2)] rounded-full px-4 py-1.5 transition-all">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type prompt or command (e.g. 'What is my name?')..."
            className="flex-1 bg-transparent border-none outline-none text-slate-100 placeholder:text-slate-500 text-xs sm:text-sm"
          />
          <button
            type="submit"
            aria-label="Send message"
            className="w-8 h-8 rounded-full bg-cyan-500/15 hover:bg-cyan-400 border border-cyan-500/30 text-cyan-300 hover:text-black flex items-center justify-center transition-colors shrink-0"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
};
