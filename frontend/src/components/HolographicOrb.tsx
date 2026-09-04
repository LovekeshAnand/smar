"use client";

import React, { useEffect, useRef } from "react";

export type OrbState = "IDLE" | "LISTENING" | "THINKING" | "SPEAKING";

interface HolographicOrbProps {
  state: OrbState;
  audioData: Uint8Array;
}

interface Particle {
  x: number;
  y: number;
  radius: number;
  speedX: number;
  speedY: number;
  alpha: number;
}

export const HolographicOrb: React.FC<HolographicOrbProps> = ({ state, audioData }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const waveRef = useRef<HTMLCanvasElement | null>(null);
  const stateRef = useRef<OrbState>(state);
  const audioDataRef = useRef<Uint8Array>(audioData);
  const phaseRef = useRef<number>(0);
  const rotationRef = useRef<number>(0);
  const smoothAmpRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);

  // Keep refs fresh
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    audioDataRef.current = audioData;
  }, [audioData]);

  useEffect(() => {
    // Initialize background particles
    const particles: Particle[] = [];
    for (let i = 0; i < 36; i++) {
      particles.push({
        x: Math.random() * 380,
        y: Math.random() * 380,
        radius: Math.random() * 1.8 + 0.5,
        speedX: (Math.random() - 0.5) * 0.4,
        speedY: (Math.random() - 0.5) * 0.4,
        alpha: Math.random() * 0.5 + 0.2,
      });
    }
    particlesRef.current = particles;

    let animId: number;

    const render = () => {
      const orbCanvas = canvasRef.current;
      const waveCanvas = waveRef.current;
      if (!orbCanvas || !waveCanvas) {
        animId = requestAnimationFrame(render);
        return;
      }

      const ctx = orbCanvas.getContext("2d");
      const waveCtx = waveCanvas.getContext("2d");
      if (!ctx || !waveCtx) {
        animId = requestAnimationFrame(render);
        return;
      }

      const currentState = stateRef.current;
      const data = audioDataRef.current;

      // Compute average amplitude
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += data[i];
      const currentAmp = sum / (Math.max(1, data.length) * 255);
      smoothAmpRef.current += (currentAmp - smoothAmpRef.current) * 0.25;

      phaseRef.current += 0.035;
      rotationRef.current += currentState === "THINKING" ? 0.08 : 0.015;

      ctx.clearRect(0, 0, 380, 380);
      waveCtx.clearRect(0, 0, 360, 36);

      const cx = 190;
      const cy = 190;

      // 1. Render floating background stardust
      for (const p of particlesRef.current) {
        p.x += p.speedX;
        p.y += p.speedY;
        if (p.x < 0) p.x = 380;
        if (p.x > 380) p.x = 0;
        if (p.y < 0) p.y = 380;
        if (p.y > 380) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 240, 255, ${p.alpha * 0.4})`;
        ctx.fill();
      }

      // 2. Render state-dependent Orb
      if (currentState === "LISTENING") {
        renderListeningOrb(ctx, cx, cy, smoothAmpRef.current, phaseRef.current, data);
      } else if (currentState === "THINKING") {
        renderThinkingOrb(ctx, cx, cy, rotationRef.current, phaseRef.current);
      } else if (currentState === "SPEAKING") {
        renderSpeakingOrb(ctx, cx, cy, smoothAmpRef.current, phaseRef.current, data);
      } else {
        renderIdleOrb(ctx, cx, cy, phaseRef.current, rotationRef.current);
      }

      // 3. Render Spectrogram Bar Equalizer
      renderWaveform(waveCtx, data, currentState);

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, []);

  const renderIdleOrb = (ctx: CanvasRenderingContext2D, cx: number, cy: number, phase: number, rot: number) => {
    const baseRadius = 80 + Math.sin(phase) * 5;

    // Outer aura
    const gradOuter = ctx.createRadialGradient(cx, cy, 20, cx, cy, baseRadius + 40);
    gradOuter.addColorStop(0, "rgba(0, 240, 255, 0.35)");
    gradOuter.addColorStop(0.5, "rgba(168, 85, 247, 0.2)");
    gradOuter.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = gradOuter;
    ctx.beginPath();
    ctx.arc(cx, cy, baseRadius + 40, 0, Math.PI * 2);
    ctx.fill();

    // Inner glossy sphere
    const gradInner = ctx.createRadialGradient(cx - 25, cy - 25, 5, cx, cy, baseRadius);
    gradInner.addColorStop(0, "#cffafe");
    gradInner.addColorStop(0.3, "#00f0ff");
    gradInner.addColorStop(0.7, "#6366f1");
    gradInner.addColorStop(1, "#0f172a");

    ctx.beginPath();
    ctx.arc(cx, cy, baseRadius, 0, Math.PI * 2);
    ctx.fillStyle = gradInner;
    ctx.shadowColor = "#00f0ff";
    ctx.shadowBlur = 24;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Gyro ring
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(rot);
    ctx.beginPath();
    ctx.ellipse(0, 0, baseRadius + 18, (baseRadius + 18) * 0.35, Math.PI / 4, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(0, 240, 255, 0.4)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();
  };

  const renderListeningOrb = (
    ctx: CanvasRenderingContext2D,
    cx: number,
    cy: number,
    amp: number,
    phase: number,
    data: Uint8Array
  ) => {
    const baseRadius = 85 + amp * 60 + Math.sin(phase * 2) * 3;

    // Reactive frequency spike contours
    ctx.beginPath();
    const points = 64;
    for (let i = 0; i < points; i++) {
      const angle = (i / points) * Math.PI * 2;
      const freqIdx = i % data.length;
      const freqVal = (data[freqIdx] || 0) / 255;
      const r = baseRadius + freqVal * 35;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();

    const grad = ctx.createRadialGradient(cx, cy, 20, cx, cy, baseRadius + 40);
    grad.addColorStop(0, "rgba(255, 255, 255, 0.9)");
    grad.addColorStop(0.4, "rgba(0, 240, 255, 0.7)");
    grad.addColorStop(0.8, "rgba(14, 165, 233, 0.3)");
    grad.addColorStop(1, "rgba(0, 0, 0, 0)");

    ctx.fillStyle = grad;
    ctx.shadowColor = "#00f0ff";
    ctx.shadowBlur = 35;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Outer shockwave ring
    ctx.beginPath();
    ctx.arc(cx, cy, baseRadius + 20 + amp * 30, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(0, 240, 255, ${0.4 + amp * 0.5})`;
    ctx.lineWidth = 2;
    ctx.stroke();
  };

  const renderThinkingOrb = (ctx: CanvasRenderingContext2D, cx: number, cy: number, rot: number, phase: number) => {
    const baseRadius = 80;

    // Swirling concentric gyroscopic vortex rings in violet & magenta
    for (let r = 0; r < 3; r++) {
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(rot * (r % 2 === 0 ? 1.5 : -1.2) + r * (Math.PI / 3));

      ctx.beginPath();
      ctx.ellipse(0, 0, baseRadius + r * 14, (baseRadius + r * 14) * 0.45, 0, 0, Math.PI * 2);
      ctx.strokeStyle = r === 0 ? "#c084fc" : r === 1 ? "#ec4899" : "#818cf8";
      ctx.lineWidth = 2.5;
      ctx.shadowColor = "#a855f7";
      ctx.shadowBlur = 20;
      ctx.stroke();
      ctx.restore();
    }

    // Core pulsing nucleus
    const pulseRadius = 55 + Math.sin(phase * 4) * 8;
    const gradCore = ctx.createRadialGradient(cx, cy, 5, cx, cy, pulseRadius);
    gradCore.addColorStop(0, "#ffffff");
    gradCore.addColorStop(0.5, "#a855f7");
    gradCore.addColorStop(1, "#3b0764");

    ctx.beginPath();
    ctx.arc(cx, cy, pulseRadius, 0, Math.PI * 2);
    ctx.fillStyle = gradCore;
    ctx.shadowColor = "#d946ef";
    ctx.shadowBlur = 30;
    ctx.fill();
    ctx.shadowBlur = 0;
  };

  const renderSpeakingOrb = (
    ctx: CanvasRenderingContext2D,
    cx: number,
    cy: number,
    amp: number,
    phase: number,
    data: Uint8Array
  ) => {
    const effectiveAmp = amp || 0.35;
    const baseRadius = 85 + effectiveAmp * 45;

    // Glowing warm rose & golden plasma
    const grad = ctx.createRadialGradient(cx, cy, 15, cx, cy, baseRadius + 30);
    grad.addColorStop(0, "#fff1f2");
    grad.addColorStop(0.3, "#f43f5e");
    grad.addColorStop(0.7, "#fbbf24");
    grad.addColorStop(1, "rgba(244, 63, 94, 0)");

    ctx.beginPath();
    const waveCount = 48;
    for (let i = 0; i < waveCount; i++) {
      const angle = (i / waveCount) * Math.PI * 2;
      const freqIdx = i % data.length;
      const audioVal = (data[freqIdx] || 0) / 255;
      const r = baseRadius + Math.sin(angle * 8 + phase * 3) * (6 + audioVal * 25);
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();

    ctx.fillStyle = grad;
    ctx.shadowColor = "#f43f5e";
    ctx.shadowBlur = 35;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Expanding speech ring
    const ringRadius = baseRadius + 22 + ((phase * 25) % 40);
    const ringAlpha = 1 - ((phase * 25) % 40) / 40;
    ctx.beginPath();
    ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(251, 191, 36, ${ringAlpha * 0.7})`;
    ctx.lineWidth = 2;
    ctx.stroke();
  };

  const renderWaveform = (waveCtx: CanvasRenderingContext2D, data: Uint8Array, currentState: OrbState) => {
    const w = 360;
    const h = 36;
    const bars = 36;
    const barWidth = 6;
    const gap = (w - bars * barWidth) / (bars - 1);

    for (let i = 0; i < bars; i++) {
      const val = (data[i % data.length] || 15) / 255;
      const barHeight = Math.max(3, val * (h - 6));
      const x = i * (barWidth + gap);
      const y = h - barHeight;

      let color = "rgba(0, 240, 255, 0.4)";
      if (currentState === "LISTENING") color = "#00f0ff";
      else if (currentState === "THINKING") color = "#c084fc";
      else if (currentState === "SPEAKING") color = "#fb7185";

      waveCtx.fillStyle = color;
      waveCtx.beginPath();
      // Draw rounded bar
      waveCtx.roundRect(x, y, barWidth, barHeight, [2, 2, 0, 0]);
      waveCtx.fill();
    }
  };

  const getStateLabel = () => {
    switch (state) {
      case "LISTENING":
        return "LISTENING (MIC ACTIVE)";
      case "THINKING":
        return "THINKING (EPSILON 7B)";
      case "SPEAKING":
        return "SPEAKING (NALINI TTS)";
      default:
        return "SYSTEM READY";
    }
  };

  const getStateClasses = () => {
    switch (state) {
      case "LISTENING":
        return "border-cyan-400 bg-cyan-500/10 shadow-[0_0_25px_rgba(0,240,255,0.3)] text-cyan-300";
      case "THINKING":
        return "border-purple-400 bg-purple-500/10 shadow-[0_0_25px_rgba(168,85,247,0.3)] text-purple-300";
      case "SPEAKING":
        return "border-rose-400 bg-rose-500/10 shadow-[0_0_25px_rgba(244,63,94,0.3)] text-rose-300";
      default:
        return "border-slate-700/60 bg-slate-900/60 text-slate-300";
    }
  };

  const getDotClasses = () => {
    switch (state) {
      case "LISTENING":
        return "bg-cyan-400 shadow-[0_0_10px_#00f0ff]";
      case "THINKING":
        return "bg-purple-400 shadow-[0_0_10px_#a855f7]";
      case "SPEAKING":
        return "bg-rose-400 shadow-[0_0_10px_#f43f5e]";
      default:
        return "bg-emerald-400 shadow-[0_0_10px_#10b981]";
    }
  };

  return (
    <div className="flex flex-col items-center justify-center gap-4">
      {/* State badge */}
      <div
        className={`flex items-center gap-2 px-4 py-1.5 rounded-full border backdrop-blur-md transition-all duration-300 font-mono text-xs font-semibold tracking-wider ${getStateClasses()}`}
      >
        <span className={`w-2 h-2 rounded-full ${getDotClasses()}`} />
        <span>{getStateLabel()}</span>
      </div>

      {/* Canvas container */}
      <div className="relative w-[380px] h-[380px] flex items-center justify-center">
        <canvas ref={canvasRef} width={380} height={380} className="relative z-10" />
        <div className="absolute w-72 h-72 rounded-full bg-radial from-cyan-500/15 via-purple-500/10 to-transparent blur-3xl pointer-events-none" />
      </div>

      {/* Audio spectrogram */}
      <div className="w-[360px] h-[36px] bg-slate-900/40 border border-slate-800/80 rounded-lg overflow-hidden flex items-center justify-center shadow-inner">
        <canvas ref={waveRef} width={360} height={36} />
      </div>
    </div>
  );
};
