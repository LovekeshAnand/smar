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
    <div className="w-full flex flex-col items-center gap-4">
      {/* Sleek Minimalist Microphone Trigger */}
      <button
        onClick={onToggleRecord}
        className="relative w-14 h-14 rounded-full flex items-center justify-center group focus:outline-none transition-transform active:scale-95"
        aria-label="Toggle Microphone"
      >
        {isRecording && (
          <span className="absolute inset-0 rounded-full border border-cyan-400/60 animate-ping pointer-events-none" />
        )}

        <div
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-300 ${
            isRecording
              ? "bg-cyan-500 text-black shadow-[0_0_30px_rgba(0,240,255,0.7)]"
              : "bg-white/10 hover:bg-white/15 text-slate-200 border border-white/10 hover:border-white/20 shadow-lg"
          }`}
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        </div>
      </button>

      {/* Floating Minimal Input Bar */}
      <form onSubmit={handleSubmit} className="w-full max-w-sm">
        <div className="flex items-center bg-white/[0.04] hover:bg-white/[0.06] focus-within:bg-white/[0.08] border border-white/10 focus-within:border-cyan-400/50 rounded-full px-4 py-2 transition-all">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="ask or type anything..."
            className="flex-1 bg-transparent border-none outline-none text-slate-200 placeholder:text-slate-500 text-xs font-sans tracking-wide"
          />
          {inputText.trim() && (
            <button
              type="submit"
              className="text-cyan-400 hover:text-cyan-300 transition-colors p-1"
              aria-label="Send prompt"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          )}
        </div>
      </form>
    </div>
  );
};
