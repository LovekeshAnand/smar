"use client";

import React, { useState, useEffect, useRef } from "react";

export interface BusinessRule {
  id: string;
  title: string;
  category: string;
  priority: number;
  keywords: string[];
  description: string;
  is_active: boolean;
  created_at?: string;
}

interface BusinessRulesDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onRuleAdded?: () => void;
}

export const BusinessRulesDrawer: React.FC<BusinessRulesDrawerProps> = ({
  isOpen,
  onClose,
  onRuleAdded,
}) => {
  const [rules, setRules] = useState<BusinessRule[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showAddForm, setShowAddForm] = useState<boolean>(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  // Form State
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("operations");
  const [priority, setPriority] = useState<number>(5);
  const [keywords, setKeywords] = useState("");

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchRules();
    }
  }, [isOpen]);

  const fetchRules = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/rules");
      if (res.ok) {
        const data = await res.json();
        setRules(data.rules || []);
      }
    } catch (e) {
      console.error("Failed to fetch business rules:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;

    try {
      const kwList = keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);

      const res = await fetch("/api/rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          category,
          priority,
          keywords: kwList,
          is_active: true,
        }),
      });

      if (res.ok) {
        setTitle("");
        setDescription("");
        setKeywords("");
        setShowAddForm(false);
        await fetchRules();
        if (onRuleAdded) onRuleAdded();
      }
    } catch (err) {
      console.error("Failed to create rule:", err);
    }
  };

  const handleDeleteRule = async (ruleId: string) => {
    try {
      const res = await fetch(`/api/rules/${ruleId}`, { method: "DELETE" });
      if (res.ok) {
        setRules((prev) => prev.filter((r) => r.id !== ruleId));
      }
    } catch (e) {
      console.error("Failed to delete rule:", e);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus("Ingesting rules...");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/rules/upload", {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        setUploadStatus(`Successfully ingested ${data.added_count} rules!`);
        setTimeout(() => setUploadStatus(null), 3000);
        await fetchRules();
        if (onRuleAdded) onRuleAdded();
      } else {
        setUploadStatus("Upload failed.");
      }
    } catch (err) {
      console.error("Rule upload error:", err);
      setUploadStatus("Upload error.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  if (!isOpen) return null;

  const categories = ["all", "operations", "pricing", "safety", "sla", "returns"];
  const filteredRules =
    selectedCategory === "all"
      ? rules
      : rules.filter((r) => r.category.toLowerCase() === selectedCategory.toLowerCase());

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm transition-opacity">
      <div className="w-full max-w-xl bg-zinc-950/95 border-l border-white/[0.1] h-full flex flex-col shadow-2xl text-zinc-100 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-white/[0.08] flex items-center justify-between bg-zinc-900/40">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <h2 className="text-lg font-semibold tracking-tight text-white">Business Rules Engine</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/10 text-zinc-300">
                Layer 4
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Enterprise policies & operational workflows dynamically injected into local LLM
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Action Toolbar */}
        <div className="px-6 py-3 border-b border-white/[0.08] bg-zinc-900/20 flex items-center justify-between gap-2">
          {/* Category Filter Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto custom-scrollbar py-0.5">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`text-[11px] px-2.5 py-1 rounded-full font-mono uppercase tracking-wider transition-all cursor-pointer ${
                  selectedCategory === cat
                    ? "bg-white text-zinc-950 font-semibold shadow-sm"
                    : "bg-zinc-900/80 text-zinc-400 hover:text-zinc-200 border border-zinc-800"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Upload Document Button */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.txt,.md"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-2.5 py-1 text-xs font-mono rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-700/60 transition-all flex items-center gap-1.5 cursor-pointer"
              title="Upload Markdown, Text, or JSON rules file"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <span>Upload</span>
            </button>

            {/* Add Rule Toggle */}
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="px-3 py-1 text-xs font-medium rounded-lg bg-white text-zinc-950 hover:bg-zinc-200 transition-all flex items-center gap-1.5 shadow-sm cursor-pointer"
            >
              <span>{showAddForm ? "Cancel" : "+ Add Rule"}</span>
            </button>
          </div>
        </div>

        {uploadStatus && (
          <div className="px-6 py-2 text-xs bg-emerald-950/60 border-b border-emerald-500/30 text-emerald-300 font-mono flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            {uploadStatus}
          </div>
        )}

        {/* Add Rule Form */}
        {showAddForm && (
          <form onSubmit={handleCreateRule} className="p-6 border-b border-white/[0.1] bg-zinc-900/60 space-y-3">
            <h3 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
              Define New Business Policy
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] text-zinc-400 font-mono uppercase mb-1">Rule Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Fragile Freight Packaging"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder:text-zinc-600 focus:border-white/40 outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] text-zinc-400 font-mono uppercase mb-1">Category</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-white focus:border-white/40 outline-none"
                  >
                    <option value="operations">Operations</option>
                    <option value="pricing">Pricing</option>
                    <option value="safety">Safety</option>
                    <option value="sla">SLA</option>
                    <option value="returns">Returns</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-zinc-400 font-mono uppercase mb-1">Priority (1-10)</label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={priority}
                    onChange={(e) => setPriority(parseInt(e.target.value) || 5)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-white focus:border-white/40 outline-none"
                  />
                </div>
              </div>
            </div>
            <div>
              <label className="block text-[10px] text-zinc-400 font-mono uppercase mb-1">Rule Directive / Description</label>
              <textarea
                required
                rows={2}
                placeholder="Exact guidelines and procedural actions enforced by the AI..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder:text-zinc-600 focus:border-white/40 outline-none"
              />
            </div>
            <div>
              <label className="block text-[10px] text-zinc-400 font-mono uppercase mb-1">
                Keywords (comma separated)
              </label>
              <input
                type="text"
                placeholder="packaging, fragile, bubble wrap, glassware"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder:text-zinc-600 focus:border-white/40 outline-none"
              />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-3 py-1 rounded-lg text-xs text-zinc-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 text-xs font-semibold"
              >
                Commit Rule
              </button>
            </div>
          </form>
        )}

        {/* Rules List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3 custom-scrollbar">
          {isLoading ? (
            <div className="text-center py-12 text-zinc-500 text-xs font-mono">Loading active rules...</div>
          ) : filteredRules.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-xs font-mono">
              No rules registered in this category.
            </div>
          ) : (
            filteredRules.map((rule) => (
              <div
                key={rule.id}
                className="p-4 rounded-xl bg-zinc-900/50 border border-white/[0.08] hover:border-white/[0.18] transition-all space-y-2 group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/10 text-white font-medium border border-white/10">
                      {rule.id}
                    </span>
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-500/20">
                      {rule.category}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-400">P{rule.priority}</span>
                  </div>
                  <button
                    onClick={() => handleDeleteRule(rule.id)}
                    className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-rose-400 transition-opacity p-1"
                    title="Deactivate rule"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                </div>
                <h4 className="text-sm font-medium text-zinc-100">{rule.title}</h4>
                <p className="text-xs text-zinc-300 leading-relaxed">{rule.description}</p>
                {rule.keywords && rule.keywords.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {rule.keywords.map((kw, i) => (
                      <span key={i} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-800/80 text-zinc-400">
                        #{kw}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
