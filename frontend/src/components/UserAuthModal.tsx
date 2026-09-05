"use client";

import React, { useState, useEffect } from "react";

export interface UserProfile {
  username: string;
  name: string;
  role: string;
  created_at?: string;
  token?: string;
}

interface UserAuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: UserProfile;
  onUserChange: (user: UserProfile) => void;
}

export const UserAuthModal: React.FC<UserAuthModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  onUserChange,
}) => {
  const [activeTab, setActiveTab] = useState<"profile" | "switch" | "register" | "login">("profile");
  const [usersList, setUsersList] = useState<UserProfile[]>([]);
  const [loginUsername, setLoginUsername] = useState("lovekesh");
  const [loginPassword, setLoginPassword] = useState("lovekesh123");
  const [regUsername, setRegUsername] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regName, setRegName] = useState("");
  const [regRole, setRegRole] = useState("user");
  const [statusMsg, setStatusMsg] = useState<{ text: string; isError: boolean } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchUsers();
      setStatusMsg(null);
    }
  }, [isOpen]);

  const fetchUsers = async () => {
    try {
      const res = await fetch("/api/auth/users");
      if (res.ok) {
        const data = await res.json();
        setUsersList(data.users || []);
      }
    } catch (e) {
      console.error("Failed to fetch users:", e);
    }
  };

  if (!isOpen) return null;

  const handleLogin = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsLoading(true);
    setStatusMsg(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: loginUsername.trim(),
          password: loginPassword,
        }),
      });
      const data = await res.json();
      if (res.ok && data.user) {
        const u = { ...data.user, token: data.token };
        onUserChange(u);
        setStatusMsg({ text: `Successfully logged in as ${u.name}!`, isError: false });
        setTimeout(() => onClose(), 800);
      } else {
        setStatusMsg({ text: data.detail || "Authentication failed", isError: true });
      }
    } catch (err: any) {
      setStatusMsg({ text: err.message || "Network error", isError: true });
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setStatusMsg(null);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: regUsername.trim(),
          password: regPassword,
          name: regName.trim() || regUsername.trim(),
          role: regRole,
        }),
      });
      const data = await res.json();
      if (res.ok && data.user) {
        const u = { ...data.user, token: data.token };
        onUserChange(u);
        setStatusMsg({ text: `Created user and logged in as ${u.name}!`, isError: false });
        fetchUsers();
        setTimeout(() => onClose(), 800);
      } else {
        setStatusMsg({ text: data.detail || "Registration failed", isError: true });
      }
    } catch (err: any) {
      setStatusMsg({ text: err.message || "Network error", isError: true });
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickSwitch = async (username: string) => {
    // If switching to lovekesh, use known password lovekesh123
    if (username === "lovekesh") {
      setLoginUsername("lovekesh");
      setLoginPassword("lovekesh123");
      setIsLoading(true);
      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: "lovekesh", password: "lovekesh123" }),
        });
        const data = await res.json();
        if (res.ok && data.user) {
          onUserChange({ ...data.user, token: data.token });
          setStatusMsg({ text: `Switched to ${data.user.name}`, isError: false });
          setTimeout(() => onClose(), 600);
          return;
        }
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    }
    // Otherwise open login tab pre-populated
    setLoginUsername(username);
    setLoginPassword("");
    setActiveTab("login");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-md bg-slate-950/95 border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="w-8 h-8 rounded-full bg-cyan-500/20 text-cyan-300 font-mono font-bold flex items-center justify-center text-xs border border-cyan-500/30">
              {currentUser.username[0]?.toUpperCase() || "U"}
            </span>
            <div>
              <h3 className="text-sm font-semibold text-white">Multi-User Management</h3>
              <p className="text-[10px] text-slate-400">
                Active: <span className="text-cyan-400 font-mono font-bold">{currentUser.username}</span> ({currentUser.role})
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white flex items-center justify-center transition-colors text-xs"
          >
            ✕
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-white/5 bg-white/[0.02] p-1 gap-1">
          <button
            onClick={() => setActiveTab("profile")}
            className={`flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-colors ${
              activeTab === "profile" ? "bg-white/10 text-white font-bold" : "text-slate-400 hover:text-white"
            }`}
          >
            Profile
          </button>
          <button
            onClick={() => setActiveTab("switch")}
            className={`flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-colors ${
              activeTab === "switch" ? "bg-white/10 text-white font-bold" : "text-slate-400 hover:text-white"
            }`}
          >
            Switch User ({usersList.length})
          </button>
          <button
            onClick={() => setActiveTab("register")}
            className={`flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-colors ${
              activeTab === "register" ? "bg-white/10 text-white font-bold" : "text-slate-400 hover:text-white"
            }`}
          >
            + New User
          </button>
          <button
            onClick={() => setActiveTab("login")}
            className={`flex-1 py-1.5 rounded-lg text-[11px] font-mono transition-colors ${
              activeTab === "login" ? "bg-white/10 text-white font-bold" : "text-slate-400 hover:text-white"
            }`}
          >
            Login
          </button>
        </div>

        {/* Status banner */}
        {statusMsg && (
          <div
            className={`mx-6 mt-3 px-3 py-2 rounded-lg text-[11px] font-mono ${
              statusMsg.isError
                ? "bg-red-500/20 text-red-300 border border-red-500/30"
                : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
            }`}
          >
            {statusMsg.text}
          </div>
        )}

        {/* Tab Content */}
        <div className="p-6 space-y-4">
          {/* 1. Profile View */}
          {activeTab === "profile" && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-white/[0.03] border border-white/5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 text-xs font-mono">Logged in as</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    🟢 Active Session
                  </span>
                </div>
                <div className="space-y-1">
                  <div className="text-base font-bold text-white">{currentUser.name}</div>
                  <div className="text-xs font-mono text-cyan-400">@{currentUser.username}</div>
                  <div className="text-[11px] font-mono text-purple-300 uppercase tracking-wide">
                    Role: {currentUser.role}
                  </div>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-cyan-500/[0.04] border border-cyan-500/20 text-[11px] text-slate-300 leading-relaxed">
                🛡️ <strong>Multi-User Isolation Active:</strong> Your conversation memory, personal facts, and vector memories are scoped strictly to <code>{currentUser.username}</code>. Shared warehouse schemas are globally synchronized.
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setActiveTab("switch");
                  }}
                  className="flex-1 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white font-mono text-xs transition-colors"
                >
                  Switch User
                </button>
                <button
                  onClick={() => {
                    setLoginUsername("");
                    setLoginPassword("");
                    setActiveTab("login");
                  }}
                  className="px-4 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 font-mono text-xs transition-colors border border-red-500/20"
                >
                  Log Out
                </button>
              </div>
            </div>
          )}

          {/* 2. Switch User List */}
          {activeTab === "switch" && (
            <div className="space-y-3">
              <span className="text-slate-400 text-xs font-mono block">Registered Users in System:</span>
              <div className="space-y-2 max-h-60 overflow-y-auto custom-scrollbar">
                {usersList.map((u) => {
                  const isCurrent = u.username === currentUser.username;
                  return (
                    <div
                      key={u.username}
                      className={`p-3 rounded-xl border flex items-center justify-between transition-all ${
                        isCurrent
                          ? "bg-cyan-500/10 border-cyan-500/30"
                          : "bg-white/[0.02] border-white/5 hover:border-white/15"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="w-7 h-7 rounded-full bg-white/10 text-white font-mono font-bold flex items-center justify-center text-xs">
                          {u.username[0]?.toUpperCase()}
                        </span>
                        <div>
                          <div className="text-xs font-bold text-white">{u.name}</div>
                          <div className="text-[10px] font-mono text-slate-400">@{u.username} • {u.role}</div>
                        </div>
                      </div>
                      {isCurrent ? (
                        <span className="text-[10px] font-mono text-cyan-400 font-bold px-2 py-0.5 rounded bg-cyan-500/20">
                          Active
                        </span>
                      ) : (
                        <button
                          onClick={() => handleQuickSwitch(u.username)}
                          className="px-3 py-1 rounded-lg bg-white/10 hover:bg-cyan-500 hover:text-slate-950 font-mono text-[10px] text-white transition-all font-bold"
                        >
                          Switch
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 3. Register New User */}
          {activeTab === "register" && (
            <form onSubmit={handleRegister} className="space-y-3">
              <div className="space-y-1">
                <label className="text-[11px] font-mono text-slate-400">Username *</label>
                <input
                  type="text"
                  required
                  value={regUsername}
                  onChange={(e) => setRegUsername(e.target.value)}
                  placeholder="e.g. rahul"
                  className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-xs font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-mono text-slate-400">Full Name</label>
                <input
                  type="text"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  placeholder="e.g. Rahul Sharma"
                  className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-xs font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-mono text-slate-400">Password *</label>
                <input
                  type="password"
                  required
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  placeholder="Minimum 4 characters"
                  className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-xs font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-mono text-slate-400">Role</label>
                <select
                  value={regRole}
                  onChange={(e) => setRegRole(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-white/10 text-white text-xs font-mono focus:border-cyan-500 focus:outline-none"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                  <option value="analyst">Analyst</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full mt-2 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-slate-950 font-mono font-bold text-xs hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {isLoading ? "Creating User..." : "Create User & Log In"}
              </button>
            </form>
          )}

          {/* 4. Login Form */}
          {activeTab === "login" && (
            <form onSubmit={handleLogin} className="space-y-3">
              <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5 text-[11px] text-slate-300">
                Pre-configured user credentials: <br />
                <span className="font-mono text-cyan-400">username: lovekesh</span> |{" "}
                <span className="font-mono text-cyan-400">password: lovekesh123</span>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-mono text-slate-400">Username</label>
                <input
                  type="text"
                  required
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  placeholder="lovekesh"
                  className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-xs font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-mono text-slate-400">Password</label>
                <input
                  type="password"
                  required
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="lovekesh123"
                  className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-xs font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setLoginUsername("lovekesh");
                    setLoginPassword("lovekesh123");
                  }}
                  className="px-3 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 font-mono text-[11px] transition-colors border border-white/5"
                >
                  Fill Lovekesh
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex-1 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs transition-colors disabled:opacity-50"
                >
                  {isLoading ? "Authenticating..." : "Log In"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
