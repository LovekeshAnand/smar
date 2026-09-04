"use client";

import React from "react";

interface HeaderProps {
  onToggleMemory: () => void;
  isMemoryOpen: boolean;
  isConnected: boolean;
  language: string;
  onToggleLanguage: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleMemory,
  isMemoryOpen,
  isConnected,
  language,
  onToggleLanguage,
}) => {
  return (
    <header className="h-14 px-6 flex items-center justify-between border-b border-white/5 bg-transparent backdrop-blur-sm z-30">
      {/* Minimal Brand */}
      <div className="flex items-center gap-2.5">
        <span
          className={`w-2 h-2 rounded-full ${
            isConnected ? "bg-cyan-400 shadow-[0_0_8px_#00f0ff]" : "bg-slate-600"
          }`}
        />
        <span className="font-sans font-semibold tracking-wider text-sm text-slate-200 lowercase">
          smar
        </span>
      </div>

      {/* Right Actions: Minimal language toggle & memory drawer toggle */}
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleLanguage}
          className="px-2.5 py-0.5 rounded-full text-[11px] font-mono text-cyan-300 bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
          title={`Language: ${language === "en-IN" ? "English" : "Hindi"}. Click to toggle.`}
        >
          {language === "en-IN" ? "EN" : "HI"}
        </button>

        <button
          onClick={onToggleMemory}
          className={`px-3 py-1 rounded-full text-xs font-mono transition-all flex items-center gap-1.5 ${
            isMemoryOpen
              ? "bg-white/15 text-white border border-white/20"
              : "bg-white/5 hover:bg-white/10 text-slate-400 hover:text-slate-200 border border-transparent"
          }`}
          aria-label="Toggle Memory Drawer"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          <span>memory</span>
        </button>
      </div>
    </header>
  );
};
