"use client";

import React, { useEffect, useRef } from "react";

export type VisualizerState = "IDLE" | "LISTENING" | "THINKING" | "SPEAKING";

interface AudioSpikesVisualizerProps {
  state: VisualizerState;
  audioData: Uint8Array;
}

export const AudioSpikesVisualizer: React.FC<AudioSpikesVisualizerProps> = ({
  state,
  audioData,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const stateRef = useRef<VisualizerState>(state);
  const audioDataRef = useRef<Uint8Array>(audioData);
  const phaseRef = useRef<number>(0);
  const spikeHeightsRef = useRef<number[]>(new Array(72).fill(4));

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    audioDataRef.current = audioData;
  }, [audioData]);

  useEffect(() => {
    let animId: number;

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) {
        animId = requestAnimationFrame(render);
        return;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        animId = requestAnimationFrame(render);
        return;
      }

      const width = canvas.width;
      const height = canvas.height;
      const cx = width / 2;
      const cy = height / 2;

      ctx.clearRect(0, 0, width, height);

      phaseRef.current += 0.04;
      const phase = phaseRef.current;
      const currentState = stateRef.current;
      const rawData = audioDataRef.current;

      const numSpikes = 72;
      const baseRadius = 65;
      const maxSpikeHeight = 85;

      // Smooth spike interpolation with spring-like physics
      const heights = spikeHeightsRef.current;

      for (let i = 0; i < numSpikes; i++) {
        // Mirror frequencies around circle (lows at top/bottom, highs at sides)
        const halfIndex = i < numSpikes / 2 ? i : numSpikes - i;
        const dataIdx = Math.floor((halfIndex / (numSpikes / 2)) * (rawData.length / 2));
        const audioVal = (rawData[dataIdx] || 0) / 255;

        let target = 4;

        if (currentState === "LISTENING") {
          // Dynamic music spikes from microphone voice
          target = 4 + audioVal * maxSpikeHeight + Math.sin(phase * 4 + i) * 3;
        } else if (currentState === "SPEAKING") {
          // High energetic music spikes synced to TTS audio
          target = 6 + audioVal * (maxSpikeHeight + 15) + Math.sin(phase * 3 + i * 0.5) * 4;
        } else if (currentState === "THINKING") {
          // Sleek rotating wave ripple
          const wave = Math.sin(phase * 3 + (i / numSpikes) * Math.PI * 4);
          target = 6 + Math.max(0, wave) * 28;
        } else {
          // Calm minimalist breathing ripple
          const idleWave = Math.sin(phase * 1.5 + (i / numSpikes) * Math.PI * 2);
          target = 4 + idleWave * 3;
        }

        // Smooth decay / spring lerp
        heights[i] += (target - heights[i]) * 0.35;
      }

      // Draw Center Minimalist Core
      const centerRadius = baseRadius - 8;
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, centerRadius, 0, Math.PI * 2);
      ctx.fillStyle = "#090d16";
      ctx.fill();

      // Subtle core border
      ctx.lineWidth = 1.5;
      if (currentState === "LISTENING") {
        ctx.strokeStyle = "rgba(0, 240, 255, 0.4)";
        ctx.shadowColor = "#00f0ff";
        ctx.shadowBlur = 12;
      } else if (currentState === "SPEAKING") {
        ctx.strokeStyle = "rgba(244, 63, 94, 0.4)";
        ctx.shadowColor = "#f43f5e";
        ctx.shadowBlur = 12;
      } else if (currentState === "THINKING") {
        ctx.strokeStyle = "rgba(168, 85, 247, 0.4)";
        ctx.shadowColor = "#a855f7";
        ctx.shadowBlur = 12;
      } else {
        ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
        ctx.shadowBlur = 0;
      }
      ctx.stroke();
      ctx.restore();

      // Draw Music Spikes radiating outwards
      for (let i = 0; i < numSpikes; i++) {
        const angle = (i / numSpikes) * Math.PI * 2 - Math.PI / 2;
        const h = Math.max(3, heights[i]);

        const startX = cx + Math.cos(angle) * baseRadius;
        const startY = cy + Math.sin(angle) * baseRadius;
        const endX = cx + Math.cos(angle) * (baseRadius + h);
        const endY = cy + Math.sin(angle) * (baseRadius + h);

        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.lineWidth = 2.5;
        ctx.lineCap = "round";

        // Color styling according to voice state
        if (currentState === "LISTENING") {
          // Crisp electric cyan spikes
          ctx.strokeStyle = `rgba(0, 240, 255, ${0.4 + (h / maxSpikeHeight) * 0.6})`;
          ctx.shadowColor = "#00f0ff";
          ctx.shadowBlur = h > 20 ? 8 : 0;
        } else if (currentState === "SPEAKING") {
          // Warm vibrant rose & gold spikes
          ctx.strokeStyle = i % 2 === 0
            ? `rgba(244, 63, 94, ${0.4 + (h / maxSpikeHeight) * 0.6})`
            : `rgba(251, 191, 36, ${0.4 + (h / maxSpikeHeight) * 0.6})`;
          ctx.shadowColor = "#f43f5e";
          ctx.shadowBlur = h > 20 ? 8 : 0;
        } else if (currentState === "THINKING") {
          // Minimalist violet spikes
          ctx.strokeStyle = `rgba(168, 85, 247, ${0.4 + (h / 30) * 0.6})`;
          ctx.shadowColor = "#a855f7";
          ctx.shadowBlur = 4;
        } else {
          // Minimalist soft white/slate spikes
          ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
          ctx.shadowBlur = 0;
        }

        ctx.stroke();
      }

      // Small central subtle breathing dot
      ctx.beginPath();
      const dotRadius = 4 + Math.sin(phase * 2) * 1.5;
      ctx.arc(cx, cy, dotRadius, 0, Math.PI * 2);
      if (currentState === "LISTENING") ctx.fillStyle = "#00f0ff";
      else if (currentState === "SPEAKING") ctx.fillStyle = "#f43f5e";
      else if (currentState === "THINKING") ctx.fillStyle = "#a855f7";
      else ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
      ctx.fill();

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, []);

  return (
    <div className="relative flex flex-col items-center justify-center">
      <canvas
        ref={canvasRef}
        width={340}
        height={340}
        className="w-[240px] h-[240px] sm:w-[280px] sm:h-[280px] select-none"
      />
      {/* Subtle soft backdrop radial bloom */}
      <div className="absolute inset-0 m-auto w-40 h-40 rounded-full bg-cyan-500/5 blur-3xl pointer-events-none" />
    </div>
  );
};

