"use client";

import React from "react";
import Link from "next/link";
import { GradientWaves } from "@/components/landing/GradientWaves";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 flex flex-col selection:bg-white selection:text-black font-sans antialiased">
      {/* ─── Minimalist Header: Logo Left, Launch Console Right ─────── */}
      <div className="fixed top-0 left-0 right-0 z-50 flex justify-center px-4 pt-4 sm:pt-6 pointer-events-none">
        <header className="pointer-events-auto w-full max-w-5xl h-14 px-5 sm:px-6 rounded-full border border-white/[0.1] bg-zinc-950/75 backdrop-blur-xl flex items-center justify-between shadow-[0_8px_32px_rgba(0,0,0,0.6)]">
          {/* Logo Left */}
          <Link href="/" className="flex items-center gap-2 group cursor-pointer">
            <img
              src="/logo.png"
              onError={(e) => {
                e.currentTarget.src = "/smar_logo_transparent.png";
              }}
              alt="logo"
              className="h-7 sm:h-8 w-auto object-contain transition-transform group-hover:scale-105"
            />
            <span
              style={{ fontFamily: '"Times New Roman", Times, serif', color: "#ffffff" }}
              className="text-2xl sm:text-[26px] font-normal tracking-normal text-white lowercase select-none"
            >
              smar
            </span>
          </Link>

          {/* Get Started Right */}
          <Link
            href="/console"
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-medium bg-white text-zinc-950 hover:bg-zinc-200 transition-all shadow-sm active:scale-95 cursor-pointer"
          >
            <span>Get Started</span>
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </Link>
        </header>
      </div>

      {/* ─── Hero Section with Vibrant GradientWaves WebGL ─────────────── */}
      <section className="relative min-h-[96vh] flex flex-col items-center justify-center text-center px-4 sm:px-6 pt-24 pb-16 overflow-hidden">
        {/* Dynamic Gradient Waves WebGL (Vibrant, Fully Visible) */}
        <div className="absolute inset-0 z-0">
          <GradientWaves
            horizonColor="#5227FF"
            waveColor="#FF9FFC"
            crestColor="#FFFFFF"
            speed={0.35}
            amplitude={2.5}
            waveScale={0.6}
            waveRatio={0.9}
            swell={35}
            turbulence={20}
            tilt={1.11}
            zoom={1.0}
            height={5.2}
            fogDepth={15}
            detail="medium"
            brightness={1.05}
            opacity={0.9}
            mouseInteraction={true}
            parallaxStrength={0.45}
            grain={true}
            grainIntensity={0.04}
            className="w-full h-full"
          />
        </div>

        {/* Subtle Bottom Gradient Fade into Content */}
        <div className="absolute inset-x-0 bottom-0 h-44 z-[1] bg-gradient-to-t from-[#09090b] via-[#09090b]/70 to-transparent pointer-events-none" />

        {/* Hero Content (Ultra-Clean, Concise, No Latency Mentions) */}
        <div className="relative z-10 max-w-4xl mx-auto flex flex-col items-center space-y-6 animate-in fade-in duration-700">
          {/* Headline: Both Lines White with Subtle Gradient */}
          <h1 className="text-3xl sm:text-5xl md:text-6xl font-normal tracking-[-0.03em] leading-[1.18] max-w-4xl mx-auto drop-shadow-[0_4px_30px_rgba(0,0,0,0.8)]">
            <span className="bg-clip-text text-transparent bg-gradient-to-b from-white via-white/95 to-zinc-200 block">
              Autonomous Voice Engine
            </span>
            <span className="bg-clip-text text-transparent bg-gradient-to-b from-white/95 via-white/85 to-zinc-300 block mt-1 font-light">
              for Enterprise Data
            </span>
          </h1>

          {/* Expanded Subtitle: AI Voice Assistant that Remembers and Executes Operations */}
          <p className="max-w-3xl mx-auto text-base sm:text-lg text-zinc-300 font-normal leading-relaxed tracking-tight drop-shadow-[0_2px_14px_rgba(0,0,0,0.9)]">
            An autonomous AI voice assistant that doesn&apos;t just answer queries from your data,
            but remembers context, executes complex operations, and audits live records in real&nbsp;time.
          </p>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-3.5 pt-2">
            <Link
              href="/console"
              className="group relative inline-flex items-center gap-2 px-7 py-3 rounded-full text-xs sm:text-sm font-medium 
                         bg-white text-zinc-950 hover:bg-zinc-100 
                         shadow-[0_0_25px_rgba(255,255,255,0.2),inset_0_1px_0_rgba(255,255,255,1)] 
                         transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
            >
              <span>Get Started</span>
              <svg 
                className="w-3.5 h-3.5 transition-transform duration-200 group-hover:translate-x-0.5" 
                viewBox="0 0 24 24" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="2.5"
              >
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </Link>

            <a
              href="#platform"
              className="inline-flex items-center gap-2 px-7 py-3 rounded-full text-xs sm:text-sm font-normal 
                         text-zinc-200 bg-zinc-950/60 hover:bg-zinc-900/80 
                         border border-white/15 hover:border-white/30 
                         backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] 
                         transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
            >
              <svg className="w-3 h-3 text-zinc-400" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="6 3 20 12 6 21 6 3" />
              </svg>
              <span>Explore Architecture</span>
            </a>
          </div>
        </div>
      </section>

      {/* ─── Modern Bento Grid ($2B AI Startup Design) ───────────────────── */}
      <section id="platform" className="py-24 px-6 sm:px-12 max-w-7xl mx-auto w-full relative z-20">
        <div className="max-w-3xl mb-16 space-y-3">
          <p className="text-xs font-mono uppercase tracking-widest text-zinc-400">
            Autonomous Infrastructure
          </p>
          <h2 className="text-3xl sm:text-5xl font-semibold tracking-tight text-white leading-tight">
            Conversational Intelligence Engineered for Enterprise Production
          </h2>
          <p className="text-zinc-400 text-base font-normal leading-relaxed">
            Eliminate complex SQL interfaces and stale BI dashboards. Empower operators to command,
            query, and audit physical business data through real-time conversational agents.
          </p>
        </div>

        {/* 6 High-End Neomorphic Bento Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Card 1: Row Provenance */}
          <div className="p-7 rounded-2xl bg-zinc-950/60 border border-white/[0.08] hover:border-white/[0.16] 
                          shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_12px_24px_-12px_rgba(0,0,0,0.8)] 
                          transition-all duration-300 flex flex-col justify-between group backdrop-blur-sm">
            <div>
              <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.08] flex items-center justify-center text-zinc-200 mb-5">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <ellipse cx="12" cy="5" rx="9" ry="3" />
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-white mb-2">Auditable Database Provenance</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Every calculation and record lookup reveals the active database file, queried table,
                and exact physical row ID directly on the response bubble.
              </p>
            </div>
            <div className="mt-6 p-3 rounded-xl bg-zinc-900/80 border border-white/[0.06] font-mono text-[11px] text-zinc-300 flex items-center justify-between">
              <span>smar_inventory.db / employees</span>
              <span className="text-zinc-400">Row #48</span>
            </div>
          </div>

          {/* Card 2: Voice Pipeline */}
          <div className="p-7 rounded-2xl bg-zinc-950/60 border border-white/[0.08] hover:border-white/[0.16] 
                          shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_12px_24px_-12px_rgba(0,0,0,0.8)] 
                          transition-all duration-300 flex flex-col justify-between group backdrop-blur-sm">
            <div>
              <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.08] flex items-center justify-center text-zinc-200 mb-5">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" x2="12" y1="19" y2="22" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-white mb-2">Voice AI Agent</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Natural bidirectional speech interaction equipped with live frequency visualizers,
                hands-free voice control, and real-time English and Hindi neural translation.
              </p>
            </div>
            <div className="mt-6 p-3 rounded-xl bg-zinc-900/80 border border-white/[0.06] font-mono text-[11px] text-zinc-300 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                Streaming Visualizer
              </span>
              <span className="text-zinc-400">Multilingual</span>
            </div>
          </div>

          {/* Card 3: Deterministic Ground Truth */}
          <div className="p-7 rounded-2xl bg-zinc-950/60 border border-white/[0.08] hover:border-white/[0.16] 
                          shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_12px_24px_-12px_rgba(0,0,0,0.8)] 
                          transition-all duration-300 flex flex-col justify-between group backdrop-blur-sm">
            <div>
              <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.08] flex items-center justify-center text-zinc-200 mb-5">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <path d="m9 12 2 2 4-4" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-white mb-2">Zero-Hallucination Execution</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Queries compile deterministically into validated SQL statements against physical records.
                Operators can inspect, audit, and copy exact query statements with one click.
              </p>
            </div>
            <div className="mt-6 p-3 rounded-xl bg-zinc-900/80 border border-white/[0.06] font-mono text-[11px] text-zinc-300 flex items-center justify-between">
              <span className="truncate max-w-[190px]">SELECT * FROM warehouse...</span>
              <span className="text-zinc-400">1-Click SQL</span>
            </div>
          </div>

          {/* Card 4: Dynamic Knowledge Graph */}
          <div className="p-7 rounded-2xl bg-zinc-950/60 border border-white/[0.08] hover:border-white/[0.16] 
                          shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_12px_24px_-12px_rgba(0,0,0,0.8)] 
                          transition-all duration-300 flex flex-col justify-between group backdrop-blur-sm">
            <div>
              <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.08] flex items-center justify-center text-zinc-200 mb-5">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <circle cx="6" cy="6" r="3" />
                  <circle cx="18" cy="18" r="3" />
                  <circle cx="18" cy="6" r="3" />
                  <line x1="8.5" x2="15.5" y1="7.5" y2="16.5" />
                  <line x1="9" x2="15" y1="6" y2="6" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-white mb-2">Zero-ETL Adaptive Graphs</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Eliminates brittle ETL pipelines. The secondary indexing graph adapts dynamically
                to schema changes, warehouse mutations, and custom relational schemas in real time.
              </p>
            </div>
            <div className="mt-6 p-3 rounded-xl bg-zinc-900/80 border border-white/[0.06] font-mono text-[11px] text-zinc-300 flex items-center justify-between">
              <span>Dual-Graph Architecture</span>
              <span className="text-zinc-400">Continuous Sync</span>
            </div>
          </div>

          {/* Card 5: High Performance */}
          <div className="p-7 rounded-2xl bg-zinc-950/60 border border-white/[0.08] hover:border-white/[0.16] 
                          shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_12px_24px_-12px_rgba(0,0,0,0.8)] 
                          transition-all duration-300 flex flex-col justify-between group backdrop-blur-sm">
            <div>
              <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.08] flex items-center justify-center text-zinc-200 mb-5">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-white mb-2">Instant Response Latency</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Engineered for rapid data retrieval across millions of warehouse rows. Delivers
                instant aggregated KPIs, multi-table joins, and complex mutations in milliseconds.
              </p>
            </div>
            <div className="mt-6 p-3 rounded-xl bg-zinc-900/80 border border-white/[0.06] font-mono text-[11px] text-zinc-300 flex items-center justify-between">
              <span>Operational Pipeline</span>
              <span className="text-emerald-400 font-medium">Real-time</span>
            </div>
          </div>

          {/* Card 6: Enterprise Security */}
          <div className="p-7 rounded-2xl bg-zinc-950/60 border border-white/[0.08] hover:border-white/[0.16] 
                          shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_12px_24px_-12px_rgba(0,0,0,0.8)] 
                          transition-all duration-300 flex flex-col justify-between group backdrop-blur-sm">
            <div>
              <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.08] flex items-center justify-center text-zinc-200 mb-5">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-white mb-2">Airgapped & Private VPC Ready</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Designed to operate completely within your enterprise security perimeter. All speech
                models, database connections, and index caches run locally with zero telemetry egress.
              </p>
            </div>
            <div className="mt-6 p-3 rounded-xl bg-zinc-900/80 border border-white/[0.06] font-mono text-[11px] text-zinc-300 flex items-center justify-between">
              <span>Security Perimeter</span>
              <span className="text-zinc-400">Zero Data Leakage</span>
            </div>
          </div>
        </div>

        {/* Minimalist Executive CTA Block */}
        <div className="mt-20 p-8 sm:p-10 rounded-3xl bg-zinc-950/80 border border-white/[0.1] shadow-2xl flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="space-y-1 text-center sm:text-left">
            <h4 className="text-xl font-semibold text-white">Experience SMAR in Real Time</h4>
            <p className="text-xs text-zinc-400">
              Launch the live interactive workspace with real database queries, voice synthesis, and row provenance.
            </p>
          </div>
          <Link
            href="/console"
            className="px-7 py-3 rounded-full text-xs font-semibold bg-white text-zinc-950 hover:bg-zinc-200 transition-all shadow-lg shrink-0 cursor-pointer"
          >
            Get Started →
          </Link>
        </div>
      </section>

      {/* ─── Ultra-Clean Minimalist Footer ──────────────────────────────── */}
      <footer className="border-t border-white/[0.08] py-8 px-6 sm:px-12 bg-zinc-950 text-xs font-mono text-zinc-500 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="font-medium text-zinc-300">SMAR</span>
          <span>© {new Date().getFullYear()}</span>
        </div>
        <div className="flex items-center gap-6">
          <a href="#platform" className="hover:text-zinc-300 transition-colors">Platform</a>
          <Link href="/console" className="hover:text-zinc-300 transition-colors">Console</Link>
          <span className="text-zinc-400">Enterprise AI Infrastructure</span>
        </div>
      </footer>
    </div>
  );
}
