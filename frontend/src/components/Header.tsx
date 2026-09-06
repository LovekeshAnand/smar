"use client";

import React from "react";
import { UserProfile } from "./UserAuthModal";

interface HeaderProps {
  onToggleMemory: () => void;
  isMemoryOpen: boolean;
  isConnected: boolean;
  language: string;
  onToggleLanguage: () => void;
  currentUser: UserProfile;
  onOpenUserModal: () => void;
  onToggleDataUpload: () => void;
  isDataReady?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleMemory,
  isMemoryOpen,
  isConnected,
  language,
  onToggleLanguage,
  currentUser,
  onOpenUserModal,
  onToggleDataUpload,
  isDataReady = true,
}) => {
  return (
    <header className="h-20 px-6 flex items-center justify-between border-b border-white/5 bg-slate-950/60 backdrop-blur-md z-30">
      {/* Brand & Connection Status */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-3.5">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isConnected ? "bg-cyan-400 shadow-[0_0_8px_#00f0ff]" : "bg-slate-600"
            }`}
          />
          <img
            src="/smar_logo_transparent.png"
            alt="smar logo"
            className="h-14 sm:h-16 w-auto object-contain select-none transition-transform hover:scale-105"
          />
          <span
            style={{ fontFamily: '"Times New Roman", Times, serif', color: "#ffffff" }}
            className="text-2xl sm:text-3xl font-normal tracking-wide text-white lowercase select-none"
          >
            smar
          </span>
        </div>
      </div>

      {/* Right Actions: User Badge, Language toggle & Memory drawer toggle */}
      <div className="flex items-center gap-2.5">
        {/* User Profile Chip */}
        <button
          onClick={onOpenUserModal}
          className="flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-xs font-mono text-slate-200 transition-all shadow-sm group"
          title={`Logged in as ${currentUser.name} (@${currentUser.username}). Click to manage users.`}
        >
          <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-300 font-bold flex items-center justify-center text-[10px] border border-cyan-500/30">
            {currentUser.username[0]?.toUpperCase() || "L"}
          </span>
          <span className="font-semibold text-[11px] text-white group-hover:text-cyan-300 transition-colors">
            {currentUser.username}
          </span>
          <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 uppercase">
            {currentUser.role}
          </span>
        </button>

        {/* Language Toggle */}
        <button
          onClick={onToggleLanguage}
          className="px-2.5 py-1 rounded-full text-[11px] font-mono text-cyan-300 bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
          title={`Language: ${language === "en-IN" ? "English" : "Hindi"}. Click to toggle.`}
        >
          {language === "en-IN" ? "EN" : "HI"}
        </button>

        {/* Memory Drawer Toggle */}
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
