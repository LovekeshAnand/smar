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
  onToggleRules?: () => void;
  isRulesOpen?: boolean;
  onToggleAlerts?: () => void;
  unresolvedAlertsCount?: number;
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
  onToggleRules,
  isRulesOpen = false,
  onToggleAlerts,
  unresolvedAlertsCount = 0,
}) => {
  return (
    <header className="h-16 px-6 sm:px-10 flex items-center justify-between border-b border-white/[0.08] bg-zinc-950/75 backdrop-blur-xl z-30">
      {/* Brand Lockup */}
      <div className="flex items-center">
        <a href="/" className="flex items-center gap-2 group cursor-pointer transition-opacity hover:opacity-90" title="Return to Landing Page">
          <img
            src="/logo.png"
            onError={(e) => {
              e.currentTarget.src = "/smar_logo_transparent.png";
            }}
            alt="smar logo"
            className="h-7 sm:h-8 w-auto object-contain select-none transition-transform group-hover:scale-105"
          />
          <span
            style={{ fontFamily: '"Times New Roman", Times, serif', color: "#ffffff" }}
            className="text-2xl sm:text-[26px] font-normal tracking-normal text-white lowercase select-none"
          >
            smar
          </span>
        </a>
      </div>

      {/* Right Actions: User Badge, Language toggle & Memory drawer toggle */}
      <div className="flex items-center gap-2.5">
        {/* User Profile Chip */}
        <button
          onClick={onOpenUserModal}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900/80 hover:bg-zinc-800 border border-zinc-800/90 text-xs font-mono text-zinc-200 transition-all shadow-sm group cursor-pointer"
          title={`Logged in as ${currentUser.name} (@${currentUser.username}). Click to manage users.`}
        >
          <span className="w-5 h-5 rounded-full bg-white/10 text-white font-bold flex items-center justify-center text-[10px] border border-white/20">
            {currentUser.username[0]?.toUpperCase() || "L"}
          </span>
          <span className="font-medium text-[11px] text-zinc-200 group-hover:text-white transition-colors">
            {currentUser.username}
          </span>
          <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-white/10 text-zinc-300 border border-white/10 uppercase">
            {currentUser.role}
          </span>
        </button>

        {/* Language Toggle */}
        <button
          onClick={onToggleLanguage}
          className="px-3 py-1.5 rounded-full text-[11px] font-mono text-zinc-300 bg-zinc-900/80 hover:bg-zinc-800 border border-zinc-800/90 hover:border-zinc-700 transition-colors cursor-pointer"
          title={`Language: ${language === "en-IN" ? "English" : "Hindi"}. Click to toggle.`}
        >
          {language === "en-IN" ? "EN" : "HI"}
        </button>

        {/* Business Rules Drawer Toggle */}
        <button
          onClick={onToggleRules}
          className={`px-3 py-1.5 rounded-full text-xs font-mono transition-all flex items-center gap-1.5 cursor-pointer ${
            isRulesOpen
              ? "bg-white text-zinc-950 font-semibold shadow-md"
              : "bg-zinc-900/80 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800/90 hover:border-zinc-700"
          }`}
          title="Open Business Rules Engine"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          <span>Rules</span>
        </button>

        {/* Admin Alerts Modal Toggle */}
        <button
          onClick={onToggleAlerts}
          className={`px-3 py-1.5 rounded-full text-xs font-mono transition-all flex items-center gap-1.5 cursor-pointer ${
            (unresolvedAlertsCount || 0) > 0
              ? "bg-rose-500/15 border border-rose-500/40 text-rose-300 hover:bg-rose-500/25"
              : "bg-zinc-900/80 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-800/90"
          }`}
          title="View Admin Security Inbox & Access Violations"
        >
          <svg className="w-3.5 h-3.5 text-rose-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span>Alerts</span>
          {(unresolvedAlertsCount || 0) > 0 && (
            <span className="w-4 h-4 rounded-full bg-rose-500 text-white text-[9px] font-bold flex items-center justify-center animate-pulse">
              {unresolvedAlertsCount}
            </span>
          )}
        </button>

        {/* Memory Drawer Toggle */}
        <button
          onClick={onToggleMemory}
          className={`px-3.5 py-1.5 rounded-full text-xs font-mono transition-all flex items-center gap-1.5 cursor-pointer ${
            isMemoryOpen
              ? "bg-white text-zinc-950 font-semibold shadow-md"
              : "bg-zinc-900/80 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800/90 hover:border-zinc-700"
          }`}
          aria-label="Toggle Memory Drawer"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          <span>Memory</span>
        </button>
      </div>
    </header>
  );
};
